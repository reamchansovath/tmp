# ── network_graph/pipeline/relationship_builder.py ───────────────────────────
# Determines the buyer/supplier relationship for every unique UEN pair across
# all 4 data sources, applying a priority chain: FITAS > AA Paper > TT > RSME.
#
# Output: relationship_df -- one row per unique pair, wide format.
# Used by:
#   - Recipe 1 Cell 10  : builds consolidated_edges_df for vis.js
#   - Recipe 3          : populates "Buyer-Supplier Pairs" Excel sheet
#
# Direction convention throughout:
#   buyer  -> pays money  -> supplier
#   sender -> sends money -> receiver  (TT)
# For is_both=True edges, from_uen = higher combined outflow (FITAS + TT).

import pandas as pd
import numpy as np
from ..sources.fitas_source import FITAS_BUYER_PRODUCTS, FITAS_SUPPLIER_PRODUCTS

_INVALID_IDS  = {'', 'nan', 'none', 'None', 'NaN', 'NAN'}

# Known FITAS products -- anything else maps to 'OTHERS'
_ALL_FITAS_PRODUCTS = ['LC', 'TR', 'STA', 'EXPORTLC', 'FBEP', 'OAT', 'OTHERS']

# Payment Transactions direction thresholds (TT + MEPS + FAST + GIRO combined
# per direction, with FITAS outflow folded in for tie-break).
_BUYER_THRESHOLD    = 0.60   # pct(A->B) > 60% => A is buyer
_SUPPLIER_THRESHOLD = 0.40   # pct(A->B) < 40% => A is supplier


class RelationshipBuilder:
    """
    Builds a one-row-per-pair relationship table from all 4 network sources.

    Priority logic for determining buyer/supplier direction:
      1. FITAS  -- product classification (LC/TR/STA = buyer, ExportLC/FBEP/OAT = supplier)
      2. AA Paper -- SOURCE = buyer, TARGET = supplier (direction already enforced)
      3. TT     -- flow % threshold: >60% buyer, <40% supplier, 40-60% both
      4. RSME   -- direction unknown; customer/counterparty labels only

    For is_both=True:
      from_uen = UEN with higher combined outflow (FITAS sent + TT sent).
      Tie-break: alphabetical UEN ascending.

    Attributes
    ----------
    relationship_df : pd.DataFrame
        One row per unique pair. See _build_row() for full column list.
    """

    def __init__(self):
        self.relationship_df = None

    def build(self,
              rsme_source,
              consol_tt_source,
              fitas_source,
              aa_paper_source,
              fast_source,
              giro_source) -> 'RelationshipBuilder':
        """
        Run the full priority chain across all 6 sources and produce
        relationship_df. Call this once after all sources are loaded.

        Priority chain (unchanged):
          1. FITAS  -- product classification
          2. AA Paper
          3. All Txn flow % (FITAS+TT+FAST+GIRO combined per direction)
          4. RSME

        Returns self (for chaining).
        """
        print("\n" + "="*60)
        print("BUILDING RELATIONSHIP TABLE")
        print("="*60)

        fitas_lookup = self._prep_fitas(fitas_source)
        aa_lookup    = self._prep_aa(aa_paper_source)
        tt_lookup    = self._prep_tt(consol_tt_source)
        fast_lookup  = self._prep_fg(fast_source, kind='fast')
        giro_lookup  = self._prep_fg(giro_source, kind='giro')
        rsme_lookup  = self._prep_rsme(rsme_source)

        all_pairs = (
            set(fitas_lookup) | set(aa_lookup) | set(tt_lookup) |
            set(fast_lookup)  | set(giro_lookup) | set(rsme_lookup)
        )
        print(f"  Total unique pairs: {len(all_pairs):,}")

        rows = []
        for pair in all_pairs:
            row = self._build_row(
                pair,
                fitas_lookup.get(pair),
                aa_lookup.get(pair),
                tt_lookup.get(pair),
                fast_lookup.get(pair),
                giro_lookup.get(pair),
                rsme_lookup.get(pair),
            )
            rows.append(row)

        self.relationship_df = pd.DataFrame(rows)

        src_counts = self.relationship_df['priority_source'].value_counts().to_dict()
        both_count = int(self.relationship_df['is_both'].sum())
        print(f"  Priority source breakdown: {src_counts}")
        print(f"  is_both pairs:             {both_count:,}")
        print(f"  Undirected (RSME only):    "
              f"{int((~self.relationship_df['is_directed']).sum()):,}")
        print("  Relationship table complete.")
        return self

    # ══════════════════════════════════════════════════════════════════════
    # SOURCE PRE-PROCESSORS
    # Each returns a dict keyed by canonical pair tuple(sorted([a, b])).
    # ══════════════════════════════════════════════════════════════════════

    def _prep_fitas(self, fitas_source) -> dict:
        """
        Build FITAS lookup.
        Key   : canonical pair (uen_lo, uen_hi)
        Value : dict with product counts/amounts and outflow per UEN.

        SOURCE_UEN is always the buyer after direction assignment in
        fitas_source._aggregate_edges(), so outflow belongs to SOURCE_UEN.
        """
        if fitas_source.fitas_product_df is None or len(fitas_source.fitas_product_df) == 0:
            return {}

        df = fitas_source.fitas_product_df.copy()

        # Exclude self-loops -- not relevant for pair relationships
        df = df[df['SOURCE_UEN'] != df['TARGET_UEN']]

        lookup = {}
        for (src, tgt), grp in df.groupby(['SOURCE_UEN', 'TARGET_UEN']):
            pair = tuple(sorted([src, tgt]))

            if pair not in lookup:
                lookup[pair] = {
                    'products'      : {},   # {product: {src_tgt_key: {count, amt}}}
                    'outflow'       : {},   # {uen: total LCY_TRADE_AMT sent}
                    # Per-direction roll-ups across all products. Source data has
                    # SOURCE_UEN = buyer after FITAS direction assignment, so
                    # ab_* / ba_* track buyer->supplier counts in canonical
                    # (lexicographic) pair direction.
                    'ab_count'      : 0,
                    'ab_amt'        : 0.0,
                    'ba_count'      : 0,
                    'ba_amt'        : 0.0,
                }

            total_amt   = float(grp['txn_amt'].sum())
            total_count = int(grp['txn_count'].sum())
            lookup[pair]['outflow'][src] = (
                lookup[pair]['outflow'].get(src, 0.0) + total_amt
            )
            if src == pair[0]:
                lookup[pair]['ab_count'] += total_count
                lookup[pair]['ab_amt']   += total_amt
            else:
                lookup[pair]['ba_count'] += total_count
                lookup[pair]['ba_amt']   += total_amt

            for _, row in grp.iterrows():
                prod = row['fitas_product']
                key  = f"{src}__{tgt}"
                if prod not in lookup[pair]['products']:
                    lookup[pair]['products'][prod] = {}
                if key not in lookup[pair]['products'][prod]:
                    lookup[pair]['products'][prod][key] = {'count': 0, 'amt': 0.0}
                lookup[pair]['products'][prod][key]['count'] += int(row['txn_count'])
                lookup[pair]['products'][prod][key]['amt']   += float(row['txn_amt'])

        return lookup

    def _prep_aa(self, aa_paper_source) -> dict:
        """
        Build AA Paper lookup.
        Key   : canonical pair
        Value : dict of {buyer_uen, supplier_uen, is_both}

        aa_paper_source.edges_df has SOURCE=buyer, TARGET=supplier already.
        If a pair appears in both directions, is_both=True.
        """
        if aa_paper_source.edges_df is None or len(aa_paper_source.edges_df) == 0:
            return {}

        df = aa_paper_source.edges_df.copy()
        df = df[df['SOURCE_UEN'] != df['TARGET_UEN']]

        # Build set of directed pairs that exist
        directed_pairs = set(zip(df['SOURCE_UEN'], df['TARGET_UEN']))

        lookup = {}
        for src, tgt in directed_pairs:
            pair    = tuple(sorted([src, tgt]))
            reverse = (tgt, src)
            is_both = reverse in directed_pairs

            if pair not in lookup:
                lookup[pair] = {
                    'buyer_uen'   : src,
                    'supplier_uen': tgt,
                    'is_both'     : is_both,
                    # track outflow for is_both from_uen resolution
                    'outflow'     : {src: 0.0, tgt: 0.0},
                }
            else:
                # pair already registered from the other direction
                lookup[pair]['is_both'] = True

        return lookup

    def _prep_tt(self, consol_tt_source) -> dict:
        """
        Build TT lookup.
        Key   : canonical pair
        Value : dict with per-direction count/amt and outflow per UEN.

        edges_df has one row per directed pair A->B with txn_count + txn_amt.
        """
        if consol_tt_source.edges_df is None or len(consol_tt_source.edges_df) == 0:
            return {}

        df = consol_tt_source.edges_df.copy()
        df = df[df['SOURCE_UEN'] != df['TARGET_UEN']]

        lookup = {}
        for _, row in df.iterrows():
            src   = str(row['SOURCE_UEN']).strip()
            tgt   = str(row['TARGET_UEN']).strip()
            count = int(row['txn_count']) if pd.notna(row['txn_count']) else 0
            amt   = float(row['txn_amt'])  if pd.notna(row['txn_amt'])  else 0.0
            pair  = tuple(sorted([src, tgt]))

            if pair not in lookup:
                lookup[pair] = {
                    'ab_count': 0, 'ab_amt': 0.0,   # sorted[0] -> sorted[1]
                    'ba_count': 0, 'ba_amt': 0.0,   # sorted[1] -> sorted[0]
                    'outflow' : {},
                }

            p = lookup[pair]
            if src == pair[0]:
                p['ab_count'] += count
                p['ab_amt']   += amt
            else:
                p['ba_count'] += count
                p['ba_amt']   += amt

            p['outflow'][src] = p['outflow'].get(src, 0.0) + amt

        return lookup

    def _prep_fg(self, source, kind: str) -> dict:
        """
        Build FAST or GIRO lookup from source.directed_edges_df.
        Key   : canonical pair
        Value : dict with per-direction count/amt and outflow per UEN.
        kind  : 'fast' or 'giro' (only used for diagnostic prints if needed).
        """
        if source is None or source.directed_edges_df is None or len(source.directed_edges_df) == 0:
            return {}
        df = source.directed_edges_df.copy()
        df = df[df['SOURCE_UEN'] != df['TARGET_UEN']]

        lookup = {}
        for _, row in df.iterrows():
            src   = str(row['SOURCE_UEN']).strip()
            tgt   = str(row['TARGET_UEN']).strip()
            count = int(row['txn_count']) if pd.notna(row['txn_count']) else 0
            amt   = float(row['txn_amt'])  if pd.notna(row['txn_amt'])  else 0.0
            pair  = tuple(sorted([src, tgt]))

            if pair not in lookup:
                lookup[pair] = {
                    'ab_count': 0, 'ab_amt': 0.0,
                    'ba_count': 0, 'ba_amt': 0.0,
                    'outflow' : {},
                }
            p = lookup[pair]
            if src == pair[0]:
                p['ab_count'] += count
                p['ab_amt']   += amt
            else:
                p['ba_count'] += count
                p['ba_amt']   += amt
            p['outflow'][src] = p['outflow'].get(src, 0.0) + amt
        return lookup

    def _prep_rsme(self, rsme_source) -> dict:
        """
        Build RSME lookup.
        Key   : canonical pair
        Value : dict of {customer_uen, counterparty_uen}
                customer = BOR (borrower/buyer-checklist declarer)
                counterparty = SUP (supplier/counterparty being declared)
        """
        edges = rsme_source.get_edges()
        if edges is None or len(edges) == 0:
            return {}

        edges = edges[edges['SOURCE_UEN'] != edges['TARGET_UEN']]

        lookup = {}
        for _, row in edges.iterrows():
            src  = str(row['SOURCE_UEN']).strip()
            tgt  = str(row['TARGET_UEN']).strip()
            pair = tuple(sorted([src, tgt]))

            if pair not in lookup:
                # SOURCE = BOR (customer), TARGET = SUP (counterparty)
                lookup[pair] = {
                    'customer_uen'     : src,
                    'counterparty_uen' : tgt,
                }

        return lookup

    # ══════════════════════════════════════════════════════════════════════
    # ROW BUILDER
    # ══════════════════════════════════════════════════════════════════════

    def _build_row(self, pair, fitas, aa, tt, fast, giro, rsme) -> dict:
        """
        Apply priority chain for one pair and return a flat dict row.
        """
        uen_a, uen_b = pair

        row = {
            'uen_a'             : uen_a,
            'uen_b'             : uen_b,
            'buyer_uen'         : None,
            'supplier_uen'      : None,
            'customer_uen'      : None,
            'counterparty_uen'  : None,
            'is_both'           : False,
            'is_directed'       : True,
            'priority_source'   : None,
            'from_uen'          : None,
            'to_uen'            : None,
            'in_fitas'          : fitas is not None,
            'in_aa'             : aa    is not None,
            'in_tt'             : tt    is not None,
            'in_fast'           : fast  is not None,
            'in_giro'           : giro  is not None,
            'in_payment'        : (tt is not None) or (fast is not None) or (giro is not None),
            'in_rsme'           : rsme  is not None,
        }

        # Per-source pair fields (always populated when source data exists)
        row.update(self._extract_per_source_fields(pair, tt,    'tt'))
        row.update(self._extract_per_source_fields(pair, fast,  'fast'))
        row.update(self._extract_per_source_fields(pair, giro,  'giro'))
        row.update(self._extract_payment_fields(row))
        row.update(self._extract_fitas_fields(pair, fitas))
        row.update(self._extract_all_txn_fields(row, pair, fitas))

        # Grand total kept for backwards compat -- equal to all_txn_total_amt
        row['grand_total_amt'] = row.get('all_txn_total_amt') or 0.0

        # Priority chain
        if fitas is not None:
            self._apply_fitas_direction(row, pair, fitas)
        elif aa is not None:
            self._apply_aa_direction(row, pair, aa)
        elif row['in_payment']:
            self._apply_payment_direction(row, pair, fitas, tt, fast, giro)
        else:
            row['is_directed']     = False
            row['is_both']         = False
            row['priority_source'] = 'RSME Buyer/Supplier Checklist'
            if rsme is not None:
                row['customer_uen']     = rsme['customer_uen']
                row['counterparty_uen'] = rsme['counterparty_uen']
                row['from_uen']         = rsme['customer_uen']
                row['to_uen']           = rsme['counterparty_uen']
            else:
                row['from_uen'] = uen_a
                row['to_uen']   = uen_b

        if row['is_both'] and row['is_directed']:
            from_uen = self._resolve_from_uen(pair, fitas, tt, fast, giro)
            to_uen   = uen_b if from_uen == uen_a else uen_a
            row['from_uen'] = from_uen
            row['to_uen']   = to_uen
            row['buyer_uen']    = from_uen
            row['supplier_uen'] = to_uen

        return row

    # ══════════════════════════════════════════════════════════════════════
    # DIRECTION APPLIERS
    # ══════════════════════════════════════════════════════════════════════

    def _apply_fitas_direction(self, row, pair, fitas):
        """
        Determine buyer/supplier from FITAS product classification.
        Products in FITAS_BUYER_PRODUCTS mean SOURCE is the buyer.
        Products in FITAS_SUPPLIER_PRODUCTS mean SOURCE is the supplier.
        If both product types present for the same pair -> is_both=True.
        """
        uen_a, uen_b = pair
        products     = fitas.get('products', {})

        # Accumulate outflow per UEN across all product types for direction
        # SOURCE always sent money in fitas_product_df (buyer perspective)
        # Use outflow dict built in _prep_fitas
        outflow = fitas.get('outflow', {})

        has_buyer_products    = False
        has_supplier_products = False

        # For each product-direction key, classify as buyer or supplier activity
        for prod, dir_dict in products.items():
            for dir_key in dir_dict.keys():
                src_uen = dir_key.split('__')[0]
                if prod in FITAS_BUYER_PRODUCTS:
                    # src_uen is acting as buyer to their counterparty
                    has_buyer_products = True
                elif prod in FITAS_SUPPLIER_PRODUCTS:
                    # src_uen is acting as supplier to their counterparty
                    has_supplier_products = True
                else:
                    # 'OTHERS' -- classified as buyer activity by default
                    has_buyer_products = True

        # Identify who is predominantly buyer based on outflow and product type
        # The UEN with buyer products is the buyer; with supplier products is supplier
        # Collect buyer-side UENs and supplier-side UENs
        buyer_uens    = set()
        supplier_uens = set()
        for prod, dir_dict in products.items():
            for dir_key in dir_dict.keys():
                src_uen = dir_key.split('__')[0]
                tgt_uen = dir_key.split('__')[1]
                if prod in FITAS_BUYER_PRODUCTS or prod == 'OTHERS':
                    buyer_uens.add(src_uen)
                    supplier_uens.add(tgt_uen)
                elif prod in FITAS_SUPPLIER_PRODUCTS:
                    # src acts as supplier, so counterparty is the buyer
                    buyer_uens.add(tgt_uen)
                    supplier_uens.add(src_uen)

        row['priority_source'] = 'FITAS'
        row['is_directed']     = True

        if has_buyer_products and has_supplier_products:
            # The same UEN acts as both buyer and supplier to its counterparty
            row['is_both']      = True
            row['buyer_uen']    = None
            row['supplier_uen'] = None
            # from_uen resolved later by _resolve_from_uen
        elif has_buyer_products:
            # Unique buyer/supplier -- take the first resolved values
            buyer_uen    = next(iter(buyer_uens),    uen_a)
            supplier_uen = next(iter(supplier_uens), uen_b)
            row['is_both']      = False
            row['buyer_uen']    = buyer_uen
            row['supplier_uen'] = supplier_uen
            row['from_uen']     = buyer_uen
            row['to_uen']       = supplier_uen
        else:
            # Only supplier products -- flip
            buyer_uen    = next(iter(buyer_uens),    uen_b)
            supplier_uen = next(iter(supplier_uens), uen_a)
            row['is_both']      = False
            row['buyer_uen']    = buyer_uen
            row['supplier_uen'] = supplier_uen
            row['from_uen']     = buyer_uen
            row['to_uen']       = supplier_uen

    def _apply_aa_direction(self, row, pair, aa):
        """
        Apply AA Paper direction -- SOURCE already enforced as buyer in
        aa_paper_source. is_both if pair appeared in both directions.
        """
        row['priority_source'] = 'AA Paper'
        row['is_directed']     = True
        row['is_both']         = aa['is_both']

        if not aa['is_both']:
            row['buyer_uen']    = aa['buyer_uen']
            row['supplier_uen'] = aa['supplier_uen']
            row['from_uen']     = aa['buyer_uen']
            row['to_uen']       = aa['supplier_uen']
        # is_both=True -> from_uen resolved later by _resolve_from_uen

    def _apply_payment_direction(self, row, pair, fitas, tt, fast, giro):
        """
        Apply All Txn direction via combined flow percentage.
        Combined per direction = TT + FAST + GIRO + FITAS amt (when present).
        > 60%: pair[0] is buyer; < 40%: pair[1] is buyer; otherwise is_both.
        """
        uen_a, uen_b = pair

        ab_amt = (
            (tt['ab_amt']    if tt    else 0.0) +
            (fast['ab_amt']  if fast  else 0.0) +
            (giro['ab_amt']  if giro  else 0.0)
        )
        ba_amt = (
            (tt['ba_amt']    if tt    else 0.0) +
            (fast['ba_amt']  if fast  else 0.0) +
            (giro['ba_amt']  if giro  else 0.0)
        )
        # FITAS pair-level amt is per-direction in fitas['products'] -> pre-aggregated below
        if fitas is not None:
            outflow = fitas.get('outflow', {})
            ab_amt += outflow.get(uen_a, 0.0)
            ba_amt += outflow.get(uen_b, 0.0)

        total_amt = ab_amt + ba_amt
        row['priority_source'] = 'Payment Transactions (TT/MEPS/FAST/GIRO)'
        row['is_directed']     = True

        if total_amt <= 0:
            row['is_both']      = False
            row['buyer_uen']    = uen_a
            row['supplier_uen'] = uen_b
            row['from_uen']     = uen_a
            row['to_uen']       = uen_b
            return

        pct_ab = ab_amt / total_amt
        if pct_ab > _BUYER_THRESHOLD:
            row['is_both'], row['buyer_uen'], row['supplier_uen'] = False, uen_a, uen_b
            row['from_uen'], row['to_uen'] = uen_a, uen_b
        elif pct_ab < _SUPPLIER_THRESHOLD:
            row['is_both'], row['buyer_uen'], row['supplier_uen'] = False, uen_b, uen_a
            row['from_uen'], row['to_uen'] = uen_b, uen_a
        else:
            row['is_both']      = True
            row['buyer_uen']    = None
            row['supplier_uen'] = None
            # from_uen resolved later by _resolve_from_uen

    # ══════════════════════════════════════════════════════════════════════
    # FROM_UEN RESOLVER FOR IS_BOTH EDGES
    # ══════════════════════════════════════════════════════════════════════

    def _resolve_from_uen(self, pair, fitas, tt, fast, giro) -> str:
        """
        For is_both edges, set from_uen = UEN with higher combined outflow
        (FITAS + TT + FAST + GIRO sent). Tie-break: alphabetical ascending.
        """
        uen_a, uen_b = pair
        outflow_a, outflow_b = 0.0, 0.0
        for src in (fitas, tt, fast, giro):
            if src is None:
                continue
            outflow_a += src.get('outflow', {}).get(uen_a, 0.0)
            outflow_b += src.get('outflow', {}).get(uen_b, 0.0)
        if outflow_a > outflow_b:   return uen_a
        if outflow_b > outflow_a:   return uen_b
        return min(uen_a, uen_b)

    # ══════════════════════════════════════════════════════════════════════
    # FIELD EXTRACTORS
    # ══════════════════════════════════════════════════════════════════════

    def _extract_per_source_fields(self, pair, src, prefix) -> dict:
        """
        Generic extractor for tt/fast/giro source-shaped lookups.
        prefix: 'tt' | 'fast' | 'giro'.
        Emits {prefix}_ab_count/amt, {prefix}_ba_count/amt, {prefix}_total_count/amt,
        {prefix}_net_amt and placeholder buyer_to_supplier columns (filled by remap).
        """
        empty = {
            f'{prefix}_ab_count'                 : None,
            f'{prefix}_ab_amt'                   : None,
            f'{prefix}_ba_count'                 : None,
            f'{prefix}_ba_amt'                   : None,
            f'{prefix}_total_count'              : None,
            f'{prefix}_total_amt'                : None,
            f'{prefix}_net_amt'                  : None,
            f'{prefix}_buyer_to_supplier_count'  : None,
            f'{prefix}_buyer_to_supplier_amt'    : None,
            f'{prefix}_buyer_to_supplier_amt_pct': None,
            f'{prefix}_supplier_to_buyer_count'  : None,
            f'{prefix}_supplier_to_buyer_amt'    : None,
            f'{prefix}_supplier_to_buyer_amt_pct': None,
        }
        if src is None:
            return empty
        ab_c, ab_a = src.get('ab_count', 0), src.get('ab_amt', 0.0)
        ba_c, ba_a = src.get('ba_count', 0), src.get('ba_amt', 0.0)
        empty[f'{prefix}_ab_count']    = ab_c    or None
        empty[f'{prefix}_ab_amt']      = ab_a    or None
        empty[f'{prefix}_ba_count']    = ba_c    or None
        empty[f'{prefix}_ba_amt']      = ba_a    or None
        empty[f'{prefix}_total_count'] = (ab_c + ba_c) or None
        empty[f'{prefix}_total_amt']   = (ab_a + ba_a) or None
        empty[f'{prefix}_net_amt']     = (ab_a - ba_a) if (ab_a or ba_a) else None
        return empty

    def _extract_payment_fields(self, row) -> dict:
        """
        Aggregate tt + fast + giro per-direction columns into payment_*.
        Reads back from row (already populated by _extract_per_source_fields).
        """
        ab_c = sum((row.get(f'{p}_ab_count') or 0)    for p in ('tt','fast','giro'))
        ab_a = sum((row.get(f'{p}_ab_amt')   or 0.0)  for p in ('tt','fast','giro'))
        ba_c = sum((row.get(f'{p}_ba_count') or 0)    for p in ('tt','fast','giro'))
        ba_a = sum((row.get(f'{p}_ba_amt')   or 0.0)  for p in ('tt','fast','giro'))
        return {
            'payment_ab_count'                 : ab_c or None,
            'payment_ab_amt'                   : ab_a or None,
            'payment_ba_count'                 : ba_c or None,
            'payment_ba_amt'                   : ba_a or None,
            'payment_total_count'              : (ab_c + ba_c) or None,
            'payment_total_amt'                : (ab_a + ba_a) or None,
            'payment_net_amt'                  : (ab_a - ba_a) if (ab_a or ba_a) else None,
            'payment_buyer_to_supplier_count'  : None,
            'payment_buyer_to_supplier_amt'    : None,
            'payment_buyer_to_supplier_amt_pct': None,
            'payment_supplier_to_buyer_count'  : None,
            'payment_supplier_to_buyer_amt'    : None,
            'payment_supplier_to_buyer_amt_pct': None,
        }

    def _extract_all_txn_fields(self, row, pair, fitas) -> dict:
        """
        Aggregate fitas + payment per-direction. FITAS direction is exact:
        _prep_fitas tracks ab_count/ab_amt/ba_count/ba_amt per canonical pair
        based on SOURCE_UEN = buyer (after FITAS direction assignment). So
        all_txn_ab = payment_ab + fitas_ab and all_txn_total exactly equals
        all_txn_ab + all_txn_ba.
        """
        ab_a_pay = (row.get('payment_ab_amt')   or 0.0)
        ba_a_pay = (row.get('payment_ba_amt')   or 0.0)
        ab_c_pay = (row.get('payment_ab_count') or 0)
        ba_c_pay = (row.get('payment_ba_count') or 0)

        if fitas is not None:
            ab_a_fitas = float(fitas.get('ab_amt',   0.0))
            ba_a_fitas = float(fitas.get('ba_amt',   0.0))
            ab_c_fitas = int(  fitas.get('ab_count', 0))
            ba_c_fitas = int(  fitas.get('ba_count', 0))
        else:
            ab_a_fitas = ba_a_fitas = 0.0
            ab_c_fitas = ba_c_fitas = 0

        ab_c = ab_c_pay + ab_c_fitas
        ba_c = ba_c_pay + ba_c_fitas
        ab_a = ab_a_pay + ab_a_fitas
        ba_a = ba_a_pay + ba_a_fitas

        return {
            'all_txn_ab_count'                 : ab_c or None,
            'all_txn_ab_amt'                   : ab_a or None,
            'all_txn_ba_count'                 : ba_c or None,
            'all_txn_ba_amt'                   : ba_a or None,
            'all_txn_total_count'              : (ab_c + ba_c) or None,
            'all_txn_total_amt'                : (ab_a + ba_a) or None,
            'all_txn_net_amt'                  : (ab_a - ba_a) if (ab_a or ba_a) else None,
            'all_txn_buyer_to_supplier_count'  : None,
            'all_txn_buyer_to_supplier_amt'    : None,
            'all_txn_buyer_to_supplier_amt_pct': None,
            'all_txn_supplier_to_buyer_count'  : None,
            'all_txn_supplier_to_buyer_amt'    : None,
            'all_txn_supplier_to_buyer_amt_pct': None,
        }

    def _extract_fitas_fields(self, pair, fitas) -> dict:
        """
        Pivot FITAS product data into flat columns.
        Totals across both directions (SOURCE->TARGET + TARGET->SOURCE) since
        the sheet wants total volume regardless of who was buyer for that trade.
        """
        base = {}
        for prod in _ALL_FITAS_PRODUCTS:
            col = prod.lower()
            base[f'fitas_{col}_count'] = None
            base[f'fitas_{col}_amt']   = None
        base['fitas_total_count'] = None
        base['fitas_total_amt']   = None

        if fitas is None:
            return base

        products   = fitas.get('products', {})
        total_cnt  = 0
        total_amt  = 0.0

        for prod, dir_dict in products.items():
            col       = prod.lower()
            prod_cnt  = sum(v['count'] for v in dir_dict.values())
            prod_amt  = sum(v['amt']   for v in dir_dict.values())
            total_cnt += prod_cnt
            total_amt += prod_amt

            base[f'fitas_{col}_count'] = prod_cnt or None
            base[f'fitas_{col}_amt']   = prod_amt or None

        base['fitas_total_count'] = total_cnt or None
        base['fitas_total_amt']   = total_amt or None

        return base

    def remap_all_txn_direction(self):
        """
        After relationship_df is fully built, remap ab/ba fields for every
        per-source layer (tt, fast, giro, payment, all_txn) into
        buyer_to_supplier / supplier_to_buyer based on resolved buyer_uen vs uen_a.

        Vectorised: avoids per-row .iterrows()/.at[] which scales O(N*P) and
        becomes the dominant cost on large pair sets. Outer loop is now
        prefixes (5), inner work is np.where on whole columns.
        """
        if self.relationship_df is None:
            return

        import numpy as np

        df = self.relationship_df
        # Include is_both pairs in the remap. _build_row already sets
        # buyer_uen for is_both via _resolve_from_uen (outflow tie-break),
        # so b2s/s2b columns get populated using the heuristic buyer.
        directed_mask = df['is_directed'] & df['buyer_uen'].notna()
        buyer_is_a    = (df['buyer_uen'] == df['uen_a'])

        for prefix in ('tt', 'fast', 'giro', 'payment', 'all_txn'):
            ab_c = df[f'{prefix}_ab_count']
            ab_a = df[f'{prefix}_ab_amt']
            ba_c = df[f'{prefix}_ba_count']
            ba_a = df[f'{prefix}_ba_amt']
            tot  = df[f'{prefix}_total_amt'].fillna(0.0).astype(float)

            b2s_c = np.where(buyer_is_a, ab_c, ba_c)
            b2s_a = np.where(buyer_is_a, ab_a, ba_a)
            s2b_c = np.where(buyer_is_a, ba_c, ab_c)
            s2b_a = np.where(buyer_is_a, ba_a, ab_a)

            with np.errstate(divide='ignore', invalid='ignore'):
                b2s_pct = np.where(tot > 0, np.round(b2s_a.astype(float) / tot * 100, 1), np.nan)
                s2b_pct = np.where(tot > 0, np.round(s2b_a.astype(float) / tot * 100, 1), np.nan)

            # Only assign for rows in directed_mask (others remain NaN)
            mask = directed_mask.to_numpy()
            df.loc[mask, f'{prefix}_buyer_to_supplier_count']   = b2s_c[mask]
            df.loc[mask, f'{prefix}_buyer_to_supplier_amt']     = b2s_a[mask]
            df.loc[mask, f'{prefix}_buyer_to_supplier_amt_pct'] = b2s_pct[mask]
            df.loc[mask, f'{prefix}_supplier_to_buyer_count']   = s2b_c[mask]
            df.loc[mask, f'{prefix}_supplier_to_buyer_amt']     = s2b_a[mask]
            df.loc[mask, f'{prefix}_supplier_to_buyer_amt_pct'] = s2b_pct[mask]

        self.relationship_df = df
        n = int(directed_mask.sum())
        print(f"  All-Txn direction remapped for {n:,} directed non-both rows "
              f"(tt+fast+giro+payment+all_txn).")
