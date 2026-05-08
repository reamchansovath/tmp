# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Local twin: when DATAIKU_ENV=local, register mock_dataiku as the dataiku
# module so every later `import dataiku` (across all cells) resolves to the
# mock. In Dataiku, DATAIKU_ENV is not set so this block is a no-op.

import os, sys
if os.getenv('DATAIKU_ENV') == 'local':
    import mock_dataiku
    sys.modules['dataiku'] = mock_dataiku


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Recipe 4

# Cell 1: Imports, load Excel reports from input folder + load Maybank logo as base64

import dataiku  # type: ignore[import-not-found]
import pandas as pd
import numpy as np
import json
import io
import base64
from datetime import datetime

Network_Graph_Report              = dataiku.Folder("rHjCkctR")
Network_Graph_Professional_Report = dataiku.Folder("vYiC1wqZ")
Main_Folder                       = dataiku.Folder("PeU8Pmk0")

def load_excel_report(folder, filename):
    with folder.get_download_stream(filename) as f:
        raw = f.read()
    xl     = pd.ExcelFile(io.BytesIO(raw))
    sheets = xl.sheet_names
    print(f"  {filename}: sheets = {sheets}")
    nodes_df = pd.read_excel(io.BytesIO(raw), sheet_name=sheets[0])
    edges_df = pd.read_excel(io.BytesIO(raw), sheet_name=sheets[1])
    return nodes_df, edges_df

LOGO_B64 = ""
LOGO_PATHS_TO_TRY = [
    "/Maybank Logo/maybank-logo-png-transparent.png",
    "Maybank Logo/maybank-logo-png-transparent.png",
]
for logo_path in LOGO_PATHS_TO_TRY:
    try:
        with Main_Folder.get_download_stream(logo_path) as f:
            logo_bytes = f.read()
        if len(logo_bytes) > 100:
            LOGO_B64 = "data:image/png;base64," + base64.b64encode(logo_bytes).decode("utf-8")
            print(f"Logo loaded OK: {logo_path}")
            print(f"  Raw bytes  : {len(logo_bytes):,}")
            print(f"  Base64 len : {len(LOGO_B64):,} chars")
            break
        else:
            print(f"Logo path returned empty file: {logo_path} ({len(logo_bytes)} bytes)")
    except Exception as e:
        print(f"Logo path failed: {logo_path} -- {e}")

if not LOGO_B64:
    print("WARNING: Logo not loaded. Header will show text fallback.")

available = Network_Graph_Report.list_paths_in_partition()
print("Files in input folder:")
for f in available: print(f"  {f}")

TARGET   = "MEXT_SCREENER_filtered.xlsx"
FALLBACK = "MEXT_SCREENER_full.xlsx"

if f"/{TARGET}" in available:
    print(f"\nLoading: {TARGET}")
    nodes_df, edges_df = load_excel_report(Network_Graph_Report, TARGET)
elif f"/{FALLBACK}" in available:
    print(f"\nFalling back to: {FALLBACK}")
    nodes_df, edges_df = load_excel_report(Network_Graph_Report, FALLBACK)
else:
    raise FileNotFoundError("No report Excel found in input folder.")

print(f"\nNodes: {len(nodes_df):,} rows x {nodes_df.shape[1]} cols")
print(f"Edges: {len(edges_df):,} rows x {edges_df.shape[1]} cols")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 1b: Load and process CIP property-level (application-level) data
# *** new | CIP_Collaterals_Info_Agg_Appl_df.feather from pD0HDxZR
# *** new | One row per property per UEN, sorted by SEC_AMT_SGD descending

CIP_FOLDER    = dataiku.Folder("pD0HDxZR")
CIP_APPL_FILE = "CIP_Collaterals_Info_Agg_Appl_df.feather"

_NULL_STRS = {'nan', 'null', 'na', '<na>', 'none', 'undefined', 'nat', ''}

def _pcs(v):
    if v is None: return None
    try:
        if pd.isna(v): return None
    except (TypeError, ValueError): pass
    s = str(v).strip()
    return None if s.lower() in _NULL_STRS else s

def _pci(v):
    if v is None: return None
    try:
        if pd.isna(v): return None
    except (TypeError, ValueError): pass
    try: return int(round(float(v)))
    except: return None

def _pfmt_date(v):
    """'2023-04-03 00:00:00' -> '03 Apr 2023'."""
    if v is None: return None
    try:
        if pd.isna(v): return None
    except (TypeError, ValueError): pass
    s = str(v).strip()
    if not s or s.lower() in _NULL_STRS: return None
    try: return pd.to_datetime(s).strftime('%d %b %Y')
    except: return s

def _pfmt_amt(ccy, amt):
    """'SGD' + 1250000 -> 'SGD 1,250,000'."""
    ccy_s = _pcs(ccy) or ''
    n = _pci(amt)
    if n is None: return None
    return f"{ccy_s} {n:,}".strip()

def _pconcat(a, b):
    a_s = _pcs(a) or ''
    b_s = _pcs(b) or ''
    r = f"{a_s} {b_s}".strip()
    return r if r else None

def _pbuild_addr(r):
    def gc(col):
        v = r.get(col)
        s = str(v).strip() if v is not None else ''
        return '' if s.lower() in _NULL_STRS else s
    unit        = gc('PLD_UNIT_NO')
    block       = gc('PLD_BLOCK')
    street      = gc('PLD_STREET')
    building    = gc('PLD_BUILDING')
    postal      = gc('PLD_POSTAL_CODE')
    street_part = f"{block} {street}".strip()
    parts = []
    if unit:        parts.append(unit)
    if street_part: parts.append(street_part)
    if building:    parts.append(building)
    if postal:      parts.append(f'Singapore {postal}')
    return ', '.join(parts) if parts else None

cip_props_by_uen = {}

try:
    with CIP_FOLDER.get_download_stream(CIP_APPL_FILE) as f:
        cip_appl_df = pd.read_feather(io.BytesIO(f.read()))
    print(f"CIP appl data loaded: {len(cip_appl_df):,} rows x {cip_appl_df.shape[1]} cols")

    cip_appl_df['ID_CODE'] = cip_appl_df['ID_CODE'].astype(str).str.strip().str.upper()

    if 'SEC_AMT_SGD' in cip_appl_df.columns:
        cip_appl_df['SEC_AMT_SGD'] = pd.to_numeric(cip_appl_df['SEC_AMT_SGD'], errors='coerce')

    cip_appl_df = cip_appl_df.sort_values(
        by=['ID_CODE', 'SEC_AMT_SGD'], ascending=[True, False], na_position='last'
    ).reset_index(drop=True)

    for uen, grp in cip_appl_df.groupby('ID_CODE', sort=False):
        props = []
        for _, row in grp.iterrows():
            r = row.to_dict()
            props.append({
                'appl_no'     : _pcs(r.get('APPL_NO')),
                'appl_closed' : _pcs(r.get('APPL_CLOSED')),
                'latest_opn'  : _pfmt_date(r.get('LATEST_AC_OPN_DTE')),
                'latest_cls'  : _pfmt_date(r.get('LATEST_AC_CLS_DTE')),
                'tot_rpym'    : _pci(r.get('TOT_RPYM_NO')),
                'sec_type'    : _pcs(r.get('SEC_SCRTY_TYPE')),
                'sec_amt'     : _pfmt_amt(r.get('SEC_CCY'), r.get('SEC_AMT_SGD')),
                'sec_emv'     : _pfmt_amt(r.get('SEC_CCY'), r.get('SEC_EMV_SGD')),
                'sec_fsv'     : _pfmt_amt(r.get('SEC_CCY'), r.get('SEC_FSV_SGD')),
                'sec_fiv'     : _pfmt_amt(r.get('SEC_CCY'), r.get('SEC_FIV_SGD')),
                'value_dte'   : _pfmt_date(r.get('VALUE_DTE')),
                'mort_cat'    : _pcs(r.get('MORT_CAT')),
                'ppty_amt'    : _pfmt_amt(r.get('PPTY_PURCH_CURCY_CODE'), r.get('PPTY_PURCH_AMT')),
                'land_area'   : _pconcat(r.get('PLD_LAND_AREA'), r.get('PLD_LAND_AREA_UNIT')),
                'built_up'    : _pconcat(r.get('BUILT_UP_AREA'), r.get('BUILT_UP_AREA_UNIT')),
                'lease_prd'   : _pconcat(r.get('PLD_LEASE_PRD'), r.get('PLD_LEASE_PRD_UNIT')),
                'occp_type'   : _pcs(r.get('PBD_OCCP_TYPE')),
                'first_party' : _pcs(r.get('FIRST_PARTY_SURETY')),
                'shared_sec'  : _pcs(r.get('SHARED_SEC_IND')),
                'jtc'         : _pcs(r.get('JTC_FLAG')),
                'address'     : _pbuild_addr(r),
            })
        cip_props_by_uen[uen] = props

    total_props = sum(len(v) for v in cip_props_by_uen.values())
    print(f"  UENs with property records : {len(cip_props_by_uen):,}")
    print(f"  Total property records     : {total_props:,}")

except Exception as e:
    print(f"WARNING: CIP application data not loaded -- {e}")
    import traceback; traceback.print_exc()
    cip_props_by_uen = {}

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 2: Auto-detect column names from Excel display headers
# *** updated | full MFI column set (all 33 fields) and full CIP column set
# *** updated | cip_dte_late removed; cip_dte_cls added (Latest Account Close Date)

NODE_COLS = list(nodes_df.columns)
EDGE_COLS = list(edges_df.columns)

def fc(cols, *patterns):
    for pat in patterns:
        for c in cols:
            if pat.lower() in c.lower():
                return c
    return None

N = {
    # ── Identity ──────────────────────────────────────────────────────────
    "uen":        fc(NODE_COLS, "UEN"),
    "name":       fc(NODE_COLS, "Company Name"),
    "cif":        fc(NODE_COLS, "CIF Number"),
    "country":    fc(NODE_COLS, "Country"),
    "segment":    fc(NODE_COLS, "Customer Segment"),
    "cust_type":  fc(NODE_COLS, "Customer Type"),
    "status":     fc(NODE_COLS, "Entity Status"),
    "ent_type":   fc(NODE_COLS, "Entity Type"),
    "sector":     fc(NODE_COLS, "Sector"),
    "industry":   fc(NODE_COLS, "Industry"),
    "ssic":       fc(NODE_COLS, "SSIC"),
    "parent":     fc(NODE_COLS, "Parent Group"),
    "first_ca":   fc(NODE_COLS, "First CA"),
    "tenure":     fc(NODE_COLS, "Relationship Tenure"),
    "data_src":   fc(NODE_COLS, "Data Source"),
    # ── Network degrees ───────────────────────────────────────────────────
    "total_deg":   fc(NODE_COLS, "Total Connections (All"),
    "tt_deg":      fc(NODE_COLS, "TT Total Connections"),
    "tt_sg":       fc(NODE_COLS, "TT Connections - SG"),
    "tt_my":       fc(NODE_COLS, "TT Connections - MY"),
    "rsme_deg":    fc(NODE_COLS, "RSME Total"),
    "fitas_deg":   fc(NODE_COLS, "FITAS Total"),
    "aa_deg":      fc(NODE_COLS, "AA Paper Total"),
    "total_sg":    fc(NODE_COLS, "Total Connections - SG"),
    "total_my":    fc(NODE_COLS, "Total Connections - MY"),
    "to_buyers":   fc(NODE_COLS, "Total Connections to Buyers"),
    "to_suppliers":fc(NODE_COLS, "Total Connections to Suppliers"),
    # ── TT flow ───────────────────────────────────────────────────────────
    "tt_sent":    fc(NODE_COLS, "TT Amount Sent"),
    "tt_recv":    fc(NODE_COLS, "TT Amount Received"),
    "tt_net":     fc(NODE_COLS, "TT Net Flow"),
    "tt_sc":      fc(NODE_COLS, "TT Self-Transfer (Count)"),
    "tt_sa":      fc(NODE_COLS, "TT Self-Transfer Amount"),
    # ── FAST flow ─────────────────────────────────────────────────────────
    "fast_deg":    fc(NODE_COLS, "FAST Total Connections"),
    "fast_sent":   fc(NODE_COLS, "FAST Amount Sent"),
    "fast_recv":   fc(NODE_COLS, "FAST Amount Received"),
    "fast_net":    fc(NODE_COLS, "FAST Net Flow"),
    "fast_sc":     fc(NODE_COLS, "FAST Self-Transfer (Count)"),
    "fast_sa":     fc(NODE_COLS, "FAST Self-Transfer Amount"),
    # ── GIRO flow ─────────────────────────────────────────────────────────
    "giro_deg":    fc(NODE_COLS, "GIRO Total Connections"),
    "giro_sent":   fc(NODE_COLS, "GIRO Amount Sent"),
    "giro_recv":   fc(NODE_COLS, "GIRO Amount Received"),
    "giro_net":    fc(NODE_COLS, "GIRO Net Flow"),
    "giro_sc":     fc(NODE_COLS, "GIRO Self-Transfer (Count)"),
    "giro_sa":     fc(NODE_COLS, "GIRO Self-Transfer Amount"),
    # ── Payment flow (TT + FAST + GIRO) ───────────────────────────────────
    "pay_deg":     fc(NODE_COLS, "Payment Total Connections"),
    "pay_sent":    fc(NODE_COLS, "Payment Amount Sent"),
    "pay_recv":    fc(NODE_COLS, "Payment Amount Received"),
    "pay_net":     fc(NODE_COLS, "Payment Net Flow"),
    "pay_sc":      fc(NODE_COLS, "Payment Self-Transfer (Count)"),
    "pay_sa":      fc(NODE_COLS, "Payment Self-Transfer Amount"),
    # ── All Transactions (FITAS + Payment) ────────────────────────────────
    "all_deg":     fc(NODE_COLS, "All Txn Total Connections"),
    "all_sent":    fc(NODE_COLS, "All Txn Amount Sent"),
    "all_recv":    fc(NODE_COLS, "All Txn Amount Received"),
    "all_net":     fc(NODE_COLS, "All Txn Net Flow"),
    # ── FITAS flow (recomputed in Recipe 3) ───────────────────────────────
    "fitas_sent":  fc(NODE_COLS, "FITAS Amount Sent"),
    "fitas_recv":  fc(NODE_COLS, "FITAS Amount Received"),
    "fitas_net_flow": fc(NODE_COLS, "FITAS Net Flow"),  # may be absent if not recomputed

    # ── Latest record dates ───────────────────────────────────────────────
    "tt_yr"     : fc(NODE_COLS, "TT Latest Record"),
    "fitas_yr"  : fc(NODE_COLS, "FITAS Latest Record"),
    "fast_yr"   : fc(NODE_COLS, "FAST Latest Record"),
    "giro_yr"   : fc(NODE_COLS, "GIRO Latest Record"),
    "all_txn_yr": fc(NODE_COLS, "All Txn Latest Record"),
    # ── Credit ────────────────────────────────────────────────────────────
    "credit_sts": fc(NODE_COLS, "Credit Status"),
    "impairment": fc(NODE_COLS, "Impairment"),
    "risk_grade": fc(NODE_COLS, "Risk Grade"),
    "brr":        fc(NODE_COLS, "Borrower Risk Rating", "BRR"),
    "watchlist":  fc(NODE_COLS, "Is Watchlist", "Watchlist"),
    "sma":        fc(NODE_COLS, "Special Mention"),
    "npl":        fc(NODE_COLS, "Is NPL", "NPL"),
    "mob":        fc(NODE_COLS, "Months on Book"),
    "rating_dte": fc(NODE_COLS, "Rating Date"),
    "dpd":        fc(NODE_COLS, "DPD Bucket"),
    "del_12m":    fc(NODE_COLS, "Delinquency Count"),
    # ── Facilities ────────────────────────────────────────────────────────
    "avail_lmt":  fc(NODE_COLS, "Available Limit"),
    "auth_lmt":   fc(NODE_COLS, "Authorised Limit"),
    "aa_date":    fc(NODE_COLS, "Latest AA Creation"),
    "outstanding":fc(NODE_COLS, "Outstanding Balance"),
    "on_bs":      fc(NODE_COLS, "On-Balance Sheet Outstanding"),
    "off_bs":     fc(NODE_COLS, "Off-Balance Sheet Outstanding"),
    "util_pct":   fc(NODE_COLS, "Utilisation"),
    "casa":       fc(NODE_COLS, "Current Account"),
    "fd":         fc(NODE_COLS, "TD (SGD)"),
    "strctd":     fc(NODE_COLS, "Structured TD"),
    "dep_tot":    fc(NODE_COLS, "Total Deposit Balances"),
    "tr_ln":      fc(NODE_COLS, "Trade Loan"),
    "ntr_ln":     fc(NODE_COLS, "Non-Trade Loan"),
    "ln_tot":     fc(NODE_COLS, "Total Loan Balances"),
    # ── ACRA financials ───────────────────────────────────────────────────
    "fin_yr":     fc(NODE_COLS, "ACRA Financial Year"),
    "fin_rev":    fc(NODE_COLS, "ACRA Sales Revenue"),
    "fin_pbt":    fc(NODE_COLS, "ACRA Profit Before Tax"),
    "fin_cash":   fc(NODE_COLS, "ACRA Cash"),
    "fin_cred":   fc(NODE_COLS, "ACRA Trade Creditors"),
    "fin_debt":   fc(NODE_COLS, "ACRA Trade Debtors"),
    # ── ACRA charges ─────────────────────────────────────────────────────
    "chg_count":   fc(NODE_COLS, "Charge Count"),
    "chg_chargee": fc(NODE_COLS, "Unique Chargee"),
    "chg_earliest":fc(NODE_COLS, "Earliest Charge Reg"),
    "chg_latest":  fc(NODE_COLS, "Latest Charge Reg"),
    "chg_amt":     fc(NODE_COLS, "Charge Secured Amount"),
    "chg_amo_y":   fc(NODE_COLS, "All Monies Owing (Y"),
    "chg_amo_n":   fc(NODE_COLS, "All Monies Owing (N"),
    # ── EMIS overview ─────────────────────────────────────────────────────
    "city":        fc(NODE_COLS, "City"),
    "employees":   fc(NODE_COLS, "No. Employees", "Number of Employees"),
    "listed":      fc(NODE_COLS, "Listed / Unlisted", "Listed/Unlisted"),
    "export_cty":  fc(NODE_COLS, "Export Countries"),
    "incorp_date": fc(NODE_COLS, "Incorporation Date"),
    # ── EMIS financials ───────────────────────────────────────────────────
    "emis_yr":    fc(NODE_COLS, "EMIS Fiscal Year"),
    "emis_rev":   fc(NODE_COLS, "Total Operating Revenue (USD)"),
    "emis_op":    fc(NODE_COLS, "Operating Profit (USD)"),
    "emis_pbt":   fc(NODE_COLS, "Profit Before Income Tax (USD)"),
    "emis_assets":fc(NODE_COLS, "Total Assets (USD)"),
    "emis_fcf":   fc(NODE_COLS, "Free Cash Flow (USD)"),
    "emis_ncf":   fc(NODE_COLS, "Net Cash Flow from Operations"),
    "emis_roa":   fc(NODE_COLS, "EMIS ROA"),
    "emis_roe":   fc(NODE_COLS, "EMIS ROE"),
    "emis_aud":   fc(NODE_COLS, "EMIS Audited"),
    "emis_src":   fc(NODE_COLS, "EMIS Source"),
    # ── MFI: statement metadata ───────────────────────────────────────────
    # Patterns match Recipe 3's NODE_RENAME display names (Recipe 4 reads
    # only the Recipe 3 Excel; raw enricher names never reach here).
    "mfi_fy":     fc(NODE_COLS, "MFI Financial Year End"),
    "mfi_typ":    fc(NODE_COLS, "MFI Statement Type"),
    "mfi_aud":    fc(NODE_COLS, "MFI Auditor"),
    "mfi_qual":   fc(NODE_COLS, "MFI Qualified Opinion"),
    "mfi_seg":    fc(NODE_COLS, "MFI Segment"),
    "mfi_model":  fc(NODE_COLS, "MFI Model Name"),
    "mfi_tcurr":  fc(NODE_COLS, "MFI Target Currency"),
    "mfi_bcurr":  fc(NODE_COLS, "MFI Base Currency"),
    "mfi_mths":   fc(NODE_COLS, "MFI Period Length"),
    "mfi_sts":    fc(NODE_COLS, "MFI Statement Status"),
    "mfi_proc":   fc(NODE_COLS, "MFI Processing Date"),
    # ── MFI: P&L ──────────────────────────────────────────────────────────
    "mfi_sales":  fc(NODE_COLS, "MFI Sales Revenue"),
    "mfi_cogs":   fc(NODE_COLS, "MFI COGS"),
    "mfi_gpnl":   fc(NODE_COLS, "MFI Gross Operating"),
    "mfi_prepnl": fc(NODE_COLS, "MFI Pre-Tax P&L Before Int"),
    "mfi_pbt":    fc(NODE_COLS, "MFI Profit Before Tax"),
    "mfi_pat":    fc(NODE_COLS, "MFI Profit After Tax"),
    "mfi_ebitda": fc(NODE_COLS, "MFI EBITDA"),
    # ── MFI: balance sheet ────────────────────────────────────────────────
    "mfi_ast":    fc(NODE_COLS, "MFI Total Assets"),
    "mfi_cast":   fc(NODE_COLS, "MFI Current Assets"),
    "mfi_ncast":  fc(NODE_COLS, "MFI Non-Current Assets"),
    "mfi_lbl":    fc(NODE_COLS, "MFI Total Liabilities"),
    "mfi_clbl":   fc(NODE_COLS, "MFI Current Liabilities"),
    "mfi_nclbl":  fc(NODE_COLS, "MFI Non-Current Liabilities"),
    "mfi_eq":     fc(NODE_COLS, "MFI Total Equity"),
    "mfi_stdebt": fc(NODE_COLS, "MFI Short-Term Debt"),
    "mfi_ltdebt": fc(NODE_COLS, "MFI Long-Term Debt"),
    "mfi_debt":   fc(NODE_COLS, "MFI Total Debt"),
    "mfi_dsvc":   fc(NODE_COLS, "MFI Debt Service"),
    "mfi_tnw":    fc(NODE_COLS, "MFI Tangible Net Worth"),
    "mfi_atnw":   fc(NODE_COLS, "MFI Adjusted TNW"),
    # ── MFI: ratios ───────────────────────────────────────────────────────
    "mfi_dcsr":   fc(NODE_COLS, "MFI DSCR"),
    "mfi_gear":   fc(NODE_COLS, "MFI Gearing Ratio"),
    # ── CIP: facility & loan ──────────────────────────────────────────────
    "cip_lmt":    fc(NODE_COLS, "CIP Facility Limit"),
    "cip_loan":   fc(NODE_COLS, "CIP Loan Balance"),
    "cip_npl":    fc(NODE_COLS, "CIP NPL Balance"),
    # ── CIP: collateral valuations ────────────────────────────────────────
    "cip_sec":    fc(NODE_COLS, "CIP Security Amount"),
    "cip_emv":    fc(NODE_COLS, "CIP Estimated Market Value"),
    "cip_fsv":    fc(NODE_COLS, "CIP Forced Sale Value"),
    "cip_fiv":    fc(NODE_COLS, "CIP Fire Insurance Value"),
    # ── CIP: properties & accounts ────────────────────────────────────────
    "cip_prop":      fc(NODE_COLS, "CIP No. Properties"),
    "cip_acc_tot":   fc(NODE_COLS, "CIP Total Accounts"),
    "cip_acc_opn":   fc(NODE_COLS, "CIP Open Accounts"),
    "cip_acc_cls":   fc(NODE_COLS, "CIP Closed Accounts"),
    "cip_dte_early": fc(NODE_COLS, "CIP Earliest Account Open Date"),
    # *** updated | cip_dte_late removed; cip_dte_cls added
    "cip_dte_cls":   fc(NODE_COLS, "CIP Latest Account Close Date"),
    "cip_dte_fac":   fc(NODE_COLS, "CIP Facility Processing Date"),
    "cip_dte_bal":   fc(NODE_COLS, "CIP Balance Processing Date"),
    "cip_dte_def":   fc(NODE_COLS, "CIP Latest Default Date"),
    "cip_jtc":       fc(NODE_COLS, "CIP JTC"),
    "cip_own":       fc(NODE_COLS, "CIP Owner Occupied"),
    "cip_ten":       fc(NODE_COLS, "CIP Tenanted"),
    "cip_biz":       fc(NODE_COLS, "CIP Business Ops"),
    "cip_vac":       fc(NODE_COLS, "CIP Vacant"),
}

E = {
    "src_uen":  fc(EDGE_COLS, "Source (UEN)"),
    "src_name": fc(EDGE_COLS, "Source (Name)"),
    "src_cty":  fc(EDGE_COLS, "Source (Country)"),
    "src_seg":  fc(EDGE_COLS, "Source (Segment)"),
    "tgt_uen":  fc(EDGE_COLS, "Target (UEN)"),
    "tgt_name": fc(EDGE_COLS, "Target (Name)"),
    "tgt_cty":  fc(EDGE_COLS, "Target (Country)"),
    "tgt_seg":  fc(EDGE_COLS, "Target (Segment)"),
    "txn_cnt":  fc(EDGE_COLS, "Transaction Count"),
    "txn_amt":  fc(EDGE_COLS, "Transaction Amount"),
    "self":     fc(EDGE_COLS, "Self-Transfer"),
    "source":   fc(EDGE_COLS, "Data Source"),
    "rel_desc": fc(EDGE_COLS, "Relationship Description"),
}

print("=== NODE COLUMN MAPPING ===")
for k, v in N.items():
    print(f"  {'OK' if v else '!!'} {k:<15}: {v or 'NOT FOUND'}")
print("\n=== EDGE COLUMN MAPPING ===")
for k, v in E.items():
    print(f"  {'OK' if v else '!!'} {k:<12}: {v or 'NOT FOUND'}")

mfi_found = sum(1 for k, v in N.items() if k.startswith('mfi_') and v)
cip_found = sum(1 for k, v in N.items() if k.startswith('cip_') and v)
mfi_total = sum(1 for k in N if k.startswith('mfi_'))
cip_total = sum(1 for k in N if k.startswith('cip_'))
print(f"\nMFI cols mapped: {mfi_found}/{mfi_total}")
print(f"CIP cols mapped: {cip_found}/{cip_total}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 3: Build standardised records with safe typing
# *** updated | full MFI and CIP field sets
# *** updated | cip_dte_late removed; cip_dte_cls added
# *** updated | cs_ssic added to fix SSIC float display (41009.0 -> 41009)

def cs(v):
    if v is None: return None
    if isinstance(v, float) and np.isnan(v): return None
    s = str(v).strip()
    return None if s in ("", "nan", "None", "NaT") else s

def cs_ssic(v):
    """Strip .0 float artifact from SSIC codes read from Excel."""
    if v is None: return None
    if isinstance(v, float) and np.isnan(v): return None
    try: return str(int(float(v))).zfill(5)
    except:
        s = str(v).strip()
        return None if s in ("", "nan", "None", "NaT") else s

def cn(v):
    if v is None: return None
    if isinstance(v, float) and np.isnan(v): return None
    try: return float(v)
    except: return None

def cb(v):
    if v is None: return False
    if isinstance(v, float) and np.isnan(v): return False
    if isinstance(v, bool): return v
    if isinstance(v, (int, float)): return bool(v)
    return str(v).strip().upper() in ("1", "Y", "YES", "TRUE")

def g(row, col):
    if col is None or col not in row.index: return None
    return row[col]

std_nodes = []
for _, row in nodes_df.iterrows():
    std_nodes.append({
        # ── Identity ──────────────────────────────────────────────────────
        "uen":         cs(g(row, N["uen"])),
        "name":        cs(g(row, N["name"])),
        "cif":         cs(g(row, N["cif"])),
        "country":     cs(g(row, N["country"])),
        "segment":     cs(g(row, N["segment"])),
        "cust_type":   cs(g(row, N["cust_type"])),
        "status":      cs(g(row, N["status"])),
        "ent_type":    cs(g(row, N["ent_type"])),
        "sector":      cs(g(row, N["sector"])),
        "industry":    cs(g(row, N["industry"])),
        "ssic":        cs_ssic(g(row, N["ssic"])),      # *** fixed | strip .0 float
        "parent":      cs(g(row, N["parent"])),
        "first_ca":    cs(g(row, N["first_ca"])),
        "tenure":      cn(g(row, N["tenure"])),
        "data_src":    cs(g(row, N["data_src"])),
        # ── Network degrees ───────────────────────────────────────────────
        "total_deg":   cn(g(row, N["total_deg"])),
        "tt_deg":      cn(g(row, N["tt_deg"])),
        "tt_sg":       cn(g(row, N["tt_sg"])),
        "tt_my":       cn(g(row, N["tt_my"])),
        "rsme_deg":    cn(g(row, N["rsme_deg"])),
        "fitas_deg":   cn(g(row, N["fitas_deg"])),
        "aa_deg":      cn(g(row, N["aa_deg"])),
        "total_sg":    cn(g(row, N["total_sg"])),
        "total_my":    cn(g(row, N["total_my"])),
        "to_buyers":   cn(g(row, N["to_buyers"])),
        "to_suppliers":cn(g(row, N["to_suppliers"])),
        # ── TT flow ───────────────────────────────────────────────────────
        "tt_sent":     cn(g(row, N["tt_sent"])),
        "tt_recv":     cn(g(row, N["tt_recv"])),
        "tt_net":      cn(g(row, N["tt_net"])),
        "tt_sc":       cn(g(row, N["tt_sc"])),
        "tt_sa":       cn(g(row, N["tt_sa"])),
        # FAST
        "fast_deg":    cn(g(row, N["fast_deg"])),
        "fast_sent":   cn(g(row, N["fast_sent"])),
        "fast_recv":   cn(g(row, N["fast_recv"])),
        "fast_net":    cn(g(row, N["fast_net"])),
        "fast_sc":     cn(g(row, N["fast_sc"])),
        "fast_sa":     cn(g(row, N["fast_sa"])),
        # GIRO
        "giro_deg":    cn(g(row, N["giro_deg"])),
        "giro_sent":   cn(g(row, N["giro_sent"])),
        "giro_recv":   cn(g(row, N["giro_recv"])),
        "giro_net":    cn(g(row, N["giro_net"])),
        "giro_sc":     cn(g(row, N["giro_sc"])),
        "giro_sa":     cn(g(row, N["giro_sa"])),
        # Payment combined
        "pay_deg":     cn(g(row, N["pay_deg"])),
        "pay_sent":    cn(g(row, N["pay_sent"])),
        "pay_recv":    cn(g(row, N["pay_recv"])),
        "pay_net":     cn(g(row, N["pay_net"])),
        "pay_sc":      cn(g(row, N["pay_sc"])),
        "pay_sa":      cn(g(row, N["pay_sa"])),
        # All Transactions
        "all_deg":     cn(g(row, N["all_deg"])),
        "all_sent":    cn(g(row, N["all_sent"])),
        "all_recv":    cn(g(row, N["all_recv"])),
        "all_net":     cn(g(row, N["all_net"])),
        # FITAS flow (re-read so std_nodes has it for Section E)
        "fitas_sent":  cn(g(row, N["fitas_sent"])),
        "fitas_recv":  cn(g(row, N["fitas_recv"])),
        "fitas_net":   cn(g(row, N["fitas_net_flow"])),
        # Latest record dates per source
        "tt_yr"     :  cs(g(row, N["tt_yr"])),
        "fitas_yr"  :  cs(g(row, N["fitas_yr"])),
        "fast_yr"   :  cs(g(row, N["fast_yr"])),
        "giro_yr"   :  cs(g(row, N["giro_yr"])),
        "all_txn_yr":  cs(g(row, N["all_txn_yr"])),
        # ── Credit ────────────────────────────────────────────────────────
        "credit_sts":  cs(g(row, N["credit_sts"])),
        "impairment":  cs(g(row, N["impairment"])),
        "risk_grade":  cs(g(row, N["risk_grade"])),
        "brr":         cn(g(row, N["brr"])),
        "watchlist":   cb(g(row, N["watchlist"])),
        "sma":         cb(g(row, N["sma"])),
        "npl":         cb(g(row, N["npl"])),
        "mob":         cn(g(row, N["mob"])),
        "rating_dte":  cs(g(row, N["rating_dte"])),
        "dpd":         cs(g(row, N["dpd"])),
        "del_12m":     cn(g(row, N["del_12m"])),
        # ── Facilities ────────────────────────────────────────────────────
        "avail_lmt":   cn(g(row, N["avail_lmt"])),
        "auth_lmt":    cn(g(row, N["auth_lmt"])),
        "aa_date":     cs(g(row, N["aa_date"])),
        "outstanding": cn(g(row, N["outstanding"])),
        "on_bs":       cn(g(row, N["on_bs"])),
        "off_bs":      cn(g(row, N["off_bs"])),
        "util_pct":    cn(g(row, N["util_pct"])),
        "casa":        cn(g(row, N["casa"])),
        "fd":          cn(g(row, N["fd"])),
        "strctd":      cn(g(row, N["strctd"])),
        "dep_tot":     cn(g(row, N["dep_tot"])),
        "tr_ln":       cn(g(row, N["tr_ln"])),
        "ntr_ln":      cn(g(row, N["ntr_ln"])),
        "ln_tot":      cn(g(row, N["ln_tot"])),
        # ── ACRA financials ───────────────────────────────────────────────
        "fin_yr":      cs(g(row, N["fin_yr"])),
        "fin_rev":     cn(g(row, N["fin_rev"])),
        "fin_pbt":     cn(g(row, N["fin_pbt"])),
        "fin_cash":    cn(g(row, N["fin_cash"])),
        "fin_cred":    cn(g(row, N["fin_cred"])),
        "fin_debt":    cn(g(row, N["fin_debt"])),
        # ── ACRA charges ─────────────────────────────────────────────────
        "chg_count":   cn(g(row, N["chg_count"])),
        "chg_chargee": cn(g(row, N["chg_chargee"])),
        "chg_earliest":cs(g(row, N["chg_earliest"])),
        "chg_latest":  cs(g(row, N["chg_latest"])),
        "chg_amt":     cn(g(row, N["chg_amt"])),
        "chg_amo_y":   cn(g(row, N["chg_amo_y"])),
        "chg_amo_n":   cn(g(row, N["chg_amo_n"])),
        # ── EMIS overview ─────────────────────────────────────────────────
        "city":        cs(g(row, N["city"])),
        "employees":   cs(g(row, N["employees"])),
        "listed":      cs(g(row, N["listed"])),
        "export_cty":  cs(g(row, N["export_cty"])),
        "incorp_date": cs(g(row, N["incorp_date"])),
        # ── EMIS financials ───────────────────────────────────────────────
        "emis_yr":     cs(g(row, N["emis_yr"])),
        "emis_rev":    cn(g(row, N["emis_rev"])),
        "emis_op":     cn(g(row, N["emis_op"])),
        "emis_pbt":    cn(g(row, N["emis_pbt"])),
        "emis_assets": cn(g(row, N["emis_assets"])),
        "emis_fcf":    cn(g(row, N["emis_fcf"])),
        "emis_ncf":    cn(g(row, N["emis_ncf"])),
        "emis_roa":    cn(g(row, N["emis_roa"])),
        "emis_roe":    cn(g(row, N["emis_roe"])),
        "emis_aud":    cs(g(row, N["emis_aud"])),
        "emis_src":    cs(g(row, N["emis_src"])),
        # ── MFI: statement metadata ───────────────────────────────────────
        "mfi_fy":      cs(g(row, N["mfi_fy"])),
        "mfi_typ":     cs(g(row, N["mfi_typ"])),
        "mfi_aud":     cs(g(row, N["mfi_aud"])),
        "mfi_qual":    cs(g(row, N["mfi_qual"])),
        "mfi_seg":     cs(g(row, N["mfi_seg"])),
        "mfi_model":   cs(g(row, N["mfi_model"])),
        "mfi_tcurr":   cs(g(row, N["mfi_tcurr"])),
        "mfi_bcurr":   cs(g(row, N["mfi_bcurr"])),
        "mfi_mths":    cn(g(row, N["mfi_mths"])),
        "mfi_sts":     cs(g(row, N["mfi_sts"])),
        "mfi_proc":    cs(g(row, N["mfi_proc"])),
        # ── MFI: P&L ──────────────────────────────────────────────────────
        "mfi_sales":   cn(g(row, N["mfi_sales"])),
        "mfi_cogs":    cn(g(row, N["mfi_cogs"])),
        "mfi_gpnl":    cn(g(row, N["mfi_gpnl"])),
        "mfi_prepnl":  cn(g(row, N["mfi_prepnl"])),
        "mfi_pbt":     cn(g(row, N["mfi_pbt"])),
        "mfi_pat":     cn(g(row, N["mfi_pat"])),
        "mfi_ebitda":  cn(g(row, N["mfi_ebitda"])),
        # ── MFI: balance sheet ────────────────────────────────────────────
        "mfi_ast":     cn(g(row, N["mfi_ast"])),
        "mfi_cast":    cn(g(row, N["mfi_cast"])),
        "mfi_ncast":   cn(g(row, N["mfi_ncast"])),
        "mfi_lbl":     cn(g(row, N["mfi_lbl"])),
        "mfi_clbl":    cn(g(row, N["mfi_clbl"])),
        "mfi_nclbl":   cn(g(row, N["mfi_nclbl"])),
        "mfi_eq":      cn(g(row, N["mfi_eq"])),
        "mfi_stdebt":  cn(g(row, N["mfi_stdebt"])),
        "mfi_ltdebt":  cn(g(row, N["mfi_ltdebt"])),
        "mfi_debt":    cn(g(row, N["mfi_debt"])),
        "mfi_dsvc":    cn(g(row, N["mfi_dsvc"])),
        "mfi_tnw":     cn(g(row, N["mfi_tnw"])),
        "mfi_atnw":    cn(g(row, N["mfi_atnw"])),
        # ── MFI: ratios ───────────────────────────────────────────────────
        "mfi_dcsr":    cn(g(row, N["mfi_dcsr"])),
        "mfi_gear":    cn(g(row, N["mfi_gear"])),
        # ── CIP: facility & loan ──────────────────────────────────────────
        "cip_lmt":     cn(g(row, N["cip_lmt"])),
        "cip_loan":    cn(g(row, N["cip_loan"])),
        "cip_npl":     cn(g(row, N["cip_npl"])),
        # ── CIP: collateral valuations ────────────────────────────────────
        "cip_sec":     cn(g(row, N["cip_sec"])),
        "cip_emv":     cn(g(row, N["cip_emv"])),
        "cip_fsv":     cn(g(row, N["cip_fsv"])),
        "cip_fiv":     cn(g(row, N["cip_fiv"])),
        # ── CIP: properties & accounts ────────────────────────────────────
        "cip_prop":      cn(g(row, N["cip_prop"])),
        "cip_acc_tot":   cn(g(row, N["cip_acc_tot"])),
        "cip_acc_opn":   cn(g(row, N["cip_acc_opn"])),
        "cip_acc_cls":   cn(g(row, N["cip_acc_cls"])),
        "cip_dte_early": cs(g(row, N["cip_dte_early"])),
        "cip_dte_cls":   cs(g(row, N["cip_dte_cls"])),
        "cip_dte_fac":   cs(g(row, N["cip_dte_fac"])),
        "cip_dte_bal":   cs(g(row, N["cip_dte_bal"])),
        "cip_dte_def":   cs(g(row, N["cip_dte_def"])),
        "cip_jtc":       cn(g(row, N["cip_jtc"])),
        "cip_own":       cn(g(row, N["cip_own"])),
        "cip_ten":       cn(g(row, N["cip_ten"])),
        "cip_biz":       cn(g(row, N["cip_biz"])),
        "cip_vac":       cn(g(row, N["cip_vac"])),
    })

std_edges = []
for _, row in edges_df.iterrows():
    std_edges.append({
        "src_uen":  cs(g(row, E["src_uen"])),
        "src_name": cs(g(row, E["src_name"])),
        "src_cty":  cs(g(row, E["src_cty"])),
        "src_seg":  cs(g(row, E["src_seg"])),
        "tgt_uen":  cs(g(row, E["tgt_uen"])),
        "tgt_name": cs(g(row, E["tgt_name"])),
        "tgt_cty":  cs(g(row, E["tgt_cty"])),
        "tgt_seg":  cs(g(row, E["tgt_seg"])),
        "txn_cnt":  cn(g(row, E["txn_cnt"])),
        "txn_amt":  cn(g(row, E["txn_amt"])),
        "self":     cb(g(row, E["self"])),
        "source":   cs(g(row, E["source"])),
        "rel_desc": cs(g(row, E["rel_desc"])),
    })

print(f"std_nodes: {len(std_nodes):,}  |  std_edges: {len(std_edges):,}")

for label, prefix in [("MFI", "mfi_"), ("CIP", "cip_")]:
    keys   = [k for k in N if k.startswith(prefix)]
    mapped = [k for k in keys if N[k] is not None]
    filled = sum(1 for rec in std_nodes if any(rec.get(k) is not None for k in keys))
    print(f"  {label}: {len(mapped)}/{len(keys)} cols mapped, "
          f"{filled:,}/{len(std_nodes):,} nodes with at least one non-null value")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# # TEMP: sample companies by UEN
# SAMPLE_UENS = {
#     '199200297K',
#     '200515214C',
#     '197301209G',
#     '197200078R',
#     '197400888M',
# }

# std_nodes = [n for n in std_nodes if n['uen'] in SAMPLE_UENS]
# std_edges = [e for e in std_edges if e['src_uen'] in SAMPLE_UENS and e['tgt_uen'] in SAMPLE_UENS]

# # Report what was found vs missing
# found   = {n['uen'] for n in std_nodes}
# missing = SAMPLE_UENS - found

# print("TEMP SAMPLE -- selected companies:")
# for i, n in enumerate(std_nodes, 1):
#     print(f"  {i}. {n['name']:<50}  UEN: {n['uen']}")
# if missing:
#     print(f"\n  WARNING: {len(missing)} UEN(s) not found in std_nodes:")
#     for u in missing:
#         print(f"    {u}")
# print(f"\nstd_nodes: {len(std_nodes)}  |  std_edges: {len(std_edges)}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 4: Serialise to JSON
# *** updated | added cip_props_json_str (filtered to UENs in std_nodes)

_std_uens = {n['uen'] for n in std_nodes if n.get('uen')}
cip_props_filtered = {k: v for k, v in cip_props_by_uen.items() if k in _std_uens}

nodes_json_str     = json.dumps(std_nodes,           ensure_ascii=True, separators=(',', ':'), default=str)
edges_json_str     = json.dumps(std_edges,           ensure_ascii=True, separators=(',', ':'), default=str)
cip_props_json_str = json.dumps(cip_props_filtered,  ensure_ascii=True, separators=(',', ':'), default=str)

print(f"Nodes JSON     : {len(nodes_json_str):,} chars  (~{len(nodes_json_str)//1024} KB)")
print(f"Edges JSON     : {len(edges_json_str):,} chars  (~{len(edges_json_str)//1024} KB)")
print(f"CIP Props JSON : {len(cip_props_json_str):,} chars  (~{len(cip_props_json_str)//1024} KB)")
print(f"Total          : ~{(len(nodes_json_str)+len(edges_json_str)+len(cip_props_json_str))//1024} KB embedded in HTML")
print(f"  CIP property UENs in report : {len(cip_props_filtered):,} / {len(cip_props_by_uen):,} total")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Cell 5: Build full self-contained HTML and write to output folder
# *** updated | ACRA Charges: own section C, always shows
# *** updated | All sections always render; "No data available" when empty
# *** updated | Section letters: C=ACRA, D=Facilities, E=Network, F=TT,
#               G=RSME, H=FITAS, I=AA Paper, J=Financial, K=MFI, L=CIP
# *** updated | L6: CIP property-level details per property sorted by secured amount
# *** updated | SSIC code fixed (41009.0 -> 41009) via cs_ssic in Cell 3

GEN_DATE    = datetime.now().strftime("%d %b %Y")
N_COMPANIES = len(std_nodes)
N_EDGES     = len(std_edges)

if LOGO_B64:
    LOGO_CSS = ".ph-logo-bg{background-image:url('" + LOGO_B64 + "');}"
    print(f"Logo CSS rule: {len(LOGO_CSS):,} chars")
else:
    LOGO_CSS = ".ph-logo-bg::after{content:'Maybank';font-family:var(--font);font-size:14px;font-weight:700;color:var(--white);}"
    print("Logo not available -- using text fallback in CSS")

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>M-EXT -- Maybank Ecosystem eXchange Topology</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{
  box-sizing:border-box;margin:0;padding:0;
  print-color-adjust:exact;
  -webkit-print-color-adjust:exact;
}}
:root{{
  --gold:#FFCF01;--gold-pale:#FFFAE6;--gold-mid:#FFE55A;
  --black:#111111;--charcoal:#222222;--grey-label:#3D3D3D;
  --grey-dark:#505050;--grey-mid:#888888;--grey-row:#F4F4F4;
  --grey-border:#D4D4D4;--white:#FFFFFF;--green:#1A6B3E;
  --red:#C0392B;
  --font:'Poppins',sans-serif;
}}
body{{font-family:var(--font);background:#EFEFEF;color:var(--black);min-height:100vh;}}
#ss{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;background:var(--black);}}
.brand{{display:flex;align-items:baseline;gap:14px;margin-bottom:6px;}}
.brand-logo{{font-size:46px;font-weight:700;color:var(--gold);letter-spacing:-1.5px;line-height:1;}}
.brand-full{{font-size:12.5px;color:#a0a0a0;font-weight:400;}}
.brand-tag{{font-size:10.5px;color:#9A9A9A;margin-bottom:44px;letter-spacing:1px;text-transform:uppercase;}}
.sbw{{width:100%;max-width:600px;position:relative;}}
.sbw input{{width:100%;padding:16px 52px 16px 20px;font-family:var(--font);font-size:15px;font-weight:500;background:#161616;border:1.5px solid #252525;border-radius:4px;color:var(--white);outline:none;transition:border-color 0.2s;}}
.sbw input:focus{{border-color:var(--gold);box-shadow:0 0 0 3px rgba(255,207,1,0.08);}}
.sbw input::placeholder{{color:#7A7A7A;}}
.sbw-icon{{position:absolute;right:18px;top:50%;transform:translateY(-50%);color:#9A9A9A;pointer-events:none;}}
#sug{{position:absolute;top:calc(100% + 5px);left:0;right:0;background:#141414;border:1px solid #252525;border-radius:4px;z-index:100;overflow:hidden;display:none;max-height:340px;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.5);}}
.si{{padding:12px 20px;cursor:pointer;border-bottom:1px solid #1A1A1A;transition:background 0.12s;}}
.si:last-child{{border-bottom:none;}}
.si:hover{{background:#1C1C1C;}}
.si-name{{font-size:13px;font-weight:600;color:var(--white);}}
.si-meta{{font-size:10.5px;color:#9A9A9A;margin-top:2px;}}
.search-hint{{margin-top:14px;font-size:10px;color:#888888;text-align:center;}}
.search-stats{{margin-top:40px;display:flex;gap:48px;}}
.sstat{{text-align:center;}}
.sstat-n{{font-size:26px;font-weight:700;color:var(--gold);}}
.sstat-l{{font-size:10px;color:#9A9A9A;margin-top:3px;letter-spacing:0.5px;text-transform:uppercase;}}
#rs{{display:none;background:#EFEFEF;min-height:100vh;}}
.tb{{position:sticky;top:0;z-index:200;background:var(--black);display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:48px;border-bottom:2.5px solid var(--gold);}}
.tb-l{{display:flex;align-items:center;gap:14px;}}
.tb-brand{{font-size:16px;font-weight:700;color:var(--gold);letter-spacing:-0.3px;}}
.tb-sep{{width:1px;height:20px;background:#252525;}}
.tb-co{{font-size:12px;font-weight:500;color:#bbbbbb;max-width:420px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.tb-r{{display:flex;align-items:center;gap:8px;}}
.btn{{display:inline-flex;align-items:center;gap:7px;padding:7px 16px;font-family:var(--font);font-size:12px;font-weight:600;border:none;border-radius:3px;cursor:pointer;transition:opacity 0.15s,transform 0.1s;}}
.btn:hover{{opacity:0.88;transform:translateY(-1px);}}
.btn-gold{{background:var(--gold);color:var(--black);}}
.btn-out{{background:transparent;color:#777;border:1px solid #2E2E2E;}}
.btn-out:hover{{border-color:var(--gold);color:var(--gold);opacity:1;}}
.rp{{max-width:940px;margin:24px auto;padding:0 16px 60px;}}
.ph{{background:var(--black);border-radius:4px 4px 0 0;overflow:hidden;margin-bottom:0;}}
.ph-bar{{display:flex;align-items:stretch;min-height:56px;}}
.ph-acc{{width:7px;background:var(--gold);flex-shrink:0;}}
.ph-l{{display:flex;align-items:center;padding:10px 18px;flex:1;}}
.ph-logo-bg{{height:36px;width:130px;background-size:contain;background-repeat:no-repeat;background-position:left center;flex-shrink:0;}}
.ss-logo{{height:48px;width:160px;background-position:center;margin-bottom:20px;}}
{LOGO_CSS}
.ph-r{{display:flex;flex-direction:column;align-items:flex-end;justify-content:center;padding:10px 20px;gap:2px;border-left:1px solid #1E1E1E;}}
.ph-mx{{font-size:22px;font-weight:700;color:var(--gold);letter-spacing:-0.5px;line-height:1;}}
.ph-fn{{font-size:8.5px;color:#a0a0a0;font-weight:400;text-align:right;}}
.ph-sub{{background:var(--gold-pale);display:flex;align-items:center;justify-content:space-between;padding:5px 14px;border-left:6px solid var(--gold);}}
.ph-cn{{font-size:11px;font-weight:600;color:var(--black);}}
.ph-dt{{font-size:10px;color:var(--grey-mid);}}
.cov{{background:var(--white);padding:28px 28px 22px;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
.cov-cls{{display:inline-block;background:var(--gold);color:var(--black);font-size:8.5px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:3px 10px;margin-bottom:14px;}}
.cov-nm{{font-size:25px;font-weight:700;color:var(--black);line-height:1.2;margin-bottom:12px;}}
.cov-bdg{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;}}
.bdg{{font-size:9px;font-weight:700;padding:3px 10px;border-radius:2px;letter-spacing:0.4px;text-transform:uppercase;}}
.bdg-live{{background:var(--green);color:#fff;}}
.bdg-trade{{background:var(--black);color:var(--gold);}}
.bdg-seg{{background:var(--grey-dark);color:#fff;}}
.bdg-cty{{background:var(--grey-dark);color:#fff;}}
.cov-meta{{font-size:10px;color:var(--grey-mid);border-top:1px solid var(--grey-border);padding-top:10px;}}
.sc{{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;background:var(--black);margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
.sc-card{{background:var(--gold);padding:18px 16px 14px;text-align:center;border-top:3px solid var(--black);}}
.sc-v{{font-size:22px;font-weight:700;color:var(--black);line-height:1.1;}}
.sc-s{{font-size:10px;font-weight:600;color:#333;margin:3px 0 4px;}}
.sc-l{{font-size:9.5px;color:#555;}}
.sec{{margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,0.07);}}
.sec-hdr{{display:flex;align-items:stretch;background:var(--black);border-radius:3px 3px 0 0;overflow:hidden;cursor:pointer;user-select:none;transition:background 0.12s;}}
.sec-hdr:hover{{background:#1A1A1A;}}
.sec-code{{background:var(--gold);color:var(--black);font-size:11px;font-weight:700;padding:7px 14px;display:flex;align-items:center;justify-content:center;min-width:36px;}}
.sec-title{{color:var(--white);font-size:10.5px;font-weight:600;padding:7px 14px;display:flex;align-items:center;letter-spacing:0.4px;text-transform:uppercase;flex:1;}}
.sec-arrow{{color:var(--gold);font-size:11px;padding:7px 16px;display:flex;align-items:center;justify-content:center;transition:transform 0.18s ease;}}
.sec-hdr.closed .sec-arrow{{transform:rotate(-90deg);}}
.sec-body{{background:var(--white);border:1px solid var(--grey-border);border-top:none;border-radius:0 0 3px 3px;overflow:hidden;}}
/* Section content fonts -- reduced 1px from prior values so Section F's
   long counterparty tables fit on print without truncation. */
.ssl{{background:var(--gold-pale);border-left:4px solid var(--gold);padding:6px 12px;font-size:9px;font-weight:600;color:var(--charcoal);border-bottom:1px solid var(--gold-mid);}}
.ssl-sub{{background:#E6B800;border-left:4px solid #B8940A;padding:5px 12px;font-size:9px;font-weight:700;color:var(--charcoal);border-bottom:1px solid #CCCCCC;margin-top:2px;}}
.kv-grid{{display:grid;grid-template-columns:1fr 1px 1fr;}}
.kv-divider{{background:var(--grey-border);}}
.kv-row{{display:grid;grid-template-columns:185px 1fr;border-bottom:1px solid var(--grey-border);}}
.kv-row:last-child{{border-bottom:none;}}
.kv-lbl{{background:#EBEBEB;padding:7px 10px;font-size:9px;font-weight:600;color:var(--grey-label);border-right:1px solid var(--grey-border);line-height:1.4;display:flex;align-items:flex-start;word-break:break-word;}}
.kv-val{{padding:7px 10px;font-size:9px;color:var(--black);line-height:1.4;word-break:break-word;}}
.kv-row:nth-child(odd)  .kv-val{{background:var(--grey-row);}}
.kv-row:nth-child(even) .kv-val{{background:var(--white);}}
.dtw{{overflow-x:auto;}}
table.dt{{width:100%;border-collapse:collapse;font-size:9px;}}
/* When explicit colWidths are passed to tbl(), enforce them on screen AND
   print. Without table-layout:fixed the browser treats width:X% as a hint
   and grows narrow columns to fit content (eg. the "Country" header was
   ~50px wide regardless of the requested 1%). Headers wrap instead of
   forcing a min width; body cells clip rather than overflow. */
table.dt.dt-fixed{{table-layout:fixed;}}
table.dt.dt-fixed thead th{{white-space:normal;word-break:break-word;}}
table.dt.dt-fixed tbody td{{overflow:hidden;text-overflow:ellipsis;}}
table.dt thead tr{{background:var(--black);}}
table.dt thead th{{padding:8px 10px;text-align:left;font-size:8.5px;font-weight:600;color:var(--white);letter-spacing:0.2px;border-bottom:2.5px solid var(--gold);white-space:nowrap;}}
table.dt tbody tr:nth-child(odd){{background:var(--white);}}
table.dt tbody tr:nth-child(even){{background:var(--grey-row);}}
/* Light-blue row hover for ALL .dt tables (any section). */
table.dt tbody tr:hover{{background:#EAF4FF;}}
/* Sortable column headers (3-state cycle) attach to Sections F, G, H via JS. */
.sec[data-section="F"] table.dt thead th,
.sec[data-section="G"] table.dt thead th,
.sec[data-section="H"] table.dt thead th{{cursor:pointer;user-select:none;}}
.sec[data-section="F"] table.dt thead th .sort-arrow,
.sec[data-section="G"] table.dt thead th .sort-arrow,
.sec[data-section="H"] table.dt thead th .sort-arrow{{display:inline-block;margin-left:5px;font-size:8px;opacity:0.4;color:#FFFFFF;}}
.sec[data-section="F"] table.dt thead th.sorted .sort-arrow,
.sec[data-section="G"] table.dt thead th.sorted .sort-arrow,
.sec[data-section="H"] table.dt thead th.sorted .sort-arrow{{opacity:1;color:var(--gold);}}
table.dt tbody td{{padding:7px 10px;color:var(--black);border-bottom:1px solid var(--grey-border);line-height:1.4;vertical-align:top;word-break:break-word;}}
.note{{font-size:8.5px;color:var(--grey-mid);padding:8px 12px;font-style:italic;border-bottom:1px solid var(--grey-border);}}
.no-data{{font-size:8.5px;color:var(--grey-mid);padding:10px 14px;font-style:italic;}}
.disc{{background:var(--grey-row);border:1px solid var(--grey-border);border-top:2.5px solid var(--gold);border-radius:3px;padding:14px 16px;font-size:9px;color:var(--grey-mid);line-height:1.7;margin-top:20px;}}
.disc b{{color:var(--grey-dark);}}
@media print{{
  body,#rs{{background:white;}}
  .tb{{display:none!important;}}
  .rp{{max-width:100%;margin:0;padding:0;}}
  .sec,.cov,.ph,.sc{{box-shadow:none;}}
  .sec{{page-break-inside:avoid;}}
  .ph,.ph-bar{{background:var(--black)!important;}}
  .ph-acc{{background:var(--gold)!important;}}
  .ph-sub{{background:var(--gold-pale)!important;}}
  .ph-logo-bg{{background-size:contain!important;background-repeat:no-repeat!important;}}
  .sec-hdr{{background:var(--black)!important;cursor:default!important;}}
  /* Print respects the user's collapsed state. Two-tier behaviour:
     - Open section: header + body both print as-is.
     - Closed section: header (with alphabet code + title) still prints so
       the section index is visible, but the body is hidden. */
  .sec-hdr.closed + .sec-body{{display:none!important;}}
  .sec-arrow{{display:none!important;}}
  .sec-code{{background:var(--gold)!important;color:var(--black)!important;}}
  .sc-card{{background:var(--gold)!important;}}
  .ssl{{background:var(--gold-pale)!important;}}
  .ssl-sub{{background:#E6B800!important;}}
  table.dt thead tr{{background:var(--black)!important;}}
  table.dt thead th{{color:var(--white)!important;}}
  table.dt tbody tr:nth-child(even){{background:var(--grey-row)!important;}}
  .kv-lbl{{background:#EBEBEB!important;}}
  .kv-row:nth-child(odd) .kv-val{{background:var(--grey-row)!important;}}
  .cov-cls{{background:var(--gold)!important;color:var(--black)!important;}}
  .bdg-live{{background:var(--green)!important;color:#fff!important;}}
  .bdg-trade{{background:var(--black)!important;color:var(--gold)!important;}}
  .bdg-seg,.bdg-cty{{background:var(--grey-dark)!important;color:#fff!important;}}
  .disc{{background:var(--grey-row)!important;}}
  .sec-title{{color:var(--white)!important;}}
}}
</style>
</head>
<body>

<div id="ss">
  <div class="ph-logo-bg ss-logo"></div>
  <div class="brand">
    <span class="brand-logo">M-EXT</span>
    <span class="brand-full">Maybank Ecosystem eXchange Topology</span>
  </div>
  <div class="brand-tag">Company Intelligence Report Generator</div>
  <div class="sbw">
    <input type="text" id="sinp" placeholder="Search by company name or UEN..." autocomplete="off"/>
    <span class="sbw-icon">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    </span>
    <div id="sug"></div>
  </div>
  <div class="search-hint">Type at least 2 characters &nbsp;·&nbsp; Press Enter or click to generate report</div>
  <div class="search-stats">
    <div class="sstat"><div class="sstat-n" id="stat-n">-</div><div class="sstat-l">Companies</div></div>
    <div class="sstat"><div class="sstat-n" id="stat-e">-</div><div class="sstat-l">Relationships</div></div>
    <div class="sstat"><div class="sstat-n">{GEN_DATE}</div><div class="sstat-l">Data As Of</div></div>
  </div>
</div>

<div id="rs">
  <div class="tb">
    <div class="tb-l">
      <span class="tb-brand">M-EXT</span>
      <div class="tb-sep"></div>
      <span class="tb-co" id="tb-co">-</span>
    </div>
    <div class="tb-r">
      <button class="btn btn-out" onclick="goBack()">&#8592; New Search</button>
      <button class="btn btn-gold" onclick="window.print()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
        Print / Save PDF
      </button>
    </div>
  </div>
  <div class="rp" id="ro"></div>
</div>

<script>
const NODES     = {nodes_json_str};
const EDGES     = {edges_json_str};
const CIP_PROPS = {cip_props_json_str};

document.getElementById('stat-n').textContent = NODES.length.toLocaleString();
document.getElementById('stat-e').textContent = EDGES.length.toLocaleString();

const dv    = v => (v == null || v === '') ? '-' : v;
// Negatives shown in accounting-style parentheses, eg. -45000 -> "(S$ 45,000)".
// (Inline net-flow branches in Section F predate this and produce the same
// output, so leaving them is harmless.)
const fsgd  = v => {{
  if (v == null) return '-';
  const r = Math.round(v);
  return r < 0
    ? '(S$ ' + Math.abs(r).toLocaleString('en-SG') + ')'
    : 'S$ ' + r.toLocaleString('en-SG');
}};
const fusd  = v => {{
  if (v == null) return '-';
  const r = Math.round(v);
  return r < 0
    ? '(USD ' + Math.abs(r).toLocaleString('en-US') + ')'
    : 'USD ' + r.toLocaleString('en-US');
}};
const fnum  = v => v == null ? '-' : Number(v).toLocaleString();
const fpct  = v => v == null ? '-' : Number(v).toFixed(1) + '%';
const fbool = v => v ? 'Yes' : 'No';
const frat  = v => v == null ? '-' : Number(v).toFixed(2);
const noData = () => `<div class="no-data">No data available</div>`;
const today = () => new Date().toLocaleDateString('en-SG',{{day:'2-digit',month:'short',year:'numeric'}});
const rno   = uen => {{
  const now = new Date();
  const dd  = String(now.getDate()).padStart(2,'0');
  const mm  = String(now.getMonth()+1).padStart(2,'0');
  const yyyy= now.getFullYear();
  return 'MXT' + (uen||'') + dd + mm + yyyy;
}};

const nodeByUen  = {{}};
const nodeByName = {{}};
NODES.forEach(n => {{
  if (n.uen)  nodeByUen[n.uen]   = n;
  if (n.name) nodeByName[n.name] = n;
}});

function lookupCpty(uen, name) {{
  return nodeByUen[uen] || nodeByName[name] || null;
}}

function countryBreakdown(uen, sourceFilter) {{
  // sourceFilter may be: null/undefined (any source), a string, or an array of strings.
  let allowed = null;
  if (Array.isArray(sourceFilter)) allowed = new Set(sourceFilter);
  else if (typeof sourceFilter === 'string') allowed = new Set([sourceFilter]);
  const sgSet = new Set(), mySet = new Set();
  EDGES.forEach(e => {{
    if (allowed && !allowed.has(e.source)) return;
    if (e.self) return;
    const isSrc = e.src_uen === uen;
    const isTgt = e.tgt_uen === uen;
    if (!isSrc && !isTgt) return;
    const cptyUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cptyName = isSrc ? e.tgt_name : e.src_name;
    const cptyCty  = isSrc ? e.tgt_cty  : e.src_cty;
    const cptyNode = lookupCpty(cptyUen, cptyName);
    const cty = (cptyNode && cptyNode.country) || cptyCty || '';
    const key = cptyUen || cptyName || '';
    if (key) {{
      if (cty === 'SG') sgSet.add(key);
      else if (cty === 'MY') mySet.add(key);
    }}
  }});
  return [sgSet.size > 0 ? sgSet.size : '-', mySet.size > 0 ? mySet.size : '-'];
}}

function fmtDataSrc(raw) {{
  if (!raw) return '-';
  return raw.split('|').map(s => {{
    const t = s.trim();
    if (t === 'Consolidated_TT') return 'Telegraphic Transfer';
    if (t === 'FAST')            return 'FAST';
    if (t === 'GIRO')            return 'GIRO';
    if (t === 'RSME')            return 'RSME Buyer/Supplier Checklist';
    if (t === 'FITAS')           return 'FITAS';
    if (t === 'AA_Paper')        return 'AA Paper';
    return t;
  }}).join(', ');
}}

const CTYPE_ORDER = {{
  'Maybank Trade Customer':     0,
  'Maybank Non-Trade Customer': 1,
  'Non-Maybank Customer':       2,
}};
function sortCpty(rows) {{
  return [...rows].sort((a, b) => {{
    const oa = CTYPE_ORDER[a[2]] ?? 3;
    const ob = CTYPE_ORDER[b[2]] ?? 3;
    if (oa !== ob) return oa - ob;
    return (a[0]||'').localeCompare(b[0]||'');
  }});
}}

const sinp = document.getElementById('sinp');
const sug  = document.getElementById('sug');

sinp.addEventListener('input', () => {{
  const q = sinp.value.trim().toLowerCase();
  sug.innerHTML = '';
  if (q.length < 2) {{ sug.style.display='none'; return; }}
  const hits = NODES.filter(n =>
    (n.name||'').toLowerCase().includes(q) || (n.uen||'').toLowerCase().includes(q)
  ).slice(0, 12);
  if (!hits.length) {{ sug.style.display='none'; return; }}
  hits.forEach(n => {{
    const el = document.createElement('div');
    el.className = 'si';
    el.innerHTML = `<div class="si-name">${{n.name||'-'}}</div>
      <div class="si-meta">UEN: ${{n.uen||'-'}} &nbsp;|&nbsp; ${{n.segment||'-'}} &nbsp;|&nbsp; ${{n.country||'-'}}</div>`;
    el.addEventListener('mousedown', ev => {{ ev.preventDefault(); gen(n.uen); }});
    sug.appendChild(el);
  }});
  sug.style.display = 'block';
}});

document.addEventListener('click', ev => {{
  if (!sug.contains(ev.target) && ev.target !== sinp) sug.style.display = 'none';
}});

sinp.addEventListener('keydown', ev => {{
  if (ev.key !== 'Enter') return;
  const q = sinp.value.trim().toLowerCase();
  const m = NODES.find(n =>
    (n.name||'').toLowerCase().includes(q) || (n.uen||'').toLowerCase().includes(q)
  );
  if (m) gen(m.uen);
}});

function gen(uen) {{
  const node = NODES.find(n => n.uen === uen);
  if (!node) return;

  const edges     = EDGES.filter(e => e.src_uen === uen || e.tgt_uen === uen);
  const ttEdges   = edges.filter(e => e.source === 'Consolidated_TT' && !e.self);
  const rsmeEdges = edges.filter(e => e.source === 'RSME');
  const fitEdges  = edges.filter(e => e.source === 'FITAS');
  const aaEdges   = edges.filter(e => e.source === 'AA_Paper');

  const allSG = node.total_sg != null ? fnum(node.total_sg) : '-';
  const allMY = node.total_my != null ? fnum(node.total_my) : '-';
  const [rsmeSG,  rsmeMY ] = countryBreakdown(uen, 'RSME');
  const [ttSG,    ttMY   ] = countryBreakdown(uen, 'Consolidated_TT');
  const [fitasSG, fitasMY] = countryBreakdown(uen, 'FITAS');
  const [aaSG,    aaMY   ] = countryBreakdown(uen, 'AA_Paper');
  const [fastSG,    fastMY   ] = countryBreakdown(uen, 'FAST');
  const [giroSG,    giroMY   ] = countryBreakdown(uen, 'GIRO');
  const [paySG,     payMY    ] = countryBreakdown(uen, ['Consolidated_TT','FAST','GIRO']);
  const [allSGreal, allMYreal] = countryBreakdown(uen, null);   // every source

  // ── TT counterparties ─────────────────────────────────────────────────
  const ttMap = {{}};
  ttEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cKey  = isSrc ? (e.tgt_uen||e.tgt_name) : (e.src_uen||e.src_name);
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    if (!ttMap[cKey]) ttMap[cKey] = {{name:cName, uen:cUen, cty:cCty, sent:0, recv:0}};
    if (isSrc) ttMap[cKey].sent += (e.txn_amt||0);
    else       ttMap[cKey].recv += (e.txn_amt||0);
  }});
  const ttRows = Object.values(ttMap)
    .sort((a,b) => b.sent - a.sent).slice(0, 10)
    .map(r => {{
      const cn = lookupCpty(r.uen, r.name);
      const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
      const cs = cn ? cn.segment   : '-';
      const net = r.sent - r.recv;
      const ns = net >= 0
        ? 'S$ ' + Math.round(net).toLocaleString()
        : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
      return [
        r.name||'-', r.cty||'-', ct, cs,
        {{d: fsgd(r.sent), v: r.sent}}, {{d: fsgd(r.recv), v: r.recv}},
        {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
      ];
    }});
  const ttRowsSorted = sortCpty(ttRows);

  // ── FAST counterparties ────────────────────────────────────────────────
  const fastEdges = edges.filter(e => e.source === 'FAST' && !e.self);
  const fastMap = {{}};
  fastEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cKey  = isSrc ? (e.tgt_uen||e.tgt_name) : (e.src_uen||e.src_name);
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    if (!fastMap[cKey]) fastMap[cKey] = {{name:cName, uen:cUen, cty:cCty, sent:0, recv:0}};
    if (isSrc) fastMap[cKey].sent += (e.txn_amt||0);
    else       fastMap[cKey].recv += (e.txn_amt||0);
  }});
  const fastRows = Object.values(fastMap).sort((a,b) => b.sent - a.sent).map(r => {{
    const cn = lookupCpty(r.uen, r.name);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    const net = r.sent - r.recv;
    const ns = net>=0 ? 'S$ ' + Math.round(net).toLocaleString()
                      : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
    return [
      r.name||'-', r.cty||'-', ct, cs,
      {{d: fsgd(r.sent), v: r.sent}}, {{d: fsgd(r.recv), v: r.recv}},
      {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
    ];
  }});
  const fastRowsSorted = sortCpty(fastRows);

  // ── GIRO counterparties ────────────────────────────────────────────────
  const giroEdges = edges.filter(e => e.source === 'GIRO' && !e.self);
  const giroMap = {{}};
  giroEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cKey  = isSrc ? (e.tgt_uen||e.tgt_name) : (e.src_uen||e.src_name);
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    if (!giroMap[cKey]) giroMap[cKey] = {{name:cName, uen:cUen, cty:cCty, sent:0, recv:0}};
    if (isSrc) giroMap[cKey].sent += (e.txn_amt||0);
    else       giroMap[cKey].recv += (e.txn_amt||0);
  }});
  const giroRows = Object.values(giroMap).sort((a,b) => b.sent - a.sent).map(r => {{
    const cn = lookupCpty(r.uen, r.name);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    const net = r.sent - r.recv;
    const ns = net>=0 ? 'S$ ' + Math.round(net).toLocaleString()
                      : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
    return [
      r.name||'-', r.cty||'-', ct, cs,
      {{d: fsgd(r.sent), v: r.sent}}, {{d: fsgd(r.recv), v: r.recv}},
      {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
    ];
  }});
  const giroRowsSorted = sortCpty(giroRows);

  // ── Payment combined counterparties (TT + FAST + GIRO) ─────────────────
  const payEdges = edges.filter(e => ['Consolidated_TT','FAST','GIRO'].indexOf(e.source) >= 0 && !e.self);
  const payMap = {{}};
  payEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cKey  = isSrc ? (e.tgt_uen||e.tgt_name) : (e.src_uen||e.src_name);
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    if (!payMap[cKey]) payMap[cKey] = {{name:cName, uen:cUen, cty:cCty, sent:0, recv:0}};
    if (isSrc) payMap[cKey].sent += (e.txn_amt||0);
    else       payMap[cKey].recv += (e.txn_amt||0);
  }});
  const payRows = Object.values(payMap).sort((a,b) => b.sent - a.sent).map(r => {{
    const cn = lookupCpty(r.uen, r.name);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    const net = r.sent - r.recv;
    const ns = net>=0 ? 'S$ ' + Math.round(net).toLocaleString()
                      : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
    return [
      r.name||'-', r.cty||'-', ct, cs,
      {{d: fsgd(r.sent), v: r.sent}}, {{d: fsgd(r.recv), v: r.recv}},
      {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
    ];
  }});
  const payRowsSorted = sortCpty(payRows);

  // ── All Transactions counterparties (FITAS + Payment, deduped union) ───
  const allEdges = edges.filter(e => !e.self);
  const allMap = {{}};
  allEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cKey  = isSrc ? (e.tgt_uen||e.tgt_name) : (e.src_uen||e.src_name);
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    if (!allMap[cKey]) allMap[cKey] = {{name:cName, uen:cUen, cty:cCty, sent:0, recv:0}};
    if (isSrc) allMap[cKey].sent += (e.txn_amt||0);
    else       allMap[cKey].recv += (e.txn_amt||0);
  }});
  const allRows = Object.values(allMap).sort((a,b) => b.sent - a.sent).map(r => {{
    const cn = lookupCpty(r.uen, r.name);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    const net = r.sent - r.recv;
    const ns = net>=0 ? 'S$ ' + Math.round(net).toLocaleString()
                      : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
    return [
      r.name||'-', r.cty||'-', ct, cs,
      {{d: fsgd(r.sent), v: r.sent}}, {{d: fsgd(r.recv), v: r.recv}},
      {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
    ];
  }});
  const allRowsSorted = sortCpty(allRows);

  // ── Section F shared header + column widths (F1-F6) ───────────────────
  // Country and Customer Segment kept narrow; counterparty name + amount
  // columns get the bulk of the width.
  const F_HEAD = ['Counterparty Name','🌐','Cust. Type','Cust. Segment',
                  'Sent (SGD)','Received (SGD)','Net Flow (SGD)','Dir.'];
  const F_WIDTHS = ['18%','5%','12%','12%','12%','12%','12%','7%'];

  // ── RSME counterparties ───────────────────────────────────────────────
  const rsmeSeen = {{}};
  const rsmeRows = [];
  rsmeEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    const key   = cUen || cName;
    if (rsmeSeen[key]) return;
    rsmeSeen[key] = true;
    const cn = lookupCpty(cUen, cName);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    rsmeRows.push([cName||'-', cCty||'-', ct, cs]);
  }});
  const rsmeRowsSorted = sortCpty(rsmeRows);

  // ── FITAS counterparties ──────────────────────────────────────────────
  const fitMap = {{}};
  let fitTotalSent = 0, fitTotalRecv = 0;
  fitEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    const key   = cUen || cName;
    if (!fitMap[key]) fitMap[key] = {{name:cName, uen:cUen, cty:cCty, sf:0, sa:0, rf:0, ra:0}};
    if (isSrc) {{ fitMap[key].sf += (e.txn_cnt||0); fitMap[key].sa += (e.txn_amt||0); fitTotalSent += (e.txn_amt||0); }}
    else       {{ fitMap[key].rf += (e.txn_cnt||0); fitMap[key].ra += (e.txn_amt||0); fitTotalRecv += (e.txn_amt||0); }}
  }});
  const fitRows = Object.values(fitMap).map(r => {{
    const cn = lookupCpty(r.uen, r.name);
    const ct = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs = cn ? cn.segment   : '-';
    const sent = r.sa, recv = r.ra;
    const net  = sent - recv;
    const ns = net>=0 ? 'S$ ' + Math.round(net).toLocaleString()
                      : '(S$ ' + Math.round(Math.abs(net)).toLocaleString() + ')';
    return [
      r.name||'-', r.cty||'-', ct, cs,
      {{d: fsgd(sent), v: sent}}, {{d: fsgd(recv), v: recv}},
      {{d: ns, v: net}}, net>=0?'Outflow':'Inflow',
    ];
  }});
  const fitRowsSorted = sortCpty(fitRows);

  // ── AA Paper counterparties ───────────────────────────────────────────
  const aaSeen = {{}};
  const aaRows = [];
  aaEdges.forEach(e => {{
    const isSrc = e.src_uen === uen;
    const cName = isSrc ? e.tgt_name : e.src_name;
    const cUen  = isSrc ? e.tgt_uen  : e.src_uen;
    const cCty  = isSrc ? e.tgt_cty  : e.src_cty;
    const key   = cUen || cName;
    if (aaSeen[key]) return;
    aaSeen[key] = true;
    const cn  = lookupCpty(cUen, cName);
    const ct  = cn ? cn.cust_type : 'Non-Maybank Customer';
    const cs  = cn ? cn.segment   : '-';
    const rel = isSrc ? 'Buyer' : 'Supplier';
    aaRows.push([cName||'-', cCty||'-', ct, cs, rel]);
  }});
  const aaRowsSorted = sortCpty(aaRows);

  const rn      = rno(uen);
  const rd      = today();
  const netAll  = node.all_net || 0;
  const netDir  = netAll >= 0 ? 'Net Outflow' : 'Net Inflow';
  const ctyLbl  = node.country === 'SG' ? 'Singapore' : node.country === 'MY' ? 'Malaysia' : (node.country||'-');
  const dataSrc = fmtDataSrc(node.data_src);

  // ── CIP property-level data ───────────────────────────────────────────
  const cipProps = CIP_PROPS[uen] || [];

  // ── MFI per-sub-section presence flags ────────────────────────────────
  const hasJ1 = [node.mfi_fy, node.mfi_typ, node.mfi_aud, node.mfi_qual,
                 node.mfi_sts, node.mfi_proc, node.mfi_seg, node.mfi_model,
                 node.mfi_tcurr, node.mfi_bcurr, node.mfi_mths].some(v => v != null);
  const hasJ2 = [node.mfi_sales, node.mfi_cogs, node.mfi_gpnl, node.mfi_prepnl,
                 node.mfi_pbt, node.mfi_pat, node.mfi_ebitda].some(v => v != null);
  const hasJ3 = [node.mfi_ast, node.mfi_cast, node.mfi_ncast, node.mfi_lbl,
                 node.mfi_clbl, node.mfi_nclbl, node.mfi_eq, node.mfi_stdebt,
                 node.mfi_ltdebt, node.mfi_debt, node.mfi_dsvc, node.mfi_tnw,
                 node.mfi_atnw].some(v => v != null);
  const hasJ4 = [node.mfi_dcsr, node.mfi_gear].some(v => v != null);

  // ── CIP aggregated sub-section presence flags ─────────────────────────
  const hasK1 = [node.cip_acc_tot, node.cip_acc_opn, node.cip_prop,
                 node.cip_dte_early, node.cip_dte_cls].some(v => v != null);
  const hasK2 = [node.cip_lmt, node.cip_loan, node.cip_npl,
                 node.cip_dte_fac, node.cip_dte_bal].some(v => v != null);
  const hasK3 = [node.cip_sec, node.cip_emv, node.cip_fsv, node.cip_fiv].some(v => v != null);
  const hasK4 = [node.cip_own, node.cip_ten, node.cip_biz, node.cip_vac].some(v => v != null);
  const hasK5 = node.cip_jtc != null;

  document.getElementById('ro').innerHTML = `
  <div class="ph">
    <div class="ph-bar">
      <div class="ph-acc"></div>
      <div class="ph-l"><div class="ph-logo-bg"></div></div>
      <div class="ph-r">
        <div class="ph-mx">M-EXT</div>
        <div class="ph-fn">Maybank Ecosystem eXchange Topology</div>
      </div>
    </div>
    <div class="ph-sub">
      <span class="ph-cn">${{node.name||'-'}}</span>
      <span class="ph-dt">Report: ${{rn}} &nbsp;|&nbsp; ${{rd}}</span>
    </div>
  </div>

  <div class="cov">
    <div class="cov-cls">Strictly Confidential &nbsp;|&nbsp; Internal Use Only</div>
    <div class="cov-nm">${{node.name||'-'}}</div>
    <div class="cov-bdg">
      <span class="bdg bdg-live">${{node.status||'Live'}}</span>
      <span class="bdg bdg-trade">${{node.cust_type||'-'}}</span>
      <span class="bdg bdg-seg">${{node.segment||'-'}}</span>
      <span class="bdg bdg-cty">${{ctyLbl}}</span>
    </div>
    <div class="cov-meta">
      UEN: ${{node.uen||'-'}} &nbsp;|&nbsp; CIF: ${{node.cif||'-'}} &nbsp;|&nbsp;
      Report No: ${{rn}} &nbsp;|&nbsp; Generated: ${{rd}}
    </div>
  </div>

  <div class="sc">
    <div class="sc-card">
      <div class="sc-v">${{fnum(node.total_deg)}}</div>
      <div class="sc-s">All Networks</div>
      <div class="sc-l">Total Unique Connections</div>
    </div>
    <div class="sc-card">
      <div class="sc-v">S$&nbsp;${{Math.abs(Math.round(netAll)).toLocaleString()}}</div>
      <div class="sc-s">${{netDir}}</div>
      <div class="sc-l">All Transactions (FITAS + TT/MEPS/FAST/GIRO) Net Flow</div>
    </div>
    <div class="sc-card">
      <div class="sc-v">S$&nbsp;${{Math.round(node.ln_tot||0).toLocaleString()}}</div>
      <div class="sc-s">Trade + Non-Trade</div>
      <div class="sc-l">Total Loan Balances</div>
    </div>
  </div>

  ${{sec('A','COMPANY OVERVIEW',`
    <div class="kv-grid">
      <div>
        ${{kv([
          ['UEN', node.uen],
          ['CIF Number', node.cif],
          ['Entity Type', node.ent_type],
          ['Company Status', node.status],
          ['Sector', node.sector],
          ['Industry', node.industry],
          ['SSIC Code', node.ssic],
          ['Data Sources', dataSrc],
          ['Country', ctyLbl],
          ['City', node.city],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Parent Group', node.parent],
          ['No. Employees', node.employees],
          ['Listed / Unlisted', node.listed],
          ['Export Countries', node.export_cty],
          ['Incorporation Date', node.incorp_date],
          ['Customer Segment', node.segment],
          ['Customer Type', node.cust_type],
          ['First CA Opening Date', node.first_ca],
          ['Relationship Tenure', node.tenure ? fnum(node.tenure)+' days' : '-'],
        ])}}
      </div>
    </div>
  `)}}

  ${{sec('B','CREDIT STATUS',`
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Credit Status', node.credit_sts],
          ['Impairment Stage', node.impairment],
          ['Risk Grade', node.risk_grade],
          ['Borrower Risk Rating (BRR)', node.brr],
          ['Rating Date', node.rating_dte],
          ['Months on Book', node.mob],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Watchlist', fbool(node.watchlist)],
          ['Special Mention (SMA)', fbool(node.sma)],
          ['NPL', fbool(node.npl)],
          ['Latest DPD Bucket', node.dpd],
          ['Delinquency Count (12M)', node.del_12m ?? 0],
          ['', ''],
        ])}}
      </div>
    </div>
  `)}}

  ${{sec('C','ACRA CHARGES',`
    ${{node.chg_count != null && node.chg_count > 0 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Total Charges Registered', fnum(node.chg_count)],
          ['Unique Chargees', fnum(node.chg_chargee)],
          ['Charge Secured Amount (SGD)', fsgd(node.chg_amt)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Earliest Charge Date', node.chg_earliest],
          ['Latest Charge Date', node.chg_latest],
          ['All Monies Owing (Yes)', fnum(node.chg_amo_y)],
          ['All Monies Owing (No)', fnum(node.chg_amo_n)],
        ])}}
      </div>
    </div>` : noData()}}
  `)}}

  ${{sec('D','FACILITIES & BALANCE SHEET',`
    <div class="ssl">Trade Facilities</div>
    ${{kv([
      ['Authorised Limit (SGD)', fsgd(node.auth_lmt)],
      ['Available Limit (SGD)', fsgd(node.avail_lmt)],
      ['Outstanding Balance (SGD)', fsgd(node.outstanding)],
      ['  On-Balance Sheet (SGD)', fsgd(node.on_bs)],
      ['  Off-Balance Sheet (SGD)', fsgd(node.off_bs)],
      ['Utilisation (%)', node.util_pct != null ? fpct(node.util_pct) : '-'],
      ['Latest AA Creation Date', node.aa_date],
    ])}}
    <div class="ssl">Balance Sheet</div>
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Current Account (SGD)', fsgd(node.casa)],
          ['Fixed Deposit (SGD)', fsgd(node.fd)],
          ['Structured TD (SGD)', fsgd(node.strctd)],
          ['Total Deposit Balances (SGD)', fsgd(node.dep_tot)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Trade Loan (SGD)', fsgd(node.tr_ln)],
          ['Non-Trade Loan (SGD)', fsgd(node.ntr_ln)],
          ['Total Loan Balances (SGD)', fsgd(node.ln_tot)],
          ['', ''],
        ])}}
      </div>
    </div>
  `)}}

  ${{sec('E','NETWORK SUMMARY',`
    <div class="ssl">Connection Overview</div>
    ${{tbl(
      ['Network Source','Connections','SG','MY','Description'],
      [
        ['All Networks (Combined)',     fnum(node.total_deg), allSGreal, allMYreal, 'Cross-source unique counterparties'],
        ['RSME Buyer/Supplier',         fnum(node.rsme_deg),  rsmeSG,    rsmeMY,    'Declared buyer/supplier relationships'],
        ['AA Paper',                    fnum(node.aa_deg),    aaSG,      aaMY,      'AA Paper counterparties'],
        ['FITAS',                       fnum(node.fitas_deg), fitasSG,   fitasMY,   'FITAS trade-finance counterparties'],
        ['TT',                          fnum(node.tt_deg),    ttSG,      ttMY,      'TT payment counterparties'],
        ['FAST',                        fnum(node.fast_deg),  fastSG,    fastMY,    'FAST payment counterparties'],
        ['GIRO',                        fnum(node.giro_deg),  giroSG,    giroMY,    'GIRO payment counterparties'],
        ['Payment Transactions (TT/MEPS/FAST/GIRO)', fnum(node.pay_deg), paySG, payMY, 'TT + MEPS + FAST + GIRO union'],
        ['All Transactions (FITAS + TT/MEPS/FAST/GIRO)', fnum(node.all_deg), allSGreal, allMYreal, 'FITAS + TT + MEPS + FAST + GIRO union'],
      ]
    )}}
    <div class="ssl">Buyer / Supplier Breakdown</div>
    ${{kv([
      ['Connections to Buyers',    fnum(node.to_buyers)],
      ['Connections to Suppliers', fnum(node.to_suppliers)],
    ])}}
    <div class="ssl">FITAS Flow Summary &nbsp;|&nbsp; Latest record: ${{dv(node.fitas_yr || '-')}}</div>
    ${{kv([
      ['FITAS Amount Sent (SGD)',     fsgd(node.fitas_sent)],
      ['FITAS Amount Received (SGD)', fsgd(node.fitas_recv)],
      ['FITAS Net Flow (SGD)',        fsgd(node.fitas_net) + (node.fitas_net != null ? '  (' + (node.fitas_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
    ])}}

    <div class="ssl">TT Flow Summary</div>
    ${{kv([
      ['TT Amount Sent (SGD)',          fsgd(node.tt_sent)],
      ['TT Amount Received (SGD)',      fsgd(node.tt_recv)],
      ['TT Net Flow (SGD)',             fsgd(node.tt_net) + (node.tt_net != null ? '  (' + (node.tt_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
      ['TT Self-Transfer Count',        fnum(node.tt_sc)],
      ['TT Self-Transfer Amount (SGD)', fsgd(node.tt_sa)],
    ])}}

    <div class="ssl">FAST Flow Summary</div>
    ${{kv([
      ['FAST Amount Sent (SGD)',          fsgd(node.fast_sent)],
      ['FAST Amount Received (SGD)',      fsgd(node.fast_recv)],
      ['FAST Net Flow (SGD)',             fsgd(node.fast_net) + (node.fast_net != null ? '  (' + (node.fast_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
      ['FAST Self-Transfer Count',        fnum(node.fast_sc)],
      ['FAST Self-Transfer Amount (SGD)', fsgd(node.fast_sa)],
    ])}}

    <div class="ssl">GIRO Flow Summary</div>
    ${{kv([
      ['GIRO Amount Sent (SGD)',          fsgd(node.giro_sent)],
      ['GIRO Amount Received (SGD)',      fsgd(node.giro_recv)],
      ['GIRO Net Flow (SGD)',             fsgd(node.giro_net) + (node.giro_net != null ? '  (' + (node.giro_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
      ['GIRO Self-Transfer Count',        fnum(node.giro_sc)],
      ['GIRO Self-Transfer Amount (SGD)', fsgd(node.giro_sa)],
    ])}}

    <div class="ssl">Payment Transactions (TT/MEPS/FAST/GIRO) Flow Summary</div>
    ${{kv([
      ['Payment Amount Sent (SGD)',          fsgd(node.pay_sent)],
      ['Payment Amount Received (SGD)',      fsgd(node.pay_recv)],
      ['Payment Net Flow (SGD)',             fsgd(node.pay_net) + (node.pay_net != null ? '  (' + (node.pay_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
      ['Payment Self-Transfer Count',        fnum(node.pay_sc)],
      ['Payment Self-Transfer Amount (SGD)', fsgd(node.pay_sa)],
    ])}}

    <div class="ssl">All Transactions (FITAS + TT/MEPS/FAST/GIRO) Flow Summary</div>
    ${{kv([
      ['All Txn Amount Sent (SGD)',     fsgd(node.all_sent)],
      ['All Txn Amount Received (SGD)', fsgd(node.all_recv)],
      ['All Txn Net Flow (SGD)',        fsgd(node.all_net) + (node.all_net != null ? '  (' + (node.all_net >= 0 ? 'Net Outflow' : 'Net Inflow') + ')' : '')],
    ])}}
  `)}}

  ${{sec('F','ALL TRANSACTIONS (FITAS + TT/MEPS/FAST/GIRO) COUNTERPARTIES',`
    <div class="ssl">F1 &nbsp; FITAS Counterparties</div>
    ${{fitRowsSorted.length ? `
    <div class="note">Sorted by customer type then alphabetically.</div>
    ${{tbl(F_HEAD, fitRowsSorted, F_WIDTHS)}}` : noData()}}

    <div class="ssl">F2 &nbsp; TT Counterparties</div>
    ${{ttRowsSorted.length ? tbl(F_HEAD, ttRowsSorted, F_WIDTHS) : noData()}}

    <div class="ssl">F3 &nbsp; FAST Counterparties</div>
    ${{fastRowsSorted.length ? tbl(F_HEAD, fastRowsSorted, F_WIDTHS) : noData()}}

    <div class="ssl">F4 &nbsp; GIRO Counterparties</div>
    ${{giroRowsSorted.length ? tbl(F_HEAD, giroRowsSorted, F_WIDTHS) : noData()}}

    <div class="ssl">F5 &nbsp; Payment Transactions (TT/MEPS/FAST/GIRO) Counterparties</div>
    ${{payRowsSorted.length ? tbl(F_HEAD, payRowsSorted, F_WIDTHS) : noData()}}

    <div class="ssl">F6 &nbsp; All Transactions (FITAS + TT/MEPS/FAST/GIRO) Counterparties</div>
    ${{allRowsSorted.length ? tbl(F_HEAD, allRowsSorted, F_WIDTHS) : noData()}}
  `)}}

  ${{sec('G','RSME BUYER/SUPPLIER CHECKLIST',`
    ${{rsmeRowsSorted.length ? `
    <div class="note">Sorted by customer type then alphabetically.</div>
    ${{tbl(
      ['Counterparty Name','Country','Customer Type','Customer Segment'],
      rsmeRowsSorted
    )}}` : noData()}}
  `)}}

  ${{sec('H','AA PAPER COUNTERPARTIES',`
    ${{aaRowsSorted.length ? `
    <div class="note">Sorted by customer type then alphabetically.</div>
    ${{tbl(
      ['Counterparty Name','Country','Customer Type','Customer Segment','Relationship'],
      aaRowsSorted
    )}}` : noData()}}
  `)}}

  ${{sec('I','FINANCIAL HIGHLIGHTS',`
    <div class="ssl">J1 &nbsp; ACRA Financials (SGD) &nbsp;|&nbsp; FY: ${{dv(node.fin_yr)}}</div>
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Financial Year End',       node.fin_yr],
          ['Sales Revenue (SGD)',      fsgd(node.fin_rev)],
          ['Profit Before Tax (SGD)',  fsgd(node.fin_pbt)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Cash & Bank Balance (SGD)', fsgd(node.fin_cash)],
          ['Trade Creditors (SGD)',     fsgd(node.fin_cred)],
          ['Trade Debtors (SGD)',       fsgd(node.fin_debt)],
        ])}}
      </div>
    </div>
    <div class="ssl">J2 &nbsp; EMIS Financials (USD) &nbsp;|&nbsp; FY${{dv(node.emis_yr)}} &nbsp;|&nbsp; Source: ${{dv(node.emis_src)}}</div>
    <div class="note">EMIS figures denominated in USD. No currency conversion applied.</div>
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Fiscal Year',                   node.emis_yr],
          ['Total Operating Revenue (USD)', fusd(node.emis_rev)],
          ['Operating Profit (USD)',         fusd(node.emis_op)],
          ['Profit Before Income Tax (USD)', fusd(node.emis_pbt)],
          ['Total Assets (USD)',             fusd(node.emis_assets)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Free Cash Flow (USD)',          fusd(node.emis_fcf)],
          ['Net Cash Flow from Ops (USD)',  fusd(node.emis_ncf)],
          ['Return on Assets (ROA %)',      fpct(node.emis_roa)],
          ['Return on Equity (ROE %)',      fpct(node.emis_roe)],
          ['Audited',                       node.emis_aud],
          ['Data Source',                   node.emis_src],
        ])}}
      </div>
    </div>
  `)}}

  ${{sec('J','MFI FINANCIAL STATEMENTS',`
    <div class="ssl">J1 &nbsp; Statement Info &nbsp;|&nbsp; FY End: ${{dv(node.mfi_fy)}} &nbsp;|&nbsp; Type: ${{dv(node.mfi_typ)}}</div>
    ${{hasJ1 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Financial Year End',     node.mfi_fy],
          ['Statement Type',         node.mfi_typ],
          ['Auditor',                node.mfi_aud],
          ['Qualified Opinion',      node.mfi_qual],
          ['Statement Status',       node.mfi_sts],
          ['Processing Date',        node.mfi_proc],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Segment',                node.mfi_seg],
          ['Model Name',             node.mfi_model],
          ['Target Currency',        node.mfi_tcurr],
          ['Base Currency',          node.mfi_bcurr],
          ['Period Length (Months)', node.mfi_mths != null ? fnum(node.mfi_mths) : '-'],
          ['', ''],
        ])}}
      </div>
    </div>` : noData()}}
    <div class="ssl">J2 &nbsp; P&amp;L (SGD)</div>
    ${{hasJ2 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Sales Revenue',             fsgd(node.mfi_sales)],
          ['COGS',                      fsgd(node.mfi_cogs)],
          ['Gross Operating P&amp;L',   fsgd(node.mfi_gpnl)],
          ['Pre-Tax P&amp;L Before Int',fsgd(node.mfi_prepnl)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Profit Before Tax',   fsgd(node.mfi_pbt)],
          ['Profit After Tax',    fsgd(node.mfi_pat)],
          ['EBITDA',              fsgd(node.mfi_ebitda)],
          ['', ''],
        ])}}
      </div>
    </div>` : noData()}}
    <div class="ssl">J3 &nbsp; Balance Sheet (SGD)</div>
    ${{hasJ3 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Total Assets',            fsgd(node.mfi_ast)],
          ['Current Assets',          fsgd(node.mfi_cast)],
          ['Non-Current Assets',      fsgd(node.mfi_ncast)],
          ['Total Liabilities',       fsgd(node.mfi_lbl)],
          ['Current Liabilities',     fsgd(node.mfi_clbl)],
          ['Non-Current Liabilities', fsgd(node.mfi_nclbl)],
          ['Total Equity',            fsgd(node.mfi_eq)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Short-Term Debt',    fsgd(node.mfi_stdebt)],
          ['Long-Term Debt',     fsgd(node.mfi_ltdebt)],
          ['Total Debt',         fsgd(node.mfi_debt)],
          ['Debt Service',       fsgd(node.mfi_dsvc)],
          ['Tangible Net Worth', fsgd(node.mfi_tnw)],
          ['Adjusted TNW',       fsgd(node.mfi_atnw)],
          ['', ''],
        ])}}
      </div>
    </div>` : noData()}}
    <div class="ssl">J4 &nbsp; Financial Ratios</div>
    ${{hasJ4 ? kv([
      ['DSCR',          frat(node.mfi_dcsr)],
      ['Gearing Ratio', frat(node.mfi_gear)],
    ]) : noData()}}
  `)}}

  ${{sec('K','CIP COLLATERALS',`
    <div class="ssl">K1 &nbsp; Holdings Overview</div>
    ${{hasK1 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['No. of Total Accounts', fnum(node.cip_acc_tot)],
          ['No. of Open Accounts',  fnum(node.cip_acc_opn)],
          ['No. of Properties',     fnum(node.cip_prop)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Earliest Account Open Date', node.cip_dte_early],
          ['Latest Account Close Date',  node.cip_dte_cls],
          ['', ''],
        ])}}
      </div>
    </div>` : noData()}}
    <div class="ssl">K2 &nbsp; Limits &amp; Outstanding Balances (SGD) &nbsp;|&nbsp; Limit Last Updated: ${{dv(node.cip_dte_fac)}} &nbsp;|&nbsp; Balance Last Updated: ${{dv(node.cip_dte_bal)}}</div>
    ${{hasK2 ? `
    <div class="kv-grid">
      <div>
        ${{kv([
          ['Facility Limit', fsgd(node.cip_lmt)],
          ['Loan Balance',   fsgd(node.cip_loan)],
          ['NPL Balance',    fsgd(node.cip_npl)],
        ])}}
      </div>
      <div class="kv-divider"></div>
      <div>
        ${{kv([
          ['Limit Last Updated',   node.cip_dte_fac],
          ['Balance Last Updated', node.cip_dte_bal],
          ['', ''],
        ])}}
      </div>
    </div>` : noData()}}
    <div class="ssl">K3 &nbsp; Valuations (SGD)</div>
    ${{hasK3 ? kv([
      ['Secured Amount',               fsgd(node.cip_sec)],
      ['Estimated Market Value (EMV)', fsgd(node.cip_emv)],
      ['Forced Sale Value (FSV)',       fsgd(node.cip_fsv)],
      ['Fire Insurance Value (FIV)',    fsgd(node.cip_fiv)],
    ]) : noData()}}
    <div class="ssl">K4 &nbsp; Property Info</div>
    ${{hasK4 ? kv([
      ['Owner Occupied', node.cip_own != null ? fnum(node.cip_own) : '-'],
      ['Tenanted',       node.cip_ten != null ? fnum(node.cip_ten) : '-'],
      ['Biz Operations', node.cip_biz != null ? fnum(node.cip_biz) : '-'],
      ['Vacant',         node.cip_vac != null ? fnum(node.cip_vac) : '-'],
    ]) : noData()}}
    <div class="ssl">K5 &nbsp; Other Info</div>
    ${{hasK5 ? kv([
      ['No. of JTC-linked Properties', fnum(node.cip_jtc)],
    ]) : noData()}}
    <div class="ssl">K6 &nbsp; Property Details &nbsp;(${{cipProps.length}} propert${{cipProps.length === 1 ? 'y' : 'ies'}})</div>
    ${{cipProps.length ? cipProps.map((p, i) => `
      <div class="ssl-sub">Property No. #${{i+1}} &nbsp;&nbsp;&nbsp;&mdash;&nbsp;&nbsp;&nbsp; ${{p.address || 'Address not available'}}</div>
      <div class="kv-grid">
        <div>
          ${{kv([
            ['AA Number',                       p.appl_no],
            ['Application Closed',              p.appl_closed],
            ['Latest Account Opening Date',     p.latest_opn],
            ['Latest Account Closed Date',      p.latest_cls],
            ['Total Repayment Months',          p.tot_rpym != null ? String(p.tot_rpym) : null],
            ['Security Type',                   p.sec_type],
            ['Secured Amount',                  p.sec_amt],
            ['Estimated Market Value (EMV)',     p.sec_emv],
            ['Forced Sale Value (FSV)',          p.sec_fsv],
            ['Fire Insurance Value (FIV)',       p.sec_fiv],
            ['Valuation Date',                  p.value_dte],
          ])}}
        </div>
        <div class="kv-divider"></div>
        <div>
          ${{kv([
            ['Mortgage Category',               p.mort_cat],
            ['Property Purchase Amount',        p.ppty_amt],
            ['Property Land Area',              p.land_area],
            ['Built-Up Area',                   p.built_up],
            ['Lease Period',                    p.lease_prd],
            ['Occupancy Type',                  p.occp_type],
            ['First Party Surety',              p.first_party],
            ['Shared Security Indicator',       p.shared_sec],
            ['Is JTC-Linked',                   p.jtc],
          ])}}
        </div>
      </div>
    `).join('') : noData()}}
  `)}}

  <div class="disc">
    <b>DISCLAIMER:</b> This report is generated by the M-EXT (Maybank Ecosystem eXchange Topology) platform
    and is intended solely for authorised Maybank personnel. Information is compiled from multiple internal
    and external sources including ACRA, EMIS, MFI, CIP, CIF Segment Master, RSME, Consolidated TT,
    FAST, GIRO, FITAS, and AA Paper. Maybank does not warrant the accuracy, completeness, or timeliness of the contents.
    This report is strictly confidential and must not be reproduced or distributed without prior written
    authorisation. &nbsp;Report No: ${{rn}} &nbsp;|&nbsp; Generated: ${{rd}}
  </div>
  `;

  document.getElementById('tb-co').textContent = node.name || uen;
  document.getElementById('ss').style.display  = 'none';
  document.getElementById('rs').style.display  = 'block';
  window.scrollTo(0, 0);
}}

function sec(code, title, body) {{
  // *** updated | sec-hdr is now a clickable accordion that toggles sec-body
  // visibility (matches the network-graph side panel pattern). Default state
  // is open. The chevron rotates 90 deg via CSS when the section is closed.
  // *** updated | data-section attr lets CSS/JS scope to a specific section
  // (used by Section F for sortable tables and a blue row-hover).
  return `<div class="sec" data-section="${{code}}">
    <div class="sec-hdr" onclick="toggleSec(this)">
      <div class="sec-code">${{code}}</div>
      <div class="sec-title">${{title}}</div>
      <div class="sec-arrow">&#9660;</div>
    </div>
    <div class="sec-body">${{body}}</div>
  </div>`;
}}

function toggleSec(hdr) {{
  // Toggle the sec-body that follows the clicked sec-hdr. Rotates the
  // chevron via the .closed class on .sec-hdr.
  var body = hdr.nextElementSibling;
  if (!body) return;
  var willClose = body.style.display !== 'none' && !hdr.classList.contains('closed');
  if (willClose) {{
    body.style.display = 'none';
    hdr.classList.add('closed');
  }} else {{
    body.style.display = '';
    hdr.classList.remove('closed');
  }}
}}

function kv(pairs) {{
  return pairs.map(([l, v]) =>
    `<div class="kv-row">
      <div class="kv-lbl">${{l}}</div>
      <div class="kv-val">${{(v == null || v === '') ? '-' : v}}</div>
    </div>`
  ).join('');
}}

function tbl(headers, rows, colWidths) {{
  // Cells may be primitives (string/number) OR an object {{d, v}} where
  // d = displayed string and v = raw value used for sorting. The raw value
  // is emitted as a data-sort attribute so JS sorting is independent of the
  // formatted display (eg. "(S$ 12,345)" sorts as -12345 not as a string).
  // When colWidths are passed, the table opts into table-layout:fixed via
  // the "dt-fixed" class so the explicit widths are honoured exactly
  // (otherwise browsers treat width as a hint and grow columns to fit).
  const fixed = colWidths && colWidths.length ? ' dt-fixed' : '';
  const ths = headers.map((h, i) => {{
    const w = colWidths && colWidths[i] ? ` style="width:${{colWidths[i]}}"` : '';
    return `<th${{w}}><span class="th-label">${{h}}</span><span class="sort-arrow"></span></th>`;
  }}).join('');
  const trs = rows.map(r =>
    `<tr>${{r.map(c => {{
      if (c && typeof c === 'object' && 'd' in c) {{
        const raw = (c.v == null) ? '' : String(c.v);
        const sa  = raw === '' ? '' : ` data-sort="${{raw.replace(/"/g, '&quot;')}}"`;
        const dsp = (c.d == null || c.d === '') ? '-' : c.d;
        return `<td${{sa}}>${{dsp}}</td>`;
      }}
      return `<td>${{(c == null || c === '') ? '-' : c}}</td>`;
    }}).join('')}}</tr>`
  ).join('');
  return `<div class="dtw">
    <table class="dt${{fixed}}">
      <thead><tr>${{ths}}</tr></thead>
      <tbody>${{trs}}</tbody>
    </table>
  </div>`;
}}

// Click-to-sort for sortable tables in Sections F, G, H. Three-state cycle
// on the active column: asc -> desc -> default (original order) -> asc -> ...
// Uses td[data-sort] when present (numeric if all values parse, else
// lexical on raw); falls back to td.textContent. The DOM mutation is what
// print sees, so the printed output follows the current sort.
const SORTABLE_SECTIONS = ['F','G','H'];
document.addEventListener('click', function(ev) {{
  const th = ev.target.closest('table.dt thead th');
  if (!th) return;
  const sec = th.closest('.sec');
  if (!sec || !SORTABLE_SECTIONS.includes(sec.dataset.section)) return;
  sortDtTable(th);
}});

function sortDtTable(th) {{
  const tr    = th.parentElement;
  const ths   = Array.from(tr.children);
  const idx   = ths.indexOf(th);
  const table = th.closest('table');
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  if (rows.length < 2) return;

  // Snapshot the original row order on first interaction so we can restore
  // the default view (3rd click). Stored on the <table> element.
  if (!table._origRows) table._origRows = rows.slice();

  // Decide next state. Three-state cycle on the same column:
  //   none -> asc -> desc -> none -> asc -> ...
  // Clicking a DIFFERENT column resets previous column and starts at asc.
  const sameCol = th.classList.contains('sorted');
  const prevDir = th.dataset.sortDir;
  let nextDir;
  if (!sameCol)            nextDir = 'asc';
  else if (prevDir==='asc')  nextDir = 'desc';
  else if (prevDir==='desc') nextDir = 'none';
  else                       nextDir = 'asc';

  // Clear all header indicators
  ths.forEach(t => {{
    t.classList.remove('sorted');
    const a = t.querySelector('.sort-arrow');
    if (a) a.textContent = '';
    delete t.dataset.sortDir;
  }});

  if (nextDir === 'none') {{
    // Restore original DOM order
    const frag = document.createDocumentFragment();
    table._origRows.forEach(r => frag.appendChild(r));
    tbody.appendChild(frag);
    return;
  }}

  th.classList.add('sorted');
  th.dataset.sortDir = nextDir;
  const arr = th.querySelector('.sort-arrow');
  if (arr) arr.textContent = (nextDir === 'asc') ? '▲' : '▼';

  // Decide numeric vs lexical from the column's raw values
  const raws = rows.map(r => {{
    const td = r.children[idx];
    if (!td) return '';
    if (td.hasAttribute('data-sort')) return td.getAttribute('data-sort');
    return td.textContent.trim();
  }});
  const allNum = raws.every(v => v === '' || v === '-' || !isNaN(parseFloat(v)));
  const cmp = allNum
    ? (a, b) => {{
        const av = (a === '' || a === '-') ? Number.NEGATIVE_INFINITY : parseFloat(a);
        const bv = (b === '' || b === '-') ? Number.NEGATIVE_INFINITY : parseFloat(b);
        return av - bv;
      }}
    : (a, b) => a.localeCompare(b, undefined, {{numeric:true, sensitivity:'base'}});

  const indexed = rows.map((r, i) => ({{ r:r, k: raws[i] }}));
  indexed.sort((x, y) => cmp(x.k, y.k));
  if (nextDir === 'desc') indexed.reverse();
  const frag = document.createDocumentFragment();
  indexed.forEach(it => frag.appendChild(it.r));
  tbody.appendChild(frag);
}}

function goBack() {{
  document.getElementById('rs').style.display  = 'none';
  document.getElementById('ss').style.display  = 'flex';
  document.getElementById('sinp').value        = '';
  sug.style.display = 'none';
}}
</script>
</body>
</html>"""

OUTPUT_FILENAME = "MEXT_REPORT.html"
html_bytes      = HTML.encode("utf-8")
Network_Graph_Professional_Report.upload_stream(OUTPUT_FILENAME, io.BytesIO(html_bytes))

print(f"HTML size   : {len(html_bytes)/1024:.0f} KB")
print(f"Output file : {OUTPUT_FILENAME}")
print(f"Folder      : vYiC1wqZ")
print(f"\nDone. Download the HTML from the output folder and open in Chrome.")
print(f"Chrome: File > Print > Save as PDF for best colour output.")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Diagnostic: CIP data coverage -- aggregated (L1-L5) and property-level (L6)

CIP_AGG_FIELDS = [
    'cip_lmt', 'cip_loan', 'cip_npl', 'cip_sec', 'cip_emv', 'cip_fsv', 'cip_fiv',
    'cip_prop', 'cip_acc_tot', 'cip_acc_opn', 'cip_acc_cls',
    'cip_dte_early', 'cip_dte_cls', 'cip_dte_fac', 'cip_dte_bal',
    'cip_jtc', 'cip_own', 'cip_ten', 'cip_biz', 'cip_vac',
]

has_cip_agg  = {n['uen'] for n in std_nodes if any(n.get(f) is not None for f in CIP_AGG_FIELDS)}
has_cip_prop = set(cip_props_by_uen.keys()) & {n['uen'] for n in std_nodes if n.get('uen')}
has_both     = has_cip_agg & has_cip_prop
has_agg_only = has_cip_agg - has_cip_prop
has_prop_only= has_cip_prop - has_cip_agg

name_map = {n['uen']: (n.get('name') or n['uen']) for n in std_nodes if n.get('uen')}

print("=" * 70)
print("CIP DATA COVERAGE")
print("=" * 70)
print(f"  Nodes in report          : {len(std_nodes):,}")
print(f"  With CIP aggregated data : {len(has_cip_agg):,}")
print(f"  With CIP property data   : {len(has_cip_prop):,}")
print(f"  With BOTH                : {len(has_both):,}")
print(f"  Aggregated only (no props): {len(has_agg_only):,}")
print(f"  Property only (no agg)   : {len(has_prop_only):,}")

print(f"\n{'─'*70}")
print(f"  {'#':<4} {'UEN':<15} {'Name':<45} {'Agg':>4} {'Props':>6}")
print(f"{'─'*70}")

all_with_cip = sorted(has_cip_agg | has_cip_prop, key=lambda u: name_map.get(u, u))
for i, uen in enumerate(all_with_cip, 1):
    name     = name_map.get(uen, uen)[:44]
    has_agg  = 'Y' if uen in has_cip_agg  else '-'
    n_props  = len(cip_props_by_uen.get(uen, []))
    props_s  = str(n_props) if n_props > 0 else '-'
    print(f"  {i:<4} {uen:<15} {name:<45} {has_agg:>4} {props_s:>6}")

print(f"{'─'*70}")
print(f"  Total: {len(all_with_cip):,} companies with any CIP data")