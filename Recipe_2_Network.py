# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Local twin: when DATAIKU_ENV=local, register mock_dataiku as the dataiku
# module so every later `import dataiku` (across all cells) resolves to the
# mock. In Dataiku, DATAIKU_ENV is not set so this block is a no-op.

import os, sys
if os.getenv('DATAIKU_ENV') == 'local':
    import mock_dataiku
    sys.modules['dataiku'] = mock_dataiku


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# ────────────────────────────────────────────────────────────────────────────
# RECIPE 2: Network Graph HTML Generation
# Loads pickle cache and generates interactive HTML visualization.
# NO PyVis, NO neighbor cache -- in-browser BFS from adjacency maps.
# Edge architecture: undirected (RSME/AA/FITAS) + directed (TT) + selfloop
# Generates 4 HTML files: full, full_minified, filtered, filtered_minified.
# ────────────────────────────────────────────────────────────────────────────

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 1: Imports

import pandas as pd
import dataiku  # type: ignore[import-not-found]
import pickle
import base64
from network_graph.config          import NetworkGraphConfig as cfg
from network_graph.viz.config      import VizConfig
from network_graph.viz.builder     import HTMLBuilder
from network_graph.viz.js_payloads import JSPayloadBuilder
from network_graph.exporters       import DatasetExporter

viz_config = VizConfig()

print("Imports loaded")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 2: Load pickle cache

print("\n" + "="*60)
print("LOADING PICKLE CACHE")
print("="*60)

pipeline_folder = dataiku.Folder(cfg.FOLDER_PIPELINE)

with pipeline_folder.get_download_stream('network_cache.pkl') as r:
    cache = pickle.load(r)

_rsme_adjacency          = cache['rsme_adjacency']
_rsme_degree_map         = cache['rsme_degree_map']
_original_sizes_js       = cache['original_sizes_js']
_enriched_nodes          = cache['enriched_nodes']
rsme_source              = cache['rsme_source']
consol_tt_source         = cache['consol_tt_source']
fitas_source             = cache['fitas_source']
aa_paper_source          = cache['aa_paper_source']
_undirected_edges_df     = cache['undirected_edges_df']
_selfloop_edges_df       = cache['selfloop_edges_df']
_tt_summary              = cache['tt_summary']
_fitas_summary           = cache['fitas_summary']
consol_tt_metric_ranges  = cache['consol_tt_metric_ranges']
fitas_metric_ranges      = cache['fitas_metric_ranges']
_directed_edges_df_full  = cache['directed_edges_df']
tt_edge_min_amt_cached   = cache.get('tt_edge_min_amt', None)

# ── Pre-filtered selfloops -- same values as Recipe 1, no float gap ───────
if 'selfloop_edges_df_filtered' not in cache:
    raise KeyError(
        "selfloop_edges_df_filtered not found in pickle. "
        "Re-run Recipe 1 with the updated Cell 14 to generate it."
    )
_selfloop_edges_df_filtered = cache['selfloop_edges_df_filtered']

# ── Filtered directed edges ───────────────────────────────────────────────
if 'directed_edges_df_filtered' not in cache:
    raise KeyError(
        "directed_edges_df_filtered not found in pickle. "
        "Re-run Recipe 1 with the updated Cell 10 to generate the filtered edge set."
    )
_directed_edges_df_filtered = cache['directed_edges_df_filtered']

# *** updated | load relationship_df from pickle | built by RelationshipBuilder in Recipe 1
# Not used for vis.js rendering in Recipe 2 (edge architecture unchanged here)
# but loaded so diagnostic cells can reference it without re-running Recipe 1.
if 'relationship_df' not in cache:
    raise KeyError(
        "relationship_df not found in pickle. "
        "Re-run Recipe 1 Cell 10b to generate the buyer-supplier relationship table."
    )
_relationship_df = cache['relationship_df']

fast_source                       = cache['fast_source']
giro_source                       = cache['giro_source']
_fast_summary                     = cache['fast_summary']
_fast_summary_filtered            = cache['fast_summary_filtered']
_giro_summary                     = cache['giro_summary']
_giro_summary_filtered            = cache['giro_summary_filtered']
_payment_summary                  = cache['payment_summary']
_payment_summary_filtered         = cache['payment_summary_filtered']
_all_txn_summary                  = cache['all_txn_summary']
_all_txn_summary_filtered         = cache['all_txn_summary_filtered']
_tt_summary_filtered              = cache['tt_summary_filtered']
_fitas_summary_filtered           = cache['fitas_summary_filtered']
fast_metric_ranges                = cache['fast_metric_ranges']
giro_metric_ranges                = cache['giro_metric_ranges']
payment_metric_ranges             = cache['payment_metric_ranges']
all_txn_metric_ranges             = cache['all_txn_metric_ranges']
_payment_directed_edges_df_full     = cache['payment_directed_edges_df_full']
_payment_directed_edges_df_filtered = cache['payment_directed_edges_df_filtered']
_all_txn_selfloop_edges_df_full     = cache['all_txn_selfloop_edges_df_full']
_all_txn_selfloop_edges_df_filtered = cache['all_txn_selfloop_edges_df_filtered']
_payment_selfloop_edges_df_full     = cache.get('payment_selfloop_edges_df_full')
_payment_selfloop_edges_df_filtered = cache.get('payment_selfloop_edges_df_filtered')
_fitas_selfloop_edges_df_full       = cache.get('fitas_selfloop_edges_df_full')
_fitas_selfloop_edges_df_filtered   = cache.get('fitas_selfloop_edges_df_filtered')
_fast_edges_filtered              = cache.get('fast_edges_filtered')
_giro_edges_filtered              = cache.get('giro_edges_filtered')
_all_txn_latest_date              = cache.get('all_txn_latest_date', '')
threshold_txn_sgd_cached          = cache.get('threshold_txn_sgd', cache.get('tt_edge_min_amt'))

print(f"  FAST edges:                    {len(fast_source.directed_edges_df):,}")
print(f"  GIRO edges:                    {len(giro_source.directed_edges_df):,}")
print(f"  Payment edges (filtered):      {len(_payment_directed_edges_df_filtered):,}")
print(f"  All-Txn self-loops (filtered): {len(_all_txn_selfloop_edges_df_filtered):,}")

# ── Store original TT adjacency maps for restoration between modes ────────
# _build_mode_data patches consol_tt_source in-place -- must restore
# before building the next mode so full and filtered are fully isolated.
_tt_out_adj_original = {k: list(v) for k, v in consol_tt_source.out_adj.items()}
_tt_in_adj_original  = {k: list(v) for k, v in consol_tt_source.in_adj.items()}
_fast_out_adj_original = {k: list(v) for k, v in fast_source.out_adj.items()}
_fast_in_adj_original  = {k: list(v) for k, v in fast_source.in_adj.items()}
_giro_out_adj_original = {k: list(v) for k, v in giro_source.out_adj.items()}
_giro_in_adj_original  = {k: list(v) for k, v in giro_source.in_adj.items()}

print(f"✓ Cache loaded:")
print(f"  Enriched nodes:                {len(_enriched_nodes):,}")
print(f"  RSME adjacency:                {len(_rsme_adjacency):,} nodes")
print(f"  Original sizes:                {len(_original_sizes_js):,} nodes")
print(f"  Undirected edges:              {len(_undirected_edges_df):,}")
print(f"  Directed edges (full):         {len(_directed_edges_df_full):,}")
print(f"  Directed edges (filtered):     {len(_directed_edges_df_filtered):,}")
print(f"  TT self-loops (full):          {len(_selfloop_edges_df):,}")
print(f"  TT self-loops (filtered):      {len(_selfloop_edges_df_filtered):,}")
print(f"  Relationship pairs:            {len(_relationship_df):,}")
print(f"  TT edge filter threshold:      S${tt_edge_min_amt_cached:,}  (set in Recipe 1)")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 3: Build per-mode data function
# FIX 1: in filtered mode, selfloop_edges_df uses pre-filtered version from
#         pickle -- avoids float rounding gap vs Excel report.
# FIX 2: in filtered mode, consol_tt_source.out_adj and in_adj rebuilt from
#         directed_edges_df_filtered so BFS only traverses edges that exist
#         in directed_edges_js -- prevents floating 2-hop nodes.
# FIX 3: in filtered mode, FITAS self-loop nodes added to still_connected
#         so nodes whose only remaining connection is a FITAS self-loop are
#         not orphaned -- consistent with Excel which keeps them via non_tt_mask.

print("\n" + "="*60)
print("DEFINING MODE BUILDER")
print("="*60)

def _build_mode_data(output_mode):
    enriched_nodes      = _enriched_nodes.drop_duplicates(subset='UEN', keep='first').copy()
    undirected_edges_df = _undirected_edges_df.copy()
    original_sizes_js   = dict(_original_sizes_js)
    rsme_adjacency      = {k: list(v) for k, v in _rsme_adjacency.items()}

    # ── Select directed edges and selfloops for this mode ─────────────────
    if output_mode == 'filtered':
        directed_edges_df = _directed_edges_df_filtered.copy()
        selfloop_edges_df = _selfloop_edges_df_filtered.copy()
        payment_directed_edges_df = _payment_directed_edges_df_filtered.copy()
        all_txn_selfloop_edges_df = _all_txn_selfloop_edges_df_filtered.copy()
        payment_selfloop_edges_df = (
            _payment_selfloop_edges_df_filtered.copy()
            if _payment_selfloop_edges_df_filtered is not None
            else pd.DataFrame(columns=['uen','_payment_count','_payment_amt']))
        fitas_selfloop_edges_df = (
            _fitas_selfloop_edges_df_filtered.copy()
            if _fitas_selfloop_edges_df_filtered is not None
            else pd.DataFrame(columns=['uen','_fitas_count','_fitas_amt']))
        # Side panel stats reflect filtered edges in filtered HTML
        tt_summary_for_panel      = _tt_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
        fast_summary_for_panel    = _fast_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
        giro_summary_for_panel    = _giro_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
        fitas_summary_for_panel   = _fitas_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
        payment_summary_for_panel = _payment_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
        all_txn_summary_for_panel = _all_txn_summary_filtered.drop_duplicates(subset='UEN', keep='first').copy()
    else:
        directed_edges_df = _directed_edges_df_full.copy()
        selfloop_edges_df = _selfloop_edges_df.copy()
        payment_directed_edges_df = _payment_directed_edges_df_full.copy()
        all_txn_selfloop_edges_df = _all_txn_selfloop_edges_df_full.copy()
        payment_selfloop_edges_df = (
            _payment_selfloop_edges_df_full.copy()
            if _payment_selfloop_edges_df_full is not None
            else pd.DataFrame(columns=['uen','_payment_count','_payment_amt']))
        fitas_selfloop_edges_df = (
            _fitas_selfloop_edges_df_full.copy()
            if _fitas_selfloop_edges_df_full is not None
            else pd.DataFrame(columns=['uen','_fitas_count','_fitas_amt']))
        tt_summary_for_panel      = _tt_summary.drop_duplicates(subset='UEN', keep='first').copy()
        fast_summary_for_panel    = _fast_summary.drop_duplicates(subset='UEN', keep='first').copy()
        giro_summary_for_panel    = _giro_summary.drop_duplicates(subset='UEN', keep='first').copy()
        fitas_summary_for_panel   = _fitas_summary.drop_duplicates(subset='UEN', keep='first').copy()
        payment_summary_for_panel = _payment_summary.drop_duplicates(subset='UEN', keep='first').copy()
        all_txn_summary_for_panel = _all_txn_summary.drop_duplicates(subset='UEN', keep='first').copy()

    kept_uens = set(enriched_nodes['UEN'].astype(str).tolist())

    # ── Orphan removal (filtered mode only) ──────────────────────────────
    if output_mode == 'filtered':
        tt_connected = (
            set(directed_edges_df['from_uen'].astype(str)) |
            set(directed_edges_df['to_uen'].astype(str))
        )
        undirected_connected = (
            set(undirected_edges_df['from_uen'].astype(str)) |
            set(undirected_edges_df['to_uen'].astype(str))
        )
        tt_selfloop_connected      = set(selfloop_edges_df['uen'].astype(str))
        # *** fix | use the post-threshold dataframes (not source.self_loop_ids
        # which are pre-threshold) so orphan removal is consistent with what
        # the side panel actually shows. Also include payment_self separately:
        # a node could be below threshold per-source (TT/FAST/GIRO) but
        # above threshold when summed as Payment.
        fitas_selfloop_connected   = set(fitas_selfloop_edges_df['uen'].astype(str))
        payment_selfloop_connected = set(payment_selfloop_edges_df['uen'].astype(str))

        payment_connected = (
            set(payment_directed_edges_df['from_uen'].astype(str)) |
            set(payment_directed_edges_df['to_uen'].astype(str))
        )
        all_txn_self_connected = set(all_txn_selfloop_edges_df['uen'].astype(str))
        fast_self_connected    = set(str(u) for u in fast_source.self_loop_ids)
        giro_self_connected    = set(str(u) for u in giro_source.self_loop_ids)

        still_connected = (
            tt_connected               |
            undirected_connected       |
            tt_selfloop_connected      |
            fitas_selfloop_connected   |
            payment_connected          |
            payment_selfloop_connected |
            all_txn_self_connected     |
            fast_self_connected        |
            giro_self_connected
        )

        before_orphan = len(kept_uens)
        kept_uens     = kept_uens & still_connected
        orphaned      = before_orphan - len(kept_uens)

        enriched_nodes = enriched_nodes[
            enriched_nodes['UEN'].astype(str).isin(kept_uens)
        ].copy()

        print(f"  [{output_mode}] Orphan removal:")
        print(f"    Nodes before:                {before_orphan:,}")
        print(f"    Removed:                     {orphaned:,}")
        print(f"    Nodes after:                 {len(kept_uens):,}")
        print(f"    FITAS self-loop nodes kept:  {len(fitas_selfloop_connected & kept_uens):,}")
    else:
        print(f"  [{output_mode}] No orphan removal -- all {len(kept_uens):,} nodes kept")

    # ── Cascade kept_uens to all edge tables and dicts ────────────────────
    undirected_edges_df = undirected_edges_df[
        undirected_edges_df['from_uen'].astype(str).isin(kept_uens) &
        undirected_edges_df['to_uen'].astype(str).isin(kept_uens)
    ].copy()

    directed_edges_df = directed_edges_df[
        directed_edges_df['from_uen'].astype(str).isin(kept_uens) &
        directed_edges_df['to_uen'].astype(str).isin(kept_uens)
    ].copy()

    selfloop_edges_df = selfloop_edges_df[
        selfloop_edges_df['uen'].astype(str).isin(kept_uens)
    ].copy()

    payment_directed_edges_df = payment_directed_edges_df[
        payment_directed_edges_df['from_uen'].astype(str).isin(kept_uens) &
        payment_directed_edges_df['to_uen'].astype(str).isin(kept_uens)
    ].copy()
    all_txn_selfloop_edges_df = all_txn_selfloop_edges_df[
        all_txn_selfloop_edges_df['uen'].astype(str).isin(kept_uens)
    ].copy()
    payment_selfloop_edges_df = payment_selfloop_edges_df[
        payment_selfloop_edges_df['uen'].astype(str).isin(kept_uens)
    ].copy()
    fitas_selfloop_edges_df = fitas_selfloop_edges_df[
        fitas_selfloop_edges_df['uen'].astype(str).isin(kept_uens)
    ].copy()

    tt_summary_for_panel      = tt_summary_for_panel[tt_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()
    fitas_summary_for_panel   = fitas_summary_for_panel[fitas_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()
    fast_summary_for_panel    = fast_summary_for_panel[fast_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()
    giro_summary_for_panel    = giro_summary_for_panel[giro_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()
    payment_summary_for_panel = payment_summary_for_panel[payment_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()
    all_txn_summary_for_panel = all_txn_summary_for_panel[all_txn_summary_for_panel['UEN'].astype(str).isin(kept_uens)].copy()

    original_sizes_js = {k: v for k, v in original_sizes_js.items() if k in kept_uens}

    rsme_adjacency = {
        k: [nb for nb in v if nb in kept_uens]
        for k, v in rsme_adjacency.items()
        if k in kept_uens
    }

    # ── FIX 2: rebuild TT adjacency maps from mode-specific edge set ──────
    # *** updated | iterate via numpy arrays (zip) for ~3x speed at scale.
    new_out_adj = {}
    new_in_adj  = {}
    _src_arr = directed_edges_df['from_uen'].astype(str).str.strip().to_numpy()
    _tgt_arr = directed_edges_df['to_uen']  .astype(str).str.strip().to_numpy()
    for src, tgt in zip(_src_arr, _tgt_arr):
        if src in kept_uens and tgt in kept_uens:
            new_out_adj.setdefault(src, []).append(tgt)
            new_in_adj.setdefault(tgt, []).append(src)

    consol_tt_source.out_adj = new_out_adj
    consol_tt_source.in_adj  = new_in_adj

    # Rebuild FAST adjacency from this mode's edge set.
    # In filtered mode, use the per-pair-Payment-threshold-filtered edges from
    # Recipe 1 (fast_edges_filtered) so the graph adjacency matches the same
    # threshold semantics as Excel's edges_filtered. In full mode, use the
    # source's full directed_edges_df.
    if output_mode == 'filtered' and _fast_edges_filtered is not None:
        fast_edges_for_adj = _fast_edges_filtered
    else:
        fast_edges_for_adj = fast_source.directed_edges_df
    new_fast_out, new_fast_in = {}, {}
    _fa_src = fast_edges_for_adj['SOURCE_UEN'].astype(str).str.strip().to_numpy()
    _fa_tgt = fast_edges_for_adj['TARGET_UEN'].astype(str).str.strip().to_numpy()
    for s, t in zip(_fa_src, _fa_tgt):
        if s in kept_uens and t in kept_uens:
            new_fast_out.setdefault(s, []).append(t)
            new_fast_in.setdefault(t, []).append(s)
    fast_source.out_adj, fast_source.in_adj = new_fast_out, new_fast_in

    if output_mode == 'filtered' and _giro_edges_filtered is not None:
        giro_edges_for_adj = _giro_edges_filtered
    else:
        giro_edges_for_adj = giro_source.directed_edges_df
    new_giro_out, new_giro_in = {}, {}
    _gi_src = giro_edges_for_adj['SOURCE_UEN'].astype(str).str.strip().to_numpy()
    _gi_tgt = giro_edges_for_adj['TARGET_UEN'].astype(str).str.strip().to_numpy()
    for s, t in zip(_gi_src, _gi_tgt):
        if s in kept_uens and t in kept_uens:
            new_giro_out.setdefault(s, []).append(t)
            new_giro_in.setdefault(t, []).append(s)
    giro_source.out_adj, giro_source.in_adj = new_giro_out, new_giro_in

    print(f"  [{output_mode}] TT adjacency rebuilt from {output_mode} edges:")
    print(f"    out_adj nodes: {len(new_out_adj):,}")
    print(f"    in_adj nodes:  {len(new_in_adj):,}")
    print(f"  [{output_mode}] Final state:")
    print(f"    Nodes:                {len(enriched_nodes):,}")
    print(f"    Undirected edges:     {len(undirected_edges_df):,}")
    print(f"    Directed edges (TT):  {len(directed_edges_df):,}")
    print(f"    TT self-loops:        {len(selfloop_edges_df):,}")

    return {
        'enriched_nodes'     : enriched_nodes,
        'undirected_edges_df': undirected_edges_df,
        'directed_edges_df'  : directed_edges_df,
        'selfloop_edges_df'  : selfloop_edges_df,
        'original_sizes_js'  : original_sizes_js,
        'rsme_adjacency'     : rsme_adjacency,
        'kept_uens'          : kept_uens,
        'payment_directed_edges_df': payment_directed_edges_df,
        'all_txn_selfloop_edges_df': all_txn_selfloop_edges_df,
        'payment_selfloop_edges_df': payment_selfloop_edges_df,
        'fitas_selfloop_edges_df'  : fitas_selfloop_edges_df,
        'tt_summary'                : tt_summary_for_panel,
        'fitas_summary'             : fitas_summary_for_panel,
        'fast_summary'              : fast_summary_for_panel,
        'giro_summary'              : giro_summary_for_panel,
        'payment_summary'           : payment_summary_for_panel,
        'all_txn_summary'           : all_txn_summary_for_panel,
    }

print("Mode builder defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 4: Load logo

print("\n" + "="*60)
print("LOADING LOGO")
print("="*60)

logo_b64 = None
try:
    main_folder = dataiku.Folder(cfg.FOLDER_MAIN)
    logo_path   = cfg.FILES['logo'].lstrip('/')
    with main_folder.get_download_stream(logo_path) as r:
        logo_b64 = base64.b64encode(r.read()).decode('utf-8')
    print("✓ Logo loaded")
except Exception as e:
    print(f"  Logo not found: {e} (continuing without logo)")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 5: Build JavaScript payloads helper

print("\n" + "="*60)
print("DEFINING PAYLOAD BUILDER")
print("="*60)

def _build_js_payloads(mode_data):
    """Builds all JavaScript payloads from a mode data dict."""
    enriched_nodes      = mode_data['enriched_nodes']
    undirected_edges_df = mode_data['undirected_edges_df']
    directed_edges_df   = mode_data['directed_edges_df']
    selfloop_edges_df   = mode_data['selfloop_edges_df']

    payload_builder = JSPayloadBuilder(cfg)

    node_type_js = enriched_nodes.set_index('UEN')['CUST_TYPE'].to_dict()
    node_meta_js = payload_builder.build_node_meta(enriched_nodes, node_type_js)

    name_series = (
        enriched_nodes['source_name']
        .fillna('')
        .replace('', pd.NA)
        .fillna(enriched_nodes['UEN'])
    )
    id_name_lookup_js  = dict(zip(enriched_nodes['UEN'], name_series))
    original_labels_js = id_name_lookup_js.copy()

    consol_tt_node_summary_js = (
        mode_data['tt_summary']
        .loc[(mode_data['tt_summary']['tt_ord_freq'] > 0) | (mode_data['tt_summary']['tt_bene_freq'] > 0)]
        .set_index('UEN')[[
            'tt_ord_freq', 'tt_ord_amt',
            'tt_bene_freq', 'tt_bene_amt',
            'tt_net_flow_amt',
        ]]
        .to_dict('index')
    )

    fitas_node_summary_js = (
        mode_data['fitas_summary']
        .loc[(mode_data['fitas_summary']['fitas_ord_freq'] > 0) | (mode_data['fitas_summary']['fitas_bene_freq'] > 0)]
        .set_index('UEN')[[
            'fitas_ord_freq', 'fitas_ord_amt',
            'fitas_bene_freq', 'fitas_bene_amt',
            'fitas_net_flow_amt',
        ]]
        .to_dict('index')
    )

    fast_node_summary_js = (
        mode_data['fast_summary'].set_index('UEN')[
            ['fast_ord_freq','fast_ord_amt','fast_bene_freq','fast_bene_amt','fast_net_flow_amt']
        ].to_dict('index')
    )
    giro_node_summary_js = (
        mode_data['giro_summary'].set_index('UEN')[
            ['giro_ord_freq','giro_ord_amt','giro_bene_freq','giro_bene_amt','giro_net_flow_amt']
        ].to_dict('index')
    )
    payment_node_summary_js = (
        mode_data['payment_summary'].set_index('UEN')[
            ['payment_ord_freq','payment_ord_amt','payment_bene_freq','payment_bene_amt','payment_net_flow_amt']
        ].to_dict('index')
    )
    all_txn_node_summary_js = (
        mode_data['all_txn_summary'].set_index('UEN')[
            ['all_txn_ord_freq','all_txn_ord_amt','all_txn_bene_freq','all_txn_bene_amt','all_txn_net_flow_amt']
        ].to_dict('index')
    )

    undirected_edges_js = (
        undirected_edges_df
        .rename(columns={'from_uen': 'from', 'to_uen': 'to'})
        .to_dict('records')
    )

    directed_edges_js = (
        directed_edges_df
        .rename(columns={'from_uen': 'from', 'to_uen': 'to'})
        .to_dict('records')
    )

    selfloop_edges_js = selfloop_edges_df.to_dict('records')

    payment_directed_edges_js = (
        mode_data['payment_directed_edges_df']
            .rename(columns={'from_uen': 'from', 'to_uen': 'to'})
            .to_dict('records')
    )
    all_txn_selfloop_edges_js = mode_data['all_txn_selfloop_edges_df'].to_dict('records')
    payment_selfloop_edges_js  = mode_data['payment_selfloop_edges_df'].to_dict('records')
    fitas_selfloop_edges_js    = mode_data['fitas_selfloop_edges_df'].to_dict('records')

    return {
        'node_type_js'             : node_type_js,
        'node_meta_js'             : node_meta_js,
        'id_name_lookup_js'        : id_name_lookup_js,
        'original_labels_js'       : original_labels_js,
        'consol_tt_node_summary_js': consol_tt_node_summary_js,
        'fitas_node_summary_js'    : fitas_node_summary_js,
        'undirected_edges_js'      : undirected_edges_js,
        'directed_edges_js'        : directed_edges_js,
        'selfloop_edges_js'        : selfloop_edges_js,
        'fast_node_summary_js'      : fast_node_summary_js,
        'giro_node_summary_js'      : giro_node_summary_js,
        'payment_node_summary_js'   : payment_node_summary_js,
        'all_txn_node_summary_js'   : all_txn_node_summary_js,
        'payment_directed_edges_js' : payment_directed_edges_js,
        'all_txn_selfloop_edges_js' : all_txn_selfloop_edges_js,
        'payment_selfloop_edges_js' : payment_selfloop_edges_js,
        'fitas_selfloop_edges_js'   : fitas_selfloop_edges_js,
    }

print("Payload builder defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 6: Build HTML helper

print("\n" + "="*60)
print("DEFINING HTML BUILDER")
print("="*60)

def _build_html(mode_data, payloads):
    """Builds HTML string from mode data and JS payloads."""
    builder = HTMLBuilder(cfg, viz_config)

    html = builder.build(
        rsme_adjacency             = mode_data['rsme_adjacency'],
        rsme_degree_map            = _rsme_degree_map,
        original_sizes_js          = mode_data['original_sizes_js'],
        node_type_js               = payloads['node_type_js'],
        node_meta_js               = payloads['node_meta_js'],
        id_name_lookup_js          = payloads['id_name_lookup_js'],
        original_labels_js         = payloads['original_labels_js'],
        rsme_source                = rsme_source,
        consol_tt_source           = consol_tt_source,
        fitas_source               = fitas_source,
        aa_paper_source            = aa_paper_source,
        fast_source                = fast_source,
        giro_source                = giro_source,
        consol_tt_node_summary_js  = payloads['consol_tt_node_summary_js'],
        fitas_node_summary_js      = payloads['fitas_node_summary_js'],
        fast_node_summary_js       = payloads['fast_node_summary_js'],
        giro_node_summary_js       = payloads['giro_node_summary_js'],
        payment_node_summary_js    = payloads['payment_node_summary_js'],
        all_txn_node_summary_js    = payloads['all_txn_node_summary_js'],
        consol_tt_metric_ranges    = consol_tt_metric_ranges,
        fitas_metric_ranges        = fitas_metric_ranges,
        fast_metric_ranges         = fast_metric_ranges,
        giro_metric_ranges         = giro_metric_ranges,
        payment_metric_ranges      = payment_metric_ranges,
        all_txn_metric_ranges      = all_txn_metric_ranges,
        undirected_edges_js        = payloads['undirected_edges_js'],
        directed_edges_js          = payloads['directed_edges_js'],
        selfloop_edges_js          = payloads['selfloop_edges_js'],
        payment_directed_edges_js  = payloads['payment_directed_edges_js'],
        all_txn_selfloop_edges_js  = payloads['all_txn_selfloop_edges_js'],
        payment_selfloop_edges_js  = payloads['payment_selfloop_edges_js'],
        fitas_selfloop_edges_js    = payloads['fitas_selfloop_edges_js'],
        all_txn_latest_date        = _all_txn_latest_date,
        logo_b64                   = logo_b64,
        relationship_df            = _relationship_df,
    )

    assert "waitForVis"   in html, "JavaScript initialization missing"
    assert "renderSearch" in html, "Search function missing"

    return html

print("HTML builder defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 7: Generate and save all 4 HTML files
# FIX: after each mode build, restore consol_tt_source adjacency maps to the
# original full set so the next mode starts from a clean state.

print("\n" + "="*60)
print("GENERATING ALL HTML FILES")
print("="*60)

exporter   = DatasetExporter(cfg)
html_sizes = {}

for mode in ['full', 'filtered']:
    print(f"\n{'─'*50}")
    print(f"  Building {mode.upper()} mode...")
    print(f"{'─'*50}")

    mode_data = _build_mode_data(mode)
    payloads  = _build_js_payloads(mode_data)
    html      = _build_html(mode_data, payloads)

    # Restore original TT adjacency maps before next mode
    consol_tt_source.out_adj = {k: list(v) for k, v in _tt_out_adj_original.items()}
    consol_tt_source.in_adj  = {k: list(v) for k, v in _tt_in_adj_original.items()}
    fast_source.out_adj = {k: list(v) for k, v in _fast_out_adj_original.items()}
    fast_source.in_adj  = {k: list(v) for k, v in _fast_in_adj_original.items()}
    giro_source.out_adj = {k: list(v) for k, v in _giro_out_adj_original.items()}
    giro_source.in_adj  = {k: list(v) for k, v in _giro_in_adj_original.items()}

    size_mb          = len(html) / 1024 / 1024
    html_sizes[mode] = size_mb

    exporter.export_html(html,        filename=f'MEXT_NETWORK_{mode}.html')
    exporter.export_minify_html(html, filename=f'MEXT_NETWORK_{mode}_minified.html')

    print(f"  ✓ {mode} HTML: {size_mb:.2f} MB")

print("\n" + "="*60)
print("RECIPE 2 COMPLETE")
print("="*60)
print(f"  4 HTML files generated:")
print(f"    MEXT_NETWORK_full.html")
print(f"    MEXT_NETWORK_full_minified.html")
print(f"    MEXT_NETWORK_filtered.html")
print(f"    MEXT_NETWORK_filtered_minified.html")
print(f"\n  Size comparison:")
print(f"    Full:      {html_sizes['full']:.2f} MB")
print(f"    Filtered:  {html_sizes['filtered']:.2f} MB")
print(f"    Reduction: {(html_sizes['full'] - html_sizes['filtered']) / html_sizes['full'] * 100:.1f}%")
print(f"\n  TT edge filter threshold: S${tt_edge_min_amt_cached:,}  (set in Recipe 1)")
print(f"  Relationship pairs loaded: {len(_relationship_df):,}  (available for diagnostics)")
print(f"  No neighbor cache -- in-browser BFS from adjacency maps")
print(f"  Blank canvas with lazy node injection")
print(f"  Consolidated edge architecture (undirected/directed/selfloop)")