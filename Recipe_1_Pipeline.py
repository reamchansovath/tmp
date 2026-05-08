# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Local twin: when DATAIKU_ENV=local, register mock_dataiku as the dataiku
# module so every later `import dataiku` (across all cells) resolves to the
# mock. In Dataiku, DATAIKU_ENV is not set so this block is a no-op.

import os, sys
if os.getenv('DATAIKU_ENV') == 'local':
    import mock_dataiku
    sys.modules['dataiku'] = mock_dataiku


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# In Dataiku, run this in a notebook cell to clear old cache before re-running:
import dataiku  # type: ignore[import-not-found]

pipeline_folder = dataiku.Folder("oSbAKnR6")

try:
    pipeline_folder.delete_path('network_cache.pkl')
    print("Old pickle deleted")
except:
    print("No old pickle found (OK)")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# ────────────────────────────────────────────────────────────────────────────
# RECIPE 1: Network Graph Data Preparation
# Loads 4 networks (RSME, TT, FITAS, AA Paper), enriches nodes,
# builds consolidated edge tables. NO NetworkX, NO PyVis, NO neighbor cache.
# ────────────────────────────────────────────────────────────────────────────

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 1: Imports and configuration

import dataiku  # type: ignore[import-not-found]
import pandas as pd
import numpy as np
import pickle
from network_graph.config      import NetworkGraphConfig as cfg
from network_graph             import RSMESource, ConsolTTSource, FITASSource, AAPaperSource, FastGiroSource
from network_graph.pipeline    import Enricher, Classifier
from network_graph.pipeline    import RelationshipBuilder
from network_graph.exporters   import DatasetExporter

_INVALID_IDS = {'', 'nan', 'none', 'None', 'NaN', 'NAN'}

# Per-direction Payment threshold: drop A->B if (TT + FAST + GIRO).ab < THRESHOLD_TXN_SGD
THRESHOLD_TXN_SGD = 5_000   # SGD

print("Imports complete")
print(f"Payment threshold (per direction, TT+FAST+GIRO combined): S${THRESHOLD_TXN_SGD:,}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 2: Get managed folders

rsme_harm_folder    = dataiku.Folder(cfg.FOLDER_RSME_HARM)
consol_tt_folder    = dataiku.Folder(cfg.FOLDER_CONSOL_TT)
fitas_folder        = dataiku.Folder(cfg.FOLDER_FITAS)
aa_paper_folder     = dataiku.Folder(cfg.FOLDER_AA_PAPER)
main_folder         = dataiku.Folder(cfg.FOLDER_MAIN)
enrichment_folder   = dataiku.Folder(cfg.FOLDER_ENRICHMENT)
acra_folder         = dataiku.Folder(cfg.FOLDER_ACRA)
emis_folder         = dataiku.Folder(cfg.FOLDER_EMIS)
pipeline_folder     = dataiku.Folder(cfg.FOLDER_PIPELINE)
acra_charges_folder = dataiku.Folder(cfg.FOLDER_ACRA_CHARGES)
# *** new | CIP collaterals processed data
cip_folder          = dataiku.Folder(cfg.FOLDER_CIP)
fast_giro_folder    = dataiku.Folder(cfg.FOLDER_FAST_GIRO)

print("Managed folders loaded")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 3: Load all 4 network sources

print("\n" + "="*60)
print("LOADING NETWORK SOURCES")
print("="*60)

rsme_source      = RSMESource(cfg, rsme_harm_folder, main_folder).load()
consol_tt_source = ConsolTTSource(cfg, consol_tt_folder).load()
fitas_source     = FITASSource(cfg, fitas_folder).load()
aa_paper_source  = AAPaperSource(cfg, aa_paper_folder).load()
fast_source = FastGiroSource(cfg, fast_giro_folder, kind='FAST').build()
giro_source = FastGiroSource(cfg, fast_giro_folder, kind='GIRO').build()

# Apply per-direction TT edge filter to produce edges_df_filtered.
# Each row is one direction A->B -- rows where txn_amt < THRESHOLD_TXN_SGD are dropped.
# Full edges_df is kept unchanged for the full output mode.
consol_tt_source.apply_edge_filter(THRESHOLD_TXN_SGD)

rsme_nodes_df     = rsme_source.get_nodes()
tt_nodes_df       = consol_tt_source.get_nodes()
fitas_nodes_df    = fitas_source.get_nodes()
aa_paper_nodes_df = aa_paper_source.get_nodes()

rsme_edges_df     = rsme_source.get_edges()
tt_edges_df       = consol_tt_source.get_edges()
fitas_edges_df    = fitas_source.get_edges()
aa_paper_edges_df = aa_paper_source.get_edges()
fast_edges_df = fast_source.get_edges()
giro_edges_df = giro_source.get_edges()
fast_nodes_df = fast_source.get_nodes()
giro_nodes_df = giro_source.get_nodes()

print(f"\nRSME loaded:      {len(rsme_edges_df):,} edges")
print(f"TT loaded:        {len(tt_edges_df):,} edges (full)")
print(f"TT filtered:      {len(consol_tt_source.edges_df_filtered):,} edges (>= S${THRESHOLD_TXN_SGD:,})")
print(f"FITAS loaded:     {len(fitas_edges_df):,} edges")
print(f"AA Paper loaded:  {len(aa_paper_edges_df):,} edges")
print(f"FAST loaded:      {len(fast_edges_df):,} edges (ext only)")
print(f"GIRO loaded:      {len(giro_edges_df):,} edges (ext only)")
print(f"FITAS product df: {len(fitas_source.fitas_product_df):,} product rows")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 4: Combine nodes from all sources

print("\n" + "="*60)
print("COMBINING NODES")
print("="*60)

all_nodes = pd.concat([
    rsme_nodes_df,
    tt_nodes_df,
    fitas_nodes_df,
    aa_paper_nodes_df,
    fast_nodes_df,
    giro_nodes_df,
], ignore_index=True)

print(f"BEFORE dedup: {len(all_nodes):,} rows")
all_nodes = all_nodes.drop_duplicates(subset='UEN', keep='last')
print(f"AFTER dedup:  {len(all_nodes):,} rows")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 5: Combine edges from all sources

print("\n" + "="*60)
print("COMBINING EDGES")
print("="*60)

all_edges = pd.concat([
    rsme_edges_df,
    tt_edges_df,
    fitas_edges_df,
    aa_paper_edges_df,
    fast_edges_df,
    giro_edges_df,
], ignore_index=True)

print(f"Total edges: {len(all_edges):,}")
print(all_edges['edge_source'].value_counts())

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 6: Enrich nodes
# *** updated | pass acra_charges_folder and cip_folder to Enricher

print("\n" + "="*60)
print("ENRICHING NODES")
print("="*60)

enricher = Enricher(
    cfg,
    enrichment_folder,
    acra_folder,
    emis_folder,
    main_folder,
    acra_charges_folder = acra_charges_folder,
    # *** new | CIP collaterals folder -- enables Steps 10 in enricher.enrich()
    cip_folder          = cip_folder,
)
enricher.load_reference_data()
enriched_nodes = enricher.enrich(all_nodes, uen_col='UEN', cif_col='CIF_NO')

print(f"Enriched nodes: {len(enriched_nodes):,}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
all_nodes[all_nodes['UEN']=='201821780H']

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
enriched_nodes[enriched_nodes['UEN']=='201821780H']

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 7: Classify nodes

print("\n" + "="*60)
print("CLASSIFYING NODES")
print("="*60)

classifier     = Classifier(cfg)
enriched_nodes = classifier.classify(enriched_nodes, cif_col='CIF_NO')
enriched_nodes = enriched_nodes.drop_duplicates(subset='UEN', keep='first')

print(f"Classified nodes: {len(enriched_nodes):,}")
print(enriched_nodes['CUST_TYPE'].value_counts())

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 8: Build RSME adjacency (undirected, no NetworkX)

print("\n" + "="*60)
print("BUILDING RSME ADJACENCY")
print("="*60)

rsme_adjacency = {}

for r in rsme_edges_df[['SOURCE_UEN', 'TARGET_UEN']].to_dict('records'):
    src = str(r['SOURCE_UEN']).strip()
    tgt = str(r['TARGET_UEN']).strip()
    if src in _INVALID_IDS or tgt in _INVALID_IDS:
        continue
    if src not in rsme_adjacency: rsme_adjacency[src] = []
    if tgt not in rsme_adjacency: rsme_adjacency[tgt] = []
    rsme_adjacency[src].append(tgt)
    rsme_adjacency[tgt].append(src)

rsme_adjacency  = {k: list(set(v)) for k, v in rsme_adjacency.items()}
rsme_degree_map = {k: len(v) for k, v in rsme_adjacency.items()}

print(f"RSME adjacency: {len(rsme_adjacency):,} nodes")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 9: Calculate node sizes (combined degree across all networks)

print("\n" + "="*60)
print("CALCULATING NODE SIZES")
print("="*60)

all_uens = {
    u for u in (
        list(rsme_adjacency.keys()) +
        list(consol_tt_source.out_adj.keys()) + list(consol_tt_source.in_adj.keys()) +
        list(fitas_source.out_adj.keys())      + list(fitas_source.in_adj.keys()) +
        list(aa_paper_source.out_adj.keys())   + list(aa_paper_source.in_adj.keys()) +
        list(fast_source.out_adj.keys())       + list(fast_source.in_adj.keys()) +
        list(giro_source.out_adj.keys())       + list(giro_source.in_adj.keys())
    )
    if str(u).strip() not in _INVALID_IDS
}

# Default node size = unique-counterparty count across all 6 sources (set
# union, not raw sum). A UEN with the same neighbour in TT and FAST counts
# the neighbour once.
original_sizes_js = {}
for nid in all_uens:
    nid_s = str(nid).strip()
    unique_nbrs = set()
    unique_nbrs.update(str(n) for n in rsme_adjacency.get(nid_s, []))
    for src in (consol_tt_source, fitas_source, aa_paper_source,
                fast_source, giro_source):
        unique_nbrs.update(str(n) for n in src.out_adj.get(nid_s, []))
        unique_nbrs.update(str(n) for n in src.in_adj.get(nid_s, []))
    unique_nbrs.discard(nid_s)
    total_deg = len(unique_nbrs)
    original_sizes_js[nid_s] = max(8, min(50, 10 + total_deg * 2))

print(f"Total unique nodes: {len(all_uens):,}")
print(f"Node sizes calculated for {len(original_sizes_js):,} nodes")
print(f"  Size range: {min(original_sizes_js.values())}-{max(original_sizes_js.values())}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 10: Build consolidated edge tables
# Payment combined = TT + FAST + GIRO (outer-merge by sorted-pair direction)
# Per-direction threshold filter: drop A->B if combined Payment ab < THRESHOLD_TXN_SGD.

print("\n" + "="*60)
print("BUILDING CONSOLIDATED EDGE TABLES")
print("="*60)

def _safe_float(v):
    if v is None: return 0.0
    try:
        f = float(v)
        return 0.0 if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0

def _bin_widths(amounts, min_w=1.0, max_w=8.0):
    arr      = np.array([_safe_float(a) for a in amounts], dtype=float)
    log_amts = np.log1p(arr.clip(min=0))
    lo, hi   = log_amts.min(), log_amts.max()
    if hi <= lo:
        return [float(min_w)] * len(arr)
    norm = (log_amts - lo) / (hi - lo)
    return (norm * (max_w - min_w) + min_w).round(2).tolist()

# ── Undirected edges (RSME + AA Paper + FITAS) ────────────────────────────
undirected_map = {}

def _upsert_undirected(src, tgt):
    key = frozenset([src, tgt])
    if key not in undirected_map:
        undirected_map[key] = {
            'from_uen'       : src,
            'to_uen'         : tgt,
            '_rsme_ab'       : False,
            '_rsme_ba'       : False,
            '_aa_ab'         : False,
            '_aa_ba'         : False,
            '_fitas_ab_count': 0,
            '_fitas_ab_amt'  : 0.0,
            '_fitas_ba_count': 0,
            '_fitas_ba_amt'  : 0.0,
        }
    return undirected_map[key]

# *** updated | vectorize the validity filter + string stripping with pandas
# (was: `.to_dict('records')` per-row Python loop). Inner upsert kept in Python
# because frozenset-keyed `undirected_map` needs sequential first-arrival
# semantics for `from_uen`. zip(numpy arrays) is ~3-5x faster than to_dict.
_INVALID_LIST = list(_INVALID_IDS)

def _prep_edge_arrays(df, extra_cols=()):
    """Strip / validate / dedupe-mask UEN cols once (vectorized). Return
    (src_arr, tgt_arr, *extra_arrs, n_skipped).  extras: list of column names
    passed through .to_numpy() in lock-step with the filtered rows."""
    src = df['SOURCE_UEN'].astype(str).str.strip()
    tgt = df['TARGET_UEN'].astype(str).str.strip()
    mask = (~src.isin(_INVALID_IDS)) & (~tgt.isin(_INVALID_IDS)) & (src != tgt)
    n_skipped = int((~mask).sum())
    src_arr = src[mask].to_numpy()
    tgt_arr = tgt[mask].to_numpy()
    extras = tuple(df.loc[mask, c].to_numpy() for c in extra_cols)
    return (src_arr, tgt_arr) + extras + (n_skipped,)

rsme_src, rsme_tgt, rsme_skip = _prep_edge_arrays(rsme_edges_df)
for src, tgt in zip(rsme_src, rsme_tgt):
    p = _upsert_undirected(src, tgt)
    if src == p['from_uen']: p['_rsme_ab'] = True
    else:                    p['_rsme_ba'] = True

print(f"  RSME processed:      {len(rsme_edges_df):,} rows, {rsme_skip:,} skipped")

aa_src, aa_tgt, aa_skip = _prep_edge_arrays(aa_paper_edges_df)
for src, tgt in zip(aa_src, aa_tgt):
    p = _upsert_undirected(src, tgt)
    if src == p['from_uen']: p['_aa_ab'] = True
    else:                    p['_aa_ba'] = True

print(f"  AA Paper processed:  {len(aa_paper_edges_df):,} rows, {aa_skip:,} skipped")

# FITAS adds count + amt -- coerce both vectorized too.
fitas_src, fitas_tgt, fitas_count_raw, fitas_amt_raw, fitas_skip = _prep_edge_arrays(
    fitas_edges_df, extra_cols=('txn_count', 'txn_amt')
)
fitas_count_arr = pd.Series(fitas_count_raw).pipe(pd.to_numeric, errors='coerce').fillna(0).astype(int).to_numpy()
fitas_amt_arr   = pd.Series(fitas_amt_raw  ).pipe(pd.to_numeric, errors='coerce').fillna(0.0).to_numpy(dtype=float)
fitas_amt_arr   = np.where(np.isfinite(fitas_amt_arr), fitas_amt_arr, 0.0)

for src, tgt, count, amt in zip(fitas_src, fitas_tgt, fitas_count_arr, fitas_amt_arr):
    p = _upsert_undirected(src, tgt)
    if src == p['from_uen']:
        p['_fitas_ab_count'] += int(count)
        p['_fitas_ab_amt']   += float(amt)
    else:
        p['_fitas_ba_count'] += int(count)
        p['_fitas_ba_amt']   += float(amt)

print(f"  FITAS processed:     {len(fitas_edges_df):,} rows, {fitas_skip:,} skipped")

undirected_rows = list(undirected_map.values())
fitas_present   = [
    r['_fitas_ab_count'] > 0 or r['_fitas_ba_count'] > 0
    for r in undirected_rows
]
fitas_totals    = [r['_fitas_ab_amt'] + r['_fitas_ba_amt'] for r in undirected_rows]

fitas_amts_subset = [fitas_totals[i] for i, p in enumerate(fitas_present) if p]
fitas_widths_map  = {}
if fitas_amts_subset:
    binned = _bin_widths(fitas_amts_subset)
    j = 0
    for i, has_fitas in enumerate(fitas_present):
        if has_fitas:
            fitas_widths_map[i] = binned[j]
            j += 1

for i, r in enumerate(undirected_rows):
    r['_width'] = fitas_widths_map.get(i, 1.0)

undirected_edges_df = pd.DataFrame(undirected_rows)
print(f"\nundirected_edges_df: {len(undirected_edges_df):,} rows")

# ── Directed edges builder ────────────────────────────────────────────────
def _build_directed_edges_df(tt_edges_input, label=''):
    """
    Consolidates per-direction TT rows into net flow pairs.
    A->B and B->A merged into one row with net sender as from_uen.
    """
    tt_all_clean = tt_edges_input.assign(
        SOURCE_UEN = tt_edges_input['SOURCE_UEN'].astype(str).str.strip(),
        TARGET_UEN = tt_edges_input['TARGET_UEN'].astype(str).str.strip(),
    )

    tt_clean = tt_all_clean[
        (~tt_all_clean['SOURCE_UEN'].isin(_INVALID_IDS)) &
        (~tt_all_clean['TARGET_UEN'].isin(_INVALID_IDS)) &
        (tt_all_clean['SOURCE_UEN'] != tt_all_clean['TARGET_UEN'])
    ]

    tt_agg = (
        tt_clean
        .groupby(['SOURCE_UEN', 'TARGET_UEN'])
        .agg(txn_count=('txn_count', 'sum'), txn_amt=('txn_amt', 'sum'))
        .reset_index()
    )

    directed_map = {}

    # *** updated | iterate via numpy arrays (zip) instead of to_dict('records');
    # tt_agg already aggregated so the loop is O(unique pairs).
    _src_arr   = tt_agg['SOURCE_UEN'].to_numpy()
    _tgt_arr   = tt_agg['TARGET_UEN'].to_numpy()
    _count_arr = pd.to_numeric(tt_agg['txn_count'], errors='coerce').fillna(0).astype(int).to_numpy()
    _amt_arr   = pd.to_numeric(tt_agg['txn_amt'],   errors='coerce').fillna(0.0).to_numpy(dtype=float)
    _amt_arr   = np.where(np.isfinite(_amt_arr), _amt_arr, 0.0)

    for src, tgt, count, amt in zip(_src_arr, _tgt_arr, _count_arr, _amt_arr):
        key = frozenset([src, tgt])

        if key not in directed_map:
            directed_map[key] = {
                'ref_src': src, 'ref_tgt': tgt,
                'ab_count': 0,  'ab_amt': 0.0,
                'ba_count': 0,  'ba_amt': 0.0,
            }

        p = directed_map[key]
        if src == p['ref_src']:
            p['ab_count'] += count; p['ab_amt'] += amt
        else:
            p['ba_count'] += count; p['ba_amt'] += amt

    directed_rows = []
    for p in directed_map.values():
        ab_amt = p['ab_amt']
        ba_amt = p['ba_amt']
        if ab_amt >= ba_amt:
            from_uen    = p['ref_src']; to_uen = p['ref_tgt']
            tt_ab_count = p['ab_count']; tt_ab_amt = ab_amt
            tt_ba_count = p['ba_count']; tt_ba_amt = ba_amt
            net_amt     = ab_amt - ba_amt
        else:
            from_uen    = p['ref_tgt']; to_uen = p['ref_src']
            tt_ab_count = p['ba_count']; tt_ab_amt = ba_amt
            tt_ba_count = p['ab_count']; tt_ba_amt = ab_amt
            net_amt     = ba_amt - ab_amt

        directed_rows.append({
            'from_uen'       : from_uen,
            'to_uen'         : to_uen,
            '_tt_ab_count'   : tt_ab_count,
            '_tt_ab_amt'     : round(tt_ab_amt, 2),
            '_tt_ba_count'   : tt_ba_count,
            '_tt_ba_amt'     : round(tt_ba_amt, 2),
            '_tt_total_count': tt_ab_count + tt_ba_count,
            '_tt_net_amt'    : round(net_amt, 2),
            '_width'         : 1.0,
        })

    if directed_rows:
        binned = _bin_widths([r['_tt_net_amt'] for r in directed_rows])
        for i, r in enumerate(directed_rows):
            r['_width'] = binned[i]

    result = pd.DataFrame(directed_rows) if directed_rows else pd.DataFrame(
        columns=['from_uen','to_uen','_tt_ab_count','_tt_ab_amt',
                 '_tt_ba_count','_tt_ba_amt','_tt_total_count','_tt_net_amt','_width']
    )
    print(f"directed_edges_df {label}: {len(result):,} rows")
    return result


# ── Per-source directed builder (TT / FAST / GIRO) ───────────────────────────
def _build_directed_per_source(edges_input, label, count_col='txn_count', amt_col='txn_amt'):
    """Aggregate per-direction: returns dict keyed by (src,tgt) -> (count, amt)."""
    df = edges_input.assign(
        SOURCE_UEN=edges_input['SOURCE_UEN'].astype(str).str.strip(),
        TARGET_UEN=edges_input['TARGET_UEN'].astype(str).str.strip(),
    )
    df = df[
        (~df['SOURCE_UEN'].isin(_INVALID_IDS)) &
        (~df['TARGET_UEN'].isin(_INVALID_IDS)) &
        (df['SOURCE_UEN'] != df['TARGET_UEN'])
    ]
    # *** updated | zip over numpy arrays instead of to_dict('records')
    agg = df.groupby(['SOURCE_UEN','TARGET_UEN']).agg(
        c=(count_col,'sum'), a=(amt_col,'sum')
    ).reset_index()
    src_a = agg['SOURCE_UEN'].to_numpy()
    tgt_a = agg['TARGET_UEN'].to_numpy()
    c_a   = pd.to_numeric(agg['c'], errors='coerce').fillna(0).astype(int).to_numpy()
    a_a   = pd.to_numeric(agg['a'], errors='coerce').fillna(0.0).to_numpy(dtype=float)
    a_a   = np.where(np.isfinite(a_a), a_a, 0.0)
    out = {(s, t): (int(cnt), float(amt)) for s, t, cnt, amt in zip(src_a, tgt_a, c_a, a_a)}
    print(f"  per-direction {label}: {len(out):,} keys")
    return out

tt_dir   = _build_directed_per_source(tt_edges_df,   'TT')
fast_dir = _build_directed_per_source(fast_edges_df, 'FAST')
giro_dir = _build_directed_per_source(giro_edges_df, 'GIRO')

# ── Payment combined per-direction (sum across TT+FAST+GIRO) ─────────────────
all_pair_keys = set(tt_dir) | set(fast_dir) | set(giro_dir)
print(f"  Total unique payment-direction keys: {len(all_pair_keys):,}")

payment_rows = []
for key in all_pair_keys:
    src, tgt = key
    tt_c, tt_a     = tt_dir.get(key,   (0, 0.0))
    fa_c, fa_a     = fast_dir.get(key, (0, 0.0))
    gi_c, gi_a     = giro_dir.get(key, (0, 0.0))
    pay_c          = tt_c + fa_c + gi_c
    pay_a          = tt_a + fa_a + gi_a
    payment_rows.append({
        'SOURCE_UEN'    : src,
        'TARGET_UEN'    : tgt,
        '_tt_count'     : tt_c, '_tt_amt'   : tt_a,
        '_fast_count'   : fa_c, '_fast_amt' : fa_a,
        '_giro_count'   : gi_c, '_giro_amt' : gi_a,
        'txn_count'     : pay_c,
        'txn_amt'       : pay_a,
    })
payment_df = pd.DataFrame(payment_rows)
print(f"  payment_df (per-direction, full): {len(payment_df):,}")

# Apply threshold per direction (Payment combined)
mask = payment_df['txn_amt'] >= THRESHOLD_TXN_SGD
payment_df_filtered_per_direction = payment_df[mask].copy()
n_removed = len(payment_df) - len(payment_df_filtered_per_direction)
print(f"  Payment threshold S${THRESHOLD_TXN_SGD:,}: kept {len(payment_df_filtered_per_direction):,} "
      f"(removed {n_removed:,} = {n_removed/max(len(payment_df),1)*100:.1f}%)")

# ── Build directed_edges_df (TT only — kept for backwards compat / sidepanel) ─
directed_edges_df          = _build_directed_edges_df(tt_edges_df,                           label='(TT-full)')
directed_edges_df_filtered = _build_directed_edges_df(consol_tt_source.get_edges_filtered(), label='(TT-filtered)')

# ── Build payment directed-edges (one row per (src,tgt) ordered pair) ────────
def _payment_directed_from_filter(payment_filtered):
    """
    Convert per-direction payment_filtered into one row per ordered pair with
    net direction info -- used by vis.js for arrow direction.
    """
    pairs = {}
    # *** updated | zip over numpy arrays instead of to_dict('records')
    src_a = payment_filtered['SOURCE_UEN'].to_numpy()
    tgt_a = payment_filtered['TARGET_UEN'].to_numpy()
    cnt_a = payment_filtered['txn_count'].to_numpy()
    amt_a = payment_filtered['txn_amt'].to_numpy()
    for src, tgt, count, amt in zip(src_a, tgt_a, cnt_a, amt_a):
        key = frozenset([src, tgt])
        if key not in pairs:
            pairs[key] = {'ref_src': src, 'ref_tgt': tgt,
                          'ab_count': 0, 'ab_amt': 0.0, 'ba_count': 0, 'ba_amt': 0.0}
        p = pairs[key]
        if src == p['ref_src']:
            p['ab_count'] += count; p['ab_amt'] += amt
        else:
            p['ba_count'] += count; p['ba_amt'] += amt
    rows = []
    for p in pairs.values():
        if p['ab_amt'] >= p['ba_amt']:
            from_uen, to_uen = p['ref_src'], p['ref_tgt']
            ab_c, ab_a, ba_c, ba_a = p['ab_count'], p['ab_amt'], p['ba_count'], p['ba_amt']
            net = ab_a - ba_a
        else:
            from_uen, to_uen = p['ref_tgt'], p['ref_src']
            ab_c, ab_a, ba_c, ba_a = p['ba_count'], p['ba_amt'], p['ab_count'], p['ab_amt']
            net = ba_a - ab_a
        rows.append({
            'from_uen'           : from_uen,
            'to_uen'             : to_uen,
            '_payment_ab_count'  : ab_c,
            '_payment_ab_amt'    : round(ab_a, 2),
            '_payment_ba_count'  : ba_c,
            '_payment_ba_amt'    : round(ba_a, 2),
            '_payment_total_count': ab_c + ba_c,
            '_payment_net_amt'   : round(net, 2),
            '_width'             : 1.0,
        })
    if rows:
        widths = _bin_widths([r['_payment_net_amt'] for r in rows])
        for i, r in enumerate(rows): r['_width'] = widths[i]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        'from_uen','to_uen','_payment_ab_count','_payment_ab_amt',
        '_payment_ba_count','_payment_ba_amt','_payment_total_count','_payment_net_amt','_width'
    ])

payment_directed_edges_df_full     = _payment_directed_from_filter(payment_df)
payment_directed_edges_df_filtered = _payment_directed_from_filter(payment_df_filtered_per_direction)
print(f"  payment_directed_edges_df_full:     {len(payment_directed_edges_df_full):,}")
print(f"  payment_directed_edges_df_filtered: {len(payment_directed_edges_df_filtered):,}")

# ── Self-loop edges per source ───────────────────────────────────────────────
def _self_loops(edges_df_in, count_col='txn_count', amt_col='txn_amt'):
    df = edges_df_in.assign(
        SOURCE_UEN=edges_df_in['SOURCE_UEN'].astype(str).str.strip(),
        TARGET_UEN=edges_df_in['TARGET_UEN'].astype(str).str.strip(),
    )
    self_df = df[(df['SOURCE_UEN'] == df['TARGET_UEN']) & (~df['SOURCE_UEN'].isin(_INVALID_IDS))]
    if len(self_df) == 0:
        return pd.DataFrame(columns=['uen','count','amt'])
    return (self_df.groupby('SOURCE_UEN')
            .agg(count=(count_col,'sum'), amt=(amt_col,'sum'))
            .reset_index()
            .rename(columns={'SOURCE_UEN':'uen'}))

tt_selfloop_raw   = _self_loops(tt_edges_df)
# FAST/GIRO self-loops live in source.selfloop_edges_df with prefixed columns.
def _norm_fg_self(fg_self_df):
    if fg_self_df is None or len(fg_self_df) == 0:
        return pd.DataFrame(columns=['uen','count','amt'])
    cols = list(fg_self_df.columns)
    cnt_col = next(c for c in cols if c.endswith('_count'))
    amt_col = next(c for c in cols if c.endswith('_amt'))
    return fg_self_df.rename(columns={cnt_col: 'count', amt_col: 'amt'})[['uen','count','amt']]

fast_selfloop_raw = _norm_fg_self(fast_source.selfloop_edges_df)
giro_selfloop_raw = _norm_fg_self(giro_source.selfloop_edges_df)

# FITAS self-loops -- derived from fitas_source.edges_df where SOURCE == TARGET.
fitas_selfloop_raw = _self_loops(fitas_source.edges_df)

# Payment self-loop (TT + FAST + GIRO -- excludes FITAS) -- per-uen totals
# used by the side panel's Payment Transactions Summary accordion.
payment_self = (
    pd.concat([
        tt_selfloop_raw.assign(src='TT'),
        fast_selfloop_raw.assign(src='FAST'),
        giro_selfloop_raw.assign(src='GIRO'),
    ], ignore_index=True)
    .groupby('uen', as_index=False)
    .agg(_payment_count=('count','sum'), _payment_amt=('amt','sum'))
)
payment_selfloop_edges_df_full     = payment_self.copy()
payment_selfloop_edges_df_filtered = payment_self[
    payment_self['_payment_amt'].fillna(0).astype(float) >= THRESHOLD_TXN_SGD
].copy()

# FITAS self-loop (FITAS only) -- per-uen totals used by the side panel's
# Trade Transactions (FITAS) Summary accordion.
fitas_self_summary = fitas_selfloop_raw.rename(
    columns={'count': '_fitas_count', 'amt': '_fitas_amt'}
).copy()
fitas_selfloop_edges_df_full     = fitas_self_summary.copy()
fitas_selfloop_edges_df_filtered = fitas_self_summary[
    fitas_self_summary['_fitas_amt'].fillna(0).astype(float) >= THRESHOLD_TXN_SGD
].copy()

# All Transactions self-loop = sum per UEN across TT + FAST + GIRO + FITAS.
# Used by the visual self-loop edge in the graph and the new All
# Transactions Summary accordion.
all_txn_self = (
    pd.concat([
        tt_selfloop_raw.assign(src='TT'),
        fast_selfloop_raw.assign(src='FAST'),
        giro_selfloop_raw.assign(src='GIRO'),
        fitas_selfloop_raw.assign(src='FITAS'),
    ], ignore_index=True)
    .groupby('uen', as_index=False)
    .agg(_all_txn_count=('count','sum'), _all_txn_amt=('amt','sum'))
)
all_txn_selfloop_edges_df_full     = all_txn_self.copy()
all_txn_selfloop_edges_df_filtered = all_txn_self[
    all_txn_self['_all_txn_amt'].fillna(0).astype(float) >= THRESHOLD_TXN_SGD
].copy()

# Keep TT-only legacy selfloop dataframes for backwards compat (Recipe 3 reads).
selfloop_edges_df = tt_selfloop_raw.rename(columns={'count':'_tt_count','amt':'_tt_amt'})
selfloop_edges_df_filtered = selfloop_edges_df[
    selfloop_edges_df['_tt_amt'].fillna(0).astype(float) >= THRESHOLD_TXN_SGD
].copy()

print(f"  all_txn_selfloop_edges_df_filtered: {len(all_txn_selfloop_edges_df_filtered):,}")
print(f"  selfloop_edges_df (TT-only legacy): {len(selfloop_edges_df):,}")

# Sanity: 3 sample (src,tgt) pairs where TT-alone < 5000 but Payment >= 5000
sample = payment_df[
    (payment_df['_tt_amt'].fillna(0) < THRESHOLD_TXN_SGD) &
    (payment_df['txn_amt']            >= THRESHOLD_TXN_SGD)
].head(3)
print("\nSample pairs lifted past threshold by FAST+GIRO:")
print(sample[['SOURCE_UEN','TARGET_UEN','_tt_amt','_fast_amt','_giro_amt','txn_amt']].to_string(index=False))

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 10b: Build Buyer-Supplier Relationship Table
# Uses FITAS > AA Paper > TT > RSME priority chain.
# relationship_df: one row per unique pair, used by Recipe 3 Excel sheet
# and downstream by viz when consolidated edge rendering is implemented.

print("\n" + "="*60)
print("BUILDING BUYER-SUPPLIER RELATIONSHIP TABLE")
print("="*60)

relationship_builder = RelationshipBuilder()
relationship_builder.build(
    rsme_source      = rsme_source,
    consol_tt_source = consol_tt_source,
    fitas_source     = fitas_source,
    aa_paper_source  = aa_paper_source,
    fast_source      = fast_source,
    giro_source      = giro_source,
)
relationship_builder.remap_all_txn_direction()

relationship_df = relationship_builder.relationship_df

print(f"\nrelationship_df: {len(relationship_df):,} pairs, {relationship_df.shape[1]} columns")
print(f"\n  Priority source breakdown:")
print(relationship_df['priority_source'].value_counts().to_string())
print(f"\n  is_both pairs:       {relationship_df['is_both'].sum():,}")
print(f"  Directed pairs:      {relationship_df['is_directed'].sum():,}")
print(f"  Undirected (RSME):   {(~relationship_df['is_directed']).sum():,}")

assert relationship_df.duplicated(subset=['uen_a', 'uen_b']).sum() == 0, \
    "ERROR: duplicate pairs found in relationship_df"
print("\nSanity check passed: no duplicate pairs")

relationship_df.head()

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 11: Build transaction summary per node

print("\n" + "="*60)
print("BUILDING TRANSACTION SUMMARIES")
print("="*60)

enriched_nodes_unique = enriched_nodes.drop_duplicates(subset='UEN', keep='first')

tt_ord = consol_tt_source.edges_df.groupby('SOURCE_UEN').agg(
    tt_ord_freq=('txn_count', 'sum'),
    tt_ord_amt =('txn_amt',   'sum'),
)
tt_bene = consol_tt_source.edges_df.groupby('TARGET_UEN').agg(
    tt_bene_freq=('txn_count', 'sum'),
    tt_bene_amt =('txn_amt',   'sum'),
)
tt_summary = (
    enriched_nodes_unique[['UEN']]
    .merge(tt_ord,  left_on='UEN', right_index=True, how='left')
    .merge(tt_bene, left_on='UEN', right_index=True, how='left')
    .fillna(0)
)
tt_summary['tt_net_flow_amt'] = tt_summary['tt_ord_amt'] - tt_summary['tt_bene_amt']

fitas_ord = fitas_source.edges_df.groupby('SOURCE_UEN').agg(
    fitas_ord_freq=('txn_count', 'sum'),
    fitas_ord_amt =('txn_amt',   'sum'),
)
fitas_bene = fitas_source.edges_df.groupby('TARGET_UEN').agg(
    fitas_bene_freq=('txn_count', 'sum'),
    fitas_bene_amt =('txn_amt',   'sum'),
)
fitas_summary = (
    enriched_nodes_unique[['UEN']]
    .merge(fitas_ord,  left_on='UEN', right_index=True, how='left')
    .merge(fitas_bene, left_on='UEN', right_index=True, how='left')
    .fillna(0)
)
fitas_summary['fitas_net_flow_amt'] = fitas_summary['fitas_ord_amt'] - fitas_summary['fitas_bene_amt']

print(f"TT summary:    {len(tt_summary):,} rows")
print(f"FITAS summary: {len(fitas_summary):,} rows")

def _per_source_summary(edges_df_in, prefix):
    """Build per-UEN ord/bene summary for a single-source edges_df."""
    if edges_df_in is None or len(edges_df_in) == 0:
        return pd.DataFrame(columns=['UEN', f'{prefix}_ord_freq', f'{prefix}_ord_amt',
                                     f'{prefix}_bene_freq', f'{prefix}_bene_amt',
                                     f'{prefix}_net_flow_amt'])
    src = edges_df_in.groupby('SOURCE_UEN').agg(
        **{f'{prefix}_ord_freq': ('txn_count','sum'),
           f'{prefix}_ord_amt' : ('txn_amt','sum')})
    tgt = edges_df_in.groupby('TARGET_UEN').agg(
        **{f'{prefix}_bene_freq': ('txn_count','sum'),
           f'{prefix}_bene_amt' : ('txn_amt','sum')})
    out = (enriched_nodes_unique[['UEN']]
           .merge(src, left_on='UEN', right_index=True, how='left')
           .merge(tgt, left_on='UEN', right_index=True, how='left')
           .fillna(0))
    out[f'{prefix}_net_flow_amt'] = out[f'{prefix}_ord_amt'] - out[f'{prefix}_bene_amt']
    return out

fast_summary    = _per_source_summary(fast_source.directed_edges_df, 'fast')
giro_summary    = _per_source_summary(giro_source.directed_edges_df, 'giro')
# Payment = TT + FAST + GIRO (sum the three single-source summaries column-wise)
payment_summary = (
    enriched_nodes_unique[['UEN']]
    .merge(tt_summary[['UEN','tt_ord_freq','tt_ord_amt','tt_bene_freq','tt_bene_amt']],
           on='UEN', how='left')
    .merge(fast_summary[['UEN','fast_ord_freq','fast_ord_amt','fast_bene_freq','fast_bene_amt']],
           on='UEN', how='left')
    .merge(giro_summary[['UEN','giro_ord_freq','giro_ord_amt','giro_bene_freq','giro_bene_amt']],
           on='UEN', how='left')
    .fillna(0)
)
payment_summary['payment_ord_freq']      = payment_summary[['tt_ord_freq','fast_ord_freq','giro_ord_freq']].sum(axis=1).astype(int)
payment_summary['payment_ord_amt']       = payment_summary[['tt_ord_amt','fast_ord_amt','giro_ord_amt']].sum(axis=1)
payment_summary['payment_bene_freq']     = payment_summary[['tt_bene_freq','fast_bene_freq','giro_bene_freq']].sum(axis=1).astype(int)
payment_summary['payment_bene_amt']      = payment_summary[['tt_bene_amt','fast_bene_amt','giro_bene_amt']].sum(axis=1)
payment_summary['payment_net_flow_amt']  = payment_summary['payment_ord_amt'] - payment_summary['payment_bene_amt']
payment_summary = payment_summary[['UEN','payment_ord_freq','payment_ord_amt','payment_bene_freq','payment_bene_amt','payment_net_flow_amt']]

# All Transactions = FITAS + Payment (no self-transfer for FITAS — only ord/bene)
all_txn_summary = (
    enriched_nodes_unique[['UEN']]
    .merge(fitas_summary[['UEN','fitas_ord_freq','fitas_ord_amt','fitas_bene_freq','fitas_bene_amt']], on='UEN', how='left')
    .merge(payment_summary[['UEN','payment_ord_freq','payment_ord_amt','payment_bene_freq','payment_bene_amt']], on='UEN', how='left')
    .fillna(0)
)
all_txn_summary['all_txn_ord_freq']     = all_txn_summary['fitas_ord_freq'].astype(int)  + all_txn_summary['payment_ord_freq'].astype(int)
all_txn_summary['all_txn_ord_amt']      = all_txn_summary['fitas_ord_amt']  + all_txn_summary['payment_ord_amt']
all_txn_summary['all_txn_bene_freq']    = all_txn_summary['fitas_bene_freq'].astype(int) + all_txn_summary['payment_bene_freq'].astype(int)
all_txn_summary['all_txn_bene_amt']     = all_txn_summary['fitas_bene_amt'] + all_txn_summary['payment_bene_amt']
all_txn_summary['all_txn_net_flow_amt'] = all_txn_summary['all_txn_ord_amt'] - all_txn_summary['all_txn_bene_amt']
all_txn_summary = all_txn_summary[['UEN','all_txn_ord_freq','all_txn_ord_amt','all_txn_bene_freq','all_txn_bene_amt','all_txn_net_flow_amt']]

print(f"FAST summary:    {len(fast_summary):,}")
print(f"GIRO summary:    {len(giro_summary):,}")
print(f"Payment summary: {len(payment_summary):,}")
print(f"All Txn summary: {len(all_txn_summary):,}")

all_txn_latest_date = max(filter(None, [
    consol_tt_source.tt_latest_date,
    fitas_source.fitas_latest_date,
    fast_source.fg_latest_date,
    giro_source.fg_latest_date,
]), default=None)

# ── Filtered per-source summaries (for Recipe 2 'filtered' HTML side panel) ──
# Each uses the same `_per_source_summary` helper but feeds in the threshold-
# filtered edges. Threshold = Payment combined per direction; FITAS edges are
# unfiltered (no payment threshold applies to trade finance).

# Build per-direction filtered edge frames per source from payment_df_filtered_per_direction
# (built in Cell 10). For each surviving (src,tgt) row we know the per-source breakdown.
_pay_filt = payment_df_filtered_per_direction[[
    'SOURCE_UEN','TARGET_UEN','_tt_count','_tt_amt','_fast_count','_fast_amt','_giro_count','_giro_amt'
]].copy()

tt_edges_filtered = (
    _pay_filt[_pay_filt['_tt_count'] > 0]
        .rename(columns={'_tt_count': 'txn_count', '_tt_amt': 'txn_amt'})
        [['SOURCE_UEN','TARGET_UEN','txn_count','txn_amt']]
        .reset_index(drop=True)
)
fast_edges_filtered = (
    _pay_filt[_pay_filt['_fast_count'] > 0]
        .rename(columns={'_fast_count': 'txn_count', '_fast_amt': 'txn_amt'})
        [['SOURCE_UEN','TARGET_UEN','txn_count','txn_amt']]
        .reset_index(drop=True)
)
giro_edges_filtered = (
    _pay_filt[_pay_filt['_giro_count'] > 0]
        .rename(columns={'_giro_count': 'txn_count', '_giro_amt': 'txn_amt'})
        [['SOURCE_UEN','TARGET_UEN','txn_count','txn_amt']]
        .reset_index(drop=True)
)
payment_edges_filtered = (
    payment_df_filtered_per_direction[['SOURCE_UEN','TARGET_UEN','txn_count','txn_amt']]
        .reset_index(drop=True)
)

tt_summary_filtered      = _per_source_summary(tt_edges_filtered,      'tt')
fast_summary_filtered    = _per_source_summary(fast_edges_filtered,    'fast')
giro_summary_filtered    = _per_source_summary(giro_edges_filtered,    'giro')
payment_summary_filtered = _per_source_summary(payment_edges_filtered, 'payment')
fitas_summary_filtered   = fitas_summary.copy()    # FITAS not filtered by payment threshold

# All Txn filtered = FITAS (unfiltered) + Payment (filtered)
all_txn_summary_filtered = (
    enriched_nodes_unique[['UEN']]
    .merge(fitas_summary_filtered[['UEN','fitas_ord_freq','fitas_ord_amt','fitas_bene_freq','fitas_bene_amt']],   on='UEN', how='left')
    .merge(payment_summary_filtered[['UEN','payment_ord_freq','payment_ord_amt','payment_bene_freq','payment_bene_amt']], on='UEN', how='left')
    .fillna(0)
)
all_txn_summary_filtered['all_txn_ord_freq']     = all_txn_summary_filtered['fitas_ord_freq'].astype(int)  + all_txn_summary_filtered['payment_ord_freq'].astype(int)
all_txn_summary_filtered['all_txn_ord_amt']      = all_txn_summary_filtered['fitas_ord_amt']  + all_txn_summary_filtered['payment_ord_amt']
all_txn_summary_filtered['all_txn_bene_freq']    = all_txn_summary_filtered['fitas_bene_freq'].astype(int) + all_txn_summary_filtered['payment_bene_freq'].astype(int)
all_txn_summary_filtered['all_txn_bene_amt']     = all_txn_summary_filtered['fitas_bene_amt'] + all_txn_summary_filtered['payment_bene_amt']
all_txn_summary_filtered['all_txn_net_flow_amt'] = all_txn_summary_filtered['all_txn_ord_amt'] - all_txn_summary_filtered['all_txn_bene_amt']
all_txn_summary_filtered = all_txn_summary_filtered[
    ['UEN','all_txn_ord_freq','all_txn_ord_amt','all_txn_bene_freq','all_txn_bene_amt','all_txn_net_flow_amt']
]

print(f"Filtered summaries built: tt={len(tt_summary_filtered):,}, "
      f"fast={len(fast_summary_filtered):,}, giro={len(giro_summary_filtered):,}, "
      f"payment={len(payment_summary_filtered):,}, all_txn={len(all_txn_summary_filtered):,}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 12: Calculate metric ranges

print("\n" + "="*60)
print("CALCULATING METRIC RANGES")
print("="*60)

consol_tt_metric_ranges = {
    'connections': {
        'min': int(min(consol_tt_source.degree_map.values()) if consol_tt_source.degree_map else 0),
        'max': int(max(consol_tt_source.degree_map.values()) if consol_tt_source.degree_map else 0),
    },
}

fitas_metric_ranges = {
    'connections': {
        'min': int(min(fitas_source.degree_map.values()) if fitas_source.degree_map else 0),
        'max': int(max(fitas_source.degree_map.values()) if fitas_source.degree_map else 0),
    },
}

print(f"TT connections:    {consol_tt_metric_ranges['connections']['min']}-{consol_tt_metric_ranges['connections']['max']}")
print(f"FITAS connections: {fitas_metric_ranges['connections']['min']}-{fitas_metric_ranges['connections']['max']}")

def _conn_range(src):
    if not src.degree_map:
        return {'min': 0, 'max': 0}
    return {'min': int(min(src.degree_map.values())), 'max': int(max(src.degree_map.values()))}

fast_metric_ranges    = {'connections': _conn_range(fast_source)}
giro_metric_ranges    = {'connections': _conn_range(giro_source)}

# Payment combined degree map
_payment_degree = {}
for nid in (set(consol_tt_source.degree_map) | set(fast_source.degree_map) | set(giro_source.degree_map)):
    _payment_degree[nid] = (
        consol_tt_source.degree_map.get(nid, 0) +
        fast_source.degree_map.get(nid, 0) +
        giro_source.degree_map.get(nid, 0)
    )
payment_metric_ranges = {
    'connections': {'min': int(min(_payment_degree.values()) if _payment_degree else 0),
                    'max': int(max(_payment_degree.values()) if _payment_degree else 0)},
}
all_txn_metric_ranges = payment_metric_ranges  # FITAS doesn't shift node sizing range materially

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 13: Build Node Info Dataset

print("\n" + "="*60)
print("BUILDING NODE INFO DATASET")
print("="*60)

rsme_uens_final     = set(rsme_nodes_df['UEN'].tolist())
tt_uens_final       = set(tt_nodes_df['UEN'].tolist())
fitas_uens_final    = set(fitas_nodes_df['UEN'].tolist())
aa_paper_uens_final = set(aa_paper_nodes_df['UEN'].tolist())
fast_uens_final     = set(fast_nodes_df['UEN'].tolist())
giro_uens_final     = set(giro_nodes_df['UEN'].tolist())

enriched_lookup   = enriched_nodes.set_index('UEN').to_dict('index')
tt_flow_lookup    = tt_summary.set_index('UEN').to_dict('index')
fitas_flow_lookup = fitas_summary.set_index('UEN').to_dict('index')

all_sources_raw = pd.concat([
    rsme_nodes_df[['UEN', 'source_name', 'source_country']],
    tt_nodes_df[['UEN', 'source_name', 'source_country']],
    fitas_nodes_df[['UEN', 'source_name', 'source_country']],
    aa_paper_nodes_df[['UEN', 'source_name', 'source_country']],
], ignore_index=True)

all_nodes_lookup = (
    all_sources_raw
    .replace('', pd.NA)
    .groupby('UEN')
    .first()
    .fillna('')
    .to_dict('index')
)

cust_type_lookup = (
    enriched_nodes
    .set_index('UEN')['CUST_TYPE']
    .fillna('Non-Maybank Customer')
    .to_dict()
)

TRADE     = 'Maybank Trade Customer'
NON_TRADE = 'Maybank Non-Trade Customer'
NON_MB    = 'Non-Maybank Customer'

def count_by_type(nid_set):
    counts = {TRADE: 0, NON_TRADE: 0, NON_MB: 0}
    for nb in nid_set:
        counts[cust_type_lookup.get(nb, NON_MB)] += 1
    return counts

def get_node_source(nid):
    sources = []
    if nid in rsme_uens_final:     sources.append('RSME')
    if nid in tt_uens_final:       sources.append('TT')
    if nid in fast_uens_final:     sources.append('FAST')
    if nid in giro_uens_final:     sources.append('GIRO')
    if nid in fitas_uens_final:    sources.append('FITAS')
    if nid in aa_paper_uens_final: sources.append('AA')
    return '+'.join(sources) if sources else 'Unknown'

print("Building node rows...")
node_info_rows = []

# Pre-build per-uen self-loop lookup dicts -- avoids O(N) linear scan
# inside the loop below for each of N nodes (was O(N^2)).
_fast_self_lkp = {str(r['uen']): r for r in fast_source.selfloop_edges_df.to_dict('records')}
_giro_self_lkp = {str(r['uen']): r for r in giro_source.selfloop_edges_df.to_dict('records')}
_tt_self_lkp   = {str(r['uen']): r for r in selfloop_edges_df.to_dict('records')}

# ── PRECOMPUTE: vectorized count_by_type per network ──────────────────────
# Old code called count_by_type() 9x per node inside the loop AND rebuilt
# fast/giro/payment/all_txn flow lookups via set_index().to_dict('index')
# once PER NODE -- O(N^2) at 100k. Fix: hoist all of that out, replace the
# inner Python loops with a single pandas groupby per network.
print("  Precomputing per-network neighbour sets and counts...")

def _build_neighbours(out_adj, in_adj=None):
    """Return {uen: set(neighbours)} from one or two adjacency dicts."""
    out = {}
    for uen, nbs in out_adj.items():
        out[uen] = set(nbs)
    if in_adj is not None:
        for uen, nbs in in_adj.items():
            if uen in out:
                out[uen].update(nbs)
            else:
                out[uen] = set(nbs)
    return out

_rsme_nbrs  = {uen: set(rsme_adjacency.get(uen, [])) for uen in all_uens}
_tt_nbrs    = _build_neighbours(consol_tt_source.out_adj, consol_tt_source.in_adj)
_fitas_nbrs = _build_neighbours(fitas_source.out_adj,     fitas_source.in_adj)
_aa_nbrs    = _build_neighbours(aa_paper_source.out_adj,  aa_paper_source.in_adj)
_fast_nbrs  = _build_neighbours(fast_source.out_adj,      fast_source.in_adj)
_giro_nbrs  = _build_neighbours(giro_source.out_adj,      giro_source.in_adj)

# Derived union sets (per node)
_payment_nbrs = {}
_all_txn_nbrs = {}
_total_nbrs   = {}
_EMPTY = set()
for nid in all_uens:
    rs = _rsme_nbrs.get(nid,  _EMPTY)
    ts = _tt_nbrs.get(nid,    _EMPTY)
    fs = _fitas_nbrs.get(nid, _EMPTY)
    aa = _aa_nbrs.get(nid,    _EMPTY)
    fa = _fast_nbrs.get(nid,  _EMPTY)
    gi = _giro_nbrs.get(nid,  _EMPTY)
    pay = ts | fa | gi
    _payment_nbrs[nid] = pay
    _all_txn_nbrs[nid] = pay | fs
    _total_nbrs[nid]   = rs | ts | fs | aa | fa | gi

# Degree lookups (just len) -- replaces len(neighbours) inside the loop
_rsme_deg    = {k: len(v) for k, v in _rsme_nbrs.items()}
_tt_deg      = {k: len(v) for k, v in _tt_nbrs.items()}
_fitas_deg   = {k: len(v) for k, v in _fitas_nbrs.items()}
_aa_deg      = {k: len(v) for k, v in _aa_nbrs.items()}
_fast_deg    = {k: len(v) for k, v in _fast_nbrs.items()}
_giro_deg    = {k: len(v) for k, v in _giro_nbrs.items()}
_total_deg   = {k: len(v) for k, v in _total_nbrs.items()}
_payment_deg = {k: len(v) for k, v in _payment_nbrs.items()}
_all_txn_deg = {k: len(v) for k, v in _all_txn_nbrs.items()}

def _precompute_counts(adj_sets):
    """Vectorized count_by_type. Returns {uen: (trade, non_trade, non_mb)}."""
    rows_uen, rows_nb = [], []
    for uen, nbs in adj_sets.items():
        if not nbs:
            continue
        rows_uen.extend([uen] * len(nbs))
        rows_nb.extend(nbs)
    if not rows_uen:
        return {}
    df = pd.DataFrame({'UEN': rows_uen, 'NB': rows_nb})
    df['ct'] = df['NB'].map(cust_type_lookup).fillna(NON_MB)
    counts = df.groupby(['UEN', 'ct']).size().unstack(fill_value=0)
    for c in (TRADE, NON_TRADE, NON_MB):
        if c not in counts.columns:
            counts[c] = 0
    counts = counts[[TRADE, NON_TRADE, NON_MB]]
    arr = counts.to_numpy()
    idx = counts.index.tolist()
    return {idx[i]: (int(arr[i, 0]), int(arr[i, 1]), int(arr[i, 2])) for i in range(len(idx))}

_rsme_cbt    = _precompute_counts(_rsme_nbrs)
_tt_cbt      = _precompute_counts(_tt_nbrs)
_fitas_cbt   = _precompute_counts(_fitas_nbrs)
_aa_cbt      = _precompute_counts(_aa_nbrs)
_fast_cbt    = _precompute_counts(_fast_nbrs)
_giro_cbt    = _precompute_counts(_giro_nbrs)
_total_cbt   = _precompute_counts(_total_nbrs)
_payment_cbt = _precompute_counts(_payment_nbrs)
_all_txn_cbt = _precompute_counts(_all_txn_nbrs)

# Free memory -- the neighbour sets aren't needed once cbt + deg are built
del _rsme_nbrs, _tt_nbrs, _fitas_nbrs, _aa_nbrs, _fast_nbrs, _giro_nbrs
del _payment_nbrs, _all_txn_nbrs, _total_nbrs

# Hoisted flow lookups (was rebuilt PER NODE inside the loop -- O(N^2) killer)
_fast_flow_lookup    = fast_summary.set_index('UEN').to_dict('index')
_giro_flow_lookup    = giro_summary.set_index('UEN').to_dict('index')
_payment_flow_lookup = payment_summary.set_index('UEN').to_dict('index')
_all_txn_flow_lookup = all_txn_summary.set_index('UEN').to_dict('index')

_ZERO_CBT = (0, 0, 0)
print("  Precomputation done; entering per-node assembly loop...")

for i, nid in enumerate(all_uens):
    if i % 10000 == 0:
        print(f"  {i:,}/{len(all_uens):,}...")

    meta        = enriched_lookup.get(nid, {})
    source_info = all_nodes_lookup.get(nid, {})

    rsme_t,    rsme_n,    rsme_m    = _rsme_cbt.get(nid,    _ZERO_CBT)
    tt_t,      tt_n,      tt_m      = _tt_cbt.get(nid,      _ZERO_CBT)
    fitas_t,   fitas_n,   fitas_m   = _fitas_cbt.get(nid,   _ZERO_CBT)
    aa_t,      aa_n,      aa_m      = _aa_cbt.get(nid,      _ZERO_CBT)
    total_t,   total_n,   total_m   = _total_cbt.get(nid,   _ZERO_CBT)
    fast_t,    fast_n,    fast_m    = _fast_cbt.get(nid,    _ZERO_CBT)
    giro_t,    giro_n,    giro_m    = _giro_cbt.get(nid,    _ZERO_CBT)
    pay_t,     pay_n,     pay_m     = _payment_cbt.get(nid, _ZERO_CBT)
    all_t,     all_n,     all_m     = _all_txn_cbt.get(nid, _ZERO_CBT)

    tt_flow      = tt_flow_lookup.get(nid, {})
    fitas_flow   = fitas_flow_lookup.get(nid, {})
    fast_flow    = _fast_flow_lookup.get(nid, {})
    giro_flow    = _giro_flow_lookup.get(nid, {})
    payment_flow = _payment_flow_lookup.get(nid, {})
    all_txn_flow = _all_txn_flow_lookup.get(nid, {})

    row = {
        'UEN'           : nid,
        'source_name'   : source_info.get('source_name', ''),
        'source_country': source_info.get('source_country', ''),
        'node_source'   : get_node_source(nid),

        'source_rsme'    : 1 if nid in rsme_uens_final     else 0,
        'source_tt'      : 1 if nid in tt_uens_final       else 0,
        'source_fitas'   : 1 if nid in fitas_uens_final    else 0,
        'source_aa_paper': 1 if nid in aa_paper_uens_final else 0,

        'CUST_TYPE'            : meta.get('CUST_TYPE', 'Non-Maybank Customer'),
        'FINAL_CLASSIFICATION' : meta.get('FINAL_CLASSIFICATION', ''),
        'IS_MAYBANK_CUSTOMER'  : meta.get('IS_MAYBANK_CUSTOMER', 0),
        'CIF_NO'               : meta.get('CIF_NO', ''),

        'rsme_degree_trade_mb'    : rsme_t,
        'rsme_degree_non_trade_mb': rsme_n,
        'rsme_degree_non_mb'      : rsme_m,
        'rsme_degree_total'       : _rsme_deg.get(nid, 0),

        'tt_degree_trade_mb'    : tt_t,
        'tt_degree_non_trade_mb': tt_n,
        'tt_degree_non_mb'      : tt_m,
        'tt_degree_total'       : _tt_deg.get(nid, 0),

        'fitas_degree_trade_mb'    : fitas_t,
        'fitas_degree_non_trade_mb': fitas_n,
        'fitas_degree_non_mb'      : fitas_m,
        'fitas_degree_total'       : _fitas_deg.get(nid, 0),

        'aa_degree_trade_mb'    : aa_t,
        'aa_degree_non_trade_mb': aa_n,
        'aa_degree_non_mb'      : aa_m,
        'aa_degree_total'       : _aa_deg.get(nid, 0),

        'total_degree_trade_mb'    : total_t,
        'total_degree_non_trade_mb': total_n,
        'total_degree_non_mb'      : total_m,
        'total_degree_total'       : _total_deg.get(nid, 0),

        'tt_ord_freq'      : tt_flow.get('tt_ord_freq', 0),
        'tt_ord_amt'       : tt_flow.get('tt_ord_amt', 0),
        'tt_bene_freq'     : tt_flow.get('tt_bene_freq', 0),
        'tt_bene_amt'      : tt_flow.get('tt_bene_amt', 0),
        'tt_net_flow_amt'  : tt_flow.get('tt_net_flow_amt', 0),

        'fitas_ord_freq'    : fitas_flow.get('fitas_ord_freq', 0),
        'fitas_ord_amt'     : fitas_flow.get('fitas_ord_amt', 0),
        'fitas_bene_freq'   : fitas_flow.get('fitas_bene_freq', 0),
        'fitas_bene_amt'    : fitas_flow.get('fitas_bene_amt', 0),
        'fitas_net_flow_amt': fitas_flow.get('fitas_net_flow_amt', 0),
    }

    row.update({
        'source_fast'  : 1 if nid in fast_uens_final else 0,
        'source_giro'  : 1 if nid in giro_uens_final else 0,

        # Latest record dates (global per source -- same value on every row).
        'tt_yr'        : (consol_tt_source.tt_latest_date or ''),
        'fitas_yr'     : (fitas_source.fitas_latest_date  or ''),
        'fast_yr'      : (fast_source.fg_latest_date      or ''),
        'giro_yr'      : (giro_source.fg_latest_date      or ''),
        'all_txn_yr'   : (all_txn_latest_date             or ''),

        'fast_degree_trade_mb'    : fast_t,
        'fast_degree_non_trade_mb': fast_n,
        'fast_degree_non_mb'      : fast_m,
        'fast_degree_total'       : _fast_deg.get(nid, 0),
        'giro_degree_trade_mb'    : giro_t,
        'giro_degree_non_trade_mb': giro_n,
        'giro_degree_non_mb'      : giro_m,
        'giro_degree_total'       : _giro_deg.get(nid, 0),
        'payment_degree_trade_mb'    : pay_t,
        'payment_degree_non_trade_mb': pay_n,
        'payment_degree_non_mb'      : pay_m,
        'payment_degree_total'       : _payment_deg.get(nid, 0),
        'all_txn_degree_trade_mb'    : all_t,
        'all_txn_degree_non_trade_mb': all_n,
        'all_txn_degree_non_mb'      : all_m,
        'all_txn_degree_total'       : _all_txn_deg.get(nid, 0),

        'fast_ord_freq'      : fast_flow.get('fast_ord_freq', 0),
        'fast_ord_amt'       : fast_flow.get('fast_ord_amt', 0),
        'fast_bene_freq'     : fast_flow.get('fast_bene_freq', 0),
        'fast_bene_amt'      : fast_flow.get('fast_bene_amt', 0),
        'fast_net_flow_amt'  : fast_flow.get('fast_net_flow_amt', 0),
        'giro_ord_freq'      : giro_flow.get('giro_ord_freq', 0),
        'giro_ord_amt'       : giro_flow.get('giro_ord_amt', 0),
        'giro_bene_freq'     : giro_flow.get('giro_bene_freq', 0),
        'giro_bene_amt'      : giro_flow.get('giro_bene_amt', 0),
        'giro_net_flow_amt'  : giro_flow.get('giro_net_flow_amt', 0),
        'payment_ord_freq'      : payment_flow.get('payment_ord_freq', 0),
        'payment_ord_amt'       : payment_flow.get('payment_ord_amt', 0),
        'payment_bene_freq'     : payment_flow.get('payment_bene_freq', 0),
        'payment_bene_amt'      : payment_flow.get('payment_bene_amt', 0),
        'payment_net_flow_amt'  : payment_flow.get('payment_net_flow_amt', 0),
        'all_txn_ord_freq'      : all_txn_flow.get('all_txn_ord_freq', 0),
        'all_txn_ord_amt'       : all_txn_flow.get('all_txn_ord_amt', 0),
        'all_txn_bene_freq'     : all_txn_flow.get('all_txn_bene_freq', 0),
        'all_txn_bene_amt'      : all_txn_flow.get('all_txn_bene_amt', 0),
        'all_txn_net_flow_amt'  : all_txn_flow.get('all_txn_net_flow_amt', 0),
    })

    # Self-transfer (per-UEN aggregate from each source's selfloop frame)
    fst = _fast_self_lkp.get(nid)
    gst = _giro_self_lkp.get(nid)
    row['fast_self_transfer_count'] = int(fst.get('_fast_count', 0)) if fst else 0
    row['fast_self_transfer_amt']   = float(fst.get('_fast_amt',   0)) if fst else 0
    row['giro_self_transfer_count'] = int(gst.get('_giro_count', 0)) if gst else 0
    row['giro_self_transfer_amt']   = float(gst.get('_giro_amt',   0)) if gst else 0
    # tt_self_transfer_* sourced from selfloop_edges_df (TT-only legacy)
    tt_self_row = _tt_self_lkp.get(nid)
    row['tt_self_transfer_count'] = int(tt_self_row.get('_tt_count', 0)) if tt_self_row else 0
    row['tt_self_transfer_amt']   = float(tt_self_row.get('_tt_amt',   0)) if tt_self_row else 0
    row['payment_self_transfer_count'] = (
        row['tt_self_transfer_count'] + row['fast_self_transfer_count'] + row['giro_self_transfer_count']
    )
    row['payment_self_transfer_amt']   = (
        row['tt_self_transfer_amt']   + row['fast_self_transfer_amt']   + row['giro_self_transfer_amt']
    )

    # Append all FIELD_CONFIG fields from enriched meta
    # *** updated | now includes MFI and CIP fields from config.FIELD_CONFIG
    for k in cfg.FIELD_CONFIG:
        if k not in row:
            row[k] = meta.get(k)

    node_info_rows.append(row)

df_node_info = pd.DataFrame(node_info_rows)

# Sort by All Transactions activity (sent + received) descending so the most
# active entities surface at the top of the report.
if {'all_txn_ord_amt', 'all_txn_bene_amt'}.issubset(df_node_info.columns):
    df_node_info = df_node_info.assign(
        _sort_amt=df_node_info['all_txn_ord_amt'].fillna(0)
                  + df_node_info['all_txn_bene_amt'].fillna(0)
    ).sort_values('_sort_amt', ascending=False, na_position='last') \
     .drop(columns=['_sort_amt']) \
     .reset_index(drop=True)

print(f"Node info: {len(df_node_info):,} rows, {df_node_info.shape[1]} columns")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 14: Save Pickle Cache

print("\n" + "="*60)
print("SAVING PICKLE CACHE")
print("="*60)

# ── Trim enriched_nodes to match df_node_info ─────────────────────────────
df_node_info_uens     = set(df_node_info['UEN'].astype(str).tolist())
enriched_nodes_before = len(enriched_nodes)
enriched_nodes        = enriched_nodes[
    enriched_nodes['UEN'].astype(str).isin(df_node_info_uens)
].copy()

print(f"  enriched_nodes trimmed: {enriched_nodes_before:,} -> {len(enriched_nodes):,}  "
      f"(removed {enriched_nodes_before - len(enriched_nodes):,} edge-less nodes)")
print(f"  df_node_info:           {len(df_node_info):,}  (matches)")

# ── Pre-filter selfloops by threshold ─────────────────────────────────────
selfloop_edges_df_filtered = selfloop_edges_df[
    selfloop_edges_df['_tt_amt'].fillna(0).astype(float) >= THRESHOLD_TXN_SGD
].copy()

print(f"  selfloop_edges_df:           {len(selfloop_edges_df):,} rows")
print(f"  selfloop_edges_df_filtered:  {len(selfloop_edges_df_filtered):,} rows  "
      f"(removed {len(selfloop_edges_df) - len(selfloop_edges_df_filtered):,} "
      f"below S${THRESHOLD_TXN_SGD:,})")

# ── Save pickle ───────────────────────────────────────────────────────────
cache_data = {
    'rsme_adjacency'             : rsme_adjacency,
    'rsme_degree_map'            : rsme_degree_map,
    'original_sizes_js'          : original_sizes_js,
    'enriched_nodes'             : enriched_nodes,
    'df_node_info'               : df_node_info,
    'rsme_source'                : rsme_source,
    'consol_tt_source'           : consol_tt_source,
    'fitas_source'                : fitas_source,
    'aa_paper_source'            : aa_paper_source,
    'fast_source'                : fast_source,
    'giro_source'                : giro_source,
    'undirected_edges_df'        : undirected_edges_df,
    'directed_edges_df'          : directed_edges_df,
    'directed_edges_df_filtered' : directed_edges_df_filtered,
    'payment_directed_edges_df_full'    : payment_directed_edges_df_full,
    'payment_directed_edges_df_filtered': payment_directed_edges_df_filtered,
    'all_txn_selfloop_edges_df_full'    : all_txn_selfloop_edges_df_full,
    'all_txn_selfloop_edges_df_filtered': all_txn_selfloop_edges_df_filtered,
    'payment_selfloop_edges_df_full'    : payment_selfloop_edges_df_full,
    'payment_selfloop_edges_df_filtered': payment_selfloop_edges_df_filtered,
    'fitas_selfloop_edges_df_full'      : fitas_selfloop_edges_df_full,
    'fitas_selfloop_edges_df_filtered'  : fitas_selfloop_edges_df_filtered,
    'selfloop_edges_df'          : selfloop_edges_df,
    'selfloop_edges_df_filtered' : selfloop_edges_df_filtered,
    'tt_edges_filtered'          : tt_edges_filtered,
    'fast_edges_filtered'        : fast_edges_filtered,
    'giro_edges_filtered'        : giro_edges_filtered,
    'tt_summary'                 : tt_summary,
    'tt_summary_filtered'        : tt_summary_filtered,
    'fitas_summary'              : fitas_summary,
    'fitas_summary_filtered'     : fitas_summary_filtered,
    'fast_summary'               : fast_summary,
    'fast_summary_filtered'      : fast_summary_filtered,
    'giro_summary'               : giro_summary,
    'giro_summary_filtered'      : giro_summary_filtered,
    'payment_summary'            : payment_summary,
    'payment_summary_filtered'   : payment_summary_filtered,
    'all_txn_summary'            : all_txn_summary,
    'all_txn_summary_filtered'   : all_txn_summary_filtered,
    'consol_tt_metric_ranges'    : consol_tt_metric_ranges,
    'fitas_metric_ranges'        : fitas_metric_ranges,
    'fast_metric_ranges'         : fast_metric_ranges,
    'giro_metric_ranges'         : giro_metric_ranges,
    'payment_metric_ranges'      : payment_metric_ranges,
    'all_txn_metric_ranges'      : all_txn_metric_ranges,
    'all_txn_latest_date'        : all_txn_latest_date,
    'threshold_txn_sgd'          : THRESHOLD_TXN_SGD,
    # legacy alias
    'tt_edge_min_amt'            : THRESHOLD_TXN_SGD,
    'relationship_df'            : relationship_df,
    'fitas_product_df'           : fitas_source.fitas_product_df,
}

with pipeline_folder.get_writer('network_cache.pkl') as w:
    # *** updated | protocol 4 (Python 3.4+) gives ~95% of HIGHEST_PROTOCOL's
    # speedup without protocol 5's PickleBuffer (zero-copy buffer object) --
    # Dataiku's managed-folder stream writer raises "PickleBuffer has no
    # len()" on protocol 5. Protocol 4 still supports very large objects via
    # framing and is significantly faster than the default. Stdlib only.
    pickle.dump(cache_data, w, protocol=4)

print("\n" + "="*60)
print("PICKLE SAVED")
print("="*60)
print("enriched_nodes and df_node_info now share the same node set")
print("selfloop_edges_df_filtered pre-built -- no float rounding gap with Excel")
print("relationship_df saved -- one row per pair with priority source and direction")
print("fitas_product_df saved -- per-product breakdown for Excel sheet")
print("MFI and CIP fields embedded in df_node_info via FIELD_CONFIG loop")
print(f"\n  Network Summary:")
print(f"  Nodes:                          {len(df_node_info):,}")
print(f"  Undirected pairs:               {len(undirected_edges_df):,}")
print(f"  Directed pairs (full):          {len(directed_edges_df):,}")
print(f"  Directed pairs (filtered):      {len(directed_edges_df_filtered):,}")
print(f"  TT self-loops (full):           {len(selfloop_edges_df):,}")
print(f"  TT self-loops (filtered):       {len(selfloop_edges_df_filtered):,}")
print(f"  Buyer-Supplier pairs:           {len(relationship_df):,}")
print(f"  Payment threshold (per direction, TT+MEPS+FAST+GIRO combined): S${THRESHOLD_TXN_SGD:,}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 14b: Validation -- threshold-rescue sample pairs

print("\n" + "="*60)
print("VALIDATION: pairs lifted past S$5,000 threshold by FAST+GIRO")
print("="*60)

_v1 = payment_df[
    (payment_df['_tt_amt'].fillna(0) < THRESHOLD_TXN_SGD) &
    (payment_df['txn_amt']            >= THRESHOLD_TXN_SGD)
].head(3)
print(_v1[['SOURCE_UEN','TARGET_UEN','_tt_amt','_fast_amt','_giro_amt','txn_amt']].to_string(index=False) or "  (no examples)")

_v2_uens = (
    set(all_txn_self[all_txn_self['_all_txn_amt'] >= THRESHOLD_TXN_SGD]['uen']) -
    set(selfloop_edges_df_filtered['uen'])
)
print(f"\nSelf-loop UENs only present in Payment-combined (not TT-only): "
      f"{len(_v2_uens):,}; first 2: {sorted(list(_v2_uens))[:2]}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 15: Build Edge Info Dataset

print("\n" + "="*60)
print("BUILDING EDGE INFO DATASET")
print("="*60)

df_edges_info = pd.concat([
    rsme_edges_df.copy(),
    tt_edges_df.copy(),
    fitas_edges_df.copy(),
    aa_paper_edges_df.copy(),
    fast_edges_df.copy(),
    giro_edges_df.copy(),
], ignore_index=True)

# Remove edges with invalid SOURCE_UEN or TARGET_UEN
_before = len(df_edges_info)
df_edges_info['SOURCE_UEN'] = df_edges_info['SOURCE_UEN'].astype(str).str.strip()
df_edges_info['TARGET_UEN'] = df_edges_info['TARGET_UEN'].astype(str).str.strip()
df_edges_info = df_edges_info[
    ~df_edges_info['SOURCE_UEN'].isin(_INVALID_IDS) &
    ~df_edges_info['TARGET_UEN'].isin(_INVALID_IDS)
].copy()
_removed = _before - len(df_edges_info)
if _removed > 0:
    print(f"  Removed {_removed:,} edges with invalid SOURCE_UEN or TARGET_UEN")

print(f"Edge info: {len(df_edges_info):,} rows")
print(df_edges_info['edge_source'].value_counts())

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 16: Build Subnetwork Summary Dataset

print("\n" + "="*60)
print("BUILDING SUBNETWORK SUMMARY")
print("="*60)

subnetwork_summary = pd.DataFrame([
    {'network': 'RSME',            'node_count': len(rsme_uens_final),              'edge_count': len(rsme_edges_df)},
    {'network': 'Consolidated_TT', 'node_count': len(consol_tt_source.active_uens), 'edge_count': len(consol_tt_source.edges_df)},
    {'network': 'FITAS',           'node_count': len(fitas_source.active_uens),     'edge_count': len(fitas_source.edges_df)},
    {'network': 'AA_Paper',        'node_count': len(aa_paper_source.active_uens),  'edge_count': len(aa_paper_source.edges_df)},
    {'network': 'FAST',            'node_count': len(fast_source.active_uens),      'edge_count': len(fast_source.directed_edges_df)},
    {'network': 'GIRO',            'node_count': len(giro_source.active_uens),      'edge_count': len(giro_source.directed_edges_df)},
])

print(subnetwork_summary.to_string(index=False))

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 17: Export datasets to Dataiku

print("\n" + "="*60)
print("EXPORTING DATASETS")
print("="*60)

exporter = DatasetExporter(cfg)
exporter.export_datasets(subnetwork_summary, df_node_info, df_edges_info)

print("\n" + "="*60)
print("RECIPE 1 COMPLETE")
print("="*60)
print("Pickle cache saved (NO NetworkX, NO PyVis, NO neighbor cache)")
print("Consolidated edge tables (undirected/directed/selfloop)")
print("Buyer-Supplier relationship table (relationship_df)")
print("MFI and CIP enrichment applied via Enricher Steps 9 and 10")
print("3 datasets exported to Dataiku")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
import os

base = "/app/dataiku/design/jupyter-run/dku-workdirs/TB_DIGITISATION_OCR/RECIPE_1_Network_Graph_Data_Preparation7f11974f-dssuser_00155690/project-python-libs/TB_DIGITISATION_OCR/python/network_graph"

print("=" * 60)
print("FILE TREE")
print("=" * 60)
for root, dirs, files in os.walk(base):
    dirs.sort()
    depth     = root.replace(base, "").count(os.sep)
    indent    = "    " * depth
    subindent = "    " * (depth + 1)
    print(f"{indent}{os.path.basename(root)}/")
    for f in sorted(files):
        if f.endswith(".py"):
            size = os.path.getsize(os.path.join(root, f))
            print(f"{subindent}{f}  ({size:,} bytes)")

print("\n" + "=" * 60)
print("FILE CONTENTS")
print("=" * 60)
for root, dirs, files in os.walk(base):
    dirs.sort()
    for f in sorted(files):
        if f.endswith(".py"):
            path = os.path.join(root, f)
            rel  = path.replace(base, "network_graph")
            print(f"\n{'#' * 60}")
            print(f"# FILE: {rel}")
            print(f"{'#' * 60}")
            with open(path, "r", encoding="utf-8") as fh:
                print(fh.read())