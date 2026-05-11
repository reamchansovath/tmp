# ── network_graph/sources/consol_tt_source.py ────────────────────────────────
# Handles Consolidated TT (Telegraphic Transfer) data from harmonized sources.
# Stacks cross-border + domestic transactions, aggregates to directed edges.
# Each row in edges_df is one direction (A->B), txn_amt is total sent that way.
# edges_df_filtered drops rows where txn_amt < tt_edge_min_amt.

import pandas as pd
from .base_source import BaseSource

_INVALID_IDS = BaseSource.INVALID_IDS  # local alias; canonical set lives on BaseSource


class ConsolTTSource(BaseSource):
    """
    Consolidated TT data source.

    Reads filenames from config.CONSOL_TT_FILES so changes to filenames
    only need to be made in NetworkGraphConfig.

    Key columns:
    - ORD_ID_CODE (source UEN), BENE_ID_CODE (target UEN)
    - ORD_CIF_NO, BENE_CIF_NO, ORD_COUNTRY, BENE_COUNTRY
    - SGD_TRN_AMT

    Edge sets:
    - edges_df          : full aggregated directed edges, one row per A->B pair
    - edges_df_filtered : same but rows where txn_amt < tt_edge_min_amt dropped

    tt_latest_date: max TRN_MONTH across combined_df, formatted '%d %b %Y'.
    Displayed in the TT Transaction Summary accordion before the send/recv cards.
    """

    def __init__(self, config, consol_tt_folder):
        super().__init__(config, main_folder=None)
        self.consol_tt_folder  = consol_tt_folder

        self.xborder_df        = None
        self.domestic_df       = None
        self.combined_df       = None
        self.edges_df          = None
        self.edges_df_filtered = None
        self.positions         = None
        self.out_adj           = {}
        self.in_adj            = {}
        self.self_loop_ids     = set()
        self.degree_map        = {}
        self.active_uens       = set()
        # *** updated | new attribute | latest TRN_MONTH for side panel display
        self.tt_latest_date    = None

    def load(self) -> 'ConsolTTSource':
        """Load cross-border + domestic files, stack, aggregate to edges."""
        cfg = self.config
        self.xborder_df  = self._load_file(
            self.consol_tt_folder, cfg.CONSOL_TT_FILES['xborder']
        )
        self.domestic_df = self._load_file(
            self.consol_tt_folder, cfg.CONSOL_TT_FILES['domestic']
        )

        print(f"ConsolTTSource loaded:")
        print(f"  Cross-border : {len(self.xborder_df):,} rows")
        print(f"  Domestic     : {len(self.domestic_df):,} rows")

        self._clean_ids()

        self.combined_df = pd.concat(
            [self.xborder_df, self.domestic_df], ignore_index=True
        )
        print(f"  Combined     : {len(self.combined_df):,} rows")

        # *** updated | added date computation before aggregation | needs raw combined_df
        self._compute_latest_date()
        self._aggregate_edges()
        self._build_adjacency()
        self._compute_positions()

        print(f"  Edges (full)     : {len(self.edges_df):,}")
        print(f"  Self-loops       : {len(self.self_loop_ids):,}")
        print(f"  Active UENs      : {len(self.active_uens):,}")
        print(f"  Latest date      : {self.tt_latest_date}")

        return self

    def apply_edge_filter(self, tt_edge_min_amt: float) -> None:
        """
        Build edges_df_filtered by dropping per-direction rows below threshold.
        Each row is one direction A->B -- txn_amt is total sent from A to B
        across all individual transactions. If A sent B 5 transactions totalling
        S$4,999, that row is dropped regardless of what B sent A.

        Call this after load() and before get_edges_filtered().
        Results are printed for visibility.
        """
        if self.edges_df is None:
            raise RuntimeError("Call load() before apply_edge_filter()")

        self.edges_df_filtered = self.edges_df[
            self.edges_df['txn_amt'] >= tt_edge_min_amt
        ].copy()

        n_removed = len(self.edges_df) - len(self.edges_df_filtered)
        print(f"  TT edge filter (txn_amt >= S${tt_edge_min_amt:,.0f}):")
        print(f"    Edges before : {len(self.edges_df):,}")
        print(f"    Edges removed: {n_removed:,}  "
              f"({n_removed / max(len(self.edges_df), 1) * 100:.1f}%)")
        print(f"    Edges after  : {len(self.edges_df_filtered):,}")

    def _clean_ids(self):
        """Clean UEN and CIF columns."""
        for df in [self.xborder_df, self.domestic_df]:
            df['ORD_ID_CODE']  = self._clean_id(df['ORD_ID_CODE'])
            df['BENE_ID_CODE'] = self._clean_id(df['BENE_ID_CODE'])
            df['ORD_CIF_NO']   = self._clean_id(df['ORD_CIF_NO'])
            df['BENE_CIF_NO']  = self._clean_id(df['BENE_CIF_NO'])

    # *** updated | new method | extract max TRN_MONTH for side panel
    def _compute_latest_date(self):
        """
        Find max TRN_MONTH across combined_df and store as tt_latest_date.
        TRN_MONTH format is YYYY-MM-DD -- parsed and formatted as '%d %b %Y'.
        Stored as None if column absent or entirely NaT.
        """
        if 'TRN_MONTH' not in self.combined_df.columns:
            self.tt_latest_date = None
            return
        parsed = pd.to_datetime(self.combined_df['TRN_MONTH'], errors='coerce')
        latest = parsed.max()
        self.tt_latest_date = (
            latest.strftime('%d %b %Y') if pd.notna(latest) else None
        )

    def _aggregate_edges(self):
        """
        Aggregate transactions to directed edges.
        One row per ORD_ID_CODE -> BENE_ID_CODE pair.
        txn_amt = total SGD sent in that direction across all transactions.
        """
        # *** fix | coerce SGD_TRN_AMT to numeric before groupby.sum().
        # Without this, an object-dtype column with mixed strings/numbers
        # would silently produce NaN totals or raise on aggregation.
        df = self.combined_df.copy()
        df['SGD_TRN_AMT'] = pd.to_numeric(
            df.get('SGD_TRN_AMT'), errors='coerce'
        )
        self.edges_df = (
            df
            .dropna(subset=['ORD_ID_CODE', 'BENE_ID_CODE'])
            .loc[lambda x:
                ~x['ORD_ID_CODE'].astype(str).str.strip().isin(_INVALID_IDS) &
                ~x['BENE_ID_CODE'].astype(str).str.strip().isin(_INVALID_IDS)
            ]
            .groupby(['ORD_ID_CODE', 'BENE_ID_CODE'])
            .agg(
                txn_count = ('SGD_TRN_AMT', 'size'),
                txn_amt   = ('SGD_TRN_AMT', 'sum'),
            )
            .reset_index()
            .rename(columns={
                'ORD_ID_CODE'  : 'SOURCE_UEN',
                'BENE_ID_CODE' : 'TARGET_UEN',
            })
        )

        self.edges_df['SOURCE_UEN'] = self._clean_id(self.edges_df['SOURCE_UEN'])
        self.edges_df['TARGET_UEN'] = self._clean_id(self.edges_df['TARGET_UEN'])

        self.active_uens = set(
            self.edges_df['SOURCE_UEN'].tolist() +
            self.edges_df['TARGET_UEN'].tolist()
        ) - _INVALID_IDS

    def _build_adjacency(self):
        """
        Build out/in adjacency dicts and identify self-loops.
        FIX: replaced iterrows() with to_dict('records') for speed.
        """
        for r in self.edges_df[['SOURCE_UEN', 'TARGET_UEN']].to_dict('records'):
            src = str(r['SOURCE_UEN']).strip()
            tgt = str(r['TARGET_UEN']).strip()

            if src == tgt:
                self.self_loop_ids.add(src)
            else:
                self.out_adj.setdefault(src, []).append(tgt)
                self.in_adj.setdefault(tgt, []).append(src)

        # *** fix | unique-counterparty count: |out_adj ∪ in_adj|.
        # Was: len(out_adj) + len(in_adj) -- which (a) failed to dedupe parallel
        # edges within a direction (5 TT txns to one counterparty counted as 5),
        # and (b) double-counted bidirectional pairs. Same semantics as
        # _tt_deg in Recipe_1_Pipeline.py.
        for nid in self.active_uens:
            self.degree_map[nid] = len(
                set(self.out_adj.get(nid, [])) | set(self.in_adj.get(nid, []))
            )

    def get_nodes(self) -> pd.DataFrame:
        """
        Returns all unique UENs as nodes.
        ORD side takes priority over BENE side for CIF/name/country.
        """
        ord_lookup = (
            self.combined_df[['ORD_ID_CODE', 'ORD_CIF_NO', 'ORD_CIF_NAME', 'ORD_COUNTRY']]
            .dropna(subset=['ORD_ID_CODE'])
            .drop_duplicates(subset='ORD_ID_CODE', keep='first')
            .rename(columns={
                'ORD_ID_CODE'  : 'UEN',
                'ORD_CIF_NO'   : 'CIF_NO',
                'ORD_CIF_NAME' : 'source_name',
                'ORD_COUNTRY'  : 'source_country',
            })
        )

        bene_lookup = (
            self.combined_df[['BENE_ID_CODE', 'BENE_CIF_NO', 'BENE_CIF_NAME', 'BENE_COUNTRY']]
            .dropna(subset=['BENE_ID_CODE'])
            .drop_duplicates(subset='BENE_ID_CODE', keep='first')
            .rename(columns={
                'BENE_ID_CODE'  : 'UEN',
                'BENE_CIF_NO'   : 'CIF_NO',
                'BENE_CIF_NAME' : 'source_name',
                'BENE_COUNTRY'  : 'source_country',
            })
        )

        # ORD takes priority (placed last, keep='last')
        combined_lookup = pd.concat([bene_lookup, ord_lookup], ignore_index=True)
        combined_lookup = combined_lookup.drop_duplicates(subset='UEN', keep='last')

        nodes = pd.DataFrame({'UEN': list(self.active_uens)})
        nodes = nodes.merge(combined_lookup, on='UEN', how='left')
        nodes['CIF_NO']         = nodes['CIF_NO'].fillna('')
        nodes['source_name']    = nodes['source_name'].fillna('')
        nodes['source_country'] = nodes['source_country'].fillna('')
        nodes['source']         = 'Consolidated_TT'

        print(f"ConsolTTSource nodes: {len(nodes):,}")
        return nodes

    def get_edges(self) -> pd.DataFrame:
        """Returns full aggregated directed edges -- all directions kept."""
        edges = self.edges_df.copy()
        edges['edge_source'] = 'Consolidated_TT'
        return edges[['SOURCE_UEN', 'TARGET_UEN', 'edge_source', 'txn_count', 'txn_amt']]

    def get_edges_filtered(self) -> pd.DataFrame:
        """
        Returns filtered directed edges -- rows below tt_edge_min_amt removed.
        Requires apply_edge_filter() to have been called first.
        """
        if self.edges_df_filtered is None:
            raise RuntimeError(
                "Call apply_edge_filter(tt_edge_min_amt) before get_edges_filtered()"
            )
        edges = self.edges_df_filtered.copy()
        edges['edge_source'] = 'Consolidated_TT'
        return edges[['SOURCE_UEN', 'TARGET_UEN', 'edge_source', 'txn_count', 'txn_amt']]
