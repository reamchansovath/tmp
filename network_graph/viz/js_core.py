# ── network_graph/viz/js_core.py ────────────────────────────────────────────
# JavaScript Core - Embeds all data payloads and global variables.
# UEN COMPRESSION: all data structures use short string IDs internally.
# _UtoI/_ItoU maps and _e()/_d() functions handle encode/decode at boundary.
#
# Imports compression helpers from compression.py (not builder.py) to
# avoid circular import: builder.py -> js_core.py -> builder.py
#
# EDGE ARCHITECTURE:
# pairRelationshipMap is the single source of truth for all edge data.
# It serves dual purpose:
#   1. vis.js injection -- fr/to compressed IDs, ro/wb/ib visual fields,
#      ir/if/ia/it filter flags, data fields for side panel
#   2. Edge click panel -- buyer/supplier direction, TT flow, FITAS products
# consolidatedEdgesData removed -- pairRelationshipMap replaces it entirely.
# selfLoopEdgesData kept separate (self-loops have no pair relationship entry).
#
# NODE META FILTERING:
# *** updated | nodeMetaMap only contains fields where enabled=True in
# FIELD_CONFIG, plus SYSTEM_FIELDS always included for graph logic.
# Fields with enabled=False are excluded from HTML entirely -- they only
# appear in Excel report (Recipe 3) and HTML report (Recipe 4).
# Use config.get_graph_fields() + config.SYSTEM_FIELDS to get allowed set.

import math
import pandas as pd
from .compression import (
    c_key, c_key_listval, c_list,
    c_edges_from_to, c_selfloop_edges,
)


def get_js_core(config, rsme_adjacency, rsme_degree_map, original_sizes_js,
                node_type_js, node_meta_js, id_name_lookup_js, original_labels_js,
                rsme_source, consol_tt_source, fitas_source, aa_paper_source,
                fast_source, giro_source,
                consol_tt_node_summary_js, fitas_node_summary_js,
                fast_node_summary_js, giro_node_summary_js,
                payment_node_summary_js, all_txn_node_summary_js,
                consol_tt_metric_ranges, fitas_metric_ranges,
                fast_metric_ranges, giro_metric_ranges,
                payment_metric_ranges, all_txn_metric_ranges,
                undirected_edges_js, directed_edges_js, selfloop_edges_js,
                payment_directed_edges_js,
                payment_selfloop_edges_js,
                fitas_selfloop_edges_js,
                all_txn_selfloop_edges_js,
                uen_to_id, id_to_uen,
                safe_json,
                all_txn_latest_date='',
                relationship_df=None):
    """
    Returns core JavaScript code with all data payloads.

    All data structures compressed to short string IDs via uen_to_id.
    _UtoI/_ItoU maps embedded once. _e()/_d() functions handle boundary.

    Node meta filtering:
    nodeMetaMap only includes fields where enabled=True in FIELD_CONFIG,
    plus SYSTEM_FIELDS always present for graph logic. Fields with
    enabled=False are stripped from the HTML payload entirely.

    Edge data:
    - pairRelationshipMap : single source of truth, one entry per unique pair.
    - selfLoopEdgesData   : TT self-transfers, injected separately.
    """

    sj = safe_json

    # ── Step 0: Build allowed field set for node meta filtering ───────────
    # *** new | only enabled=True fields + system fields go into HTML
    _graph_fields   = config.get_graph_fields()
    _system_fields  = config.SYSTEM_FIELDS
    _allowed_fields = _graph_fields | _system_fields

    def _filter_meta(meta_dict):
        """Strip disabled fields from a single node's metadata dict."""
        return {k: v for k, v in meta_dict.items() if k in _allowed_fields}

    # Apply filter to all nodes before compression
    node_meta_js_filtered = {
        uen: _filter_meta(meta)
        for uen, meta in node_meta_js.items()
    }

    # Diagnostic
    _sample_uens = list(node_meta_js.keys())[:3]
    for _uen in _sample_uens:
        _before = len(node_meta_js.get(_uen, {}))
        _after  = len(node_meta_js_filtered.get(_uen, {}))
        print(f"  meta filter sample [{_uen}]: {_before} -> {_after} fields "
              f"({_before - _after} excluded)")

    # ── Step 1: Build raw structures (UEN-keyed) ───────────────────────────

    _consol_tt_out_adj = {str(k): list(set(v)) for k, v in consol_tt_source.out_adj.items()}
    _consol_tt_in_adj  = {str(k): list(set(v)) for k, v in consol_tt_source.in_adj.items()}
    _consol_tt_degree  = {str(k): v             for k, v in consol_tt_source.degree_map.items()}
    _consol_tt_self    = list(consol_tt_source.self_loop_ids)

    _fitas_out_adj = {str(k): list(set(v)) for k, v in fitas_source.out_adj.items()}
    _fitas_in_adj  = {str(k): list(set(v)) for k, v in fitas_source.in_adj.items()}
    _fitas_degree  = {str(k): v             for k, v in fitas_source.degree_map.items()}
    _fitas_self    = list(fitas_source.self_loop_ids)

    _aa_out_adj = {str(k): list(set(v)) for k, v in aa_paper_source.out_adj.items()}
    _aa_in_adj  = {str(k): list(set(v)) for k, v in aa_paper_source.in_adj.items()}
    _aa_degree  = {str(k): v             for k, v in aa_paper_source.degree_map.items()}
    _aa_self    = list(aa_paper_source.self_loop_ids)

    _fast_out_adj = {str(k): list(set(v)) for k, v in fast_source.out_adj.items()}
    _fast_in_adj  = {str(k): list(set(v)) for k, v in fast_source.in_adj.items()}
    _fast_degree  = {str(k): v             for k, v in fast_source.degree_map.items()}
    _fast_self    = list(fast_source.self_loop_ids)

    _giro_out_adj = {str(k): list(set(v)) for k, v in giro_source.out_adj.items()}
    _giro_in_adj  = {str(k): list(set(v)) for k, v in giro_source.in_adj.items()}
    _giro_degree  = {str(k): v             for k, v in giro_source.degree_map.items()}
    _giro_self    = list(giro_source.self_loop_ids)

    # Payment = TT + FAST + GIRO union
    def _union_listval(*ds):
        out = {}
        for d in ds:
            for k, vs in d.items():
                s = out.setdefault(str(k), set())
                for v in vs:
                    s.add(str(v))
        return {k: list(v) for k, v in out.items()}
    _payment_out_adj = _union_listval(consol_tt_source.out_adj, fast_source.out_adj, giro_source.out_adj)
    _payment_in_adj  = _union_listval(consol_tt_source.in_adj,  fast_source.in_adj,  giro_source.in_adj)
    _payment_self    = list(set(consol_tt_source.self_loop_ids) |
                             set(fast_source.self_loop_ids) |
                             set(giro_source.self_loop_ids))
    _all_txn_self    = list(set(consol_tt_source.self_loop_ids) |
                             set(fitas_source.self_loop_ids) |
                             set(fast_source.self_loop_ids) |
                             set(giro_source.self_loop_ids))
    _payment_active  = (set(consol_tt_source.active_uens) |
                        set(fast_source.active_uens) |
                        set(giro_source.active_uens))
    _payment_degree = {nid: (len(_payment_out_adj.get(nid, [])) + len(_payment_in_adj.get(nid, [])))
                       for nid in _payment_active}
    _payment_node_ids = list(_payment_active)
    _fast_node_ids    = list(fast_source.active_uens)
    _giro_node_ids    = list(giro_source.active_uens)

    _rsme_node_ids      = list(rsme_adjacency.keys())
    _consol_tt_node_ids = list(consol_tt_source.active_uens)
    _fitas_node_ids     = list(fitas_source.active_uens)
    _aa_node_ids        = list(aa_paper_source.active_uens)

    # ── Step 2: Compress all structures via uen_to_id ─────────────────────

    consol_tt_out_adj_js   = c_key_listval(_consol_tt_out_adj, uen_to_id)
    consol_tt_in_adj_js    = c_key_listval(_consol_tt_in_adj,  uen_to_id)
    consol_tt_degree_js    = c_key(_consol_tt_degree,           uen_to_id)
    consol_tt_self_loop_js = c_list(_consol_tt_self,            uen_to_id)

    fitas_out_adj_js   = c_key_listval(_fitas_out_adj, uen_to_id)
    fitas_in_adj_js    = c_key_listval(_fitas_in_adj,  uen_to_id)
    fitas_degree_js    = c_key(_fitas_degree,           uen_to_id)
    fitas_self_loop_js = c_list(_fitas_self,            uen_to_id)

    aa_paper_out_adj_js   = c_key_listval(_aa_out_adj, uen_to_id)
    aa_paper_in_adj_js    = c_key_listval(_aa_in_adj,  uen_to_id)
    aa_paper_degree_js    = c_key(_aa_degree,           uen_to_id)
    aa_paper_self_loop_js = c_list(_aa_self,            uen_to_id)

    rsme_adjacency_js  = c_key_listval(rsme_adjacency, uen_to_id)
    rsme_degree_map_js = c_key(rsme_degree_map,         uen_to_id)

    rsme_node_ids_js      = c_list(_rsme_node_ids,      uen_to_id)
    consol_tt_node_ids_js = c_list(_consol_tt_node_ids, uen_to_id)
    fitas_node_ids_js     = c_list(_fitas_node_ids,     uen_to_id)
    aa_paper_node_ids_js  = c_list(_aa_node_ids,        uen_to_id)

    fast_out_adj_js   = c_key_listval(_fast_out_adj, uen_to_id)
    fast_in_adj_js    = c_key_listval(_fast_in_adj,  uen_to_id)
    fast_degree_js    = c_key(_fast_degree,           uen_to_id)
    fast_self_loop_js = c_list(_fast_self,            uen_to_id)
    fast_node_ids_js  = c_list(_fast_node_ids,        uen_to_id)

    giro_out_adj_js   = c_key_listval(_giro_out_adj, uen_to_id)
    giro_in_adj_js    = c_key_listval(_giro_in_adj,  uen_to_id)
    giro_degree_js    = c_key(_giro_degree,           uen_to_id)
    giro_self_loop_js = c_list(_giro_self,            uen_to_id)
    giro_node_ids_js  = c_list(_giro_node_ids,        uen_to_id)

    payment_out_adj_js   = c_key_listval(_payment_out_adj, uen_to_id)
    payment_in_adj_js    = c_key_listval(_payment_in_adj,  uen_to_id)
    payment_degree_js    = c_key(_payment_degree,           uen_to_id)
    payment_self_loop_js = c_list(_payment_self,            uen_to_id)
    all_txn_self_loop_js = c_list(_all_txn_self,            uen_to_id)
    payment_node_ids_js  = c_list(_payment_node_ids,        uen_to_id)

    fast_node_summary_js_c    = c_key(fast_node_summary_js,    uen_to_id)
    giro_node_summary_js_c    = c_key(giro_node_summary_js,    uen_to_id)
    payment_node_summary_js_c = c_key(payment_node_summary_js, uen_to_id)
    all_txn_node_summary_js_c = c_key(all_txn_node_summary_js, uen_to_id)

    payment_directed_edges_js_c = c_edges_from_to(payment_directed_edges_js, uen_to_id)
    payment_selfloop_edges_js_c = c_selfloop_edges(payment_selfloop_edges_js, uen_to_id)
    fitas_selfloop_edges_js_c   = c_selfloop_edges(fitas_selfloop_edges_js,   uen_to_id)
    all_txn_selfloop_edges_js_c = c_selfloop_edges(all_txn_selfloop_edges_js, uen_to_id)

    # *** updated | use filtered meta dict instead of raw node_meta_js
    node_meta_js_c       = c_key(node_meta_js_filtered, uen_to_id)
    node_type_js_c       = c_key(node_type_js,           uen_to_id)
    original_sizes_js_c  = c_key(original_sizes_js,      uen_to_id)
    original_labels_js_c = c_key(original_labels_js,     uen_to_id)
    id_name_lookup_js_c  = c_key(id_name_lookup_js,      uen_to_id)

    consol_tt_node_summary_js_c = c_key(consol_tt_node_summary_js, uen_to_id)
    fitas_node_summary_js_c     = c_key(fitas_node_summary_js,     uen_to_id)

    undirected_edges_js_c = c_edges_from_to(undirected_edges_js, uen_to_id)
    directed_edges_js_c   = c_edges_from_to(directed_edges_js,   uen_to_id)
    selfloop_edges_js_c   = c_selfloop_edges(selfloop_edges_js,  uen_to_id)

    company_list_js_c = [
        {'id': uen_to_id[str(uen)], 'name': str(name)}
        for uen, name in id_name_lookup_js.items()
        if str(uen) in uen_to_id
    ]

    # ── Step 3: Configuration ──────────────────────────────────────────────
    seg_colors_js = sj({k: v for k, v in config.SEGMENT_COLORS.items()})

    # fieldConfig -- only enabled=True fields, with label/section/trade_only/cpty
    field_cfg_js = sj({
        k: {
            'label'     : v['label'],
            'section'   : v['section'],
            'trade_only': v['trade_only'],
            'cpty'      : v['cpty'],
        }
        for k, v in config.FIELD_CONFIG.items() if v['enabled']
    })

    # ── Step 4: AMT_FIELDS ────────────────────────────────────────────────
    # *** updated | Enricher.AMT_COLS now includes MFI and CIP amount cols
    from ..pipeline.enricher import Enricher
    amt_fields_js = sj(list(Enricher.AMT_COLS))

    # ── Step 5: Latest data dates ─────────────────────────────────────────
    tt_latest_date    = consol_tt_source.tt_latest_date or ''
    fitas_latest_date = fitas_source.fitas_latest_date  or ''

    # ── Step 5.5: Build pairRelationshipMap ───────────────────────────────

    _FITAS_PRODUCTS = ['lc', 'tr', 'sta', 'exportlc', 'fbep', 'oat', 'others']

    def _safe_val(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    def _compress_uen_field(uen_val):
        v = _safe_val(uen_val)
        if v is None:
            return None
        return uen_to_id.get(str(v))

    def _safe_float(v):
        if v is None:
            return 0.0
        try:
            f = float(v)
            return 0.0 if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            return 0.0

    def _bin_widths(amounts, min_w=1.0, max_w=8.0):
        arr      = [_safe_float(a) for a in amounts]
        log_amts = [math.log1p(max(a, 0.0)) for a in arr]
        lo       = min(log_amts)
        hi       = max(log_amts)
        if hi <= lo:
            return [float(min_w)] * len(arr)
        return [
            round(min_w + (v - lo) / (hi - lo) * (max_w - min_w), 2)
            for v in log_amts
        ]

    _undir_lookup = {}
    for e in undirected_edges_js_c:
        _key = '_'.join(str(x) for x in sorted([int(e['from']), int(e['to'])]))
        _undir_lookup[_key] = e

    _dir_lookup = {}
    for e in directed_edges_js_c:
        _key = '_'.join(str(x) for x in sorted([int(e['from']), int(e['to'])]))
        _dir_lookup[_key] = e

    pair_rel_map       = {}
    _pair_keys_ordered = []

    if relationship_df is not None and len(relationship_df) > 0:
        for row in relationship_df.to_dict('records'):
            id_a = uen_to_id.get(str(row.get('uen_a', '')))
            id_b = uen_to_id.get(str(row.get('uen_b', '')))
            if id_a is None or id_b is None:
                continue

            map_key = '_'.join(str(x) for x in sorted([int(id_a), int(id_b)]))

            from_id = uen_to_id.get(str(row.get('from_uen') or ''))
            to_id   = uen_to_id.get(str(row.get('to_uen')   or ''))
            if from_id is None or to_id is None:
                continue

            in_rsme    = bool(row.get('in_rsme',    False))
            in_fitas   = bool(row.get('in_fitas',   False))
            in_aa      = bool(row.get('in_aa',      False))
            in_tt      = bool(row.get('in_tt',      False))
            in_fast    = bool(row.get('in_fast',    False))
            in_giro    = bool(row.get('in_giro',    False))
            in_payment = bool(row.get('in_payment', False)) or in_tt or in_fast or in_giro
            is_both    = bool(row.get('is_both',    False))

            # *** fix | RSME-only must exclude ALL transaction sources, not
            # just TT. A pair with RSME + FAST/GIRO is a real directed
            # payment edge -- treating it as rsme_only would render it as a
            # green undirected line with no arrow.
            rsme_only  = in_rsme and not in_payment and not in_fitas and not in_aa

            undir_edge = _undir_lookup.get(map_key, {})
            dir_edge   = _dir_lookup.get(map_key,   {})

            entry = {
                'fr' : from_id,
                'to' : to_id,
                'ro' : rsme_only,
                'wb' : 1.0,
                'ps' : _safe_val(row.get('priority_source')),
                'ib' : is_both,
                'id' : bool(row.get('is_directed', True)),
                'if' : in_fitas,
                'ia' : in_aa,
                'it' : in_tt,
                'ir' : in_rsme,
                'bu' : _compress_uen_field(row.get('buyer_uen')),
                'su' : _compress_uen_field(row.get('supplier_uen')),
                'cu' : _compress_uen_field(row.get('customer_uen')),
                'cou': _compress_uen_field(row.get('counterparty_uen')),
                'tb2sc': _safe_val(row.get('tt_buyer_to_supplier_count')),
                'tb2sa': _safe_val(row.get('tt_buyer_to_supplier_amt')),
                'tb2sp': _safe_val(row.get('tt_buyer_to_supplier_amt_pct')),
                's2bc' : _safe_val(row.get('tt_supplier_to_buyer_count')),
                's2ba' : _safe_val(row.get('tt_supplier_to_buyer_amt')),
                's2bp' : _safe_val(row.get('tt_supplier_to_buyer_amt_pct')),
                'ttc'  : _safe_val(row.get('tt_total_count')),
                'tta'  : _safe_val(row.get('tt_total_amt')),
                'fta'  : _safe_val(row.get('fitas_total_amt')),
                'gta'  : _safe_val(row.get('all_txn_total_amt') or row.get('grand_total_amt')),
                '_rsme_ab'        : undir_edge.get('_rsme_ab',        False),
                '_rsme_ba'        : undir_edge.get('_rsme_ba',        False),
                '_aa_ab'          : undir_edge.get('_aa_ab',          False),
                '_aa_ba'          : undir_edge.get('_aa_ba',          False),
                '_fitas_ab_count' : undir_edge.get('_fitas_ab_count', 0),
                '_fitas_ab_amt'   : undir_edge.get('_fitas_ab_amt',   0),
                '_fitas_ba_count' : undir_edge.get('_fitas_ba_count', 0),
                '_fitas_ba_amt'   : undir_edge.get('_fitas_ba_amt',   0),
                '_tt_ab_count'    : dir_edge.get('_tt_ab_count',    0),
                '_tt_ab_amt'      : dir_edge.get('_tt_ab_amt',      0),
                '_tt_ba_count'    : dir_edge.get('_tt_ba_count',    0),
                '_tt_ba_amt'      : dir_edge.get('_tt_ba_amt',      0),
                '_tt_total_count' : dir_edge.get('_tt_total_count', 0),
                '_tt_net_amt'     : dir_edge.get('_tt_net_amt',     0),
            }

            for _prefix in ('tt', 'fast', 'giro', 'payment', 'all_txn'):
                entry[f'_{_prefix}_ab_count']    = _safe_val(row.get(f'{_prefix}_ab_count'))    or 0
                entry[f'_{_prefix}_ab_amt']      = _safe_val(row.get(f'{_prefix}_ab_amt'))      or 0
                entry[f'_{_prefix}_ba_count']    = _safe_val(row.get(f'{_prefix}_ba_count'))    or 0
                entry[f'_{_prefix}_ba_amt']      = _safe_val(row.get(f'{_prefix}_ba_amt'))      or 0
                entry[f'_{_prefix}_total_count'] = _safe_val(row.get(f'{_prefix}_total_count')) or 0
                entry[f'_{_prefix}_total_amt']   = _safe_val(row.get(f'{_prefix}_total_amt'))   or 0
                entry[f'_{_prefix}_net_amt']     = _safe_val(row.get(f'{_prefix}_net_amt'))     or 0
                entry[f'{_prefix}_b2sc']         = _safe_val(row.get(f'{_prefix}_buyer_to_supplier_count'))
                entry[f'{_prefix}_b2sa']         = _safe_val(row.get(f'{_prefix}_buyer_to_supplier_amt'))
                entry[f'{_prefix}_b2sp']         = _safe_val(row.get(f'{_prefix}_buyer_to_supplier_amt_pct'))
                entry[f'{_prefix}_s2bc']         = _safe_val(row.get(f'{_prefix}_supplier_to_buyer_count'))
                entry[f'{_prefix}_s2ba']         = _safe_val(row.get(f'{_prefix}_supplier_to_buyer_amt'))
                entry[f'{_prefix}_s2bp']         = _safe_val(row.get(f'{_prefix}_supplier_to_buyer_amt_pct'))

            entry['if_pay'] = bool(row.get('in_payment', False))
            entry['if_fa']  = bool(row.get('in_fast',    False))
            entry['if_gi']  = bool(row.get('in_giro',    False))

            for prod in _FITAS_PRODUCTS:
                cnt = _safe_val(row.get(f'fitas_{prod}_count'))
                amt = _safe_val(row.get(f'fitas_{prod}_amt'))
                if cnt is not None and cnt != 0:
                    entry[f'f_{prod}_c'] = int(cnt)
                if amt is not None and amt != 0:
                    entry[f'f_{prod}_a'] = float(amt)

            pair_rel_map[map_key] = entry
            _pair_keys_ordered.append(map_key)

        if _pair_keys_ordered:
            gta_vals = [_safe_float(pair_rel_map[k]['gta']) for k in _pair_keys_ordered]
            widths   = _bin_widths(gta_vals)
            for i, k in enumerate(_pair_keys_ordered):
                pair_rel_map[k]['wb'] = widths[i]

        rsme_only_count = sum(1 for e in pair_rel_map.values() if e['ro'])
        both_count      = sum(1 for e in pair_rel_map.values() if e['ib'])
        print(f"  pairRelationshipMap: {len(pair_rel_map):,} pairs built "
              f"({rsme_only_count:,} RSME-only, "
              f"{both_count:,} both-ways, "
              f"{len(pair_rel_map) - rsme_only_count - both_count:,} directed)")
    else:
        print("  pairRelationshipMap: relationship_df not provided -- empty map")

    # ── Step 6: Size reduction report ─────────────────────────────────────
    orig_size = sum([
        len(sj(node_meta_js)),
        len(sj(id_name_lookup_js)),
        len(sj(_consol_tt_out_adj)),
        len(sj(_consol_tt_in_adj)),
    ])
    comp_size = sum([
        len(sj(node_meta_js_c)),
        len(sj(id_name_lookup_js_c)),
        len(sj(consol_tt_out_adj_js)),
        len(sj(consol_tt_in_adj_js)),
    ])
    orig_meta_size = len(sj(node_meta_js))
    filt_meta_size = len(sj(node_meta_js_filtered))
    print(f"  nodeMetaMap field filter: {orig_meta_size/1024:.0f}KB -> "
          f"{filt_meta_size/1024:.0f}KB "
          f"({(1 - filt_meta_size/max(orig_meta_size,1))*100:.1f}% reduction, "
          f"{len(_allowed_fields)} allowed fields, "
          f"{len(config.FIELD_CONFIG) - len(_graph_fields)} excluded)")
    print(f"  js_core compression: {orig_size/1024:.0f}KB -> {comp_size/1024:.0f}KB "
          f"({(1 - comp_size/max(orig_size,1))*100:.1f}% reduction on key structures)")
    print(f"  pairRelationshipMap: {len(sj(pair_rel_map))/1024:.0f}KB")

    # ── Generate JavaScript ────────────────────────────────────────────────

    return f"""
// ══════════════════════════════════════════════════════════════════════════
// UEN COMPRESSION MAPS + BOUNDARY FUNCTIONS
// _UtoI : UEN string -> string ID  e.g. "202012345C" -> "1"
// _ItoU : string ID  -> UEN string e.g. "1" -> "202012345C"
// _e(uid) : encode UEN string to string ID -- call once at renderSearch entry
// _d(id)  : decode string ID to UEN string -- call only for display/external
// ══════════════════════════════════════════════════════════════════════════

var _UtoI = {sj(uen_to_id)};
var _ItoU = {sj(id_to_uen)};

function _e(uid) {{
    var id = _UtoI[uid];
    if (id === undefined) {{
        console.warn("_e(): UEN not in compression map:", uid);
        return uid;
    }}
    return id;
}}

function _d(id) {{
    var uid = _ItoU[String(id)];
    if (uid === undefined) {{
        console.warn("_d(): ID not in compression map:", id);
        return String(id);
    }}
    return uid;
}}

// ══════════════════════════════════════════════════════════════════════════
// CORE DATA PAYLOADS (all keyed by compressed string IDs)
// nodeMetaMap contains ONLY enabled=True fields from FIELD_CONFIG plus
// SYSTEM_FIELDS required for graph logic. Disabled fields are excluded
// from HTML entirely -- see config.get_graph_fields() + SYSTEM_FIELDS.
// ══════════════════════════════════════════════════════════════════════════

var originalLabels = {sj(original_labels_js_c)};
var originalSizes  = {sj(original_sizes_js_c)};
var nodeTypeMap    = {sj(node_type_js_c)};
var nodeMetaMap    = {sj(node_meta_js_c)};
var degreeMap      = {sj(rsme_degree_map_js)};
var adjacencyMap   = {sj(rsme_adjacency_js)};
var idNameLookup   = {sj(id_name_lookup_js_c)};

var companyList = {sj(company_list_js_c)};

// ══════════════════════════════════════════════════════════════════════════
// PAIR RELATIONSHIP MAP  (single source of truth for all edge data)
// Key: numerically sorted compressed IDs joined by "_"
//   e.g. IDs "3" and "17" -> "3_17"
// Resolve from any edge: [parseInt(e.fr), parseInt(e.to)].sort((a,b)=>a-b).join('_')
//
// vis.js injection fields:
//   fr  = from compressed ID (directional)
//   to  = to compressed ID   (directional)
//   ro  = rsme_only -> dashed line, no arrow
//   wb  = edge width (log1p binned from gta, 1.0-8.0)
//   ib  = is_both   -> arrows at both ends
//   id  = is_directed (false = rsme_only undirected)
//
// Filter flags:
//   ir=in_rsme  if=in_fitas  ia=in_aa  it=in_tt
//
// Side panel fields:
//   ps=priority_source  bu/su/cu/cou = buyer/supplier/customer/counterparty (cids)
//   tb2sc/tb2sa/tb2sp = tt buyer->supplier count/amt/pct
//   s2bc/s2ba/s2bp    = tt supplier->buyer count/amt/pct
//   ttc/tta=tt total count/amt  fta=fitas total amt  gta=grand total amt
//   f_{{prod}}_c/a = fitas product count/amt (sparse -- only present if non-zero)
//
// Data fields (export adjacency + side panel):
//   _rsme_ab/_rsme_ba/_aa_ab/_aa_ba
//   _fitas_ab_count/_fitas_ab_amt/_fitas_ba_count/_fitas_ba_amt
//   _tt_ab_count/_tt_ab_amt/_tt_ba_count/_tt_ba_amt/_tt_total_count/_tt_net_amt
// ══════════════════════════════════════════════════════════════════════════

var pairRelationshipMap = {sj(pair_rel_map)};

// Self-loop edges -- Payment combined (TT + FAST + GIRO union per UEN)
var selfLoopEdgesData = {sj(all_txn_selfloop_edges_js_c)};
// var selfLoopEdgesData = {sj(selfloop_edges_js_c)};   // legacy TT-only -- replaced by allTxnSelfLoopEdgesData

function _getPairRel(idA, idB) {{
    var key = [parseInt(idA), parseInt(idB)].sort(function(a,b){{return a-b;}}).join('_');
    return pairRelationshipMap[key] || null;
}}

// ══════════════════════════════════════════════════════════════════════════
// CONSOLIDATED TT (compressed string IDs)
// ══════════════════════════════════════════════════════════════════════════

var consolTTNodeSummary  = {sj(consol_tt_node_summary_js_c)};
var consolTTMetricRanges = {sj(consol_tt_metric_ranges)};
var consolTTNodeIds      = new Set({sj(consol_tt_node_ids_js)});
var consolTTOutAdj       = {sj(consol_tt_out_adj_js)};
var consolTTInAdj        = {sj(consol_tt_in_adj_js)};
var consolTTDegreeMap    = {sj(consol_tt_degree_js)};
var consolTTSelfLoopIds  = new Set({sj(consol_tt_self_loop_js)});

// ══════════════════════════════════════════════════════════════════════════
// FITAS (compressed string IDs)
// ══════════════════════════════════════════════════════════════════════════

var fitasNodeSummary  = {sj(fitas_node_summary_js_c)};
var fitasMetricRanges = {sj(fitas_metric_ranges)};
var fitasNodeIds      = new Set({sj(fitas_node_ids_js)});
var fitasOutAdj       = {sj(fitas_out_adj_js)};
var fitasInAdj        = {sj(fitas_in_adj_js)};
var fitasDegreeMap    = {sj(fitas_degree_js)};
var fitasSelfLoopIds  = new Set({sj(fitas_self_loop_js)});

// ══════════════════════════════════════════════════════════════════════════
// AA PAPER (compressed string IDs)
// ══════════════════════════════════════════════════════════════════════════

var aaPaperNodeIds     = new Set({sj(aa_paper_node_ids_js)});
var aaPaperOutAdj      = {sj(aa_paper_out_adj_js)};
var aaPaperInAdj       = {sj(aa_paper_in_adj_js)};
var aaPaperDegreeMap   = {sj(aa_paper_degree_js)};
var aaPaperSelfLoopIds = new Set({sj(aa_paper_self_loop_js)});

// ══════════════════════════════════════════════════════════════════════════
// FAST (compressed string IDs)
// ══════════════════════════════════════════════════════════════════════════

var fastNodeSummary  = {sj(fast_node_summary_js_c)};
var fastMetricRanges = {sj(fast_metric_ranges)};
var fastNodeIds      = new Set({sj(fast_node_ids_js)});
var fastOutAdj       = {sj(fast_out_adj_js)};
var fastInAdj        = {sj(fast_in_adj_js)};
var fastDegreeMap    = {sj(fast_degree_js)};
var fastSelfLoopIds  = new Set({sj(fast_self_loop_js)});

// ══════════════════════════════════════════════════════════════════════════
// GIRO (compressed string IDs)
// ══════════════════════════════════════════════════════════════════════════

var giroNodeSummary  = {sj(giro_node_summary_js_c)};
var giroMetricRanges = {sj(giro_metric_ranges)};
var giroNodeIds      = new Set({sj(giro_node_ids_js)});
var giroOutAdj       = {sj(giro_out_adj_js)};
var giroInAdj        = {sj(giro_in_adj_js)};
var giroDegreeMap    = {sj(giro_degree_js)};
var giroSelfLoopIds  = new Set({sj(giro_self_loop_js)});

// ══════════════════════════════════════════════════════════════════════════
// PAYMENT (TT + FAST + GIRO union)
// ══════════════════════════════════════════════════════════════════════════

var paymentNodeSummary       = {sj(payment_node_summary_js_c)};
var paymentMetricRanges      = {sj(payment_metric_ranges)};
var paymentNodeIds           = new Set({sj(payment_node_ids_js)});
var paymentOutAdj            = {sj(payment_out_adj_js)};
var paymentInAdj             = {sj(payment_in_adj_js)};
var paymentDegreeMap         = {sj(payment_degree_js)};
var paymentSelfLoopIds       = new Set({sj(payment_self_loop_js)});
var allTxnSelfLoopIds        = new Set({sj(all_txn_self_loop_js)});
var paymentDirectedEdgesData = {sj(payment_directed_edges_js_c)};
var paymentSelfLoopEdgesData = {sj(payment_selfloop_edges_js_c)};
var fitasSelfLoopEdgesData   = {sj(fitas_selfloop_edges_js_c)};
var allTxnSelfLoopEdgesData  = {sj(all_txn_selfloop_edges_js_c)};

// ══════════════════════════════════════════════════════════════════════════
// ALL TRANSACTIONS (FITAS + Payment) -- summary + ranges only
// ══════════════════════════════════════════════════════════════════════════

var allTxnNodeSummary  = {sj(all_txn_node_summary_js_c)};
var allTxnMetricRanges = {sj(all_txn_metric_ranges)};

// ══════════════════════════════════════════════════════════════════════════
// RSME (compressed string IDs)
// rsmeNodeIds built from rsme adjacency keys only -- not all nodes.
// ══════════════════════════════════════════════════════════════════════════

var rsmeNodeIds = new Set({sj(rsme_node_ids_js)});

// ══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// fieldConfig contains ONLY enabled=True fields from FIELD_CONFIG.
// AMT_FIELDS includes MFI and CIP amount columns for correct formatting.
// ══════════════════════════════════════════════════════════════════════════

var segmentColors   = {seg_colors_js};
var fieldConfig     = {field_cfg_js};
var colorTradeMB    = "{config.COLOR_TRADE_MB}";
var colorNonTradeMB = "{config.COLOR_NON_TRADE_MB}";
var colorNonMB      = "{config.COLOR_NON_MB}";
var colorMalaysian  = "{config.COLOR_MALAYSIAN}";

var AMT_FIELDS = new Set({amt_fields_js});

var ttLatestDate    = "{tt_latest_date}";
var fitasLatestDate = "{fitas_latest_date}";
var fastLatestDate  = "{fast_source.fg_latest_date or ''}";
var giroLatestDate  = "{giro_source.fg_latest_date or ''}";
var allTxnLatestDate = "{all_txn_latest_date}";

// ══════════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// selectedIds, currentNode always hold real UEN strings (external API)
// ══════════════════════════════════════════════════════════════════════════

var selectedIds  = [];
var currentNode  = null;
var historyStack = [];
var historyIndex = -1;

var LS_HOPS    = "nw_hops";
var LS_HISTORY = "nw_history";
var LS_LAST    = "nw_last_search";
var LS_ACC     = "nw_acc_states_v2";

var ACC_DEFAULT = {{
    overview          : true,
    datasources       : false,
    fitas_summary     : false,
    payment_summary   : false,
    all_txn_summary   : false,
    facilities        : false,
    creditstatus      : false,
    financials        : false,
    // *** updated | mfifin removed -- MFI now lives as a subsection of `financials`.
    // CIP keeps its own accordion.
    cipinfo           : false,
    network_rsme      : false,
    network_payment   : false,
    network_fitas     : false,
    network_aa_paper  : false,
}};

// ══════════════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ══════════════════════════════════════════════════════════════════════════

function getSize(id) {{
    return originalSizes[id] !== undefined ? originalSizes[id] : 10;
}}

function getTypeColor(ntype) {{
    if (ntype === "Maybank Trade Customer")     return colorTradeMB;
    if (ntype === "Maybank Non-Trade Customer") return colorNonTradeMB;
    return colorNonMB;
}}

function fmtVal(val) {{
    if (val === null || val === undefined) return "-";
    if (typeof val === "string") return val.trim() || "-";
    if (typeof val === "number") return val.toLocaleString(undefined, {{maximumFractionDigits: 0}});
    return String(val).trim() || "-";
}}

function fmtAmt(val) {{
    if (val === null || val === undefined) return "-";
    if (val < 0) return "-S$" + Math.abs(Math.round(val)).toLocaleString();
    return "S$" + Math.round(val).toLocaleString();
}}

function fmtPct(val) {{
    if (val === null || val === undefined) return "-";
    return val.toFixed(1) + "%";
}}

function escXml(s) {{
    if (!s) return "";
    return String(s)
        .replace(/&/g,  "&amp;")
        .replace(/</g,  "&lt;")
        .replace(/>/g,  "&gt;")
        .replace(/"/g,  "&quot;")
        .replace(/'/g,  "&#39;");
}}

// ══════════════════════════════════════════════════════════════════════════
// LOCALSTORAGE HELPERS
// ══════════════════════════════════════════════════════════════════════════

function getAccStates() {{
    try {{
        var s = localStorage.getItem(LS_ACC);
        if (s) return Object.assign({{}}, ACC_DEFAULT, JSON.parse(s));
    }} catch(e) {{}}
    return Object.assign({{}}, ACC_DEFAULT);
}}

function setAccState(id, isOpen) {{
    var s = getAccStates();
    s[id] = isOpen;
    try {{ localStorage.setItem(LS_ACC, JSON.stringify(s)); }} catch(e) {{}}
}}

function saveLastSearch(uen, hops) {{
    try {{ localStorage.setItem(LS_LAST, JSON.stringify({{uen: uen, hops: hops}})); }} catch(e) {{}}
}}

// ══════════════════════════════════════════════════════════════════════════
// CANVAS RELOCATION
// ══════════════════════════════════════════════════════════════════════════

(function() {{
    var gc  = document.getElementById("graph-card");
    var vis = document.getElementById("mynetwork");
    if (gc && vis) {{
        vis.style.cssText = "width:100%;height:100%;border-radius:0;background:#FAFAFA;border:none;";
        gc.appendChild(vis);
    }}
}})();
"""
