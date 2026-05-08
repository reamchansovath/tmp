# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Local twin: when DATAIKU_ENV=local, register mock_dataiku as the dataiku
# module so every later `import dataiku` (across all cells) resolves to the
# mock. In Dataiku, DATAIKU_ENV is not set so this block is a no-op.

import os, sys
if os.getenv('DATAIKU_ENV') == 'local':
    import mock_dataiku
    sys.modules['dataiku'] = mock_dataiku


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# | What to change                | Where                                    | Cell   |
# |-------------------------------|------------------------------------------|--------|
# | TT edge filter threshold      | `TT_EDGE_MIN_AMT`                        | Cell 1 |
# | Column order in Excel         | `NODE_SECTIONS` or `EDGE_SECTIONS`       | Cell 4 |
# | Which columns to include      | `NODE_COLS_TO_KEEP` or `EDGE_COLS_TO_KEEP` | Cell 3 |
# | Column display names          | `NODE_RENAME` or `EDGE_RENAME`           | Cell 4 |
# | Section colors                | `NODE_SECTIONS` or `EDGE_SECTIONS`       | Cell 4 |
# | Buyer-Supplier pairs columns  | `PAIRS_RENAME` or `PAIRS_SECTIONS`       | Cell 4 |

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Recipe 3

# Cell 1: Imports, Load Data, and Controls

import dataiku  # type: ignore[import-not-found]
import pandas as pd
import numpy as np
import xlsxwriter
import io
import math
import pickle
from pathlib import Path

THRESHOLD_TXN_SGD = 5_000   # SGD -- per-direction Payment combined (TT+FAST+GIRO)
TT_EDGE_MIN_AMT   = THRESHOLD_TXN_SGD  # legacy alias retained for any in-cell references

NetworkGraph_Node_Info     = dataiku.Dataset("NetworkGraph_Node_Info")
NetworkGraph_Node_Info_df  = NetworkGraph_Node_Info.get_dataframe()
NetworkGraph_Edges_Info    = dataiku.Dataset("NetworkGraph_Edges_Info")
NetworkGraph_Edges_Info_df = NetworkGraph_Edges_Info.get_dataframe()

Network_Graph_Report = dataiku.Folder("rHjCkctR")

pipeline_folder = dataiku.Folder("oSbAKnR6")
with pipeline_folder.get_download_stream('network_cache.pkl') as r:
    _cache = pickle.load(r)

if 'relationship_df' not in _cache:
    raise KeyError(
        "relationship_df not found in pickle. "
        "Re-run Recipe 1 Cell 10b to generate the buyer-supplier relationship table."
    )
_relationship_df_raw = _cache['relationship_df'].copy()
del _cache

print(f"Node Info:          {len(NetworkGraph_Node_Info_df):,} rows, {NetworkGraph_Node_Info_df.shape[1]} cols")
print(f"Edge Info:          {len(NetworkGraph_Edges_Info_df):,} rows, {NetworkGraph_Edges_Info_df.shape[1]} cols")
print(f"Relationship pairs: {len(_relationship_df_raw):,} pairs")
print(f"\nThreshold (per direction, Payment combined): S${THRESHOLD_TXN_SGD:,}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 2: Data Cleaning Functions
# *** updated | added MFI amount cols, MFI ratio cols, MFI string cols, MFI date cols
# *** updated | added CIP amount cols, CIP int cols, CIP date cols
# *** updated | added RATIO_COLS set and clean_ratio() for MFI DCSR/Gearing
# *** updated | added 4 new CIP open/close date cols

AMT_COLS = {
    'TF_LCY_AVAIL_LMT', 'TF_LCY_AUTH_LMT',
    'TF_LCY_TOT_OS', 'TF_LCY_OBS_OS',
    'FIN_SALES_CY', 'FIN_PROF_BEF_TAX_CY', 'FIN_CASH_BANK_BAL_CY',
    'FIN_TRADE_CRED_CY', 'FIN_TRADE_DEPT_CY',
    'tt_ord_amt', 'tt_bene_amt', 'tt_net_flow_amt', 'tt_self_transfer_amt',
    'fitas_ord_amt', 'fitas_bene_amt', 'fitas_total_amt',
    # FAST
    'fast_ord_amt', 'fast_bene_amt', 'fast_net_flow_amt', 'fast_self_transfer_amt', 'fast_total_amt',
    # GIRO
    'giro_ord_amt', 'giro_bene_amt', 'giro_net_flow_amt', 'giro_self_transfer_amt', 'giro_total_amt',
    # Payment
    'payment_ord_amt', 'payment_bene_amt', 'payment_net_flow_amt',
    'payment_self_transfer_amt', 'payment_total_amt',
    # All Transactions (FITAS + Payment)
    'all_txn_ord_amt', 'all_txn_bene_amt', 'all_txn_net_flow_amt', 'all_txn_total_amt',
    # pairs sheet -- per-source buyer/supplier amts
    'fast_buyer_to_supplier_amt', 'fast_supplier_to_buyer_amt',
    'giro_buyer_to_supplier_amt', 'giro_supplier_to_buyer_amt',
    'payment_buyer_to_supplier_amt', 'payment_supplier_to_buyer_amt',
    'all_txn_buyer_to_supplier_amt', 'all_txn_supplier_to_buyer_amt',
    'CASA', 'FD', 'STRCTD', 'DEP_BALANCES', 'TR_LN', 'NONTR_LN', 'LN_BALANCES',
    'EMIS Total Operating Revenue (USD)',
    'EMIS Operating Profit (USD)',
    'EMIS Profit Before Income Tax (USD)',
    'EMIS Total Assets (USD)',
    'EMIS Free Cash Flow (USD)',
    'EMIS Net Cash Flow from Operations (USD)',
    'CHARGE_SECURED_AMOUNT_SGD',
    # *** new | MFI financial amounts (SGD)
    'MFI_SALES', 'MFI_COGS', 'MFI_GROSS_PNL', 'MFI_PRETAX_PNL_BEFORE_INT',
    'MFI_PNL_BEFORE_TAX', 'MFI_PNL_AFT_TAX', 'MFI_TOT_AST', 'MFI_CURR_AST',
    'MFI_NON_CURR_AST', 'MFI_TOT_LBLTY', 'MFI_CURR_LBLTY', 'MFI_NON_CURR_LBLTY',
    'MFI_TOT_EQUITY', 'MFI_ST_DEBT', 'MFI_LT_DEBT', 'MFI_TOTAL_DEBT',
    'MFI_DEBT_SERVICE', 'MFI_EBITDA', 'MFI_TANGIBLE_NET_WORTH', 'MFI_ADJ_TNW',
    # *** new | CIP financial amounts (SGD)
    'CIP_FAC_LIMIT_SGD', 'CIP_LOAN_BALANCE_SGD', 'CIP_NPL_BALANCE_SGD',
    'CIP_SEC_AMT', 'CIP_SEC_EMV', 'CIP_SEC_FSV', 'CIP_SEC_FIV',
}

INT_COLS = {
    'months_on_book', 'delinquency_count_12m',
    'borrower_risk_rating', 'RLTNSHP_TENURE',
    'tt_ord_freq', 'tt_bene_freq', 'tt_self_transfer_count',
    'fitas_ord_freq', 'fitas_bene_freq',
    'fast_ord_freq', 'fast_bene_freq', 'fast_self_transfer_count',
    'giro_ord_freq', 'giro_bene_freq', 'giro_self_transfer_count',
    'payment_ord_freq', 'payment_bene_freq', 'payment_self_transfer_count',
    'all_txn_ord_freq', 'all_txn_bene_freq',
    'fast_degree_total','fast_degree_trade_mb','fast_degree_non_trade_mb','fast_degree_non_mb',
    'giro_degree_total','giro_degree_trade_mb','giro_degree_non_trade_mb','giro_degree_non_mb',
    'payment_degree_total','payment_degree_trade_mb','payment_degree_non_trade_mb','payment_degree_non_mb',
    'all_txn_degree_total','all_txn_degree_trade_mb','all_txn_degree_non_trade_mb','all_txn_degree_non_mb',
    # pairs sheet -- per-source counts
    'fast_buyer_to_supplier_count', 'fast_supplier_to_buyer_count', 'fast_total_count',
    'giro_buyer_to_supplier_count', 'giro_supplier_to_buyer_count', 'giro_total_count',
    'payment_buyer_to_supplier_count', 'payment_supplier_to_buyer_count', 'payment_total_count',
    'all_txn_buyer_to_supplier_count', 'all_txn_supplier_to_buyer_count', 'all_txn_total_count',
    'N_CHARGES', 'N_UNIQUE_CHARGEE',
    'CHARGE_ALLMONIESOWING_Y_COUNT', 'CHARGE_ALLMONIESOWING_N_COUNT',
    # *** new | MFI period length
    'MFI_LENGTH_IN_MTH',
    # *** new | CIP count cols
    'CIP_N_ACC_TOTAL', 'CIP_N_ACC_OPEN', 'CIP_N_ACC_CLOSED',
    'CIP_N_PROPERTIES', 'CIP_JTC_FLAG',
    'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT', 'CIP_PBD_OCCP_TYPE_TENANTED_COUNT',
    'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT', 'CIP_PBD_OCCP_TYPE_VACANT_COUNT',
}

# *** new | MFI ratio cols -- plain decimal (2dp), not currency/integer
RATIO_COLS = {
    'MFI_DCSR',
    'MFI_GEARING',
}

STRING_COLS = {
    'latest_dpd_bucket', 'credit_status', 'impairment_stage', 'RISK_GRADE',
    'current_rating', 'original_rating', 'FINAL_CLASSIFICATION',
    'CNTRY_CODE', 'MAS610_INDST_DESC', 'BIZ_TYP_DESC',
    'facility_risk_rating', 'entity_type_description',
    'entity_status_description', 'entity_name', 'CUST_TYPE',
    'node_source', 'source_country', 'source_name',
    'EMIS Country', 'EMIS Company Name', 'EMIS City', 'EMIS Industry',
    'EMIS Business Description', 'EMIS Key Executives', 'EMIS Export',
    'EMIS Incorporation Date', 'EMIS Number of Employees',
    'EMIS Listed / Unlisted', 'EMIS Company ID',
    'EMIS Audited', 'EMIS Source',
    # *** new | MFI string cols
    'MFI_SEG_DESC', 'MFI_MODEL_NAME', 'MFI_TARGET_CURCY_CODE', 'MFI_BASE_CURCY_CODE',
    'MFI_AUDITOR_NAME', 'MFI_QUALIFIED', 'MFI_STATEMENT_STS', 'MFI_STATEMENT_TYP',
}

FLAG_COLS = {
    'IS_MAYBANK_CUSTOMER', 'is_watchlist', 'is_special_mention', 'is_npl',
    'source_rsme', 'source_tt', 'source_fitas', 'source_aa_paper',
    'source_fast', 'source_giro',
}

DATE_COLS = {
    'original_rating_date', 'rating_date', 'ADT_CREATION_DATE',
    'FIN_FIN_YR_END_CY', 'FIRST_CA_OPN_DTE',
    'EARLIEST_CHARGE_REG_DATE', 'LATEST_CHARGE_REG_DATE',
    # *** new | MFI dates
    'MFI_END_DTE', 'MFI_PROC_DTE',
    # *** new | CIP dates
    'CIP_EARLIEST_AC_OPN_DTE', 'CIP_LATEST_AC_OPN_DTE',
    'CIP_FAC_PROC_DTE', 'CIP_BALANCE_PROC_DTE', 'CIP_LATEST_DEFAULT_DTE',
    # *** new | additional CIP open/close dates
    'EARLIEST_OPEN_AC_OPN_DTE', 'LATEST_OPEN_AC_OPN_DTE',
    'EARLIEST_CLOSED_AC_OPN_DTE', 'LATEST_AC_CLS_DTE',
}

def clean_postal(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    s = str(val).strip().split('.')[0]
    return s.zfill(6) if s and s not in ('nan','None','') else None

def clean_ssic(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    s = str(val).strip().split('.')[0]
    if not s or s in ('nan','None',''): return None
    return s.zfill(5) if s.isdigit() else s

def clean_amt(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    try:    return int(round(float(val)))
    except: return None

def clean_int(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    try:    return int(val)
    except: return None

def clean_ratio(val):
    """For MFI ratio cols (DCSR, Gearing) -- plain decimal rounded to 2dp."""
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    try:    return round(float(val), 2)
    except: return None

def clean_flag(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return 0
    if isinstance(val, bool): return int(val)
    if isinstance(val, (int, float)): return 1 if val else 0
    return 1 if str(val).strip().upper() in ('1','Y','YES','TRUE') else 0

def clean_date(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    try:
        if pd.isna(val): return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, 'strftime'):
        if hasattr(val, 'tzinfo') and val.tzinfo is not None:
            val = val.replace(tzinfo=None)
        return val.strftime('%d %b %Y')
    s = str(val).strip()
    if not s or s in ('nan', 'None', 'NaT', ''): return None
    if ':' in s and len(s) > 9:
        date_part = s.split(':')[0].strip()
        try:    return pd.to_datetime(date_part.title(), format='%d%b%Y').strftime('%d %b %Y')
        except: pass
    if 'T' in s:
        try:    return pd.to_datetime(s).strftime('%d %b %Y')
        except: pass
    if len(s) == 9 and s[2:5].isalpha():
        try:    return pd.to_datetime(s.title(), format='%d%b%Y').strftime('%d %b %Y')
        except: pass
    if '/' in s:
        try:    return pd.to_datetime(s, format='%d/%m/%Y').strftime('%d %b %Y')
        except: pass
    if '-' in s:
        try:    return pd.to_datetime(s).strftime('%d %b %Y')
        except: pass
    try:    return pd.to_datetime(s).strftime('%d %b %Y')
    except: return s

def clean_string(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    s = str(val).strip()
    return s if s and s not in ('nan','None','NaT') else None

def clean_year(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    try:    return str(int(float(val)))
    except: return None

def apply_cleaning(df):
    df_clean = df.copy()
    for col in df_clean.columns:
        if col in AMT_COLS:
            df_clean[col] = df_clean[col].apply(clean_amt)
        elif col in RATIO_COLS:
            # *** new | MFI ratio cols -- plain float, not rounded to int
            df_clean[col] = df_clean[col].apply(clean_ratio)
        elif col in INT_COLS:
            df_clean[col] = df_clean[col].apply(clean_int)
        elif col in FLAG_COLS:
            df_clean[col] = df_clean[col].apply(clean_flag)
        elif col in DATE_COLS:
            df_clean[col] = df_clean[col].apply(clean_date)
        elif col in STRING_COLS:
            df_clean[col] = df_clean[col].apply(clean_string)
        elif col == 'postal_code':
            df_clean[col] = df_clean[col].apply(clean_postal)
        elif col == 'SSIC_CODE':
            df_clean[col] = df_clean[col].apply(clean_ssic)
        elif col == 'EMIS Fiscal Year':
            df_clean[col] = df_clean[col].apply(clean_year)
        elif col == 'CIF_NO':
            df_clean[col] = df_clean[col].apply(clean_string)
    return df_clean

print("Data cleaning functions defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 3: Enrich Edges, Apply Edge-Level Filter, Configure Column Selection
# *** updated | added MFI_COLS_IN_NODE and CIP_COLS_IN_NODE to NODE_COLS_TO_KEEP

_INVALID_IDS = {'', 'nan', 'none', 'None', 'NaN', 'NAN'}

NetworkGraph_Node_Info_df['fitas_total_amt'] = (
    NetworkGraph_Node_Info_df['fitas_ord_amt'].fillna(0) +
    NetworkGraph_Node_Info_df['fitas_bene_amt'].fillna(0)
)

node_lookup = NetworkGraph_Node_Info_df[
    ['UEN', 'source_name', 'FINAL_CLASSIFICATION', 'source_country']
].copy()

edges_enriched = NetworkGraph_Edges_Info_df.merge(
    node_lookup.rename(columns={
        'UEN': 'SOURCE_UEN', 'source_name': 'source_name',
        'FINAL_CLASSIFICATION': 'source_segment', 'source_country': 'source_country',
    }),
    on='SOURCE_UEN', how='left'
)

edges_enriched = edges_enriched.merge(
    node_lookup.rename(columns={
        'UEN': 'TARGET_UEN', 'source_name': 'target_name',
        'FINAL_CLASSIFICATION': 'target_segment', 'source_country': 'target_country',
    }),
    on='TARGET_UEN', how='left'
)

edges_enriched['self_transfer'] = (
    edges_enriched['SOURCE_UEN'] == edges_enriched['TARGET_UEN']
)

# Defensive filter -- remove any leaked invalid UENs from source data
_before_invalid = len(edges_enriched)
edges_enriched = edges_enriched[
    ~edges_enriched['SOURCE_UEN'].astype(str).str.strip().isin(_INVALID_IDS) &
    ~edges_enriched['TARGET_UEN'].astype(str).str.strip().isin(_INVALID_IDS) &
    edges_enriched['SOURCE_UEN'].notna() &
    edges_enriched['TARGET_UEN'].notna()
].copy()
if len(edges_enriched) < _before_invalid:
    print(f"  Removed {_before_invalid - len(edges_enriched):,} edges with invalid UENs")

_all_uens_in_edges = pd.concat([
    NetworkGraph_Edges_Info_df[['SOURCE_UEN']].rename(columns={'SOURCE_UEN': 'UEN'}),
    NetworkGraph_Edges_Info_df[['TARGET_UEN']].rename(columns={'TARGET_UEN': 'UEN'}),
]).drop_duplicates(subset='UEN')

_edge_name_lookup  = _all_uens_in_edges.merge(
    node_lookup[['UEN', 'source_name', 'source_country']], on='UEN', how='left'
)
_edge_name_dict    = _edge_name_lookup.set_index('UEN')['source_name'].to_dict()
_edge_country_dict = _edge_name_lookup.set_index('UEN')['source_country'].to_dict()

edges_enriched['source_name'] = edges_enriched.apply(
    lambda r: r['source_name'] if pd.notna(r['source_name'])
              else _edge_name_dict.get(str(r['SOURCE_UEN']), r['SOURCE_UEN']), axis=1
)
edges_enriched['target_name'] = edges_enriched.apply(
    lambda r: r['target_name'] if pd.notna(r['target_name'])
              else _edge_name_dict.get(str(r['TARGET_UEN']), r['TARGET_UEN']), axis=1
)
edges_enriched['source_country'] = edges_enriched.apply(
    lambda r: r['source_country'] if pd.notna(r['source_country'])
              else _edge_country_dict.get(str(r['SOURCE_UEN']), ''), axis=1
)
edges_enriched['target_country'] = edges_enriched.apply(
    lambda r: r['target_country'] if pd.notna(r['target_country'])
              else _edge_country_dict.get(str(r['TARGET_UEN']), ''), axis=1
)

edges_enriched['source_segment'] = edges_enriched['source_segment'].fillna('Unknown')
edges_enriched['target_segment'] = edges_enriched['target_segment'].fillna('Unknown')
edges_enriched['source_name']    = edges_enriched['source_name'].fillna(edges_enriched['SOURCE_UEN'])
edges_enriched['target_name']    = edges_enriched['target_name'].fillna(edges_enriched['TARGET_UEN'])
edges_enriched['source_country'] = edges_enriched['source_country'].fillna('')
edges_enriched['target_country'] = edges_enriched['target_country'].fillna('')

_check_cols = ['source_name','source_country','source_segment',
               'target_name','target_country','target_segment']
print("  Edge enrichment null check:")
for col in _check_cols:
    print(f"    {col:<20}: {edges_enriched[col].isna().sum():,} nulls")

def create_relationship_desc(row):
    source = row['source_name'] if pd.notna(row['source_name']) else row['SOURCE_UEN']
    target = row['target_name'] if pd.notna(row['target_name']) else row['TARGET_UEN']
    if row['edge_source'] == 'RSME':
        return f"[{source}] declared [{target}] as counterparty"
    elif row['edge_source'] == 'Consolidated_TT':
        if row['self_transfer']:
            return f"[{source}] did TT self-transfer"
        return f"[{source}] did telegraphic transfer to [{target}]"
    elif row['edge_source'] == 'FITAS':
        return f"[{source}] did FITAS transfer to [{target}]"
    elif row['edge_source'] == 'FAST':
        if row['self_transfer']:
            return f"[{source}] did FAST self-transfer"
        return f"[{source}] did FAST payment to [{target}]"
    elif row['edge_source'] == 'GIRO':
        if row['self_transfer']:
            return f"[{source}] did GIRO self-transfer"
        return f"[{source}] did GIRO payment to [{target}]"
    elif row['edge_source'] == 'AA_Paper':
        declarer = row['declarer_name'] if pd.notna(row.get('declarer_name')) else row.get('declarer_uen', row['SOURCE_UEN'])
        declared = row['declared_name'] if pd.notna(row.get('declared_name')) else row.get('declared_uen', row['TARGET_UEN'])
        cpty     = row.get('counterparty_type', '')
        return f"[{declarer}] declared [{declared}] as {cpty}"
    return ""

edges_enriched['relationship_description'] = edges_enriched.apply(
    create_relationship_desc, axis=1
)

_all_ext_uens = (
    set(edges_enriched[~edges_enriched['self_transfer']]['SOURCE_UEN'].astype(str)) |
    set(edges_enriched[~edges_enriched['self_transfer']]['TARGET_UEN'].astype(str))
)
_self_only_uens = (
    set(edges_enriched[edges_enriched['self_transfer']]['SOURCE_UEN'].astype(str))
    - _all_ext_uens
)
print(f"\n  Self-loop-only UENs to remove from edge sheet: {len(_self_only_uens):,}")

edges_full = edges_enriched.copy()
edges_full = edges_full[
    ~(edges_full['self_transfer'].astype(bool) &
      edges_full['SOURCE_UEN'].astype(str).isin(_self_only_uens))
].copy()

full_connected_uens = (
    set(edges_full['SOURCE_UEN'].astype(str)) |
    set(edges_full['TARGET_UEN'].astype(str))
)
nodes_full = NetworkGraph_Node_Info_df[
    NetworkGraph_Node_Info_df['UEN'].astype(str).isin(full_connected_uens)
].copy()

print(f"\n  Full nodes (with edges only): {len(nodes_full):,}  "
      f"(excluded {len(NetworkGraph_Node_Info_df) - len(nodes_full):,} edge-less nodes)")

# Payment per-direction threshold: aggregate (src,tgt) across {Consolidated_TT, FAST, GIRO}
# and drop rows whose pair's combined Payment ab amount < THRESHOLD_TXN_SGD.
_PAYMENT_SOURCES = {'Consolidated_TT', 'FAST', 'GIRO'}
payment_mask = edges_enriched['edge_source'].isin(_PAYMENT_SOURCES)
non_payment_mask = ~payment_mask

# Build per-direction Payment combined sum, keyed by (SOURCE_UEN, TARGET_UEN)
_pay_dir = (
    edges_enriched.loc[payment_mask, ['SOURCE_UEN','TARGET_UEN','txn_amt']]
        .assign(SOURCE_UEN=lambda d: d['SOURCE_UEN'].astype(str).str.strip(),
                TARGET_UEN=lambda d: d['TARGET_UEN'].astype(str).str.strip())
        .groupby(['SOURCE_UEN','TARGET_UEN'])['txn_amt'].sum()
        .to_dict()
)
def _pay_combined_amt(row):
    return _pay_dir.get((str(row['SOURCE_UEN']).strip(), str(row['TARGET_UEN']).strip()), 0.0)

# Keep payment rows only if their pair's combined Payment ab amount >= threshold
payment_keep_mask = payment_mask & (
    edges_enriched.apply(_pay_combined_amt, axis=1).fillna(0).astype(float) >= THRESHOLD_TXN_SGD
)

# Helper masks for the Consolidated_TT subset of the Payment threshold filter.
tt_mask                   = edges_enriched['edge_source'] == 'Consolidated_TT'
tt_rows_keep_mask         = payment_keep_mask & tt_mask  # TT rows surviving threshold

edges_filtered = edges_enriched[non_payment_mask | payment_keep_mask].copy()
edges_filtered = edges_filtered[
    ~(edges_filtered['self_transfer'].astype(bool) &
      edges_filtered['SOURCE_UEN'].astype(str).isin(_self_only_uens))
].copy()

filtered_connected_uens = (
    set(edges_filtered['SOURCE_UEN'].astype(str)) |
    set(edges_filtered['TARGET_UEN'].astype(str))
)

nodes_filtered = nodes_full[
    nodes_full['UEN'].astype(str).isin(filtered_connected_uens)
].copy()

edges_filtered = edges_filtered[
    edges_filtered['SOURCE_UEN'].astype(str).isin(filtered_connected_uens) &
    edges_filtered['TARGET_UEN'].astype(str).isin(filtered_connected_uens)
].copy()

tt_edges_before  = tt_mask.sum()
tt_edges_removed = tt_mask.sum() - tt_rows_keep_mask.sum()
orphans_removed  = len(nodes_full) - len(nodes_filtered)

print("\n" + "="*60)
print("EDGE-LEVEL FILTER SUMMARY")
print("="*60)
print(f"  Payment threshold filter: drop a row if its (SOURCE,TARGET) per-direction Payment combined amount < S${TT_EDGE_MIN_AMT:,}")
print(f"\n  TT edges before filter:   {tt_edges_before:,}")
print(f"  TT edges removed:         {tt_edges_removed:,}  ({tt_edges_removed/max(tt_edges_before,1)*100:.1f}%)")
print(f"  TT edges kept:            {tt_edges_before - tt_edges_removed:,}")
print(f"\n  Orphaned nodes removed:   {orphans_removed:,}")
print(f"\n  Nodes -- Full: {len(nodes_full):,}  |  Filtered: {len(nodes_filtered):,}  |  Removed: {orphans_removed:,}")
print(f"  Edges -- Full: {len(edges_full):,}  |  Filtered: {len(edges_filtered):,}  |  Removed: {len(edges_full)-len(edges_filtered):,}")

from collections import defaultdict

cust_type_lookup = (
    NetworkGraph_Node_Info_df.set_index('UEN')['CUST_TYPE']
    .fillna('Non-Maybank Customer').to_dict()
)
country_lookup = (
    NetworkGraph_Node_Info_df.set_index('UEN')['source_country']
    .fillna('').to_dict()
)

TRADE     = 'Maybank Trade Customer'
NON_TRADE = 'Maybank Non-Trade Customer'
NON_MB    = 'Non-Maybank Customer'

# ── Per-network TT recompute ──────────────────────────────────────────────
tt_filtered_edges_ext  = edges_filtered[
    (edges_filtered['edge_source'] == 'Consolidated_TT') &
    (~edges_filtered['self_transfer'].astype(bool))
].copy()
tt_filtered_edges_self = edges_filtered[
    (edges_filtered['edge_source'] == 'Consolidated_TT') &
    (edges_filtered['self_transfer'].astype(bool))
].copy()

tt_neighbours_map = defaultdict(set)
for _, row in tt_filtered_edges_ext[['SOURCE_UEN', 'TARGET_UEN']].iterrows():
    src = str(row['SOURCE_UEN']); tgt = str(row['TARGET_UEN'])
    tt_neighbours_map[src].add(tgt)
    tt_neighbours_map[tgt].add(src)

tt_self_dict = (
    tt_filtered_edges_self
    .groupby('SOURCE_UEN')
    .agg(tt_self_transfer_count=('txn_count', 'sum'), tt_self_transfer_amt=('txn_amt', 'sum'))
    .to_dict('index')
)

tt_recompute_rows = []
for nid in nodes_filtered['UEN'].astype(str).tolist():
    neighbours = tt_neighbours_map.get(nid, set())
    sent       = tt_filtered_edges_ext[tt_filtered_edges_ext['SOURCE_UEN'].astype(str) == nid]
    recvd      = tt_filtered_edges_ext[tt_filtered_edges_ext['TARGET_UEN'].astype(str) == nid]
    ord_amt    = sent['txn_amt'].sum()
    bene_amt   = recvd['txn_amt'].sum()
    self_info  = tt_self_dict.get(nid, {})
    tt_recompute_rows.append({
        'UEN'                    : nid,
        'tt_degree_trade_mb'     : sum(1 for nb in neighbours if cust_type_lookup.get(nb, NON_MB) == TRADE),
        'tt_degree_non_trade_mb' : sum(1 for nb in neighbours if cust_type_lookup.get(nb, NON_MB) == NON_TRADE),
        'tt_degree_non_mb'       : sum(1 for nb in neighbours if cust_type_lookup.get(nb, NON_MB) == NON_MB),
        'tt_degree_total'        : len(neighbours),
        'tt_degree_sg'           : sum(1 for nb in neighbours if country_lookup.get(nb, '') == 'SG'),
        'tt_degree_my'           : sum(1 for nb in neighbours if country_lookup.get(nb, '') == 'MY'),
        'tt_ord_freq'            : int(sent['txn_count'].sum()),
        'tt_ord_amt'             : ord_amt,
        'tt_bene_freq'           : int(recvd['txn_count'].sum()),
        'tt_bene_amt'            : bene_amt,
        'tt_net_flow_amt'        : ord_amt - bene_amt,
        'tt_self_transfer_count' : int(self_info.get('tt_self_transfer_count', 0)),
        'tt_self_transfer_amt'   : self_info.get('tt_self_transfer_amt', 0),
    })

tt_recompute_df = pd.DataFrame(tt_recompute_rows)
rename_map = {c: f'_{c}_new' for c in tt_recompute_df.columns if c != 'UEN'}
nodes_filtered = nodes_filtered.merge(tt_recompute_df.rename(columns=rename_map), on='UEN', how='left')

for col in rename_map.keys():
    new_col = f'_{col}_new'
    if new_col in nodes_filtered.columns:
        if col in ('tt_degree_trade_mb', 'tt_degree_non_trade_mb',
                   'tt_degree_non_mb', 'tt_degree_total',
                   'tt_degree_sg', 'tt_degree_my',
                   'tt_ord_freq', 'tt_bene_freq', 'tt_self_transfer_count'):
            nodes_filtered[col] = nodes_filtered[new_col].fillna(0).astype(int)
        else:
            nodes_filtered[col] = nodes_filtered[new_col].fillna(0)
        nodes_filtered = nodes_filtered.drop(columns=[new_col])

# ── Per-source recompute (FAST, GIRO, Payment, All Txn) ───────────────────
def _per_source_recompute(label, edge_source_value, prefix):
    """
    Recompute per-source ord/bene amounts + degree counts after threshold filter.
    label             : human label for prints
    edge_source_value : 'Consolidated_TT' | 'FAST' | 'GIRO' | None (None = union of payment sources)
    prefix            : column prefix (tt|fast|giro|payment|all_txn)
    """
    if edge_source_value is None and prefix == 'payment':
        ext = edges_filtered[edges_filtered['edge_source'].isin(_PAYMENT_SOURCES) &
                             ~edges_filtered['self_transfer'].astype(bool)].copy()
        slf = edges_filtered[edges_filtered['edge_source'].isin(_PAYMENT_SOURCES) &
                             edges_filtered['self_transfer'].astype(bool)].copy()
    elif edge_source_value is None and prefix == 'all_txn':
        ext = edges_filtered[~edges_filtered['self_transfer'].astype(bool)].copy()
        slf = edges_filtered[ edges_filtered['self_transfer'].astype(bool)].copy()
    else:
        ext = edges_filtered[(edges_filtered['edge_source'] == edge_source_value) &
                             ~edges_filtered['self_transfer'].astype(bool)].copy()
        slf = edges_filtered[(edges_filtered['edge_source'] == edge_source_value) &
                              edges_filtered['self_transfer'].astype(bool)].copy()

    # Pre-bin neighbor sets and per-uen aggregates once -- avoids O(N*E)
    # rescans inside the per-node loop below.
    nbrs = defaultdict(set)
    src_arr = ext['SOURCE_UEN'].astype(str).to_numpy()
    tgt_arr = ext['TARGET_UEN'].astype(str).to_numpy()
    for s, t in zip(src_arr, tgt_arr):
        nbrs[s].add(t); nbrs[t].add(s)

    sent_grp = (ext.assign(_S=ext['SOURCE_UEN'].astype(str))
                   .groupby('_S')
                   .agg(_freq=('txn_count','sum'), _amt=('txn_amt','sum'))
                   .to_dict('index'))
    recv_grp = (ext.assign(_T=ext['TARGET_UEN'].astype(str))
                   .groupby('_T')
                   .agg(_freq=('txn_count','sum'), _amt=('txn_amt','sum'))
                   .to_dict('index'))

    self_dict = (slf.assign(_S=slf['SOURCE_UEN'].astype(str))
                    .groupby('_S')
                    .agg(_cnt=('txn_count','sum'), _amt=('txn_amt','sum'))
                    .to_dict('index'))

    rows = []
    for nid in nodes_filtered['UEN'].astype(str).tolist():
        n  = nbrs.get(nid, set())
        sent_i = sent_grp.get(nid, {'_freq': 0, '_amt': 0})
        recv_i = recv_grp.get(nid, {'_freq': 0, '_amt': 0})
        ord_amt  = sent_i['_amt']  or 0
        bene_amt = recv_i['_amt']  or 0
        si       = self_dict.get(nid, {})
        rows.append({
            'UEN': nid,
            f'{prefix}_degree_trade_mb'    : sum(1 for nb in n if cust_type_lookup.get(nb, NON_MB) == TRADE),
            f'{prefix}_degree_non_trade_mb': sum(1 for nb in n if cust_type_lookup.get(nb, NON_MB) == NON_TRADE),
            f'{prefix}_degree_non_mb'      : sum(1 for nb in n if cust_type_lookup.get(nb, NON_MB) == NON_MB),
            f'{prefix}_degree_total'       : len(n),
            f'{prefix}_ord_freq'           : int(sent_i['_freq'] or 0),
            f'{prefix}_ord_amt'            : ord_amt,
            f'{prefix}_bene_freq'          : int(recv_i['_freq'] or 0),
            f'{prefix}_bene_amt'           : bene_amt,
            f'{prefix}_net_flow_amt'       : ord_amt - bene_amt,
            f'{prefix}_self_transfer_count': int(si.get('_cnt', 0)),
            f'{prefix}_self_transfer_amt'  : si.get('_amt', 0),
        })
    df_re = pd.DataFrame(rows)
    rename = {c: f'_{c}_new' for c in df_re.columns if c != 'UEN'}
    out = nodes_filtered.merge(df_re.rename(columns=rename), on='UEN', how='left')
    for col in rename.keys():
        new_col = rename[col]
        if new_col in out.columns:
            if col.endswith(('_freq','_count','_total','_trade_mb','_non_trade_mb','_non_mb',
                             '_degree_trade_mb','_degree_non_trade_mb','_degree_non_mb',
                             '_self_transfer_count','_degree_total')):
                out[col] = out[new_col].fillna(0).astype(int)
            else:
                out[col] = out[new_col].fillna(0)
            out = out.drop(columns=[new_col])
    print(f"  Recomputed {label}: {len(df_re):,} UENs")
    return out

nodes_filtered = _per_source_recompute('FAST',    'FAST',  'fast')
nodes_filtered = _per_source_recompute('GIRO',    'GIRO',  'giro')
nodes_filtered = _per_source_recompute('Payment', None,    'payment')
nodes_filtered = _per_source_recompute('All Txn', None,    'all_txn')   # 'all_txn' branch unions every edge source

# ── Unique neighbour computation for nodes_filtered ───────────────────────
_ext_filtered = edges_filtered[~edges_filtered['self_transfer'].astype(bool)].copy()
_ext_filtered['SOURCE_UEN'] = _ext_filtered['SOURCE_UEN'].astype(str)
_ext_filtered['TARGET_UEN'] = _ext_filtered['TARGET_UEN'].astype(str)

_all_neighbours_filtered = defaultdict(set)
for _, row in _ext_filtered[['SOURCE_UEN', 'TARGET_UEN']].iterrows():
    _all_neighbours_filtered[row['SOURCE_UEN']].add(row['TARGET_UEN'])
    _all_neighbours_filtered[row['TARGET_UEN']].add(row['SOURCE_UEN'])

_unique_degree_filtered_rows = []
for nid in nodes_filtered['UEN'].astype(str).tolist():
    unique_nbs = _all_neighbours_filtered.get(nid, set())
    _unique_degree_filtered_rows.append({
        'UEN'                      : nid,
        'total_degree_total'       : len(unique_nbs),
        'total_degree_sg'          : sum(1 for nb in unique_nbs if country_lookup.get(nb, '') == 'SG'),
        'total_degree_my'          : sum(1 for nb in unique_nbs if country_lookup.get(nb, '') == 'MY'),
        'total_degree_trade_mb'    : sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == TRADE),
        'total_degree_non_trade_mb': sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == NON_TRADE),
        'total_degree_non_mb'      : sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == NON_MB),
    })

_unique_degree_filtered_df = pd.DataFrame(_unique_degree_filtered_rows)
nodes_filtered = nodes_filtered.drop(
    columns=['total_degree_total', 'total_degree_sg', 'total_degree_my',
             'total_degree_trade_mb', 'total_degree_non_trade_mb', 'total_degree_non_mb'],
    errors='ignore'
)
nodes_filtered = nodes_filtered.merge(_unique_degree_filtered_df, on='UEN', how='left')
for _col in ['total_degree_total', 'total_degree_sg', 'total_degree_my',
             'total_degree_trade_mb', 'total_degree_non_trade_mb', 'total_degree_non_mb']:
    nodes_filtered[_col] = nodes_filtered[_col].fillna(0).astype(int)

print(f"\n  nodes_filtered unique connections (deduped across all sources):")
print(f"    Max: {nodes_filtered['total_degree_total'].max():,}")
print(f"    Avg: {nodes_filtered['total_degree_total'].mean():.1f}")
print(f"    Nodes with SG connections: {(nodes_filtered['total_degree_sg'] > 0).sum():,}")
print(f"    Nodes with MY connections: {(nodes_filtered['total_degree_my'] > 0).sum():,}")

_check_total = (
    nodes_filtered['total_degree_trade_mb'] +
    nodes_filtered['total_degree_non_trade_mb'] +
    nodes_filtered['total_degree_non_mb']
) - nodes_filtered['total_degree_total']
print(f"  Sanity check (trade+non_trade+non_mb == total, max diff): {_check_total.abs().max()}")

# ── Unique neighbour computation for nodes_full ───────────────────────────
_ext_full = edges_full[~edges_full['self_transfer'].astype(bool)].copy()
_ext_full['SOURCE_UEN'] = _ext_full['SOURCE_UEN'].astype(str)
_ext_full['TARGET_UEN'] = _ext_full['TARGET_UEN'].astype(str)

_all_neighbours_full = defaultdict(set)
for _, row in _ext_full[['SOURCE_UEN', 'TARGET_UEN']].iterrows():
    _all_neighbours_full[row['SOURCE_UEN']].add(row['TARGET_UEN'])
    _all_neighbours_full[row['TARGET_UEN']].add(row['SOURCE_UEN'])

_unique_degree_full_rows = []
for nid in nodes_full['UEN'].astype(str).tolist():
    unique_nbs = _all_neighbours_full.get(nid, set())
    _unique_degree_full_rows.append({
        'UEN'                      : nid,
        'total_degree_total'       : len(unique_nbs),
        'total_degree_sg'          : sum(1 for nb in unique_nbs if country_lookup.get(nb, '') == 'SG'),
        'total_degree_my'          : sum(1 for nb in unique_nbs if country_lookup.get(nb, '') == 'MY'),
        'total_degree_trade_mb'    : sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == TRADE),
        'total_degree_non_trade_mb': sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == NON_TRADE),
        'total_degree_non_mb'      : sum(1 for nb in unique_nbs if cust_type_lookup.get(nb, NON_MB) == NON_MB),
    })

_unique_degree_full_df = pd.DataFrame(_unique_degree_full_rows)
nodes_full = nodes_full.drop(
    columns=['total_degree_total', 'total_degree_sg', 'total_degree_my',
             'total_degree_trade_mb', 'total_degree_non_trade_mb', 'total_degree_non_mb'],
    errors='ignore'
)
nodes_full = nodes_full.merge(_unique_degree_full_df, on='UEN', how='left')
for _col in ['total_degree_total', 'total_degree_sg', 'total_degree_my',
             'total_degree_trade_mb', 'total_degree_non_trade_mb', 'total_degree_non_mb']:
    nodes_full[_col] = nodes_full[_col].fillna(0).astype(int)

print(f"\n  nodes_full unique connections (deduped across all sources):")
print(f"    Max: {nodes_full['total_degree_total'].max():,}")
print(f"    Avg: {nodes_full['total_degree_total'].mean():.1f}")

nodes_filtered['source_tt'] = (
    (nodes_filtered['tt_degree_total'].fillna(0).astype(int) > 0) |
    (nodes_filtered['tt_self_transfer_count'].fillna(0).astype(int) > 0)
).astype(int)
nodes_filtered['source_fast'] = (
    (nodes_filtered['fast_degree_total'].fillna(0).astype(int) > 0) |
    (nodes_filtered['fast_self_transfer_count'].fillna(0).astype(int) > 0)
).astype(int)
nodes_filtered['source_giro'] = (
    (nodes_filtered['giro_degree_total'].fillna(0).astype(int) > 0) |
    (nodes_filtered['giro_self_transfer_count'].fillna(0).astype(int) > 0)
).astype(int)

def _recompute_node_source(row):
    parts = []
    if row.get('source_rsme', 0):     parts.append('RSME')
    if row.get('source_tt', 0):       parts.append('Consolidated_TT')
    if row.get('source_fast', 0):     parts.append('FAST')
    if row.get('source_giro', 0):     parts.append('GIRO')
    if row.get('source_fitas', 0):    parts.append('FITAS')
    if row.get('source_aa_paper', 0): parts.append('AA_Paper')
    return '|'.join(parts) if parts else ''

nodes_filtered['node_source'] = nodes_filtered.apply(_recompute_node_source, axis=1)

print(f"\n  source_tt and node_source recomputed")
print(f"    Nodes with source_tt=1 (filtered): {nodes_filtered['source_tt'].sum():,}")
print(f"    Nodes with source_tt=1 (full):     {nodes_full['source_tt'].sum():,}")

EMIS_COLS_IN_NODE = [
    'EMIS Country', 'EMIS Company Name', 'EMIS City', 'EMIS Industry',
    'EMIS Business Description', 'EMIS Key Executives', 'EMIS Export',
    'EMIS Incorporation Date', 'EMIS Number of Employees', 'EMIS Listed / Unlisted',
    'EMIS Total Operating Revenue (USD)', 'EMIS Operating Profit (USD)',
    'EMIS Profit Before Income Tax (USD)', 'EMIS Total Assets (USD)',
    'EMIS Free Cash Flow (USD)', 'EMIS Net Cash Flow from Operations (USD)',
    'EMIS Return on Assets / ROA (%)', 'EMIS Return on Equity / ROE (%)',
    'EMIS Company ID', 'EMIS Fiscal Year', 'EMIS Audited', 'EMIS Source',
]

ACRA_CHARGES_COLS_IN_NODE = [
    'N_CHARGES', 'N_UNIQUE_CHARGEE',
    'EARLIEST_CHARGE_REG_DATE', 'LATEST_CHARGE_REG_DATE',
    'CHARGE_SECURED_AMOUNT_SGD',
    'CHARGE_ALLMONIESOWING_Y_COUNT', 'CHARGE_ALLMONIESOWING_N_COUNT',
]

# *** new | MFI financial statement columns
MFI_COLS_IN_NODE = [
    'MFI_END_DTE', 'MFI_STATEMENT_TYP', 'MFI_AUDITOR_NAME', 'MFI_QUALIFIED',
    'MFI_SEG_DESC', 'MFI_MODEL_NAME', 'MFI_TARGET_CURCY_CODE', 'MFI_BASE_CURCY_CODE',
    'MFI_LENGTH_IN_MTH', 'MFI_STATEMENT_STS', 'MFI_PROC_DTE',
    'MFI_SALES', 'MFI_COGS', 'MFI_GROSS_PNL', 'MFI_PRETAX_PNL_BEFORE_INT',
    'MFI_PNL_BEFORE_TAX', 'MFI_PNL_AFT_TAX', 'MFI_EBITDA',
    'MFI_TOT_AST', 'MFI_CURR_AST', 'MFI_NON_CURR_AST',
    'MFI_TOT_LBLTY', 'MFI_CURR_LBLTY', 'MFI_NON_CURR_LBLTY',
    'MFI_TOT_EQUITY', 'MFI_ST_DEBT', 'MFI_LT_DEBT', 'MFI_TOTAL_DEBT',
    'MFI_DEBT_SERVICE', 'MFI_TANGIBLE_NET_WORTH', 'MFI_ADJ_TNW',
    'MFI_DCSR', 'MFI_GEARING',
]

# *** new | CIP collateral columns
CIP_COLS_IN_NODE = [
    'CIP_FAC_LIMIT_SGD', 'CIP_LOAN_BALANCE_SGD', 'CIP_NPL_BALANCE_SGD',
    'CIP_SEC_AMT', 'CIP_SEC_EMV', 'CIP_SEC_FSV', 'CIP_SEC_FIV',
    'CIP_N_PROPERTIES',
    'CIP_N_ACC_TOTAL', 'CIP_N_ACC_OPEN', 'CIP_N_ACC_CLOSED',
    'CIP_EARLIEST_AC_OPN_DTE', 'CIP_LATEST_AC_OPN_DTE',
    'EARLIEST_OPEN_AC_OPN_DTE', 'LATEST_OPEN_AC_OPN_DTE',
    'EARLIEST_CLOSED_AC_OPN_DTE', 'LATEST_AC_CLS_DTE',
    'CIP_FAC_PROC_DTE', 'CIP_BALANCE_PROC_DTE', 'CIP_LATEST_DEFAULT_DTE',
    'CIP_JTC_FLAG',
    'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT', 'CIP_PBD_OCCP_TYPE_TENANTED_COUNT',
    'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT', 'CIP_PBD_OCCP_TYPE_VACANT_COUNT',
]

NODE_COLS_TO_KEEP = [
    # ── Identity: 6 hidden flags + Data Source (visible summary) ──────────
    'source_rsme', 'source_tt', 'source_fast', 'source_giro',
    'source_fitas', 'source_aa_paper',
    'node_source',  # = "Data Source" -- summary, right edge of identity sub-group
    # Always-visible identity columns (no grouping)
    'CUST_TYPE', 'source_name', 'UEN', 'CIF_NO', 'CIF_GROUP_NAME',
    'FINAL_CLASSIFICATION', 'IS_MAYBANK_CUSTOMER', 'source_country',

    # ── RSME Network: 3 hidden + RSME Total Connections (visible) ─────────
    'rsme_degree_trade_mb', 'rsme_degree_non_trade_mb', 'rsme_degree_non_mb',
    'rsme_degree_total',  # summary

    # ── TT Network: 12 hidden + TT Net Flow (visible) ─────────────────────
    'tt_degree_trade_mb', 'tt_degree_non_trade_mb', 'tt_degree_non_mb',
    'tt_degree_total',
    'tt_degree_sg', 'tt_degree_my',
    'tt_ord_freq', 'tt_ord_amt', 'tt_bene_freq', 'tt_bene_amt',
    'tt_self_transfer_count', 'tt_self_transfer_amt',
    'tt_yr',  # extra (unlisted in spec) -- collapsed with the rest
    'tt_net_flow_amt',  # summary

    # ── FAST Network: 10 hidden + FAST Net Flow (visible) ─────────────────
    'fast_degree_trade_mb', 'fast_degree_non_trade_mb', 'fast_degree_non_mb',
    'fast_degree_total',
    'fast_ord_freq', 'fast_ord_amt', 'fast_bene_freq', 'fast_bene_amt',
    'fast_self_transfer_count', 'fast_self_transfer_amt',
    'fast_yr',  # extra -- collapsed
    'fast_net_flow_amt',  # summary

    # ── GIRO Network: 10 hidden + GIRO Net Flow (visible) ─────────────────
    'giro_degree_trade_mb', 'giro_degree_non_trade_mb', 'giro_degree_non_mb',
    'giro_degree_total',
    'giro_ord_freq', 'giro_ord_amt', 'giro_bene_freq', 'giro_bene_amt',
    'giro_self_transfer_count', 'giro_self_transfer_amt',
    'giro_yr',  # extra -- collapsed
    'giro_net_flow_amt',  # summary

    # ── FITAS Network: 8 hidden + FITAS Total Amount (visible) ────────────
    'fitas_degree_trade_mb', 'fitas_degree_non_trade_mb', 'fitas_degree_non_mb',
    'fitas_degree_total',
    'fitas_ord_freq', 'fitas_ord_amt', 'fitas_bene_freq', 'fitas_bene_amt',
    'fitas_yr',  # extra -- collapsed
    'fitas_total_amt',  # summary

    # ── AA Paper Network: 3 hidden + AA Paper Total Connections (visible) ─
    'aa_degree_trade_mb', 'aa_degree_non_trade_mb', 'aa_degree_non_mb',
    'aa_degree_total',  # summary

    # ── Payment Summary: 10 hidden + Payment Net Flow (visible) ───────────
    'payment_degree_trade_mb', 'payment_degree_non_trade_mb', 'payment_degree_non_mb',
    'payment_degree_total',
    'payment_ord_freq', 'payment_ord_amt', 'payment_bene_freq', 'payment_bene_amt',
    'payment_self_transfer_count', 'payment_self_transfer_amt',
    'payment_net_flow_amt',  # summary

    # ── All Transactions: 8 hidden + All Txn Net Flow (visible) ───────────
    'all_txn_degree_trade_mb', 'all_txn_degree_non_trade_mb', 'all_txn_degree_non_mb',
    'all_txn_degree_total',
    'all_txn_ord_freq', 'all_txn_ord_amt', 'all_txn_bene_freq', 'all_txn_bene_amt',
    'all_txn_yr',  # extra -- collapsed
    'all_txn_net_flow_amt',  # summary

    # ── Network Overview: 10 hidden + Total Connections (All Networks) (visible)
    'total_degree_trade_mb', 'total_degree_non_trade_mb', 'total_degree_non_mb',
    'total_degree_trade_mb_pct', 'total_degree_non_trade_mb_pct', 'total_degree_non_mb_pct',
    'total_degree_sg', 'total_degree_my',
    'total_connections_to_buyers', 'total_connections_to_suppliers',
    'total_connections_to_maybank_buyers', 'total_connections_to_maybank_suppliers',
    'total_degree_total',  # summary

    # ── Entity Info (no grouping) ─────────────────────────────────────────
    'entity_type_description', 'entity_status_description',
    'FIRST_CA_OPN_DTE', 'RLTNSHP_TENURE',
    'postal_code', 'SSIC_CODE', 'MAS610_INDST_DESC', 'BIZ_TYP_DESC',
    'EMIS City', 'EMIS Number of Employees', 'EMIS Listed / Unlisted',
    'EMIS Export', 'EMIS Incorporation Date', 'EMIS Business Description',

    # ── Facilities (no grouping) ──────────────────────────────────────────
    'TF_LCY_AUTH_LMT', 'TF_LCY_AVAIL_LMT', 'TF_LCY_OUTSTANDING',
    'TF_LCY_TOT_OS', 'TF_LCY_OBS_OS', 'TF_LCY_UTILISATION_PCT',
    'ADT_CREATION_DATE',
    'TR_LN', 'NONTR_LN', 'LN_BALANCES',
    'CASA', 'FD', 'STRCTD', 'DEP_BALANCES',

    # ── Credit Status (no grouping) ───────────────────────────────────────
    'credit_status', 'impairment_stage', 'RISK_GRADE',
    'is_watchlist', 'is_special_mention', 'is_npl',
    'months_on_book', 'borrower_risk_rating', 'rating_date',
    'latest_dpd_bucket', 'delinquency_count_12m',

    # ── ACRA Financials (no grouping) ─────────────────────────────────────
    'FIN_FIN_YR_END_CY', 'FIN_SALES_CY', 'FIN_PROF_BEF_TAX_CY',
    'FIN_CASH_BANK_BAL_CY', 'FIN_TRADE_CRED_CY', 'FIN_TRADE_DEPT_CY',
] + ACRA_CHARGES_COLS_IN_NODE + EMIS_COLS_IN_NODE + MFI_COLS_IN_NODE + CIP_COLS_IN_NODE

EDGE_COLS_TO_KEEP = [
    'SOURCE_UEN', 'source_name', 'source_country', 'source_segment',
    'TARGET_UEN', 'target_name', 'target_country', 'target_segment',
    'txn_count', 'txn_amt', 'self_transfer', 'edge_source',
    'declarer_uen', 'declarer_name', 'declared_uen', 'declared_name',
    'counterparty_type', 'relationship_description',
]

NODE_COLS_TO_KEEP = [c for c in NODE_COLS_TO_KEEP if c in nodes_full.columns or c in nodes_filtered.columns]
EDGE_COLS_TO_KEEP = [c for c in EDGE_COLS_TO_KEEP if c in edges_full.columns]

# Diagnostic: report found/missing for EMIS, MFI, CIP
for label, col_list in [
    ('EMIS',         EMIS_COLS_IN_NODE),
    ('ACRA Charges', ACRA_CHARGES_COLS_IN_NODE),
    ('MFI',          MFI_COLS_IN_NODE),
    ('CIP',          CIP_COLS_IN_NODE),
]:
    found   = [c for c in col_list if c in nodes_full.columns]
    missing = [c for c in col_list if c not in nodes_full.columns]
    print(f"\n  {label} columns found: {len(found)} / {len(col_list)}")
    if missing:
        print(f"  {label} columns not found (skipped): {missing}")

print("\nApplying data cleaning...")
nodes_full     = apply_cleaning(nodes_full)
nodes_filtered = apply_cleaning(nodes_filtered)
edges_full     = apply_cleaning(edges_full)
edges_filtered = apply_cleaning(edges_filtered)

# Derived facility cols after cleaning
def _compute_facility_derived(df):
    df  = df.copy()
    tot  = pd.to_numeric(df.get('TF_LCY_TOT_OS'),    errors='coerce').fillna(0)
    obs  = pd.to_numeric(df.get('TF_LCY_OBS_OS'),    errors='coerce').fillna(0)
    auth = pd.to_numeric(df.get('TF_LCY_AUTH_LMT'),  errors='coerce').fillna(0)
    outstanding = tot + obs
    df['TF_LCY_OUTSTANDING'] = outstanding.apply(
        lambda v: int(round(v)) if pd.notna(v) else None
    )
    pct       = pd.Series([None] * len(df), index=df.index, dtype=object)
    mask      = auth > 0
    pct[mask] = (outstanding[mask] / auth[mask] * 100).round(1)
    df['TF_LCY_UTILISATION_PCT'] = pct
    return df

nodes_full     = _compute_facility_derived(nodes_full)
nodes_filtered = _compute_facility_derived(nodes_filtered)
NODE_COLS_TO_KEEP += ['TF_LCY_OUTSTANDING', 'TF_LCY_UTILISATION_PCT']
print(f"  Derived facility cols computed: TF_LCY_OUTSTANDING, TF_LCY_UTILISATION_PCT")

def _add_pct_cols(df):
    df = df.copy()
    for col, pct_col in [
        ('total_degree_trade_mb',     'total_degree_trade_mb_pct'),
        ('total_degree_non_trade_mb', 'total_degree_non_trade_mb_pct'),
        ('total_degree_non_mb',       'total_degree_non_mb_pct'),
    ]:
        df[pct_col] = np.where(
            df['total_degree_total'] > 0,
            (df[col] / df['total_degree_total']) * 100, 0
        ).round(1)
    return df

nodes_full     = _add_pct_cols(nodes_full)
nodes_filtered = _add_pct_cols(nodes_filtered)

_base_keep  = NODE_COLS_TO_KEEP.copy()
_insert_idx = _base_keep.index('total_degree_total') + 1
for pct_col in ['total_degree_trade_mb_pct', 'total_degree_non_trade_mb_pct', 'total_degree_non_mb_pct']:
    _base_keep.insert(_insert_idx, pct_col)
    _insert_idx += 1

# Dedupe while preserving order (first occurrence wins): some EMIS-display cols
# appear both in the inline Entity Info block of NODE_COLS_TO_KEEP and in
# EMIS_COLS_IN_NODE; without this, df[NODE_COLS_TO_KEEP_FINAL] duplicates them.
_seen = set()
NODE_COLS_TO_KEEP_FINAL = []
for c in _base_keep:
    if c in _seen: continue
    if c in nodes_full.columns or c in nodes_filtered.columns:
        NODE_COLS_TO_KEEP_FINAL.append(c)
        _seen.add(c)

nodes_full_final     = nodes_full[[c for c in NODE_COLS_TO_KEEP_FINAL if c in nodes_full.columns]].copy()
nodes_filtered_final = nodes_filtered[[c for c in NODE_COLS_TO_KEEP_FINAL if c in nodes_filtered.columns]].copy()
edges_full_final     = edges_full[EDGE_COLS_TO_KEEP].copy()
edges_filtered_final = edges_filtered[EDGE_COLS_TO_KEEP].copy()

print(f"\nFiltered to {len(NODE_COLS_TO_KEEP_FINAL)} node columns, {len(EDGE_COLS_TO_KEEP)} edge columns")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 3b: Build Buyer-Supplier Pairs Sheet

print("\n" + "="*60)
print("BUILDING BUYER-SUPPLIER PAIRS")
print("="*60)

_name_dict = (
    NetworkGraph_Node_Info_df
    .set_index('UEN')['source_name']
    .fillna('')
    .to_dict()
)

def _resolve_name(uen_val):
    if uen_val is None or (isinstance(uen_val, float) and math.isnan(uen_val)):
        return None
    s = str(uen_val).strip()
    if not s or s in ('nan', 'None', ''):
        return None
    return _name_dict.get(s) or s

_FITAS_PRODUCTS = ['lc', 'tr', 'sta', 'exportlc', 'fbep', 'oat', 'others']

def _swap_pairs_for(prefix):
    return [
        (f'{prefix}_buyer_to_supplier_count',   f'{prefix}_supplier_to_buyer_count'),
        (f'{prefix}_buyer_to_supplier_amt',     f'{prefix}_supplier_to_buyer_amt'),
        (f'{prefix}_buyer_to_supplier_amt_pct', f'{prefix}_supplier_to_buyer_amt_pct'),
    ]

_PAIR_SWAP_TABLE = (
    _swap_pairs_for('tt')      +
    _swap_pairs_for('fast')    +
    _swap_pairs_for('giro')    +
    _swap_pairs_for('payment') +
    _swap_pairs_for('all_txn')
)

def _build_pairs_df(rel_df, connected_uens, label):
    df = rel_df.copy()
    df['uen_a'] = df['uen_a'].astype(str).str.strip()
    df['uen_b'] = df['uen_b'].astype(str).str.strip()

    mask = (
        df['uen_a'].isin(connected_uens) &
        df['uen_b'].isin(connected_uens)
    )
    df = df[mask].copy()
    print(f"  [{label}] Pairs before expansion: {len(df):,}  "
          f"(from {len(rel_df):,} total, {len(rel_df) - len(df):,} excluded)")

    df['buyer_name']        = df['buyer_uen'].apply(_resolve_name)
    df['supplier_name']     = df['supplier_uen'].apply(_resolve_name)
    df['customer_name']     = df['customer_uen'].apply(_resolve_name)
    df['counterparty_name'] = df['counterparty_uen'].apply(_resolve_name)

    _new_pair_prefixes = ('tt', 'fast', 'giro', 'payment', 'all_txn')
    _pair_amt_cols = (
        [f'{p}_buyer_to_supplier_amt'  for p in _new_pair_prefixes] +
        [f'{p}_supplier_to_buyer_amt'  for p in _new_pair_prefixes] +
        [f'{p}_total_amt'              for p in _new_pair_prefixes] +
        [f'{p}_net_amt'                for p in _new_pair_prefixes] +
        ['fitas_total_amt', 'grand_total_amt'] +
        [f'fitas_{p}_amt' for p in _FITAS_PRODUCTS]
    )
    _pair_int_cols = (
        [f'{p}_buyer_to_supplier_count' for p in _new_pair_prefixes] +
        [f'{p}_supplier_to_buyer_count' for p in _new_pair_prefixes] +
        [f'{p}_total_count'             for p in _new_pair_prefixes] +
        ['fitas_total_count'] +
        [f'fitas_{p}_count' for p in _FITAS_PRODUCTS]
    )
    _pair_pct_cols = (
        ['tt_buyer_to_supplier_amt_pct', 'tt_supplier_to_buyer_amt_pct'] +
        [f'{p}_buyer_to_supplier_amt_pct' for p in ('fast','giro','payment','all_txn')] +
        [f'{p}_supplier_to_buyer_amt_pct' for p in ('fast','giro','payment','all_txn')]
    )

    for col in _pair_amt_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_amt)
    for col in _pair_int_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
    for col in _pair_pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: round(float(v), 1)
                if v is not None and not (isinstance(v, float) and math.isnan(v))
                else None
            )

    for flag_col in ['is_both', 'is_directed', 'in_fitas', 'in_aa', 'in_tt', 'in_rsme']:
        if flag_col in df.columns:
            df[flag_col] = df[flag_col].apply(clean_flag)

    # is_both pairs are kept as a single row using the heuristic buyer/supplier
    # already resolved by RelationshipBuilder via _resolve_from_uen. The
    # `Is Both Ways` flag column lets users filter for these in Excel.
    n_both = int((df['is_both'] == 1).sum())
    print(f"  [{label}] is_both pairs (single-row, heuristic buyer): {n_both:,}")

    return df.reset_index(drop=True)


pairs_full_df     = _build_pairs_df(_relationship_df_raw, full_connected_uens,     'full')
pairs_filtered_df = _build_pairs_df(_relationship_df_raw, filtered_connected_uens, 'filtered')

print(f"\n  pairs_full_df:     {len(pairs_full_df):,} rows")
print(f"  pairs_filtered_df: {len(pairs_filtered_df):,} rows")

_MAYBANK_CUST_TYPES = {'Maybank Trade Customer', 'Maybank Non-Trade Customer'}

def _compute_bs_counts(pairs_df, maybank_uens):
    """
    Per-UEN distinct-counterparty counts from buyer-supplier pairs.

    Returns a frame with 4 columns keyed on UEN:
      - total_connections_to_buyers              (any counterparty)
      - total_connections_to_suppliers           (any counterparty)
      - total_connections_to_maybank_buyers      (counterparty's CUST_TYPE in {Maybank Trade, Maybank Non-Trade})
      - total_connections_to_maybank_suppliers   (same restriction)
    """
    df = pairs_df.copy()
    df['buyer_uen']    = df['buyer_uen'].astype(str).str.strip()
    df['supplier_uen'] = df['supplier_uen'].astype(str).str.strip()

    valid = df[(df['buyer_uen'] != 'None') & (df['supplier_uen'] != 'None')]

    to_buyers = (
        valid.groupby('supplier_uen')['buyer_uen'].nunique()
        .reset_index()
        .rename(columns={'supplier_uen': 'UEN', 'buyer_uen': 'total_connections_to_buyers'})
    )
    to_suppliers = (
        valid.groupby('buyer_uen')['supplier_uen'].nunique()
        .reset_index()
        .rename(columns={'buyer_uen': 'UEN', 'supplier_uen': 'total_connections_to_suppliers'})
    )

    # Maybank-only counts: restrict the counterparty side to Maybank customers
    valid_mb_buyers    = valid[valid['buyer_uen'].isin(maybank_uens)]
    valid_mb_suppliers = valid[valid['supplier_uen'].isin(maybank_uens)]
    to_mb_buyers = (
        valid_mb_buyers.groupby('supplier_uen')['buyer_uen'].nunique()
        .reset_index()
        .rename(columns={'supplier_uen': 'UEN', 'buyer_uen': 'total_connections_to_maybank_buyers'})
    )
    to_mb_suppliers = (
        valid_mb_suppliers.groupby('buyer_uen')['supplier_uen'].nunique()
        .reset_index()
        .rename(columns={'buyer_uen': 'UEN', 'supplier_uen': 'total_connections_to_maybank_suppliers'})
    )

    out = to_buyers.merge(to_suppliers,    on='UEN', how='outer') \
                   .merge(to_mb_buyers,    on='UEN', how='outer') \
                   .merge(to_mb_suppliers, on='UEN', how='outer')
    for c in ['total_connections_to_buyers', 'total_connections_to_suppliers',
              'total_connections_to_maybank_buyers', 'total_connections_to_maybank_suppliers']:
        out[c] = out[c].fillna(0).astype(int)
    return out

def _maybank_uens_from(nodes_df):
    return set(
        nodes_df.loc[nodes_df['CUST_TYPE'].isin(_MAYBANK_CUST_TYPES), 'UEN']
                .astype(str).str.strip()
    )

_maybank_uens_full     = _maybank_uens_from(nodes_full_final)
_maybank_uens_filtered = _maybank_uens_from(nodes_filtered_final)

bs_counts_full     = _compute_bs_counts(pairs_full_df,     _maybank_uens_full)
bs_counts_filtered = _compute_bs_counts(pairs_filtered_df, _maybank_uens_filtered)

_BS_COUNT_COLS = [
    'total_connections_to_buyers', 'total_connections_to_suppliers',
    'total_connections_to_maybank_buyers', 'total_connections_to_maybank_suppliers',
]

nodes_full_final = nodes_full_final.merge(bs_counts_full, on='UEN', how='left')
for _c in _BS_COUNT_COLS:
    nodes_full_final[_c] = nodes_full_final[_c].fillna(0).astype(int)

nodes_filtered_final = nodes_filtered_final.merge(bs_counts_filtered, on='UEN', how='left')
for _c in _BS_COUNT_COLS:
    nodes_filtered_final[_c] = nodes_filtered_final[_c].fillna(0).astype(int)

print(f"\n  Buyer/supplier counts merged onto node finals")
print(f"  Full    -- buyers: {(nodes_full_final['total_connections_to_buyers'] > 0).sum():,}  "
      f"suppliers: {(nodes_full_final['total_connections_to_suppliers'] > 0).sum():,}  "
      f"mb-buyers: {(nodes_full_final['total_connections_to_maybank_buyers'] > 0).sum():,}  "
      f"mb-suppliers: {(nodes_full_final['total_connections_to_maybank_suppliers'] > 0).sum():,}")
print(f"  Filtered -- buyers: {(nodes_filtered_final['total_connections_to_buyers'] > 0).sum():,}  "
      f"suppliers: {(nodes_filtered_final['total_connections_to_suppliers'] > 0).sum():,}  "
      f"mb-buyers: {(nodes_filtered_final['total_connections_to_maybank_buyers'] > 0).sum():,}  "
      f"mb-suppliers: {(nodes_filtered_final['total_connections_to_maybank_suppliers'] > 0).sum():,}")

pairs_full_df.head(3)

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 4: Define Column Renaming and Section Colors
# *** updated | added MFI and CIP column renames and sections
# *** updated | trade facility columns prefixed with "Trade" in Excel display names
# *** updated | added 4 new CIP open/close date col renames and section entries

NODE_RENAME = {
    'node_source': 'Data Source',
    'source_rsme': 'In RSME Network', 'source_tt': 'In TT Network',
    'source_fitas': 'In FITAS Network', 'source_aa_paper': 'In AA Paper Network',
    'CUST_TYPE': 'Customer Type', 'source_name': 'Company Name',
    'UEN': 'UEN', 'CIF_NO': 'CIF Number', 'CIF_GROUP_NAME': 'Parent Group',
    'FINAL_CLASSIFICATION': 'Customer Segment', 'IS_MAYBANK_CUSTOMER': 'Is Maybank Customer',
    'source_country': 'Country',
    'total_degree_trade_mb': 'Total Connections - Trade Customers',
    'total_degree_non_trade_mb': 'Total Connections - Non-Trade Customers',
    'total_degree_non_mb': 'Total Connections - Non-Maybank',
    'total_degree_total': 'Total Connections (All Networks)',
    'total_degree_trade_mb_pct': 'Total Connections - Trade %',
    'total_degree_non_trade_mb_pct': 'Total Connections - Non-Trade %',
    'total_degree_non_mb_pct': 'Total Connections - Non-Maybank %',
    'total_degree_sg': 'Total Connections - SG', 'total_degree_my': 'Total Connections - MY',
    'total_connections_to_buyers'           : 'Total Connections to Buyers',
    'total_connections_to_suppliers'        : 'Total Connections to Suppliers',
    'total_connections_to_maybank_buyers'   : 'Total Connections to Maybank Customer Buyers',
    'total_connections_to_maybank_suppliers': 'Total Connections to Maybank Customer Suppliers',
    'rsme_degree_trade_mb': 'RSME Connections - Trade Customers',
    'rsme_degree_non_trade_mb': 'RSME Connections - Non-Trade Customers',
    'rsme_degree_non_mb': 'RSME Connections - Non-Maybank', 'rsme_degree_total': 'RSME Total Connections',
    'tt_degree_trade_mb': 'TT Connections - Trade Customers',
    'tt_degree_non_trade_mb': 'TT Connections - Non-Trade Customers',
    'tt_degree_non_mb': 'TT Connections - Non-Maybank', 'tt_degree_total': 'TT Total Connections',
    'tt_degree_sg': 'TT Connections - SG', 'tt_degree_my': 'TT Connections - MY',
    'fitas_degree_trade_mb': 'FITAS Connections - Trade Customers',
    'fitas_degree_non_trade_mb': 'FITAS Connections - Non-Trade Customers',
    'fitas_degree_non_mb': 'FITAS Connections - Non-Maybank', 'fitas_degree_total': 'FITAS Total Connections',
    'aa_degree_trade_mb': 'AA Paper Connections - Trade Customers',
    'aa_degree_non_trade_mb': 'AA Paper Connections - Non-Trade Customers',
    'aa_degree_non_mb': 'AA Paper Connections - Non-Maybank', 'aa_degree_total': 'AA Paper Total Connections',
    'tt_ord_freq': 'TT Transactions Sent (Count)', 'tt_ord_amt': 'TT Amount Sent (SGD)',
    'tt_bene_freq': 'TT Transactions Received (Count)', 'tt_bene_amt': 'TT Amount Received (SGD)',
    'tt_net_flow_amt': 'TT Net Flow (SGD)',
    'tt_self_transfer_count': 'TT Self-Transfer (Count)', 'tt_self_transfer_amt': 'TT Self-Transfer Amount (SGD)',
    'fitas_ord_freq': 'FITAS Transactions Sent (Count)', 'fitas_ord_amt': 'FITAS Amount Sent (SGD)',
    'fitas_bene_freq': 'FITAS Transactions Received (Count)', 'fitas_bene_amt': 'FITAS Amount Received (SGD)',
    'fitas_total_amt': 'FITAS Total Amount (SGD)',
    'entity_type_description': 'Entity Type', 'entity_status_description': 'Entity Status',
    'FIRST_CA_OPN_DTE': 'First CA Opening Date', 'RLTNSHP_TENURE': 'Relationship Tenure (Days)',
    'postal_code': 'Postal Code', 'SSIC_CODE': 'SSIC Code',
    'MAS610_INDST_DESC': 'Sector', 'BIZ_TYP_DESC': 'Industry',
    'EMIS City'                : 'City',
    'EMIS Number of Employees' : 'No. Employees',
    'EMIS Listed / Unlisted'   : 'Listed / Unlisted',
    'EMIS Export'              : 'Export Countries',
    'EMIS Incorporation Date'  : 'Incorporation Date',
    'EMIS Business Description': 'Business Description',
    # *** updated | trade facility columns -- "Trade" prefix added
    'TF_LCY_AVAIL_LMT'      : 'Trade Available Limit (SGD)',
    'TF_LCY_AUTH_LMT'       : 'Trade Authorised Limit (SGD)',
    'ADT_CREATION_DATE'     : 'Latest AA Creation Date',
    'TF_LCY_TOT_OS'         : 'Trade On-Balance Sheet Outstanding (SGD)',
    'TF_LCY_OBS_OS'         : 'Trade Off-Balance Sheet Outstanding (SGD)',
    'TF_LCY_OUTSTANDING'    : 'Trade Outstanding Balance (SGD)',
    'TF_LCY_UTILISATION_PCT': 'Trade Utilisation (%)',
    'CASA': 'Current Account (SGD)', 'FD': 'TD (SGD)', 'STRCTD': 'Structured TD (SGD)',
    'DEP_BALANCES': 'Total Deposit Balances (SGD)', 'TR_LN': 'Trade Loan (SGD)',
    'NONTR_LN': 'Non-Trade Loan (SGD)', 'LN_BALANCES': 'Total Loan Balances (SGD)',
    'credit_status': 'Credit Status', 'impairment_stage': 'Impairment Stage', 'RISK_GRADE': 'Risk Grade',
    'is_watchlist': 'Is Watchlist', 'is_special_mention': 'Is Special Mention (SMA)', 'is_npl': 'Is NPL',
    'months_on_book': 'Months on Book', 'borrower_risk_rating': 'Borrower Risk Rating (BRR)',
    'rating_date': 'Rating Date', 'latest_dpd_bucket': 'Latest DPD Bucket',
    'delinquency_count_12m': 'Delinquency Count (12M)',
    'FIN_FIN_YR_END_CY': 'ACRA Financial Year End', 'FIN_SALES_CY': 'ACRA Sales Revenue (SGD)',
    'FIN_PROF_BEF_TAX_CY': 'ACRA Profit Before Tax (SGD)', 'FIN_CASH_BANK_BAL_CY': 'ACRA Cash & Bank Balance (SGD)',
    'FIN_TRADE_CRED_CY': 'ACRA Trade Creditors (SGD)', 'FIN_TRADE_DEPT_CY': 'ACRA Trade Debtors (SGD)',
    'N_CHARGES'                    : 'Charge Count',
    'N_UNIQUE_CHARGEE'             : 'Unique Chargee Count',
    'EARLIEST_CHARGE_REG_DATE'     : 'Earliest Charge Reg Date',
    'LATEST_CHARGE_REG_DATE'       : 'Latest Charge Reg Date',
    'CHARGE_SECURED_AMOUNT_SGD'    : 'Charge Secured Amount (SGD)',
    'CHARGE_ALLMONIESOWING_Y_COUNT': 'Charges - All Monies Owing (Y Count)',
    'CHARGE_ALLMONIESOWING_N_COUNT': 'Charges - All Monies Owing (N Count)',
    'EMIS Country': 'EMIS Country', 'EMIS Company Name': 'EMIS Company Name',
    'EMIS Industry': 'EMIS Industry', 'EMIS Key Executives': 'EMIS Key Executives',
    'EMIS Total Operating Revenue (USD)'      : 'Total Operating Revenue (USD)',
    'EMIS Operating Profit (USD)'             : 'Operating Profit (USD)',
    'EMIS Profit Before Income Tax (USD)'     : 'Profit Before Income Tax (USD)',
    'EMIS Total Assets (USD)'                 : 'Total Assets (USD)',
    'EMIS Free Cash Flow (USD)'               : 'Free Cash Flow (USD)',
    'EMIS Net Cash Flow from Operations (USD)': 'Net Cash Flow from Operations (USD)',
    'EMIS Return on Assets / ROA (%)': 'EMIS ROA (%)', 'EMIS Return on Equity / ROE (%)': 'EMIS ROE (%)',
    'EMIS Company ID': 'EMIS Company ID', 'EMIS Fiscal Year': 'EMIS Fiscal Year',
    'EMIS Audited': 'EMIS Audited', 'EMIS Source': 'EMIS Source',
    # MFI column renames
    'MFI_END_DTE'              : 'MFI Financial Year End',
    'MFI_STATEMENT_TYP'        : 'MFI Statement Type',
    'MFI_AUDITOR_NAME'         : 'MFI Auditor',
    'MFI_QUALIFIED'            : 'MFI Qualified Opinion',
    'MFI_SEG_DESC'             : 'MFI Segment',
    'MFI_MODEL_NAME'           : 'MFI Model Name',
    'MFI_TARGET_CURCY_CODE'    : 'MFI Target Currency',
    'MFI_BASE_CURCY_CODE'      : 'MFI Base Currency',
    'MFI_LENGTH_IN_MTH'        : 'MFI Period Length (Months)',
    'MFI_STATEMENT_STS'        : 'MFI Statement Status',
    'MFI_PROC_DTE'             : 'MFI Processing Date',
    'MFI_SALES'                : 'MFI Sales Revenue (SGD)',
    'MFI_COGS'                 : 'MFI COGS (SGD)',
    'MFI_GROSS_PNL'            : 'MFI Gross Operating P&L (SGD)',
    'MFI_PRETAX_PNL_BEFORE_INT': 'MFI Pre-Tax P&L Before Int (SGD)',
    'MFI_PNL_BEFORE_TAX'       : 'MFI Profit Before Tax (SGD)',
    'MFI_PNL_AFT_TAX'          : 'MFI Profit After Tax (SGD)',
    'MFI_EBITDA'               : 'MFI EBITDA (SGD)',
    'MFI_TOT_AST'              : 'MFI Total Assets (SGD)',
    'MFI_CURR_AST'             : 'MFI Current Assets (SGD)',
    'MFI_NON_CURR_AST'         : 'MFI Non-Current Assets (SGD)',
    'MFI_TOT_LBLTY'            : 'MFI Total Liabilities (SGD)',
    'MFI_CURR_LBLTY'           : 'MFI Current Liabilities (SGD)',
    'MFI_NON_CURR_LBLTY'       : 'MFI Non-Current Liabilities (SGD)',
    'MFI_TOT_EQUITY'           : 'MFI Total Equity (SGD)',
    'MFI_ST_DEBT'              : 'MFI Short-Term Debt (SGD)',
    'MFI_LT_DEBT'              : 'MFI Long-Term Debt (SGD)',
    'MFI_TOTAL_DEBT'           : 'MFI Total Debt (SGD)',
    'MFI_DEBT_SERVICE'         : 'MFI Debt Service (SGD)',
    'MFI_TANGIBLE_NET_WORTH'   : 'MFI Tangible Net Worth (SGD)',
    'MFI_ADJ_TNW'              : 'MFI Adjusted TNW (SGD)',
    'MFI_DCSR'                 : 'MFI DSCR',
    'MFI_GEARING'              : 'MFI Gearing Ratio',
    # CIP column renames
    'CIP_FAC_LIMIT_SGD'                  : 'CIP Facility Limit (SGD)',
    'CIP_LOAN_BALANCE_SGD'               : 'CIP Loan Balance (SGD)',
    'CIP_NPL_BALANCE_SGD'                : 'CIP NPL Balance (SGD)',
    'CIP_SEC_AMT'                        : 'CIP Security Amount (SGD)',
    'CIP_SEC_EMV'                        : 'CIP Estimated Market Value (SGD)',
    'CIP_SEC_FSV'                        : 'CIP Forced Sale Value (SGD)',
    'CIP_SEC_FIV'                        : 'CIP Fire Insurance Value (SGD)',
    'CIP_N_PROPERTIES'                   : 'CIP No. Properties',
    'CIP_N_ACC_TOTAL'                    : 'CIP Total Accounts',
    'CIP_N_ACC_OPEN'                     : 'CIP Open Accounts',
    'CIP_N_ACC_CLOSED'                   : 'CIP Closed Accounts',
    'CIP_EARLIEST_AC_OPN_DTE'            : 'CIP Earliest Account Open Date',
    'CIP_LATEST_AC_OPN_DTE'              : 'CIP Latest Account Open Date',
    # *** new | 4 additional open/close date cols
    'EARLIEST_OPEN_AC_OPN_DTE'           : 'CIP Earliest Open Account Date',
    'LATEST_OPEN_AC_OPN_DTE'             : 'CIP Latest Open Account Date',
    'EARLIEST_CLOSED_AC_OPN_DTE'         : 'CIP Earliest Closed Account Date',
    'LATEST_AC_CLS_DTE'                  : 'CIP Latest Account Close Date',
    'CIP_FAC_PROC_DTE'                   : 'CIP Facility Processing Date',
    'CIP_BALANCE_PROC_DTE'               : 'CIP Balance Processing Date',
    'CIP_LATEST_DEFAULT_DTE'             : 'CIP Latest Default Date',
    'CIP_JTC_FLAG'                       : 'CIP JTC Properties Count',
    'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT'   : 'CIP Owner Occupied Properties',
    'CIP_PBD_OCCP_TYPE_TENANTED_COUNT'   : 'CIP Tenanted Properties',
    'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT'     : 'CIP Business Ops Properties',
    'CIP_PBD_OCCP_TYPE_VACANT_COUNT'     : 'CIP Vacant Properties',
    # FAST
    'source_fast'            : 'In FAST Network',
    'fast_degree_trade_mb'    : 'FAST Connections - Trade Customers',
    'fast_degree_non_trade_mb': 'FAST Connections - Non-Trade Customers',
    'fast_degree_non_mb'      : 'FAST Connections - Non-Maybank',
    'fast_degree_total'       : 'FAST Total Connections',
    'fast_ord_freq'           : 'FAST Transactions Sent (Count)',
    'fast_ord_amt'            : 'FAST Amount Sent (SGD)',
    'fast_bene_freq'          : 'FAST Transactions Received (Count)',
    'fast_bene_amt'           : 'FAST Amount Received (SGD)',
    'fast_net_flow_amt'       : 'FAST Net Flow (SGD)',
    'fast_self_transfer_count': 'FAST Self-Transfer (Count)',
    'fast_self_transfer_amt'  : 'FAST Self-Transfer Amount (SGD)',
    # GIRO
    'source_giro'             : 'In GIRO Network',
    'giro_degree_trade_mb'    : 'GIRO Connections - Trade Customers',
    'giro_degree_non_trade_mb': 'GIRO Connections - Non-Trade Customers',
    'giro_degree_non_mb'      : 'GIRO Connections - Non-Maybank',
    'giro_degree_total'       : 'GIRO Total Connections',
    'giro_ord_freq'           : 'GIRO Transactions Sent (Count)',
    'giro_ord_amt'            : 'GIRO Amount Sent (SGD)',
    'giro_bene_freq'          : 'GIRO Transactions Received (Count)',
    'giro_bene_amt'           : 'GIRO Amount Received (SGD)',
    'giro_net_flow_amt'       : 'GIRO Net Flow (SGD)',
    'giro_self_transfer_count': 'GIRO Self-Transfer (Count)',
    'giro_self_transfer_amt'  : 'GIRO Self-Transfer Amount (SGD)',
    # Payment combined
    'payment_degree_trade_mb'    : 'Payment Connections - Trade Customers',
    'payment_degree_non_trade_mb': 'Payment Connections - Non-Trade Customers',
    'payment_degree_non_mb'      : 'Payment Connections - Non-Maybank',
    'payment_degree_total'       : 'Payment Total Connections',
    'payment_ord_freq'           : 'Payment Transactions Sent (Count)',
    'payment_ord_amt'            : 'Payment Amount Sent (SGD)',
    'payment_bene_freq'          : 'Payment Transactions Received (Count)',
    'payment_bene_amt'           : 'Payment Amount Received (SGD)',
    'payment_net_flow_amt'       : 'Payment Net Flow (SGD)',
    'payment_self_transfer_count': 'Payment Self-Transfer (Count)',
    'payment_self_transfer_amt'  : 'Payment Self-Transfer Amount (SGD)',
    # All Transactions = FITAS + Payment
    'all_txn_degree_trade_mb'    : 'All Txn Connections - Trade Customers',
    'all_txn_degree_non_trade_mb': 'All Txn Connections - Non-Trade Customers',
    'all_txn_degree_non_mb'      : 'All Txn Connections - Non-Maybank',
    'all_txn_degree_total'       : 'All Txn Total Connections',
    'all_txn_ord_freq'           : 'All Txn Transactions Sent (Count)',
    'all_txn_ord_amt'            : 'All Txn Amount Sent (SGD)',
    'all_txn_bene_freq'          : 'All Txn Transactions Received (Count)',
    'all_txn_bene_amt'           : 'All Txn Amount Received (SGD)',
    'all_txn_net_flow_amt'       : 'All Txn Net Flow (SGD)',
    # Latest record dates per source (global value, same on every row).
    'tt_yr'                      : 'TT Latest Record',
    'fitas_yr'                   : 'FITAS Latest Record',
    'fast_yr'                    : 'FAST Latest Record',
    'giro_yr'                    : 'GIRO Latest Record',
    'all_txn_yr'                 : 'All Txn Latest Record',
}

EDGE_RENAME = {
    'SOURCE_UEN': 'Source (UEN)', 'source_name': 'Source (Name)',
    'source_country': 'Source (Country)', 'source_segment': 'Source (Segment)',
    'TARGET_UEN': 'Target (UEN)', 'target_name': 'Target (Name)',
    'target_country': 'Target (Country)', 'target_segment': 'Target (Segment)',
    'txn_count': 'Total Transaction Count', 'txn_amt': 'Total Transaction Amount (SGD)',
    'self_transfer': 'Self-Transfer', 'edge_source': 'Data Source',
    'relationship_description': 'Relationship Description',
}

# NODE_SECTIONS -- 18 sections, each with a unique header colour.
# Sections 1-10 are grouped via _apply_column_groups() so detail columns
# collapse and only a "summary" column remains visible by default.
# Sections 11-18 have no grouping (always fully visible).
# Within each section, columns are listed in the same order as NODE_COLS_TO_KEEP;
# for grouped sections, the "show this" summary column sits at the RIGHT edge
# (matches xlsxwriter's outline_settings(symbols_right=True)).
NODE_SECTIONS = [
    # 1. Identity -- 6 hidden source flags + Data Source (visible) + 8 always-visible
    {'color': 'A8D5E2', 'columns': [
        'In RSME Network', 'In TT Network', 'In FAST Network',
        'In GIRO Network', 'In FITAS Network', 'In AA Paper Network',
        'Data Source',  # show this
        'Customer Type', 'Company Name', 'UEN', 'CIF Number', 'Parent Group',
        'Customer Segment', 'Is Maybank Customer', 'Country',
    ]},
    # 2. RSME Network -- 3 hidden + RSME Total Connections (visible)
    {'color': 'C9E4C5', 'columns': [
        'RSME Connections - Trade Customers',
        'RSME Connections - Non-Trade Customers',
        'RSME Connections - Non-Maybank',
        'RSME Total Connections',  # show this
    ]},
    # 3. TT Network -- 13 hidden + TT Net Flow (visible)
    {'color': 'E8D4F1', 'columns': [
        'TT Connections - Trade Customers',
        'TT Connections - Non-Trade Customers',
        'TT Connections - Non-Maybank',
        'TT Total Connections',
        'TT Connections - SG', 'TT Connections - MY',
        'TT Transactions Sent (Count)',     'TT Amount Sent (SGD)',
        'TT Transactions Received (Count)', 'TT Amount Received (SGD)',
        'TT Self-Transfer (Count)',         'TT Self-Transfer Amount (SGD)',
        'TT Latest Record',
        'TT Net Flow (SGD)',  # show this
    ]},
    # 4. FAST Network -- 11 hidden + FAST Net Flow (visible)
    {'color': 'D6E4F2', 'columns': [
        'FAST Connections - Trade Customers',
        'FAST Connections - Non-Trade Customers',
        'FAST Connections - Non-Maybank',
        'FAST Total Connections',
        'FAST Transactions Sent (Count)',     'FAST Amount Sent (SGD)',
        'FAST Transactions Received (Count)', 'FAST Amount Received (SGD)',
        'FAST Self-Transfer (Count)',         'FAST Self-Transfer Amount (SGD)',
        'FAST Latest Record',
        'FAST Net Flow (SGD)',  # show this
    ]},
    # 5. GIRO Network -- 11 hidden + GIRO Net Flow (visible)
    {'color': 'D0EAE2', 'columns': [
        'GIRO Connections - Trade Customers',
        'GIRO Connections - Non-Trade Customers',
        'GIRO Connections - Non-Maybank',
        'GIRO Total Connections',
        'GIRO Transactions Sent (Count)',     'GIRO Amount Sent (SGD)',
        'GIRO Transactions Received (Count)', 'GIRO Amount Received (SGD)',
        'GIRO Self-Transfer (Count)',         'GIRO Self-Transfer Amount (SGD)',
        'GIRO Latest Record',
        'GIRO Net Flow (SGD)',  # show this
    ]},
    # 6. FITAS Network -- 9 hidden + FITAS Total Amount (visible)
    {'color': 'F9E4D4', 'columns': [
        'FITAS Connections - Trade Customers',
        'FITAS Connections - Non-Trade Customers',
        'FITAS Connections - Non-Maybank',
        'FITAS Total Connections',
        'FITAS Transactions Sent (Count)',     'FITAS Amount Sent (SGD)',
        'FITAS Transactions Received (Count)', 'FITAS Amount Received (SGD)',
        'FITAS Latest Record',
        'FITAS Total Amount (SGD)',  # show this
    ]},
    # 7. AA Paper Network -- 3 hidden + AA Paper Total Connections (visible)
    {'color': 'E4F9D4', 'columns': [
        'AA Paper Connections - Trade Customers',
        'AA Paper Connections - Non-Trade Customers',
        'AA Paper Connections - Non-Maybank',
        'AA Paper Total Connections',  # show this
    ]},
    # 8. Payment Summary -- 10 hidden + Payment Net Flow (visible)
    {'color': 'B7CFE6', 'columns': [
        'Payment Connections - Trade Customers',
        'Payment Connections - Non-Trade Customers',
        'Payment Connections - Non-Maybank',
        'Payment Total Connections',
        'Payment Transactions Sent (Count)',     'Payment Amount Sent (SGD)',
        'Payment Transactions Received (Count)', 'Payment Amount Received (SGD)',
        'Payment Self-Transfer (Count)',         'Payment Self-Transfer Amount (SGD)',
        'Payment Net Flow (SGD)',  # show this
    ]},
    # 9. All Transactions -- 9 hidden + All Txn Net Flow (visible)
    {'color': 'F8D9A2', 'columns': [
        'All Txn Connections - Trade Customers',
        'All Txn Connections - Non-Trade Customers',
        'All Txn Connections - Non-Maybank',
        'All Txn Total Connections',
        'All Txn Transactions Sent (Count)',     'All Txn Amount Sent (SGD)',
        'All Txn Transactions Received (Count)', 'All Txn Amount Received (SGD)',
        'All Txn Latest Record',
        'All Txn Net Flow (SGD)',  # show this
    ]},
    # 10. Network Overview -- 12 hidden + Total Connections (All Networks) (visible)
    {'color': 'FFE5CC', 'columns': [
        'Total Connections - Trade Customers',
        'Total Connections - Non-Trade Customers',
        'Total Connections - Non-Maybank',
        'Total Connections - Trade %',
        'Total Connections - Non-Trade %',
        'Total Connections - Non-Maybank %',
        'Total Connections - SG', 'Total Connections - MY',
        'Total Connections to Buyers', 'Total Connections to Suppliers',
        'Total Connections to Maybank Customer Buyers',
        'Total Connections to Maybank Customer Suppliers',
        'Total Connections (All Networks)',  # show this
    ]},
    # 11. Entity Info (no grouping)
    {'color': 'D4E4F7', 'columns': [
        'Entity Type', 'Entity Status', 'First CA Opening Date',
        'Relationship Tenure (Days)', 'Postal Code', 'SSIC Code',
        'Sector', 'Industry',
        'City', 'No. Employees', 'Listed / Unlisted',
        'Export Countries', 'Incorporation Date', 'Business Description',
    ]},
    # 12. Facilities (no grouping)
    {'color': 'E8C5D4', 'columns': [
        'Trade Authorised Limit (SGD)', 'Trade Available Limit (SGD)',
        'Trade Outstanding Balance (SGD)',
        'Trade On-Balance Sheet Outstanding (SGD)',
        'Trade Off-Balance Sheet Outstanding (SGD)',
        'Trade Utilisation (%)',
        'Latest AA Creation Date',
        'Trade Loan (SGD)', 'Non-Trade Loan (SGD)', 'Total Loan Balances (SGD)',
        'Current Account (SGD)', 'TD (SGD)', 'Structured TD (SGD)',
        'Total Deposit Balances (SGD)',
    ]},
    # 13. Credit Status (no grouping)
    {'color': 'FFCCCC', 'columns': [
        'Credit Status', 'Impairment Stage', 'Risk Grade',
        'Is Watchlist', 'Is Special Mention (SMA)', 'Is NPL',
        'Months on Book', 'Borrower Risk Rating (BRR)', 'Rating Date',
        'Latest DPD Bucket', 'Delinquency Count (12M)',
    ]},
    # 14. ACRA Financials (no grouping)
    {'color': 'D4F1E8', 'columns': [
        'ACRA Financial Year End', 'ACRA Sales Revenue (SGD)',
        'ACRA Profit Before Tax (SGD)', 'ACRA Cash & Bank Balance (SGD)',
        'ACRA Trade Creditors (SGD)', 'ACRA Trade Debtors (SGD)',
    ]},
    # 15. Charges (no grouping)
    {'color': 'D4E8F7', 'columns': [
        'Charge Count', 'Unique Chargee Count',
        'Earliest Charge Reg Date', 'Latest Charge Reg Date',
        'Charge Secured Amount (SGD)',
        'Charges - All Monies Owing (Y Count)',
        'Charges - All Monies Owing (N Count)',
    ]},
    # 16. EMIS (no grouping)
    {'color': 'FDE8D8', 'columns': [
        'EMIS Country', 'EMIS Company Name', 'EMIS Industry',
        'EMIS Key Executives', 'EMIS Company ID',
        'EMIS Fiscal Year', 'EMIS Audited', 'EMIS Source',
        'Total Operating Revenue (USD)', 'Operating Profit (USD)',
        'Profit Before Income Tax (USD)', 'Total Assets (USD)',
        'Free Cash Flow (USD)', 'Net Cash Flow from Operations (USD)',
        'EMIS ROA (%)', 'EMIS ROE (%)',
    ]},
    # 17. MFI Financials (no grouping). Includes J1 metadata + J2 P&L +
    # J3 balance sheet + J4 ratios so Recipe 4's MFI accordion (sub-sections
    # J1-J4) renders complete data. Order: metadata, P&L, balance sheet, ratios.
    {'color': 'AED6F1', 'columns': [
        # J1 -- Statement metadata
        'MFI Financial Year End', 'MFI Statement Type', 'MFI Auditor',
        'MFI Qualified Opinion', 'MFI Segment', 'MFI Period Length (Months)',
        'MFI Statement Status', 'MFI Processing Date',
        'MFI Target Currency', 'MFI Base Currency', 'MFI Model Name',
        # J2 -- P&L
        'MFI Sales Revenue (SGD)', 'MFI COGS (SGD)',
        'MFI Gross Operating P&L (SGD)',
        'MFI Pre-Tax P&L Before Int (SGD)',
        'MFI Profit Before Tax (SGD)', 'MFI Profit After Tax (SGD)',
        'MFI EBITDA (SGD)',
        # J3 -- Balance sheet
        'MFI Total Assets (SGD)', 'MFI Current Assets (SGD)',
        'MFI Non-Current Assets (SGD)',
        'MFI Total Liabilities (SGD)', 'MFI Current Liabilities (SGD)',
        'MFI Non-Current Liabilities (SGD)',
        'MFI Total Equity (SGD)',
        'MFI Short-Term Debt (SGD)', 'MFI Long-Term Debt (SGD)',
        'MFI Total Debt (SGD)',
        'MFI Debt Service (SGD)',
        'MFI Tangible Net Worth (SGD)', 'MFI Adjusted TNW (SGD)',
        # J4 -- Ratios
        'MFI DSCR', 'MFI Gearing Ratio',
    ]},
    # 18. CIP (no grouping)
    {'color': 'D5F5E3', 'columns': [
        'CIP Facility Limit (SGD)', 'CIP Loan Balance (SGD)', 'CIP NPL Balance (SGD)',
        'CIP Security Amount (SGD)', 'CIP Estimated Market Value (SGD)',
        'CIP Forced Sale Value (SGD)', 'CIP Fire Insurance Value (SGD)',
        'CIP No. Properties',
        'CIP Total Accounts', 'CIP Open Accounts', 'CIP Closed Accounts',
        'CIP Earliest Account Open Date', 'CIP Latest Account Open Date',
        'CIP Earliest Open Account Date', 'CIP Latest Open Account Date',
        'CIP Earliest Closed Account Date', 'CIP Latest Account Close Date',
        'CIP Facility Processing Date', 'CIP Balance Processing Date',
        'CIP Latest Default Date',
        'CIP JTC Properties Count',
        'CIP Owner Occupied Properties', 'CIP Tenanted Properties',
        'CIP Business Ops Properties', 'CIP Vacant Properties',
    ]},
]

EDGE_SECTIONS = [
    {'color': 'A8D5E2', 'columns': ['Source (UEN)', 'Source (Name)', 'Source (Country)', 'Source (Segment)']},
    {'color': 'C9E4C5', 'columns': ['Target (UEN)', 'Target (Name)', 'Target (Country)', 'Target (Segment)']},
    {'color': 'FFE5CC', 'columns': ['Total Transaction Count', 'Total Transaction Amount (SGD)']},
    {'color': 'E8D4F1', 'columns': ['Self-Transfer', 'Data Source', 'Relationship Description']},
]

PAIRS_RENAME = {
    'buyer_uen': 'Buyer UEN', 'buyer_name': 'Buyer Name',
    'supplier_uen': 'Supplier UEN', 'supplier_name': 'Supplier Name',
    'customer_uen': 'Customer UEN', 'customer_name': 'Customer Name',
    'counterparty_uen': 'Counterparty UEN', 'counterparty_name': 'Counterparty Name',
    'is_both': 'Is Both Ways', 'priority_source': 'Priority Source',
    'in_fitas': 'In FITAS', 'in_aa': 'In AA Paper', 'in_tt': 'In TT', 'in_rsme': 'In RSME',
    'tt_buyer_to_supplier_count'   : 'TT Buyer->Supplier Count',
    'tt_buyer_to_supplier_amt'     : 'TT Buyer->Supplier Amount (SGD)',
    'tt_buyer_to_supplier_amt_pct' : 'TT Buyer->Supplier Amount %',
    'tt_supplier_to_buyer_count'   : 'TT Supplier->Buyer Count',
    'tt_supplier_to_buyer_amt'     : 'TT Supplier->Buyer Amount (SGD)',
    'tt_supplier_to_buyer_amt_pct' : 'TT Supplier->Buyer Amount %',
    'tt_total_count': 'TT Total Count', 'tt_total_amt': 'TT Total Amount (SGD)',
    'fitas_lc_count': 'FITAS LC Count', 'fitas_tr_count': 'FITAS TR Count',
    'fitas_sta_count': 'FITAS STA Count', 'fitas_exportlc_count': 'FITAS ExportLC Count',
    'fitas_fbep_count': 'FITAS FBEP Count', 'fitas_oat_count': 'FITAS OAT Count',
    'fitas_others_count': 'FITAS Others Count',
    'fitas_lc_amt': 'FITAS LC Amount (SGD)', 'fitas_tr_amt': 'FITAS TR Amount (SGD)',
    'fitas_sta_amt': 'FITAS STA Amount (SGD)', 'fitas_exportlc_amt': 'FITAS ExportLC Amount (SGD)',
    'fitas_fbep_amt': 'FITAS FBEP Amount (SGD)', 'fitas_oat_amt': 'FITAS OAT Amount (SGD)',
    'fitas_others_amt': 'FITAS Others Amount (SGD)',
    'fitas_total_amt': 'FITAS Trade Amount (SGD)',
    'grand_total_amt': 'Grand Total Amount (SGD)',
    # Per-source pair columns
    'fast_buyer_to_supplier_count'    : 'FAST Buyer->Supplier Count',
    'fast_buyer_to_supplier_amt'      : 'FAST Buyer->Supplier Amount (SGD)',
    'fast_buyer_to_supplier_amt_pct'  : 'FAST Buyer->Supplier Amount %',
    'fast_supplier_to_buyer_count'    : 'FAST Supplier->Buyer Count',
    'fast_supplier_to_buyer_amt'      : 'FAST Supplier->Buyer Amount (SGD)',
    'fast_supplier_to_buyer_amt_pct'  : 'FAST Supplier->Buyer Amount %',
    'fast_total_count'                : 'FAST Total Count',
    'fast_total_amt'                  : 'FAST Total Amount (SGD)',
    'giro_buyer_to_supplier_count'    : 'GIRO Buyer->Supplier Count',
    'giro_buyer_to_supplier_amt'      : 'GIRO Buyer->Supplier Amount (SGD)',
    'giro_buyer_to_supplier_amt_pct'  : 'GIRO Buyer->Supplier Amount %',
    'giro_supplier_to_buyer_count'    : 'GIRO Supplier->Buyer Count',
    'giro_supplier_to_buyer_amt'      : 'GIRO Supplier->Buyer Amount (SGD)',
    'giro_supplier_to_buyer_amt_pct'  : 'GIRO Supplier->Buyer Amount %',
    'giro_total_count'                : 'GIRO Total Count',
    'giro_total_amt'                  : 'GIRO Total Amount (SGD)',
    'payment_buyer_to_supplier_count' : 'Payment Buyer->Supplier Count',
    'payment_buyer_to_supplier_amt'   : 'Payment Buyer->Supplier Amount (SGD)',
    'payment_buyer_to_supplier_amt_pct': 'Payment Buyer->Supplier Amount %',
    'payment_supplier_to_buyer_count' : 'Payment Supplier->Buyer Count',
    'payment_supplier_to_buyer_amt'   : 'Payment Supplier->Buyer Amount (SGD)',
    'payment_supplier_to_buyer_amt_pct': 'Payment Supplier->Buyer Amount %',
    'payment_total_count'             : 'Payment Total Count',
    'payment_total_amt'               : 'Payment Total Amount (SGD)',
    'all_txn_buyer_to_supplier_count' : 'All Txn Buyer->Supplier Count',
    'all_txn_buyer_to_supplier_amt'   : 'All Txn Buyer->Supplier Amount (SGD)',
    'all_txn_buyer_to_supplier_amt_pct': 'All Txn Buyer->Supplier Amount %',
    'all_txn_supplier_to_buyer_count' : 'All Txn Supplier->Buyer Count',
    'all_txn_supplier_to_buyer_amt'   : 'All Txn Supplier->Buyer Amount (SGD)',
    'all_txn_supplier_to_buyer_amt_pct': 'All Txn Supplier->Buyer Amount %',
    'all_txn_total_count'             : 'All Txn Total Count',
    'all_txn_total_amt'               : 'All Txn Total Amount (SGD)',
    'in_fast'                         : 'In FAST',
    'in_giro'                         : 'In GIRO',
    'in_payment'                      : 'In Payment',
}

PAIRS_SECTIONS = [
    {'color': 'A8D5E2', 'columns': [
        'Buyer UEN', 'Buyer Name', 'Supplier UEN', 'Supplier Name',
        'Customer UEN', 'Customer Name', 'Counterparty UEN', 'Counterparty Name',
    ]},
    {'color': 'FFE5CC', 'columns': [
        'Is Both Ways', 'Priority Source', 'In FITAS', 'In AA Paper', 'In TT', 'In RSME',
    ]},
    {'color': 'E8D4F1', 'columns': [
        'TT Buyer->Supplier Count', 'TT Buyer->Supplier Amount (SGD)', 'TT Buyer->Supplier Amount %',
        'TT Supplier->Buyer Count', 'TT Supplier->Buyer Amount (SGD)', 'TT Supplier->Buyer Amount %',
        'TT Total Count', 'TT Total Amount (SGD)',
    ]},
    {'color': 'C9E4C5', 'columns': [
        'FITAS LC Count', 'FITAS TR Count', 'FITAS STA Count', 'FITAS ExportLC Count',
        'FITAS FBEP Count', 'FITAS OAT Count', 'FITAS Others Count',
    ]},
    {'color': 'D4F1E8', 'columns': [
        'FITAS LC Amount (SGD)', 'FITAS TR Amount (SGD)', 'FITAS STA Amount (SGD)',
        'FITAS ExportLC Amount (SGD)', 'FITAS FBEP Amount (SGD)',
        'FITAS OAT Amount (SGD)', 'FITAS Others Amount (SGD)',
    ]},
    {'color': 'FFF4CC', 'columns': [
        'FITAS Trade Amount (SGD)', 'TT Transaction Amount (SGD)', 'Grand Total Amount (SGD)',
    ]},
    {'color': 'D4F1E8', 'columns': [
        'In FAST', 'In GIRO', 'In Payment',
    ]},
    {'color': 'D6E4F2', 'columns': [
        'FAST Buyer->Supplier Count', 'FAST Buyer->Supplier Amount (SGD)', 'FAST Buyer->Supplier Amount %',
        'FAST Supplier->Buyer Count', 'FAST Supplier->Buyer Amount (SGD)', 'FAST Supplier->Buyer Amount %',
        'FAST Total Count', 'FAST Total Amount (SGD)',
    ]},
    {'color': 'D0EAE2', 'columns': [
        'GIRO Buyer->Supplier Count', 'GIRO Buyer->Supplier Amount (SGD)', 'GIRO Buyer->Supplier Amount %',
        'GIRO Supplier->Buyer Count', 'GIRO Supplier->Buyer Amount (SGD)', 'GIRO Supplier->Buyer Amount %',
        'GIRO Total Count', 'GIRO Total Amount (SGD)',
    ]},
    {'color': 'B7CFE6', 'columns': [
        'Payment Buyer->Supplier Count', 'Payment Buyer->Supplier Amount (SGD)', 'Payment Buyer->Supplier Amount %',
        'Payment Supplier->Buyer Count', 'Payment Supplier->Buyer Amount (SGD)', 'Payment Supplier->Buyer Amount %',
        'Payment Total Count', 'Payment Total Amount (SGD)',
    ]},
    {'color': 'F8D9A2', 'columns': [
        'All Txn Buyer->Supplier Count', 'All Txn Buyer->Supplier Amount (SGD)', 'All Txn Buyer->Supplier Amount %',
        'All Txn Supplier->Buyer Count', 'All Txn Supplier->Buyer Amount (SGD)', 'All Txn Supplier->Buyer Amount %',
        'All Txn Total Count', 'All Txn Total Amount (SGD)',
    ]},
]

_PAIRS_FLAT_COLS = [c for sec in PAIRS_SECTIONS for c in sec['columns']]

def _prepare_pairs_for_excel(pairs_df):
    df = pairs_df.copy()
    df = df.rename(columns=PAIRS_RENAME)
    if 'Grand Total Amount (SGD)' in df.columns and 'FITAS Trade Amount (SGD)' in df.columns:
        df['TT Transaction Amount (SGD)'] = (
            df['Grand Total Amount (SGD)'].fillna(0) -
            df['FITAS Trade Amount (SGD)'].fillna(0)
        ).apply(lambda v: int(round(v)) if pd.notna(v) else None)
    keep = [c for c in _PAIRS_FLAT_COLS if c in df.columns]
    return df[keep].copy()

pairs_full_final     = _prepare_pairs_for_excel(pairs_full_df)
pairs_filtered_final = _prepare_pairs_for_excel(pairs_filtered_df)

nodes_full_final     = nodes_full_final.rename(columns=NODE_RENAME)
nodes_filtered_final = nodes_filtered_final.rename(columns=NODE_RENAME)
edges_full_final     = edges_full_final.rename(columns=EDGE_RENAME)
edges_filtered_final = edges_filtered_final.rename(columns=EDGE_RENAME)

print(f"\nPairs columns:       {len(pairs_full_final.columns)}")
print(f"Pairs full rows:     {len(pairs_full_final):,}")
print(f"Pairs filtered rows: {len(pairs_filtered_final):,}")
print("Column renaming and section colors defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 5: Build Excel with Formatting Functions

def _build_and_upload(nodes_df, edges_df, pairs_df, filename):
    buf = io.BytesIO()
    wb  = xlsxwriter.Workbook(buf, {'in_memory': True, 'nan_inf_to_errors': True})
    node_df_ordered = _write_sheet(wb, nodes_df,  'Customer Network Data', NODE_SECTIONS,  is_node=True)
    _write_sheet(wb, edges_df,  'Relationship Details',   EDGE_SECTIONS,  is_node=False)
    _write_sheet(wb, pairs_df,  'Buyer-Supplier Pairs',   PAIRS_SECTIONS, is_node=False)
    wb.close()
    buf.seek(0)
    Network_Graph_Report.upload_stream(filename, buf)
    print(f"  Uploaded: {filename}")
    print(f"    Nodes: {len(nodes_df):,}  |  Edges: {len(edges_df):,}  |  Pairs: {len(pairs_df):,}")
    return node_df_ordered

def _write_sheet(wb, df, sheet_name, sections, is_node=False):
    column_order  = []
    column_colors = {}
    for section in sections:
        for col in section['columns']:
            if col in df.columns:
                column_order.append(col)
                column_colors[col] = section['color']

    df_ordered = df[column_order].copy()
    df_ordered = df_ordered[_source_contiguous_order(df_ordered, is_node)]
    ws         = wb.add_worksheet(sheet_name)
    n_rows     = len(df_ordered)
    n_cols     = len(df_ordered.columns)

    header_fmt_cache = {}
    def _header_fmt(hex_color):
        if hex_color not in header_fmt_cache:
            header_fmt_cache[hex_color] = wb.add_format({
                'bold': True, 'font_name': 'Arial', 'font_size': 10,
                'bg_color': f'#{hex_color}', 'font_color': '#000000',
                'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 0,
            })
        return header_fmt_cache[hex_color]

    fmt_default      = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'left',  'valign': 'vcenter'})
    fmt_alt          = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'left',  'valign': 'vcenter', 'bg_color': '#F8F9FA'})
    fmt_currency     = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '$#,##0'})
    fmt_currency_alt = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '$#,##0', 'bg_color': '#F8F9FA'})
    fmt_pct          = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00%'})
    fmt_pct_alt      = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00%', 'bg_color': '#F8F9FA'})
    fmt_raw_pct      = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00"%"'})
    fmt_raw_pct_alt  = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00"%"', 'bg_color': '#F8F9FA'})
    fmt_plain_pct     = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.0"%"'})
    fmt_plain_pct_alt = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.0"%"', 'bg_color': '#F8F9FA'})
    # *** new | MFI ratio format -- plain decimal 2dp, right-aligned
    fmt_ratio         = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00'})
    fmt_ratio_alt     = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'align': 'right', 'valign': 'vcenter', 'num_format': '0.00', 'bg_color': '#F8F9FA'})

    cust_type_fmts = {
        'Maybank Trade Customer'    : wb.add_format({'font_name': 'Arial', 'font_size': 10, 'bg_color': '#D5F5E3', 'align': 'left', 'valign': 'vcenter'}),
        'Maybank Non-Trade Customer': wb.add_format({'font_name': 'Arial', 'font_size': 10, 'bg_color': '#FEF3CD', 'align': 'left', 'valign': 'vcenter'}),
        'Non-Maybank Customer'      : wb.add_format({'font_name': 'Arial', 'font_size': 10, 'bg_color': '#E8E8E8', 'align': 'left', 'valign': 'vcenter'}),
    }

    # *** updated | ratio col display names after NODE_RENAME
    RATIO_DISPLAY_COLS = {'MFI DSCR', 'MFI Gearing Ratio'}
    RAW_PCT_COLS       = {'EMIS ROA (%)', 'EMIS ROE (%)'}
    PLAIN_PCT_COLS = {'TT Buyer->Supplier Amount %', 'TT Supplier->Buyer Amount %', 'Trade Utilisation (%)'}

    currency_set  = {col for col in df_ordered.columns if '(SGD)' in col or '(USD)' in col}
    pct_set       = {col for col in df_ordered.columns if col.endswith('(%)') and col not in RAW_PCT_COLS}
    raw_pct_set   = {col for col in df_ordered.columns if col in RAW_PCT_COLS}
    plain_pct_set = {col for col in df_ordered.columns if col in PLAIN_PCT_COLS}
    ratio_set     = {col for col in df_ordered.columns if col in RATIO_DISPLAY_COLS}

    cust_type_col_idx = (
        df_ordered.columns.get_loc('Customer Type')
        if is_node and 'Customer Type' in df_ordered.columns else None
    )

    ws.set_row(0, 30)
    for col_idx, col_name in enumerate(df_ordered.columns):
        ws.write(0, col_idx, col_name, _header_fmt(column_colors[col_name]))

    records = df_ordered.values.tolist()
    for row_idx, record in enumerate(records):
        xl_row = row_idx + 1
        is_alt = (xl_row % 2 == 0)
        for col_idx, value in enumerate(record):
            col_name     = df_ordered.columns[col_idx]
            is_cur       = col_name in currency_set
            is_pct       = col_name in pct_set
            is_raw_pct   = col_name in raw_pct_set
            is_plain_pct = col_name in plain_pct_set
            is_ratio     = col_name in ratio_set

            if is_node and col_idx == cust_type_col_idx and value in cust_type_fmts:
                fmt = cust_type_fmts[value]
            elif is_ratio:
                fmt = fmt_ratio_alt if is_alt else fmt_ratio
            elif is_cur:
                fmt = fmt_currency_alt if is_alt else fmt_currency
            elif is_pct:
                fmt = fmt_pct_alt if is_alt else fmt_pct
            elif is_raw_pct:
                fmt = fmt_raw_pct_alt if is_alt else fmt_raw_pct
            elif is_plain_pct:
                fmt = fmt_plain_pct_alt if is_alt else fmt_plain_pct
            else:
                fmt = fmt_alt if is_alt else fmt_default

            if value is None or (isinstance(value, float) and value != value):
                ws.write_blank(xl_row, col_idx, None, fmt)
            elif (is_cur or is_pct or is_raw_pct or is_plain_pct or is_ratio) and isinstance(value, (int, float)):
                ws.write_number(xl_row, col_idx, value, fmt)
            else:
                ws.write(xl_row, col_idx, value, fmt)

    for col_idx, col_name in enumerate(df_ordered.columns):
        max_len = len(str(col_name))
        if n_rows > 0:
            col_max = df_ordered.iloc[:, col_idx].astype(str).str.len().max()
            max_len = max(max_len, col_max)
        ws.set_column(col_idx, col_idx, min(max_len + 2, 60))

    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, n_rows, n_cols - 1)
    if is_node:
        _apply_column_groups(ws, df_ordered)
    return df_ordered

def _source_contiguous_order(df, is_node):
    """
    Return columns in their NODE_SECTIONS-defined order. NODE_SECTIONS already
    lays out columns per-section with the "show this" summary at the right
    edge of each grouped section, so no further reordering is needed.
    """
    return list(df.columns)


def _apply_column_groups(ws, df):
    """
    Apply Excel column outline groups so each grouped section's detail
    collapses cleanly.

    Bands (one per "show this" section, sections 1-10 of NODE_SECTIONS).
    Sections 11-18 (Entity Info, Facilities, Credit Status, ACRA Financials,
    Charges, EMIS, MFI Financials, CIP) are NOT grouped -- their columns
    stay fully visible.

    All bands collapse by default. The summary column for each band sits
    at the RIGHT edge of the grouped columns and stays visible (matches
    xlsxwriter's outline_settings(symbols_right=True)).

    Bands (column-order sequence):
      1. Identity        -- 6 source flags hidden, "Data Source" visible
      2. RSME Network    -- 3 hidden, "RSME Total Connections" visible
      3. TT Network      -- 13 hidden, "TT Net Flow (SGD)" visible
      4. FAST Network    -- 11 hidden, "FAST Net Flow (SGD)" visible
      5. GIRO Network    -- 11 hidden, "GIRO Net Flow (SGD)" visible
      6. FITAS Network   --  9 hidden, "FITAS Total Amount (SGD)" visible
      7. AA Paper        --  3 hidden, "AA Paper Total Connections" visible
      8. Payment Summary -- 10 hidden, "Payment Net Flow (SGD)" visible
      9. All Transactions--  9 hidden, "All Txn Net Flow (SGD)" visible
     10. Network Overview-- 10 hidden, "Total Connections (All Networks)" visible
    """
    col_names = list(df.columns)

    # (hidden_columns_for_this_band, hidden_default)
    # Listed columns will be hidden (collapsed by default); the summary
    # column for that section is omitted from the list and stays visible.
    BANDS = [
        # 1. Identity -- hide 6 source flags; "Data Source" + always-visible cols stay
        ([
            'In RSME Network', 'In TT Network', 'In FAST Network',
            'In GIRO Network', 'In FITAS Network', 'In AA Paper Network',
        ], True),

        # 2. RSME Network -- hide 3, keep "RSME Total Connections"
        ([
            'RSME Connections - Trade Customers',
            'RSME Connections - Non-Trade Customers',
            'RSME Connections - Non-Maybank',
        ], True),

        # 3. TT Network -- hide 13, keep "TT Net Flow (SGD)"
        ([
            'TT Connections - Trade Customers',
            'TT Connections - Non-Trade Customers',
            'TT Connections - Non-Maybank',
            'TT Total Connections',
            'TT Connections - SG', 'TT Connections - MY',
            'TT Transactions Sent (Count)',     'TT Amount Sent (SGD)',
            'TT Transactions Received (Count)', 'TT Amount Received (SGD)',
            'TT Self-Transfer (Count)',         'TT Self-Transfer Amount (SGD)',
            'TT Latest Record',
        ], True),

        # 4. FAST Network -- hide 11, keep "FAST Net Flow (SGD)"
        ([
            'FAST Connections - Trade Customers',
            'FAST Connections - Non-Trade Customers',
            'FAST Connections - Non-Maybank',
            'FAST Total Connections',
            'FAST Transactions Sent (Count)',     'FAST Amount Sent (SGD)',
            'FAST Transactions Received (Count)', 'FAST Amount Received (SGD)',
            'FAST Self-Transfer (Count)',         'FAST Self-Transfer Amount (SGD)',
            'FAST Latest Record',
        ], True),

        # 5. GIRO Network -- hide 11, keep "GIRO Net Flow (SGD)"
        ([
            'GIRO Connections - Trade Customers',
            'GIRO Connections - Non-Trade Customers',
            'GIRO Connections - Non-Maybank',
            'GIRO Total Connections',
            'GIRO Transactions Sent (Count)',     'GIRO Amount Sent (SGD)',
            'GIRO Transactions Received (Count)', 'GIRO Amount Received (SGD)',
            'GIRO Self-Transfer (Count)',         'GIRO Self-Transfer Amount (SGD)',
            'GIRO Latest Record',
        ], True),

        # 6. FITAS Network -- hide 9, keep "FITAS Total Amount (SGD)"
        ([
            'FITAS Connections - Trade Customers',
            'FITAS Connections - Non-Trade Customers',
            'FITAS Connections - Non-Maybank',
            'FITAS Total Connections',
            'FITAS Transactions Sent (Count)',     'FITAS Amount Sent (SGD)',
            'FITAS Transactions Received (Count)', 'FITAS Amount Received (SGD)',
            'FITAS Latest Record',
        ], True),

        # 7. AA Paper Network -- hide 3, keep "AA Paper Total Connections"
        ([
            'AA Paper Connections - Trade Customers',
            'AA Paper Connections - Non-Trade Customers',
            'AA Paper Connections - Non-Maybank',
        ], True),

        # 8. Payment Summary -- hide 10, keep "Payment Net Flow (SGD)"
        ([
            'Payment Connections - Trade Customers',
            'Payment Connections - Non-Trade Customers',
            'Payment Connections - Non-Maybank',
            'Payment Total Connections',
            'Payment Transactions Sent (Count)',     'Payment Amount Sent (SGD)',
            'Payment Transactions Received (Count)', 'Payment Amount Received (SGD)',
            'Payment Self-Transfer (Count)',         'Payment Self-Transfer Amount (SGD)',
        ], True),

        # 9. All Transactions -- hide 9, keep "All Txn Net Flow (SGD)"
        ([
            'All Txn Connections - Trade Customers',
            'All Txn Connections - Non-Trade Customers',
            'All Txn Connections - Non-Maybank',
            'All Txn Total Connections',
            'All Txn Transactions Sent (Count)',     'All Txn Amount Sent (SGD)',
            'All Txn Transactions Received (Count)', 'All Txn Amount Received (SGD)',
            'All Txn Latest Record',
        ], True),

        # 10. Network Overview -- hide 12, keep "Total Connections (All Networks)"
        ([
            'Total Connections - Trade Customers',
            'Total Connections - Non-Trade Customers',
            'Total Connections - Non-Maybank',
            'Total Connections - Trade %',
            'Total Connections - Non-Trade %',
            'Total Connections - Non-Maybank %',
            'Total Connections - SG', 'Total Connections - MY',
            'Total Connections to Buyers', 'Total Connections to Suppliers',
            'Total Connections to Maybank Customer Buyers',
            'Total Connections to Maybank Customer Suppliers',
        ], True),
    ]

    # First, set every column to level 0 (visible, ungrouped)
    for idx, col_name in enumerate(col_names):
        cur_width = min(len(str(col_name)) + 2, 60)
        ws.set_column(idx, idx, cur_width, None, {'level': 0, 'hidden': False})

    # Then mark each band's columns as level 1, hidden by default
    n_bands_applied = 0
    for band_cols, hidden in BANDS:
        present = [c for c in band_cols if c in col_names]
        if not present:
            continue
        for col_name in present:
            idx       = col_names.index(col_name)
            cur_width = min(len(str(col_name)) + 2, 60)
            ws.set_column(idx, idx, cur_width, None, {'level': 1, 'hidden': hidden})
        n_bands_applied += 1

    # xlsxwriter outline summary direction: by default, summary column is below
    # rows / right of grouped columns. With outline_settings(symbols_below=True,
    # symbols_right=True), the [+]/[-] toggle appears at the right edge of each
    # band -- which is what spreadsheet users expect.
    ws.outline_settings(visible=True, symbols_below=True, symbols_right=True, auto_style=False)

    print(f"  Column groups applied: {n_bands_applied}/{len(BANDS)} bands "
          f"(all detail collapsed by default; click [+] in each band to expand)")

print("Formatting functions defined")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 6: Generate Both Excel Reports and Compare

print("\n" + "="*60)
print("GENERATING EXCEL REPORTS")
print("="*60)

print("\nBuilding full report...")
node_df_ordered_full = _build_and_upload(
    nodes_full_final, edges_full_final, pairs_full_final,
    'MEXT_SCREENER_full.xlsx'
)

print("\nBuilding filtered report...")
node_df_ordered_filtered = _build_and_upload(
    nodes_filtered_final, edges_filtered_final, pairs_filtered_final,
    'MEXT_SCREENER_filtered.xlsx'
)

n_nodes_full     = len(nodes_full_final)
n_nodes_filtered = len(nodes_filtered_final)
n_edges_full     = len(edges_full_final)
n_edges_filtered = len(edges_filtered_final)

tt_full     = edges_full_final[edges_full_final['Data Source'] == 'Consolidated_TT']
tt_filtered = edges_filtered_final[edges_filtered_final['Data Source'] == 'Consolidated_TT']

print("\n" + "="*60)
print("COMPARISON SUMMARY")
print("="*60)
print(f"\n  Filter: drop TT edge rows where txn_amt < S${TT_EDGE_MIN_AMT:,} per direction")
print(f"          then remove nodes with zero remaining edges (all sources)")
print(f"\n  {'Metric':<35} {'Full':>10} {'Filtered':>10} {'Removed':>10} {'%':>7}")
print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*10} {'-'*7}")
print(f"  {'Nodes':<35} {n_nodes_full:>10,} {n_nodes_filtered:>10,} "
      f"{n_nodes_full - n_nodes_filtered:>10,} "
      f"{(n_nodes_full - n_nodes_filtered)/max(n_nodes_full,1)*100:>6.1f}%")
print(f"  {'Edges (all sources)':<35} {n_edges_full:>10,} {n_edges_filtered:>10,} "
      f"{n_edges_full - n_edges_filtered:>10,} "
      f"{(n_edges_full - n_edges_filtered)/max(n_edges_full,1)*100:>6.1f}%")
print(f"  {'TT edges only':<35} {len(tt_full):>10,} {len(tt_filtered):>10,} "
      f"{len(tt_full) - len(tt_filtered):>10,} "
      f"{(len(tt_full) - len(tt_filtered))/max(len(tt_full),1)*100:>6.1f}%")
print(f"  {'Non-TT edges':<35} {n_edges_full - len(tt_full):>10,} "
      f"{n_edges_filtered - len(tt_filtered):>10,} {'0':>10} {'0.0%':>7}")
print(f"  {'Buyer-Supplier pairs':<35} {len(pairs_full_final):>10,} "
      f"{len(pairs_filtered_final):>10,} "
      f"{len(pairs_full_final) - len(pairs_filtered_final):>10,} "
      f"{(len(pairs_full_final) - len(pairs_filtered_final))/max(len(pairs_full_final),1)*100:>6.1f}%")

print("\n" + "="*60)
print("BOTH REPORTS UPLOADED")
print("="*60)
print(f"  MEXT_SCREENER_full.xlsx     (3 sheets)")
print(f"  MEXT_SCREENER_filtered.xlsx (3 sheets)")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
self_loop_uens     = set(tt_filtered_edges_self['SOURCE_UEN'].astype(str).unique())
node_filtered_uens = set(nodes_filtered['UEN'].astype(str).unique())
missing_self_loop  = self_loop_uens - node_filtered_uens
print(f"Self-loop UENs not in nodes_filtered: {len(missing_self_loop)}")
missing_amt = tt_filtered_edges_self[
    tt_filtered_edges_self['SOURCE_UEN'].astype(str).isin(missing_self_loop)
]['txn_amt'].sum()
print(f"Their self-transfer amount: S${missing_amt:,.0f}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
nodes_filtered_final[nodes_filtered_final['Company Name'] == 'SANLI M&E ENGINEERING PTE. LTD.']