# ── network_graph/sources/fitas_source.py ────────────────────────────────────
# Handles FITAS transaction data from harmonized sources.
# DIRECTED relationships based on CUST_TRADE_ROLE (Buyer -> Supplier).
# Deduplicates by REF_NO (prefer Buyer row) before aggregation to avoid
# double-counting transactions that appear from both perspectives.
# Self-loops: badge-only in side panel (no amounts), excluded from graph edges.

import pandas as pd
from .base_source import BaseSource

_INVALID_IDS = BaseSource.INVALID_IDS  # local alias; canonical set lives on BaseSource

# Products where the customer (SOURCE) is acting as Buyer
FITAS_BUYER_PRODUCTS    = {'LC', 'TR', 'STA'}
# Products where the customer (SOURCE) is acting as Supplier
FITAS_SUPPLIER_PRODUCTS = {'EXPORTLC', 'FBEP', 'OAT'}


class FITASSource(BaseSource):
    """
    FITAS transaction data source.

    Direction logic (CUST_TRADE_ROLE):
    - 'Buyer':    ID_CODE (buyer)      -> CPTY_ID_CODE (supplier)
    - 'Supplier': CPTY_ID_CODE (buyer) -> ID_CODE (supplier)
    - Other/missing: ID_CODE -> CPTY_ID_CODE (safe default)

    Deduplication: if REF_NO is present, the same transaction appearing from
    both Buyer and Supplier perspective is collapsed to the Buyer row before
    aggregation, preventing LCY_TRADE_AMT from being double-counted.

    Self-loops: caught in _build_adjacency() via src == tgt check.
    Stored in self_loop_ids (set of UEN strings) for compression map and
    side panel badge only -- no txn amounts stored, no vis.js edge created.

    fitas_latest_date: max CRT_DATE across combined_df, formatted '%d %b %Y'.
    Displayed in the FITAS Transaction Summary accordion before the send/recv
    cards.

    fitas_product_df: per-product breakdown keyed by (SOURCE_UEN, TARGET_UEN,
    fitas_product). Used by RelationshipBuilder to determine buyer/supplier
    direction and populate the Buyer-Supplier Pairs Excel sheet.
    Null/empty FITAS_SOURCE values are labelled 'Others'.
    Self-loop rows are excluded.
    """

    def __init__(self, config, fitas_folder):
        super().__init__(config, main_folder=None)
        self.fitas_folder = fitas_folder

        self.xborder_df        = None
        self.domestic_df       = None
        self.combined_df       = None
        self.edges_df          = None
        self.positions         = None
        self.out_adj           = {}
        self.in_adj            = {}
        self.self_loop_ids     = set()
        self.degree_map        = {}
        self.active_uens       = set()
        self.fitas_latest_date = None
        # *** updated | new attribute | per-product breakdown for relationship builder
        self.fitas_product_df  = None

    def load(self) -> 'FITASSource':
        """Load cross-border + domestic files, stack, aggregate to directed edges."""
        cfg = self.config
        self.xborder_df  = self._load_file(
            self.fitas_folder, cfg.FITAS_FILES['xborder']
        )
        self.domestic_df = self._load_file(
            self.fitas_folder, cfg.FITAS_FILES['domestic']
        )

        print(f"FITASSource loaded:")
        print(f"  Cross-border : {len(self.xborder_df):,} rows")
        print(f"  Domestic     : {len(self.domestic_df):,} rows")

        self._clean_ids()

        self.combined_df = pd.concat(
            [self.xborder_df, self.domestic_df], ignore_index=True
        )
        print(f"  Combined     : {len(self.combined_df):,} rows")

        self._compute_latest_date()
        self._aggregate_edges()
        self._build_adjacency()
        self._compute_positions()

        print(f"  Edges        : {len(self.edges_df):,}")
        print(f"  Self-loops   : {len(self.self_loop_ids):,}")
        print(f"  Active UENs  : {len(self.active_uens):,}")
        print(f"  Latest date  : {self.fitas_latest_date}")
        print(f"  Product rows : {len(self.fitas_product_df):,}")

        return self

    def _clean_ids(self):
        """Clean UEN and CIF columns across both raw dataframes."""
        for df in [self.xborder_df, self.domestic_df]:
            df['ID_CODE']      = self._clean_id(df['ID_CODE'])
            df['CPTY_ID_CODE'] = self._clean_id(df['CPTY_ID_CODE'])
            df['CIF_NO']       = self._clean_id(df['CIF_NO'])
            df['CPTY_CIF_NO']  = self._clean_id(df['CPTY_CIF_NO'])

    def _compute_latest_date(self):
        """
        Find max CRT_DATE across combined_df and store as fitas_latest_date.
        Stored as None if column absent or entirely NaT.
        """
        if 'CRT_DATE' not in self.combined_df.columns:
            self.fitas_latest_date = None
            return
        parsed = pd.to_datetime(self.combined_df['CRT_DATE'], errors='coerce')
        latest = parsed.max()
        self.fitas_latest_date = (
            latest.strftime('%d %b %Y') if pd.notna(latest) else None
        )

    def _aggregate_edges(self):
        """
        Build directed edges using CUST_TRADE_ROLE to assign SOURCE/TARGET.

        Step 1 -- REF_NO dedup: collapse Buyer + Supplier views of the same
        transaction to the Buyer row. Prevents LCY_TRADE_AMT double-counting
        when both perspectives are present in the data.

        Step 2 -- Direction: assign SOURCE_UEN/TARGET_UEN per role.
        Supplier rows flip the pair so buyer is always SOURCE.

        Step 3 -- Product breakdown: group by (SOURCE_UEN, TARGET_UEN,
        fitas_product) to produce fitas_product_df. Null FITAS_SOURCE
        values are labelled 'Others'. Self-loop rows excluded.

        Step 4 -- Main aggregation: group to one row per directed pair.
        Self-loops caught by _build_adjacency() via src == tgt guard.
        """
        df = self.combined_df.copy()

        # Step 1: dedup by REF_NO -- prefer Buyer row for canonical direction.
        # *** fix | only dedup rows that have a non-null REF_NO. Pandas
        # treats NaN == NaN under drop_duplicates, so a frame with many
        # null-REF_NO rows would collapse them all to one even though they
        # represent unrelated trades. Split, dedup the keyed slice, keep
        # the unkeyed slice as-is, recombine.
        if 'REF_NO' in df.columns:
            before_dedup = len(df)
            df['_is_buyer'] = (
                df['CUST_TRADE_ROLE'].astype(str).str.strip().str.upper() == 'BUYER'
            ).astype(int)
            keyed   = df[df['REF_NO'].notna()]
            unkeyed = df[df['REF_NO'].isna()]
            keyed_dedup = (
                keyed.sort_values('_is_buyer', ascending=False)
                     .drop_duplicates(subset='REF_NO', keep='first')
            )
            df = (
                pd.concat([keyed_dedup, unkeyed], ignore_index=True)
                  .drop(columns='_is_buyer')
                  .reset_index(drop=True)
            )
            print(f"  FITAS REF_NO dedup: {before_dedup:,} -> {len(df):,} rows "
                  f"({before_dedup - len(df):,} duplicate perspectives removed; "
                  f"{len(unkeyed):,} null-REF_NO rows kept verbatim)")

        # Step 2: assign SOURCE/TARGET based on CUST_TRADE_ROLE
        # Supplier rows flip the pair so buyer is always SOURCE
        role = (
            df['CUST_TRADE_ROLE'].astype(str).str.strip().str.upper()
            if 'CUST_TRADE_ROLE' in df.columns
            else pd.Series('', index=df.index)
        )
        supplier_mask = role == 'SUPPLIER'

        df['SOURCE_UEN'] = df['ID_CODE']
        df['TARGET_UEN'] = df['CPTY_ID_CODE']
        df.loc[supplier_mask, 'SOURCE_UEN'] = df.loc[supplier_mask, 'CPTY_ID_CODE']
        df.loc[supplier_mask, 'TARGET_UEN'] = df.loc[supplier_mask, 'ID_CODE']

        df['SOURCE_UEN'] = self._clean_id(df['SOURCE_UEN'])
        df['TARGET_UEN'] = self._clean_id(df['TARGET_UEN'])

        # Drop invalid IDs before both aggregations
        valid_mask = (
            df['SOURCE_UEN'].notna() &
            df['TARGET_UEN'].notna() &
            ~df['SOURCE_UEN'].isin(_INVALID_IDS) &
            ~df['TARGET_UEN'].isin(_INVALID_IDS)
        )
        df_valid = df[valid_mask].copy()
        # *** fix | coerce LCY_TRADE_AMT to numeric so groupby.sum() doesn't
        # silently produce NaN if the column comes in object dtype.
        if 'LCY_TRADE_AMT' in df_valid.columns:
            df_valid['LCY_TRADE_AMT'] = pd.to_numeric(
                df_valid['LCY_TRADE_AMT'], errors='coerce'
            )
        else:
            df_valid['LCY_TRADE_AMT'] = 0.0

        # Step 3: product breakdown -- excludes self-loops so relationship
        # builder only sees external pair data
        # *** updated | new block | per-product groupby for RelationshipBuilder
        if 'FITAS_SOURCE' in df_valid.columns:
            df_valid['fitas_product'] = (
                df_valid['FITAS_SOURCE']
                .astype(str).str.strip().str.upper()
                .replace({'': 'OTHERS', 'NAN': 'OTHERS', 'NONE': 'OTHERS'})
            )
        else:
            # Column absent -- label everything Others so downstream doesn't break
            df_valid['fitas_product'] = 'OTHERS'

        self.fitas_product_df = (
            df_valid[df_valid['SOURCE_UEN'] != df_valid['TARGET_UEN']]
            .groupby(['SOURCE_UEN', 'TARGET_UEN', 'fitas_product'])
            .agg(
                txn_count=('LCY_TRADE_AMT', 'size'),
                txn_amt  =('LCY_TRADE_AMT', 'sum'),
            )
            .reset_index()
        )

        # Log product distribution for visibility
        product_dist = (
            self.fitas_product_df
            .groupby('fitas_product')['txn_count']
            .sum()
            .to_dict()
        )
        print(f"  FITAS product distribution: {product_dist}")

        # Step 4: main aggregation -- one row per directed pair
        self.edges_df = (
            df_valid
            .groupby(['SOURCE_UEN', 'TARGET_UEN'])
            .agg(
                txn_count=('LCY_TRADE_AMT', 'size'),
                txn_amt  =('LCY_TRADE_AMT', 'sum'),
            )
            .reset_index()
        )

        self.active_uens = set(
            self.edges_df['SOURCE_UEN'].tolist() +
            self.edges_df['TARGET_UEN'].tolist()
        ) - _INVALID_IDS

    def _build_adjacency(self):
        """
        Build directed out/in adjacency dicts and identify self-loops.
        Self-loops caught here via src == tgt -- stored in self_loop_ids as
        a set of UEN strings only (badge display, no amounts).
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
        # See consol_tt_source.py for rationale. Same semantics as _fitas_deg
        # in Recipe_1_Pipeline.py.
        for nid in self.active_uens:
            self.degree_map[nid] = len(
                set(self.out_adj.get(nid, [])) | set(self.in_adj.get(nid, []))
            )

    def get_nodes(self) -> pd.DataFrame:
        """
        Returns all unique UENs as nodes.
        ID side takes priority over CPTY side for CIF/name/country.
        """
        src_lookup = (
            self.combined_df[['ID_CODE', 'CIF_NO', 'CIF_NAME', 'CNTRY_CODE']]
            .dropna(subset=['ID_CODE'])
            .drop_duplicates(subset='ID_CODE', keep='first')
            .rename(columns={
                'ID_CODE'    : 'UEN',
                'CIF_NAME'   : 'source_name',
                'CNTRY_CODE' : 'source_country',
            })
        )

        cpty_lookup = (
            self.combined_df[[
                'CPTY_ID_CODE', 'CPTY_CIF_NO', 'CPTY_NAME', 'CPTY_CNTRY_CODE'
            ]]
            .dropna(subset=['CPTY_ID_CODE'])
            .drop_duplicates(subset='CPTY_ID_CODE', keep='first')
            .rename(columns={
                'CPTY_ID_CODE'    : 'UEN',
                'CPTY_CIF_NO'     : 'CIF_NO',
                'CPTY_NAME'       : 'source_name',
                'CPTY_CNTRY_CODE' : 'source_country',
            })
        )

        # ID side takes priority (placed last, keep='last')
        combined_lookup = pd.concat([cpty_lookup, src_lookup], ignore_index=True)
        combined_lookup = combined_lookup.drop_duplicates(subset='UEN', keep='last')

        nodes = pd.DataFrame({'UEN': list(self.active_uens)})
        nodes = nodes.merge(combined_lookup, on='UEN', how='left')
        nodes['CIF_NO']         = nodes['CIF_NO'].fillna('')
        nodes['source_name']    = nodes['source_name'].fillna('')
        nodes['source_country'] = nodes['source_country'].fillna('')
        nodes['source']         = 'FITAS'

        print(f"FITASSource nodes: {len(nodes):,}")
        return nodes

    def get_edges(self) -> pd.DataFrame:
        """Returns aggregated directed edges with txn_count and txn_amt."""
        edges = self.edges_df.copy()
        edges['edge_source'] = 'FITAS'
        return edges[['SOURCE_UEN', 'TARGET_UEN', 'edge_source', 'txn_count', 'txn_amt']]
