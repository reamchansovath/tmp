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
import gzip
import base64
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
    - selfLoopEdgesData   : All-Txn (Payment combined + FITAS) self-transfers,
                            injected separately. Per-source FITAS / Payment / TT
                            lookup maps are also emitted for the side panel.
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
    # *** fix | unique-counterparty count: |out_adj ∪ in_adj|, NOT len(out)+len(in)
    # which would double-count bidirectional pairs. Currently `paymentDegreeMap`
    # is dead JS payload (declared/hydrated, never read) but kept correct so
    # any future feature reading it gets right values.
    _payment_degree = {
        nid: len(set(_payment_out_adj.get(nid, [])) | set(_payment_in_adj.get(nid, [])))
        for nid in _payment_active
    }
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

    # min_w lifted from 1.0 to 2.5 so zero-/low-traffic pairs are still
    # visible. Render width = _bin_widths floor or e.wb || min_w fallback
    # in js_network.py -- keep both in sync.
    def _bin_widths(amounts, min_w=2.5, max_w=8.0):
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

            # Null-strip: only emit truthy/non-zero/non-None values. JS
            # consumers already use !!e.X / e.X || 0 / e.X > 0 patterns, so
            # missing keys read identically to false/0. Saves ~50-70% of
            # per-pair JSON for sparse pairs (e.g. RSME-only with no payment
            # or FITAS activity).
            entry = {'fr': from_id, 'to': to_id, 'wb': 1.0}

            # Source-presence and topology flags -- emit only when True
            if rsme_only:                                entry['ro'] = True
            if is_both:                                  entry['ib'] = True
            if bool(row.get('is_directed', True)):       entry['id'] = True
            if in_rsme:                                  entry['ir'] = True
            if in_fitas:                                 entry['if'] = True
            if in_aa:                                    entry['ia'] = True
            if in_tt:                                    entry['it'] = True
            if bool(row.get('in_payment', False)):       entry['if_pay'] = True
            if bool(row.get('in_fast',    False)):       entry['if_fa']  = True
            if bool(row.get('in_giro',    False)):       entry['if_gi']  = True

            # UEN refs / priority source -- emit only when not None
            _ps  = _safe_val(row.get('priority_source'))
            if _ps is not None: entry['ps'] = _ps
            for _src_key, _ent_key in (
                ('buyer_uen', 'bu'), ('supplier_uen', 'su'),
                ('customer_uen', 'cu'), ('counterparty_uen', 'cou'),
            ):
                _v = _compress_uen_field(row.get(_src_key))
                if _v is not None:
                    entry[_ent_key] = _v

            # Numeric stats helper -- emit only when non-None and non-zero
            def _put_nz(k, v):
                if v is not None and v != 0:
                    entry[k] = v

            # TT direction stats from relationship_df
            _put_nz('tb2sc', _safe_val(row.get('tt_buyer_to_supplier_count')))
            _put_nz('tb2sa', _safe_val(row.get('tt_buyer_to_supplier_amt')))
            _put_nz('tb2sp', _safe_val(row.get('tt_buyer_to_supplier_amt_pct')))
            _put_nz('s2bc',  _safe_val(row.get('tt_supplier_to_buyer_count')))
            _put_nz('s2ba',  _safe_val(row.get('tt_supplier_to_buyer_amt')))
            _put_nz('s2bp',  _safe_val(row.get('tt_supplier_to_buyer_amt_pct')))
            _put_nz('ttc',   _safe_val(row.get('tt_total_count')))
            _put_nz('tta',   _safe_val(row.get('tt_total_amt')))
            _put_nz('fta',   _safe_val(row.get('fitas_total_amt')))
            # gta is also read by the width-binning loop below via .get('gta',0)
            _put_nz('gta',   _safe_val(row.get('all_txn_total_amt') or row.get('grand_total_amt')))

            # Direction flags from undir_edge -- emit only when True
            if undir_edge.get('_rsme_ab'): entry['_rsme_ab'] = True
            if undir_edge.get('_rsme_ba'): entry['_rsme_ba'] = True
            if undir_edge.get('_aa_ab'):   entry['_aa_ab']   = True
            if undir_edge.get('_aa_ba'):   entry['_aa_ba']   = True

            # FITAS undirected counts/amts -- emit only when non-zero
            _put_nz('_fitas_ab_count', undir_edge.get('_fitas_ab_count') or 0)
            _put_nz('_fitas_ab_amt',   undir_edge.get('_fitas_ab_amt')   or 0)
            _put_nz('_fitas_ba_count', undir_edge.get('_fitas_ba_count') or 0)
            _put_nz('_fitas_ba_amt',   undir_edge.get('_fitas_ba_amt')   or 0)

            # Per-source aggregates (tt, fast, giro, payment, all_txn).
            # Most pairs are single-source, so 4 of 5 prefixes' fields are
            # all-zero and now omitted entirely.
            for _prefix in ('tt', 'fast', 'giro', 'payment', 'all_txn'):
                _put_nz(f'_{_prefix}_ab_count',    _safe_val(row.get(f'{_prefix}_ab_count')))
                _put_nz(f'_{_prefix}_ab_amt',      _safe_val(row.get(f'{_prefix}_ab_amt')))
                _put_nz(f'_{_prefix}_ba_count',    _safe_val(row.get(f'{_prefix}_ba_count')))
                _put_nz(f'_{_prefix}_ba_amt',      _safe_val(row.get(f'{_prefix}_ba_amt')))
                _put_nz(f'_{_prefix}_total_count', _safe_val(row.get(f'{_prefix}_total_count')))
                _put_nz(f'_{_prefix}_total_amt',   _safe_val(row.get(f'{_prefix}_total_amt')))
                _put_nz(f'_{_prefix}_net_amt',     _safe_val(row.get(f'{_prefix}_net_amt')))
                _put_nz(f'{_prefix}_b2sc',         _safe_val(row.get(f'{_prefix}_buyer_to_supplier_count')))
                _put_nz(f'{_prefix}_b2sa',         _safe_val(row.get(f'{_prefix}_buyer_to_supplier_amt')))
                _put_nz(f'{_prefix}_b2sp',         _safe_val(row.get(f'{_prefix}_buyer_to_supplier_amt_pct')))
                _put_nz(f'{_prefix}_s2bc',         _safe_val(row.get(f'{_prefix}_supplier_to_buyer_count')))
                _put_nz(f'{_prefix}_s2ba',         _safe_val(row.get(f'{_prefix}_supplier_to_buyer_amt')))
                _put_nz(f'{_prefix}_s2bp',         _safe_val(row.get(f'{_prefix}_supplier_to_buyer_amt_pct')))

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
            # gta may be absent on null-stripped entries (zero grand total) -- default to 0
            gta_vals = [_safe_float(pair_rel_map[k].get('gta', 0)) for k in _pair_keys_ordered]
            widths   = _bin_widths(gta_vals)
            for i, k in enumerate(_pair_keys_ordered):
                pair_rel_map[k]['wb'] = widths[i]

        # Diagnostic counts: ro/ib are absent on null-stripped entries -- use .get()
        rsme_only_count = sum(1 for e in pair_rel_map.values() if e.get('ro'))
        both_count      = sum(1 for e in pair_rel_map.values() if e.get('ib'))
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

    # ── Step 6.5: Column-orient + dictionary-encode nodeMetaMap ───────────
    # Convert {compId: {field: val}} into {ids:[...], fields:{field:{dict,idx}|{vals}}}.
    # Each field's unique values become a small lookup table; rows store
    # 1-byte indices into it. Repeated values like "SG"/"Y"/"N" / common MSIC
    # codes appear once per dict instead of once per row. Gzip's 32KB window
    # cannot reach across a 97k-node map, so we hoist the repetition into
    # the format itself. JS rebuilds the row-oriented map at hydrate time
    # so existing consumers (`nodeMetaMap[id].FIELD`) keep working.
    def _column_encode_meta(meta_map, dict_threshold=0.5, sparse_null_threshold=0.7):
        """
        Three encodings per field, picked by data shape:
          - sparse {dict, rows, sIdx} : when null fraction > sparse_null_threshold.
                dict has only non-null uniques. rows lists row-indices that have
                a non-null value. sIdx[k] is the dict index for rows[k].
                Missing rows decode to undefined (== null for `meta.X != null`).
          - dense  {dict, idx}        : when uniques < dict_threshold * n.
                idx[i] = dict index for row i (null may be in dict).
          - raw    {vals}             : fallback for high-cardinality cols.
        """
        if not meta_map:
            return {'ids': [], 'fields': {}}
        ids = list(meta_map.keys())
        n   = len(ids)
        field_set = set()
        for row in meta_map.values():
            field_set.update(row.keys())
        fields_out = {}
        for field in sorted(field_set):
            col = [meta_map[uen].get(field) for uen in ids]
            null_count = sum(1 for v in col if v is None)
            null_frac  = null_count / n if n else 0

            # Sparse path -- column is mostly null
            if null_frac > sparse_null_threshold:
                seen = {}
                try:
                    rows  = []
                    sIdx  = []
                    for i, v in enumerate(col):
                        if v is None:
                            continue
                        if v not in seen:
                            seen[v] = len(seen)
                        rows.append(i)
                        sIdx.append(seen[v])
                except TypeError:
                    fields_out[field] = {'vals': col}
                    continue
                fields_out[field] = {
                    'dict': list(seen.keys()),
                    'rows': rows,
                    'sIdx': sIdx,
                }
                continue

            # Dense / raw paths
            seen = {}
            try:
                for v in col:
                    if v not in seen:
                        seen[v] = len(seen)
            except TypeError:
                fields_out[field] = {'vals': col}
                continue
            unique = list(seen.keys())
            if len(unique) < dict_threshold * n:
                fields_out[field] = {
                    'dict': unique,
                    'idx':  [seen[v] for v in col],
                }
            else:
                fields_out[field] = {'vals': col}
        return {'ids': ids, 'fields': fields_out}

    node_meta_compact = _column_encode_meta(node_meta_js_c)
    _row_size = len(sj(node_meta_js_c))
    _col_size = len(sj(node_meta_compact))
    _sparse_fields = sum(1 for f in node_meta_compact['fields'].values() if 'sIdx' in f)
    _dense_fields  = sum(1 for f in node_meta_compact['fields'].values()
                         if 'idx' in f and 'sIdx' not in f)
    _vals_fields   = sum(1 for f in node_meta_compact['fields'].values() if 'vals' in f)
    print(f"  nodeMetaMap column-encode: {_row_size/1024:.0f}KB -> {_col_size/1024:.0f}KB "
          f"({(1 - _col_size/max(_row_size,1))*100:.1f}% reduction; "
          f"{_dense_fields} dense, {_sparse_fields} sparse, {_vals_fields} raw)")

    # ── Step 7: Bundle O(N) payloads into one gzipped blob ────────────────
    # All per-node / per-edge data goes into a single gzip stream. The
    # browser decompresses once at page load via DecompressionStream API
    # (Chrome 80+, Firefox 113+, Safari 16.4+, Edge 80+). Single-stream
    # gzip exploits cross-payload redundancy (repeated keys across maps)
    # for better compression than independent streams.
    _gz_payload = {
        # _UtoI is derived from _ItoU at JS bootstrap (saves ~50% of UEN map).
        '_ItoU'                   : id_to_uen,
        'originalLabels'          : original_labels_js_c,
        'originalSizes'           : original_sizes_js_c,
        'nodeTypeMap'             : node_type_js_c,
        'nodeMetaMapCompact'      : node_meta_compact,
        'degreeMap'               : rsme_degree_map_js,
        'adjacencyMap'            : rsme_adjacency_js,
        'idNameLookup'            : id_name_lookup_js_c,
        'companyList'             : company_list_js_c,
        'pairRelationshipMap'     : pair_rel_map,
        'consolTTNodeSummary'     : consol_tt_node_summary_js_c,
        'consolTTNodeIds'         : consol_tt_node_ids_js,
        'consolTTOutAdj'          : consol_tt_out_adj_js,
        'consolTTInAdj'           : consol_tt_in_adj_js,
        'consolTTDegreeMap'       : consol_tt_degree_js,
        'consolTTSelfLoopIds'     : consol_tt_self_loop_js,
        'fitasNodeSummary'        : fitas_node_summary_js_c,
        'fitasNodeIds'            : fitas_node_ids_js,
        'fitasOutAdj'             : fitas_out_adj_js,
        'fitasInAdj'              : fitas_in_adj_js,
        'fitasDegreeMap'          : fitas_degree_js,
        'fitasSelfLoopIds'        : fitas_self_loop_js,
        'aaPaperNodeIds'          : aa_paper_node_ids_js,
        'aaPaperOutAdj'           : aa_paper_out_adj_js,
        'aaPaperInAdj'            : aa_paper_in_adj_js,
        'aaPaperDegreeMap'        : aa_paper_degree_js,
        'aaPaperSelfLoopIds'      : aa_paper_self_loop_js,
        'fastNodeSummary'         : fast_node_summary_js_c,
        'fastNodeIds'             : fast_node_ids_js,
        'fastOutAdj'              : fast_out_adj_js,
        'fastInAdj'               : fast_in_adj_js,
        'fastDegreeMap'           : fast_degree_js,
        'fastSelfLoopIds'         : fast_self_loop_js,
        'giroNodeSummary'         : giro_node_summary_js_c,
        'giroNodeIds'             : giro_node_ids_js,
        'giroOutAdj'              : giro_out_adj_js,
        'giroInAdj'               : giro_in_adj_js,
        'giroDegreeMap'           : giro_degree_js,
        'giroSelfLoopIds'         : giro_self_loop_js,
        'paymentNodeSummary'      : payment_node_summary_js_c,
        'paymentNodeIds'          : payment_node_ids_js,
        'paymentOutAdj'           : payment_out_adj_js,
        'paymentInAdj'            : payment_in_adj_js,
        'paymentDegreeMap'        : payment_degree_js,
        'paymentSelfLoopIds'      : payment_self_loop_js,
        'allTxnSelfLoopIds'       : all_txn_self_loop_js,
        'paymentDirectedEdgesData': payment_directed_edges_js_c,
        'paymentSelfLoopEdgesData': payment_selfloop_edges_js_c,
        'fitasSelfLoopEdgesData'  : fitas_selfloop_edges_js_c,
        'allTxnSelfLoopEdgesData' : all_txn_selfloop_edges_js_c,
        'allTxnNodeSummary'       : all_txn_node_summary_js_c,
        'rsmeNodeIds'             : rsme_node_ids_js,
    }
    _gz_json  = sj(_gz_payload)
    _gz_bytes = gzip.compress(_gz_json.encode('utf-8'), compresslevel=6)
    _gz_b64   = base64.b64encode(_gz_bytes).decode('ascii')
    _gz_pct   = (1 - len(_gz_b64) / max(len(_gz_json), 1)) * 100
    print(f"  gzipped payload bundle: {len(_gz_json)/1024/1024:.2f}MB JSON -> "
          f"{len(_gz_bytes)/1024/1024:.2f}MB gz -> "
          f"{len(_gz_b64)/1024/1024:.2f}MB base64 "
          f"({_gz_pct:.1f}% reduction; {len(_gz_payload)} payloads)")

    # ── Generate JavaScript ────────────────────────────────────────────────

    return f"""
// ══════════════════════════════════════════════════════════════════════════
// COMPRESSED PAYLOAD BUNDLE
// All O(N) data structures (per-node maps, adjacency maps, edge lists, etc.)
// are bundled into a single gzip stream and base64-encoded for embedding
// inside this <script>. The browser decompresses once at page load via the
// native DecompressionStream API (Chrome 80+, Firefox 113+, Safari 16.4+,
// Edge 80+). This typically reduces the HTML 70-85% vs raw JSON embedding.
// Empty placeholders for each payload are declared below so existing code
// that reads them continues to compile; the actual data is hydrated inside
// the __bootstrapReady promise before any UI init runs.
// ══════════════════════════════════════════════════════════════════════════

var __GZ_BLOB = "{_gz_b64}";

async function _decompressJSON(b64) {{
    if (typeof DecompressionStream === 'undefined') {{
        throw new Error(
            "DecompressionStream API not supported. " +
            "Please use Chrome 80+, Edge 80+, Firefox 113+, or Safari 16.4+."
        );
    }}
    var bytes = Uint8Array.from(atob(b64), function(c) {{ return c.charCodeAt(0); }});
    var stream = new Response(
        new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))
    );
    return JSON.parse(await stream.text());
}}

// ── Empty placeholders for compressed payloads (hydrated below) ──────────
// Plain dicts/arrays:
var _UtoI = null, _ItoU = null;
var originalLabels = null, originalSizes = null;
var nodeTypeMap = null, nodeMetaMap = null;
var degreeMap = null, adjacencyMap = null;
var idNameLookup = null;
// companyList default is an empty array (not null) so the search box
// gracefully returns "no matches" if the user types before __bootstrapReady
// resolves. The keydown-Enter handler at js_search.py:144 reads
// `companyList.length` and `.find(...)` without awaiting bootstrap, which
// would throw on a null reference.
var companyList = [];
var pairRelationshipMap = null;
var consolTTNodeSummary = null, consolTTOutAdj = null, consolTTInAdj = null, consolTTDegreeMap = null;
var fitasNodeSummary = null, fitasOutAdj = null, fitasInAdj = null, fitasDegreeMap = null;
var aaPaperOutAdj = null, aaPaperInAdj = null, aaPaperDegreeMap = null;
var fastNodeSummary = null, fastOutAdj = null, fastInAdj = null, fastDegreeMap = null;
var giroNodeSummary = null, giroOutAdj = null, giroInAdj = null, giroDegreeMap = null;
var paymentNodeSummary = null, paymentOutAdj = null, paymentInAdj = null, paymentDegreeMap = null;
var paymentDirectedEdgesData = null, paymentSelfLoopEdgesData = null;
var fitasSelfLoopEdgesData = null, allTxnSelfLoopEdgesData = null;
var selfLoopEdgesData = null;
var allTxnNodeSummary = null;

// Sets (wrapped from arrays during hydration):
var consolTTNodeIds = null, consolTTSelfLoopIds = null;
var fitasNodeIds = null, fitasSelfLoopIds = null;
var aaPaperNodeIds = null, aaPaperSelfLoopIds = null;
var fastNodeIds = null, fastSelfLoopIds = null;
var giroNodeIds = null, giroSelfLoopIds = null;
var paymentNodeIds = null, paymentSelfLoopIds = null, allTxnSelfLoopIds = null;
var rsmeNodeIds = null;

// Bootstrap promise -- everything that depends on the big payloads must
// `await __bootstrapReady` before reading them.
var __bootstrapReady = (async function() {{
    var _t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    var data = await _decompressJSON(__GZ_BLOB);

    // Plain assignments
    _ItoU                    = data._ItoU;
    // Derive _UtoI from _ItoU instead of shipping both. _ItoU has ID-string
    // keys ("1","2",...) and UEN-string values; we invert into UEN -> ID.
    // Values stay as strings to match the build-time _UtoI shape (vis.js
    // uses string node IDs in this project).
    _UtoI = {{}};
    for (var _idK in _ItoU) {{ _UtoI[_ItoU[_idK]] = _idK; }}
    originalLabels           = data.originalLabels;
    originalSizes            = data.originalSizes;
    nodeTypeMap              = data.nodeTypeMap;
    // Reconstruct row-oriented nodeMetaMap from column-oriented payload.
    // Build-time encoder lives in js_core.py:_column_encode_meta. Three field
    // shapes:
    //   sparse: dict + rows + sIdx -- only rows listed in `rows` have a value;
    //                                 missing rows leave the field unset
    //   dense:  dict + idx         -- idx[i] indexes into dict for every row
    //   raw:    vals               -- vals[i] is the value for row i
    nodeMetaMap = (function(c) {{
        if (!c || !c.ids) return {{}};
        var ids = c.ids, fields = c.fields;
        var fieldNames = Object.keys(fields);
        var out = {{}};
        // Pre-allocate empty row objects so sparse decoding can poke fields in
        for (var i = 0; i < ids.length; i++) out[ids[i]] = {{}};
        for (var j = 0; j < fieldNames.length; j++) {{
            var fname = fieldNames[j];
            var f     = fields[fname];
            if (f.sIdx !== undefined) {{
                // Sparse: only rows in f.rows get the field set
                for (var k = 0; k < f.rows.length; k++) {{
                    out[ids[f.rows[k]]][fname] = f.dict[f.sIdx[k]];
                }}
            }} else if (f.idx !== undefined) {{
                // Dense dict-encoded
                for (var i2 = 0; i2 < ids.length; i2++) {{
                    out[ids[i2]][fname] = f.dict[f.idx[i2]];
                }}
            }} else {{
                // Raw vals
                for (var i3 = 0; i3 < ids.length; i3++) {{
                    out[ids[i3]][fname] = f.vals[i3];
                }}
            }}
        }}
        return out;
    }})(data.nodeMetaMapCompact);
    degreeMap                = data.degreeMap;
    adjacencyMap             = data.adjacencyMap;
    idNameLookup             = data.idNameLookup;
    companyList              = data.companyList;
    pairRelationshipMap      = data.pairRelationshipMap;
    consolTTNodeSummary      = data.consolTTNodeSummary;
    consolTTOutAdj           = data.consolTTOutAdj;
    consolTTInAdj            = data.consolTTInAdj;
    consolTTDegreeMap        = data.consolTTDegreeMap;
    fitasNodeSummary         = data.fitasNodeSummary;
    fitasOutAdj              = data.fitasOutAdj;
    fitasInAdj               = data.fitasInAdj;
    fitasDegreeMap           = data.fitasDegreeMap;
    aaPaperOutAdj            = data.aaPaperOutAdj;
    aaPaperInAdj             = data.aaPaperInAdj;
    aaPaperDegreeMap         = data.aaPaperDegreeMap;
    fastNodeSummary          = data.fastNodeSummary;
    fastOutAdj               = data.fastOutAdj;
    fastInAdj                = data.fastInAdj;
    fastDegreeMap            = data.fastDegreeMap;
    giroNodeSummary          = data.giroNodeSummary;
    giroOutAdj               = data.giroOutAdj;
    giroInAdj                = data.giroInAdj;
    giroDegreeMap            = data.giroDegreeMap;
    paymentNodeSummary       = data.paymentNodeSummary;
    paymentOutAdj            = data.paymentOutAdj;
    paymentInAdj             = data.paymentInAdj;
    paymentDegreeMap         = data.paymentDegreeMap;
    paymentDirectedEdgesData = data.paymentDirectedEdgesData;
    paymentSelfLoopEdgesData = data.paymentSelfLoopEdgesData;
    fitasSelfLoopEdgesData   = data.fitasSelfLoopEdgesData;
    allTxnSelfLoopEdgesData  = data.allTxnSelfLoopEdgesData;
    selfLoopEdgesData        = data.allTxnSelfLoopEdgesData;
    allTxnNodeSummary        = data.allTxnNodeSummary;

    // Wrap arrays as Sets (Sets are not JSON-serialisable, so they go through
    // the wire as arrays and get reconstructed here).
    consolTTNodeIds          = new Set(data.consolTTNodeIds);
    consolTTSelfLoopIds      = new Set(data.consolTTSelfLoopIds);
    fitasNodeIds             = new Set(data.fitasNodeIds);
    fitasSelfLoopIds         = new Set(data.fitasSelfLoopIds);
    aaPaperNodeIds           = new Set(data.aaPaperNodeIds);
    aaPaperSelfLoopIds       = new Set(data.aaPaperSelfLoopIds);
    fastNodeIds              = new Set(data.fastNodeIds);
    fastSelfLoopIds          = new Set(data.fastSelfLoopIds);
    giroNodeIds              = new Set(data.giroNodeIds);
    giroSelfLoopIds          = new Set(data.giroSelfLoopIds);
    paymentNodeIds           = new Set(data.paymentNodeIds);
    paymentSelfLoopIds       = new Set(data.paymentSelfLoopIds);
    allTxnSelfLoopIds        = new Set(data.allTxnSelfLoopIds);
    rsmeNodeIds              = new Set(data.rsmeNodeIds);

    // Free the base64 string from memory now that everything is hydrated
    __GZ_BLOB = null;

    var _t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    console.log("Decompressed " + Object.keys(data).length +
                " payloads in " + (_t1 - _t0).toFixed(0) + "ms");
}})();

// ══════════════════════════════════════════════════════════════════════════
// UEN COMPRESSION HELPERS  (operate on _UtoI/_ItoU after hydration)
// _UtoI : UEN string -> string ID  e.g. "202012345C" -> "1"
// _ItoU : string ID  -> UEN string e.g. "1" -> "202012345C"
// _e(uid) : encode UEN string to string ID -- call once at renderSearch entry
// _d(id)  : decode string ID to UEN string -- call only for display/external
// ══════════════════════════════════════════════════════════════════════════

function _e(uid) {{
    if (_UtoI === null) {{
        console.warn("_e(): called before bootstrap completed");
        return uid;
    }}
    var id = _UtoI[uid];
    if (id === undefined) {{
        console.warn("_e(): UEN not in compression map:", uid);
        return uid;
    }}
    return id;
}}

function _d(id) {{
    if (_ItoU === null) {{
        console.warn("_d(): called before bootstrap completed");
        return String(id);
    }}
    var uid = _ItoU[String(id)];
    if (uid === undefined) {{
        console.warn("_d(): ID not in compression map:", id);
        return String(id);
    }}
    return uid;
}}

// pairRelationshipMap accessor (waits implicitly via callers awaiting __bootstrapReady)
function _getPairRel(idA, idB) {{
    var key = [parseInt(idA), parseInt(idB)].sort(function(a,b){{return a-b;}}).join('_');
    return pairRelationshipMap ? (pairRelationshipMap[key] || null) : null;
}}

// ══════════════════════════════════════════════════════════════════════════
// METRIC RANGES (small, kept as raw JSON -- no compression benefit)
// ══════════════════════════════════════════════════════════════════════════

var consolTTMetricRanges = {sj(consol_tt_metric_ranges)};
var fitasMetricRanges    = {sj(fitas_metric_ranges)};
var fastMetricRanges     = {sj(fast_metric_ranges)};
var giroMetricRanges     = {sj(giro_metric_ranges)};
var paymentMetricRanges  = {sj(payment_metric_ranges)};
var allTxnMetricRanges   = {sj(all_txn_metric_ranges)};

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
