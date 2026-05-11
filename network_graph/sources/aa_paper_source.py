# ── network_graph/sources/aa_paper_source.py ──────────────────────────────────
# Handles AA Paper counterparty relationship data from harmonized source.
# DIRECTED relationships based on COUNTERPARTY_TYPE (Buyer -> Supplier).
# Declaration context (declarer_uen, declarer_name, declared_uen, declared_name,
# counterparty_type) carried through edges_df for reporting -- unaffected by
# the direction flip applied to SOURCE_UEN/TARGET_UEN.

import pandas as pd
from .base_source import BaseSource

# Invalid ID strings -- consistent with Recipe 1 and js_core.py
_INVALID_IDS = BaseSource.INVALID_IDS  # local alias; canonical set lives on BaseSource


class AAPaperSource(BaseSource):
    """
    AA Paper counterparty relationship source (DIRECTED).

    Direction logic: Buyer sends money to Supplier
    - COUNTERPARTY_TYPE = 'Supplier': UEN (buyer) -> CPTY_UEN (supplier)
    - COUNTERPARTY_TYPE = 'Buyer':    CPTY_UEN (buyer) -> UEN (supplier)

    Declaration context is always preserved in original UEN perspective:
    - declarer_uen  : UEN who made the declaration (always original UEN)
    - declared_uen  : UEN being declared (always original CPTY_UEN)
    - counterparty_type : original COUNTERPARTY_TYPE value
    """

    def __init__(self, config, aa_paper_folder):
        super().__init__(config, main_folder=None)
        self.aa_paper_folder = aa_paper_folder

        self.raw_df        = None
        self.edges_df      = None
        self.positions     = None
        self.out_adj       = {}
        self.in_adj        = {}
        self.degree_map    = {}
        self.active_uens   = set()
        self.self_loop_ids = set()

    def load(self) -> 'AAPaperSource':
        """Load AA Paper file and apply direction logic."""
        self.raw_df = self._load_file(
            self.aa_paper_folder, self.config.AA_PAPER_FILE
        )

        print(f"AAPaperSource loaded:")
        print(f"  Raw records: {len(self.raw_df):,} rows")
        print(f"  COUNTERPARTY_TYPE distribution:")
        print(f"    {self.raw_df['COUNTERPARTY_TYPE'].value_counts().to_dict()}")

        self._clean_ids()
        self._build_directed_edges()
        self._build_adjacency()
        self._compute_positions()

        print(f"  Directed edges: {len(self.edges_df):,}")
        print(f"  Active UENs:    {len(self.active_uens):,}")
        print(f"  Self-loops:     {len(self.self_loop_ids):,}")

        return self

    def _clean_ids(self):
        """Clean UEN columns."""
        self.raw_df['UEN']      = self._clean_id(self.raw_df['UEN'])
        self.raw_df['CPTY_UEN'] = self._clean_id(self.raw_df['CPTY_UEN'])

    def _build_directed_edges(self):
        """
        Build directed edges from UEN <-> CPTY_UEN using vectorised logic.
        SOURCE_UEN/TARGET_UEN direction is flipped for Buyer rows so that
        SOURCE is always the buyer and TARGET is always the supplier.

        Declaration context columns (declarer_uen, declarer_name, declared_uen,
        declared_name, counterparty_type) are carried from the original row
        BEFORE the flip so reports always reflect who declared whom.
        """
        df = self.raw_df.copy()

        df = df[
            ~df['UEN'].isin(_INVALID_IDS) &
            ~df['CPTY_UEN'].isin(_INVALID_IDS)
        ]

        # *** fix | case-insensitive role match. Without .upper(), variants
        # like 'supplier' / 'BUYER' would silently fall into other_mask and
        # the SOURCE/TARGET assignment would default to (UEN, CPTY_UEN) --
        # a wrong direction for any genuine supplier-perspective row.
        cpty_type  = df['COUNTERPARTY_TYPE'].astype(str).str.strip().str.upper()
        sup_mask   = cpty_type == 'SUPPLIER'
        buy_mask   = cpty_type == 'BUYER'
        other_mask = ~sup_mask & ~buy_mask

        # ── Supplier rows: UEN=buyer -> CPTY_UEN=supplier, no flip ───────
        sup_edges = df[sup_mask][[
            'UEN', 'CPTY_UEN', 'CIF_NAME', 'CPTY_NAME', 'COUNTERPARTY_TYPE'
        ]].rename(columns={
            'UEN'              : 'SOURCE_UEN',
            'CPTY_UEN'         : 'TARGET_UEN',
            'CIF_NAME'         : 'declarer_name',
            'CPTY_NAME'        : 'declared_name',
            'COUNTERPARTY_TYPE': 'counterparty_type',
        })
        sup_edges['declarer_uen'] = df[sup_mask]['UEN'].values
        sup_edges['declared_uen'] = df[sup_mask]['CPTY_UEN'].values

        # ── Buyer rows: CPTY_UEN=buyer -> UEN=supplier, direction flipped ─
        # SOURCE/TARGET flipped but declarer_uen stays as original UEN
        # (the one who made the declaration), declared_uen stays as CPTY_UEN.
        buy_edges = df[buy_mask][[
            'CPTY_UEN', 'UEN', 'CIF_NAME', 'CPTY_NAME', 'COUNTERPARTY_TYPE'
        ]].rename(columns={
            'CPTY_UEN'         : 'SOURCE_UEN',
            'UEN'              : 'TARGET_UEN',
            'CIF_NAME'         : 'declarer_name',
            'CPTY_NAME'        : 'declared_name',
            'COUNTERPARTY_TYPE': 'counterparty_type',
        })
        buy_edges['declarer_uen'] = df[buy_mask]['UEN'].values
        buy_edges['declared_uen'] = df[buy_mask]['CPTY_UEN'].values

        # ── Unknown type: keep original order ─────────────────────────────
        other_edges = df[other_mask][[
            'UEN', 'CPTY_UEN', 'CIF_NAME', 'CPTY_NAME', 'COUNTERPARTY_TYPE'
        ]].rename(columns={
            'UEN'              : 'SOURCE_UEN',
            'CPTY_UEN'         : 'TARGET_UEN',
            'CIF_NAME'         : 'declarer_name',
            'CPTY_NAME'        : 'declared_name',
            'COUNTERPARTY_TYPE': 'counterparty_type',
        })
        other_edges['declarer_uen'] = df[other_mask]['UEN'].values
        other_edges['declared_uen'] = df[other_mask]['CPTY_UEN'].values

        self.edges_df = (
            pd.concat([sup_edges, buy_edges, other_edges], ignore_index=True)
            .drop_duplicates(subset=['SOURCE_UEN', 'TARGET_UEN'])
            .sort_values(['SOURCE_UEN', 'TARGET_UEN'])
            .reset_index(drop=True)
        )

        self.active_uens = set(
            self.edges_df['SOURCE_UEN'].tolist() +
            self.edges_df['TARGET_UEN'].tolist()
        ) - _INVALID_IDS

    def _build_adjacency(self):
        """
        Build directed adjacency dicts with self-loop detection.
        Uses SOURCE_UEN/TARGET_UEN only -- declaration context not needed here.
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
        # Was: len(set(out_adj)) + len(set(in_adj)) -- per-direction deduped
        # but still double-counted bidirectional pairs. Same semantics as
        # _aa_deg in Recipe_1_Pipeline.py.
        for nid in self.active_uens:
            self.degree_map[nid] = len(
                set(self.out_adj.get(nid, [])) | set(self.in_adj.get(nid, []))
            )

    def get_nodes(self) -> pd.DataFrame:
        """
        Returns all unique UENs as nodes.
        UEN side takes priority over CPTY side for CIF/name/country.
        """
        uen_lookup = (
            self.raw_df[['UEN', 'CIF_NO', 'CIF_NAME', 'CIF_COUNTRY']]
            .dropna(subset=['UEN'])
            .drop_duplicates(subset='UEN', keep='first')
            .rename(columns={
                'CIF_NAME'    : 'source_name',
                'CIF_COUNTRY' : 'source_country',
            })
        )

        cpty_lookup = (
            self.raw_df[['CPTY_UEN', 'CPTY_CIF_NO', 'CPTY_NAME', 'CPTY_COUNTRY']]
            .dropna(subset=['CPTY_UEN'])
            .drop_duplicates(subset='CPTY_UEN', keep='first')
            .rename(columns={
                'CPTY_UEN'     : 'UEN',
                'CPTY_CIF_NO'  : 'CIF_NO',
                'CPTY_NAME'    : 'source_name',
                'CPTY_COUNTRY' : 'source_country',
            })
        )

        # UEN side takes priority (placed last, keep='last')
        combined_lookup = pd.concat([cpty_lookup, uen_lookup], ignore_index=True)
        combined_lookup = combined_lookup.drop_duplicates(subset='UEN', keep='last')

        nodes = pd.DataFrame({'UEN': list(self.active_uens)})
        nodes = nodes.merge(combined_lookup, on='UEN', how='left')
        nodes['CIF_NO']         = nodes['CIF_NO'].fillna('')
        nodes['source_name']    = nodes['source_name'].fillna('')
        nodes['source_country'] = nodes['source_country'].fillna('')
        nodes['source']         = 'AA_Paper'

        print(f"AAPaperSource nodes: {len(nodes):,}")
        return nodes

    def get_edges(self) -> pd.DataFrame:
        """
        Returns directed edges with original declaration context for reporting.
        SOURCE_UEN/TARGET_UEN reflect buyer->supplier direction (post-flip).
        declarer_uen/declared_uen reflect original UEN->CPTY_UEN declaration (pre-flip).
        """
        edges = self.edges_df.copy()
        edges['edge_source'] = 'AA_Paper'
        edges['txn_count']   = None
        edges['txn_amt']     = None
        return edges[[
            'SOURCE_UEN', 'TARGET_UEN', 'edge_source', 'txn_count', 'txn_amt',
            'declarer_uen', 'declarer_name', 'declared_uen', 'declared_name',
            'counterparty_type',
        ]]
