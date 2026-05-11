# ── network_graph/sources/fast_giro_source.py ────────────────────────────────
# Handles FAST and GIRO transaction data from a single harmonised feather.
# Two instances of this class (kind='FAST' and kind='GIRO') are created in
# Recipe 1, each filtering rows by TRN_TYP_L1_GRP (FST or GIR).
#
# Direction logic:
#   - DR rows: ORD = sender (account holder) -> BENE = receiver. No swap.
#   - CR rows: swap so SOURCE_UEN = sender (was BENE), TARGET_UEN = receiver (was ORD).
# Reversals (REV_IND == 'Y'): negate LCY_TRN_AMT before per-pair groupby so reversed
#   transactions cancel. Pairs with non-positive net amount are dropped after groupby.
# Self-loops (SOURCE_UEN == TARGET_UEN): same pattern as ConsolTTSource.

import pandas as pd
from .base_source import BaseSource

_INVALID_IDS = BaseSource.INVALID_IDS  # local alias; canonical set lives on BaseSource

# TRN_TYP_L1_GRP values that select FAST vs GIRO rows from the shared feather
_KIND_TO_GROUP = {'FAST': 'FST', 'GIRO': 'GIR'}


class FastGiroSource(BaseSource):
    """
    FAST or GIRO data source. Mirrors ConsolTTSource for graph compat:
    exposes active_uens, out_adj, in_adj, degree_map, self_loop_ids,
    directed_edges_df, selfloop_edges_df, node_summary, metric_ranges,
    latest_date.

    Two instances are created in Recipe 1 -- one per kind. Each independently
    reads the shared FAST_GIRO_Harmonised.feather, then filters by
    TRN_TYP_L1_GRP. File reads are cheap relative to downstream transforms.
    """

    def __init__(self, config, fast_giro_folder, kind: str):
        super().__init__(config, main_folder=None)
        if kind not in _KIND_TO_GROUP:
            raise ValueError(f"FastGiroSource kind must be 'FAST' or 'GIRO', got {kind!r}")
        self.fast_giro_folder = fast_giro_folder
        self.kind             = kind            # 'FAST' or 'GIRO'
        self.group_code       = _KIND_TO_GROUP[kind]   # 'FST' or 'GIR'

        self.raw_df               = None    # post-load, post-kind-filter
        self.combined_df          = None    # alias used downstream for parity with ConsolTTSource
        self.directed_edges_df    = None    # one row per (SOURCE_UEN, TARGET_UEN), ext only, net > 0
        self.selfloop_edges_df    = None    # one row per UEN, self-transfers only, net > 0
        self.positions            = None
        self.out_adj              = {}
        self.in_adj               = {}
        self.self_loop_ids        = set()
        self.degree_map           = {}
        self.active_uens          = set()
        self.fg_latest_date       = None    # max TRN_DTE formatted '%d %b %Y'

    # ── Public lifecycle ────────────────────────────────────────────────────

    def load(self) -> 'FastGiroSource':
        cfg = self.config
        df  = self._load_file(self.fast_giro_folder, cfg.FAST_GIRO_FILE)

        print(f"FastGiroSource[{self.kind}] file loaded: {len(df):,} rows (pre-kind-filter)")

        # Filter to this instance's kind via TRN_TYP_L1_GRP
        if 'TRN_TYP_L1_GRP' not in df.columns:
            raise KeyError(
                f"FAST_GIRO file missing TRN_TYP_L1_GRP -- cannot split FAST/GIRO. "
                f"Columns: {df.columns.tolist()[:10]}..."
            )
        grp_norm = df['TRN_TYP_L1_GRP'].astype(str).str.strip().str.upper()
        df = df[grp_norm == self.group_code].copy()
        print(f"  After TRN_TYP_L1_GRP=={self.group_code} filter: {len(df):,} rows")

        self.raw_df      = df
        self.combined_df = df    # alias for parity

        self._clean_ids()
        self._compute_latest_date()
        self._aggregate_edges()
        self._build_adjacency()
        self._compute_positions()

        print(f"  Directed edges (ext, net>0)   : {len(self.directed_edges_df):,}")
        print(f"  Self-loop edges (self, net>0) : {len(self.selfloop_edges_df):,}")
        print(f"  Active UENs                   : {len(self.active_uens):,}")
        print(f"  Self-loop UENs                : {len(self.self_loop_ids):,}")
        print(f"  Latest date                   : {self.fg_latest_date}")

        return self

    def build(self) -> 'FastGiroSource':
        """Alias for load() to match plan-level naming."""
        return self.load()

    # ── Internal pipeline ───────────────────────────────────────────────────

    def _clean_ids(self):
        df = self.raw_df
        for col in ('ORD_ID_CODE', 'BENE_ID_CODE', 'ORD_CIF_NO', 'BENE_CIF_NO'):
            if col in df.columns:
                df[col] = self._clean_id(df[col])

    def _compute_latest_date(self):
        """
        TRN_DTE comes through as e.g. '15Apr2024:00:00:00' or just '15Apr2024'.
        Take the part before ':', strip, parse '%d%b%Y', format max as '%d %b %Y'.
        """
        df = self.raw_df
        if 'TRN_DTE' not in df.columns or len(df) == 0:
            self.fg_latest_date = None
            return
        date_part = (
            df['TRN_DTE'].astype(str)
              .str.split(':').str[0]
              .str.strip()
        )
        parsed = pd.to_datetime(date_part, format='%d%b%Y', errors='coerce')
        latest = parsed.max()
        self.fg_latest_date = latest.strftime('%d %b %Y') if pd.notna(latest) else None

    def _aggregate_edges(self):
        """
        Build per-pair directed edges with reversal handling.

        Step A -- assign SOURCE/TARGET based on DR/CR direction.
            DR_CR_IND == 'D' (debit to ORD account):  ORD = sender, BENE = receiver. No swap.
            DR_CR_IND == 'C' (credit to ORD account): swap -- BENE = sender, ORD = receiver.
            Other / missing: keep ORD->BENE.
        Step B -- negate LCY_TRN_AMT for REV_IND == 'Y' rows so reversals cancel.
        Step C -- groupby (SOURCE_UEN, TARGET_UEN), sum negated LCY_TRN_AMT, count TRN_ID.
        Step D -- drop pairs where summed amt <= 0 (fully reversed).
        Step E -- split into directed_edges_df (SOURCE != TARGET) and selfloop_edges_df.
        """
        df = self.raw_df.copy()

        # *** fix | DR_CR_IND values in the harmonised feather are single
        # letters 'C' / 'D' (not the spelled-out 'CR' / 'DR'). Rows with any
        # other value are dropped so an unexpected code can't silently
        # default to ORD->BENE direction (which would mis-pair with a
        # reversal row whose original was a credit).
        if 'DR_CR_IND' in df.columns:
            ind = df['DR_CR_IND'].astype(str).str.strip().str.upper()
            cr_mask    = (ind == 'C')
            known_mask = ind.isin(['C', 'D'])
        else:
            cr_mask    = pd.Series(False, index=df.index)
            known_mask = pd.Series(True,  index=df.index)

        df['SOURCE_UEN'] = df['ORD_ID_CODE']
        df['TARGET_UEN'] = df['BENE_ID_CODE']
        df.loc[cr_mask, 'SOURCE_UEN'] = df.loc[cr_mask, 'BENE_ID_CODE']
        df.loc[cr_mask, 'TARGET_UEN'] = df.loc[cr_mask, 'ORD_ID_CODE']
        df['SOURCE_UEN'] = self._clean_id(df['SOURCE_UEN'])
        df['TARGET_UEN'] = self._clean_id(df['TARGET_UEN'])

        valid_mask = (
            df['SOURCE_UEN'].notna() & df['TARGET_UEN'].notna() &
            ~df['SOURCE_UEN'].isin(_INVALID_IDS) & ~df['TARGET_UEN'].isin(_INVALID_IDS) &
            known_mask
        )
        df = df[valid_mask].copy()

        # Reversal handling: negate amount so reversal cancels original.
        # *** fix | df.get('LCY_TRN_AMT') returns None when the column is
        # missing entirely, and `pd.to_numeric(None)` raises TypeError.
        # Fall back to a zero-filled series so the rest of the aggregation
        # still runs (the source just produces zero-amount rows).
        if 'LCY_TRN_AMT' in df.columns:
            amt = pd.to_numeric(df['LCY_TRN_AMT'], errors='coerce').fillna(0.0)
        else:
            amt = pd.Series(0.0, index=df.index)
        if 'REV_IND' in df.columns:
            rev = df['REV_IND'].astype(str).str.strip().str.upper() == 'Y'
            amt = amt.where(~rev, -amt)
        df['_signed_amt'] = amt

        # Both branches were identical -- collapsed. Each row counts as one
        # transaction regardless of whether TRN_ID is present.
        df['_trn_count_unit'] = 1

        # Aggregate
        agg = (
            df.groupby(['SOURCE_UEN', 'TARGET_UEN'], as_index=False)
              .agg(txn_count=('_trn_count_unit', 'sum'),
                   txn_amt  =('_signed_amt',     'sum'))
        )

        # Drop fully-reversed (or zero) pairs
        agg = agg[agg['txn_amt'] > 0].copy()
        agg['txn_amt'] = agg['txn_amt'].round(2)

        # Split self vs ext
        is_self = (agg['SOURCE_UEN'] == agg['TARGET_UEN'])
        ext_df  = agg[~is_self].copy().reset_index(drop=True)
        self_df = (
            agg[is_self][['SOURCE_UEN', 'txn_count', 'txn_amt']]
              .rename(columns={'SOURCE_UEN': 'uen',
                               'txn_count' : f'_{self.kind.lower()}_count',
                               'txn_amt'   : f'_{self.kind.lower()}_amt'})
              .reset_index(drop=True)
        )

        self.directed_edges_df = ext_df
        self.selfloop_edges_df = self_df

        self.active_uens = set(ext_df['SOURCE_UEN'].tolist() + ext_df['TARGET_UEN'].tolist())
        self.active_uens |= set(self_df['uen'].tolist())
        self.active_uens -= _INVALID_IDS

    def _build_adjacency(self):
        for r in self.directed_edges_df[['SOURCE_UEN', 'TARGET_UEN']].to_dict('records'):
            src = str(r['SOURCE_UEN']).strip()
            tgt = str(r['TARGET_UEN']).strip()
            self.out_adj.setdefault(src, []).append(tgt)
            self.in_adj.setdefault(tgt, []).append(src)

        self.self_loop_ids = set(self.selfloop_edges_df['uen'].astype(str).tolist())

        # *** fix | unique-counterparty count: |out_adj ∪ in_adj|.
        # See consol_tt_source.py for rationale. Same semantics as _fast_deg
        # / _giro_deg in Recipe_1_Pipeline.py.
        for nid in self.active_uens:
            self.degree_map[nid] = len(
                set(self.out_adj.get(nid, [])) | set(self.in_adj.get(nid, []))
            )

    # ── BaseSource interface ────────────────────────────────────────────────

    def get_nodes(self) -> pd.DataFrame:
        """
        Return all unique UENs as nodes. Per the plan, ORD/BENE_ID_CODE are
        UENs directly -- no BENE_ORD_INFO enrichment needed.
        ORD side takes priority over BENE side for CIF/name/country.
        """
        df = self.combined_df
        ord_lookup = (
            df[['ORD_ID_CODE', 'ORD_CIF_NO', 'ORD_CIF_NAME', 'ORD_COUNTRY']]
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
            df[['BENE_ID_CODE', 'BENE_CIF_NO', 'BENE_CIF_NAME', 'BENE_COUNTRY']]
              .dropna(subset=['BENE_ID_CODE'])
              .drop_duplicates(subset='BENE_ID_CODE', keep='first')
              .rename(columns={
                  'BENE_ID_CODE'  : 'UEN',
                  'BENE_CIF_NO'   : 'CIF_NO',
                  'BENE_CIF_NAME' : 'source_name',
                  'BENE_COUNTRY'  : 'source_country',
              })
        )
        combined = pd.concat([bene_lookup, ord_lookup], ignore_index=True)
        combined = combined.drop_duplicates(subset='UEN', keep='last')

        nodes = pd.DataFrame({'UEN': list(self.active_uens)}).merge(combined, on='UEN', how='left')
        nodes['CIF_NO']         = nodes['CIF_NO'].fillna('')
        nodes['source_name']    = nodes['source_name'].fillna('')
        nodes['source_country'] = nodes['source_country'].fillna('')
        nodes['source']         = self.kind   # 'FAST' or 'GIRO'

        print(f"FastGiroSource[{self.kind}] nodes: {len(nodes):,}")
        return nodes

    def get_edges(self) -> pd.DataFrame:
        """
        Return per-pair directed edges (ext only) with edge_source = self.kind.
        Self-loops are NOT returned here -- they are exposed via selfloop_edges_df
        and are concatenated into the edge info dataset separately in Recipe 1.
        """
        edges = self.directed_edges_df.copy()
        edges['edge_source'] = self.kind   # 'FAST' or 'GIRO'
        return edges[['SOURCE_UEN', 'TARGET_UEN', 'edge_source', 'txn_count', 'txn_amt']]
