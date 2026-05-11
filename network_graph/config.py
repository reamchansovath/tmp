# ── network_graph/config.py ───────────────────────────────────────────────────
# Single source of truth for ALL project configuration.
# To add a new file source:  add to FILES dict or create a new *_FILES dict
# To add a new field:        add to FIELD_CONFIG
# To add a new facility col: add to FAC_COLS
# To add a new credit col:   add to CREDIT_SUMMARY_RENAME
# To change graph behaviour: change node colour constants


class NetworkGraphConfig:

    # ═════════════════════════════════════════════════════════════════════════
    # DATAIKU FOLDER + FILE REFERENCES
    # ═════════════════════════════════════════════════════════════════════════

    FOLDER_MAIN         = "PeU8Pmk0"
    FOLDER_ACRA         = "bUeaZ6lx"
    FOLDER_PIPELINE     = "oSbAKnR6"
    FOLDER_VIZ          = "0i5oqJS3"
    FOLDER_EMIS         = "Jhz3K1CR"
    FOLDER_RSME_HARM    = "QK0LgLLw"
    FOLDER_CONSOL_TT    = "EQAhRNIT"
    FOLDER_FITAS        = "Lg1A4MdX"
    FOLDER_AA_PAPER     = "etLMIcr5"
    FOLDER_ENRICHMENT   = "LU4uOH1G"
    FOLDER_ACRA_CHARGES = "4DvMvyyS"
    # *** new | CIP collaterals processed data
    FOLDER_CIP          = "pD0HDxZR"
    # *** new | FAST/GIRO harmonised payment data (one file split into FAST and GIRO by TRN_TYP_L1_GRP)
    FOLDER_FAST_GIRO    = "18Yk8ZTT"

    FILES = {
        'biz_typ' : "T_BIZ_TYP_MSTR.csv",
        'chk_dtl' : "T_TRN_SUPP_BUYER_CHK_DTL.csv",
        'logo'    : "/Maybank Logo/maybank-logo-png-transparent.png",
    }

    EMIS_FILE = "EMIS_cleaned.csv"

    RSME_FILES = {
        'bor_info' : "RSME_SUPP_BUYER_BOR_INFO_Harmonised_df.feather",
        'dtl'      : "T_TRN_SUPP_BUYER_DTL_Harmonised_df.feather",
    }

    CONSOL_TT_FILES = {
        'xborder'  : "Consolidated_Transaction_CrossBorder_MY_Harmonised_df.feather",
        'domestic' : "Consolidated_Transaction_Domestic_Harmonised_df.feather",
    }

    FITAS_FILES = {
        'xborder'  : "FITAS_CrossBorder_MY_Harmonised_df.feather",
        'domestic' : "FITAS_Domestic_Harmonised_df.feather",
    }

    AA_PAPER_FILE = "AA_Paper_Counterparties_Harmonised_df.feather"

    ENRICHMENT_FILES = {
        'cif_segm_mstr' : "NONINDV_CIF_SEGM_MSTR.zip",
        'credit_summary': "WY_RTB_CIF_CREDIT_SUMMARY.zip",
        'fac_summary'   : "WY_RTB_WAA_FAC_SUMMARY.csv",
        'acra_fin'      : "SV_ACRA_INFO_WIDE_FMT.zip",
        'balance_sheet' : "WY_RTB_CUST_BALANCESHEET.csv",
        # *** new | MFI financial statements -- dedup to latest END_DTE per UEN
        'mfi'           : "WY_RTB_MFI_DTL.csv",
    }

    ACRA_CHARGES_FILE = "ACRA_Charges_Processed_df.feather"

    # *** new | CIP collaterals -- UEN-level aggregated feather
    CIP_FILE      = "CIP_Collaterals_Info_UEN_Base_df.feather"
    # *** new | Per-property (application-level) detail used by Recipe 4 K6
    CIP_APPL_FILE = "CIP_Collaterals_Info_Agg_Appl_df.feather"

    # *** new | FAST/GIRO harmonised feather -- single file, split into two sources via TRN_TYP_L1_GRP
    FAST_GIRO_FILE = "FAST_GIRO_Harmonised.feather"

    FILE_ACRA          = "merged_acra_data.feather"
    # *** updated | M-EXT standardised naming
    OUTPUT_HTML        = "MEXT_NETWORK.html"
    OUTPUT_HTML_MINIFY = "MEXT_NETWORK_minified.html"

    DATASET_SUBNETWORK_SUMMARY = "NetworkGraph_Subnetwork_Summary"
    DATASET_NODE_INFO          = "NetworkGraph_Node_Info"
    DATASET_EDGE_INFO          = "NetworkGraph_Edges_Info"

    # ═════════════════════════════════════════════════════════════════════════
    # NODE COLOURS
    # ═════════════════════════════════════════════════════════════════════════

    COLOR_TRADE_MB     = "#27ae60"
    COLOR_NON_TRADE_MB = "#e67e22"
    COLOR_NON_MB       = "#95a5a6"
    COLOR_MALAYSIAN    = "#059ef7"

    # ═════════════════════════════════════════════════════════════════════════
    # SEGMENT REMAP
    # ═════════════════════════════════════════════════════════════════════════

    SEGMENT_REMAP = {
        "Large Cap"     : "Large Cap",
        "Conglomerates" : "Large Cap",
        "GLC"           : "Large Cap",
        "FIG"           : "FIG & Sovereign",
        "Sovereign"     : "FIG & Sovereign",
    }

    # ═════════════════════════════════════════════════════════════════════════
    # SEGMENT COLOURS
    # ═════════════════════════════════════════════════════════════════════════

    SEGMENT_COLORS = {
        "RSME"           : {"bg": "#D6EAF8", "text": "#1A5276"},
        "SME+"           : {"bg": "#A9CCE3", "text": "#1A5276"},
        "BB"             : {"bg": "#7FB3D3", "text": "#FFFFFF"},
        "Mid Cap"        : {"bg": "#2E86C1", "text": "#FFFFFF"},
        "Large Cap"      : {"bg": "#1F618D", "text": "#FFFFFF"},
        "FIG & Sovereign": {"bg": "#154360", "text": "#FFFFFF"},
        "GB"             : {"bg": "#154360", "text": "#FFFFFF"},
        "Unknown"        : {"bg": "#C8C8C8", "text": "#555555"},
    }

    # ═════════════════════════════════════════════════════════════════════════
    # FIELD CONFIG
    # ─────────────────────────────────────────────────────────────────────────
    # enabled=True  --> field included in network graph HTML payload AND shown
    #                   in side panel
    # enabled=False --> field excluded from network graph HTML entirely.
    #                   Only appears in Excel report (Recipe 3) and HTML
    #                   report generator (Recipe 4).
    # Use get_graph_fields() to get the set of keys to include in the HTML.
    # ═════════════════════════════════════════════════════════════════════════

    FIELD_CONFIG = {

        # ── internal ────────────────────────────────────────────────────────
        'entity_name'              : {'label': 'Entity Name',                'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'internal'},
        'IS_MAYBANK_CUSTOMER'      : {'label': 'Is Maybank Customer',        'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'internal'},
        'FINAL_CLASSIFICATION'     : {'label': 'Segment',                    'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'internal'},

        # ── overview ─────────────────────────────────────────────────────────
        'CIF_GROUP_NAME'           : {'label': 'Parent Group',               'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'entity_type_description'  : {'label': 'Entity Type',                'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'entity_status_description': {'label': 'Status',                     'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'FIRST_CA_OPN_DTE'         : {'label': 'First CA Opening Date',      'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'overview'},
        'RLTNSHP_TENURE'           : {'label': 'Relationship Tenure (Days)', 'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'overview'},
        'SSIC_CODE'                : {'label': 'SSIC Code',                  'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'MAS610_INDST_DESC'        : {'label': 'Sector',                     'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'BIZ_TYP_DESC'             : {'label': 'Industry',                   'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'source_country'           : {'label': 'Country',                    'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'CNTRY_CODE'               : {'label': 'Country (Old)',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'overview'},
        'EMIS City'                : {'label': 'City',                       'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'postal_code'              : {'label': 'Postal Code',                'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'EMIS Number of Employees' : {'label': 'No. Employees',              'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'EMIS Listed / Unlisted'   : {'label': 'Listed / Unlisted',          'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'EMIS Export'              : {'label': 'Export Countries',           'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'EMIS Incorporation Date'  : {'label': 'Incorporation Date',         'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},
        'EMIS Business Description': {'label': 'Business Description',       'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'overview'},

        # ── facilities: trade summary ────────────────────────────────────────
        'TF_LCY_AVAIL_LMT'  : {'label': 'Available Limit',               'enabled': True,  'trade_only': True,  'cpty': False, 'section': 'facilities'},
        'TF_LCY_AUTH_LMT'   : {'label': 'Authorised Limit',              'enabled': True,  'trade_only': True,  'cpty': False, 'section': 'facilities'},
        'ADT_CREATION_DATE' : {'label': 'Latest AA Creation Date',        'enabled': False, 'trade_only': True,  'cpty': False, 'section': 'facilities'},
        'TF_LCY_TOT_OS'     : {'label': 'On-Balance Sheet Outstanding',  'enabled': True,  'trade_only': True,  'cpty': False, 'section': 'facilities'},
        'TF_LCY_OBS_OS'     : {'label': 'Off-Balance Sheet Outstanding', 'enabled': True,  'trade_only': True,  'cpty': False, 'section': 'facilities'},

        # ── facilities: balance sheet ────────────────────────────────────────
        'CASA'        : {'label': 'Current Account',        'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'facilities'},
        'FD'          : {'label': 'TD',                     'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'facilities'},
        'STRCTD'      : {'label': 'Structured TD',          'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'facilities'},
        'DEP_BALANCES': {'label': 'Total Deposit Balances', 'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'facilities'},  # excluded from HTML: side panel computes CASA+FD+STRCTD client-side; Recipe 3 has its own column list
        'TR_LN'       : {'label': 'Trade Loan',             'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'facilities'},
        'NONTR_LN'    : {'label': 'Non-Trade Loan',         'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'facilities'},
        'LN_BALANCES' : {'label': 'Total Loan Balances',    'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'facilities'},  # excluded from HTML: side panel computes TR_LN+NONTR_LN client-side; Recipe 3 has its own column list

        # ── credit status ────────────────────────────────────────────────────
        'credit_status'        : {'label': 'Credit Status',               'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'impairment_stage'     : {'label': 'Impairment Stage',            'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'RISK_GRADE'           : {'label': 'Risk Grade',                  'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'current_rating'       : {'label': 'Current Rating',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'original_rating'      : {'label': 'Original Rating',             'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'original_rating_date' : {'label': 'Original Rating Date',        'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'is_watchlist'         : {'label': 'Watchlist',                   'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'is_special_mention'   : {'label': 'Special Mention (SMA)',       'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'is_npl'               : {'label': 'NPL',                         'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'months_on_book'       : {'label': 'Months on Book',              'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'facility_risk_rating' : {'label': 'Facility Risk Rating (FRR)',  'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'borrower_risk_rating' : {'label': 'Borrower Risk Rating (BRR)',  'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'rating_date'          : {'label': 'Rating Date',                 'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'latest_dpd_bucket'    : {'label': 'Latest DPD Bucket',           'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},
        'delinquency_count_12m': {'label': 'Delinquency Count (12M)',     'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'creditstatus'},

        # ── ACRA financials ──────────────────────────────────────────────────
        'FIN_FIN_YR_END_CY'   : {'label': 'Financial Year',       'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},
        'FIN_SALES_CY'        : {'label': 'Sales Revenue',        'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},
        'FIN_PROF_BEF_TAX_CY' : {'label': 'PBT',                  'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},
        'FIN_CASH_BANK_BAL_CY': {'label': 'Cash & Bank Balances', 'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},
        'FIN_TRADE_CRED_CY'   : {'label': 'Trade Creditors',      'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},
        'FIN_TRADE_DEPT_CY'   : {'label': 'Trade Debtors',        'enabled': True, 'trade_only': False, 'cpty': False, 'section': 'acrafin'},

        # ── ACRA charges -- enabled=False, excluded from graph HTML entirely ─
        'N_CHARGES'                    : {'label': 'Charge Count',                      'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'N_UNIQUE_CHARGEE'             : {'label': 'Unique Chargee Count',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'EARLIEST_CHARGE_REG_DATE'     : {'label': 'Earliest Charge Reg Date',          'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'LATEST_CHARGE_REG_DATE'       : {'label': 'Latest Charge Reg Date',            'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'CHARGE_SECURED_AMOUNT_SGD'    : {'label': 'Charge Secured Amount (SGD)',       'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'CHARGE_ALLMONIESOWING_Y_COUNT': {'label': 'Charge All Monies Owing Count (Y)', 'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},
        'CHARGE_ALLMONIESOWING_N_COUNT': {'label': 'Charge All Monies Owing Count (N)', 'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'acracharges'},

        # ── EMIS financials (amounts in USD) ─────────────────────────────────
        'EMIS Country'                            : {'label': 'EMIS Country',                         'enabled': False, 'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Company Name'                       : {'label': 'EMIS Company Name',                    'enabled': False, 'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Industry'                           : {'label': 'EMIS Industry',                        'enabled': False, 'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Key Executives'                     : {'label': 'EMIS Key Executives',                  'enabled': False, 'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Total Operating Revenue (USD)'      : {'label': 'Total Operating Revenue (USD)',        'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Operating Profit (USD)'             : {'label': 'Operating Profit (USD)',               'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Profit Before Income Tax (USD)'     : {'label': 'Profit Before Income Tax (USD)',       'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Total Assets (USD)'                 : {'label': 'Total Assets (USD)',                   'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Free Cash Flow (USD)'               : {'label': 'Free Cash Flow (USD)',                 'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Net Cash Flow from Operations (USD)': {'label': 'Net Cash Flow from Operations (USD)',  'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Return on Assets / ROA (%)'         : {'label': 'ROA (%)',                              'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Return on Equity / ROE (%)'         : {'label': 'ROE (%)',                              'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Company ID'                         : {'label': 'EMIS Company ID',                      'enabled': False, 'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Fiscal Year'                        : {'label': 'Fiscal Year',                          'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Audited'                            : {'label': 'Audited',                              'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},
        'EMIS Source'                             : {'label': 'Source',                               'enabled': True,  'trade_only': False, 'cpty': True,  'section': 'emisfin'},

        # ── MFI financials -- only MFI_END_DTE + 7 P&L fields enabled ────────
        # MFI now renders as a third subsection inside the "Financials" accordion
        # (alongside ACRA and EMIS) -- see js_sidepanel.py + js_export.py.
        # Labels have the "MFI " prefix stripped because the parent section
        # header already says "MFI". Other MFI fields kept for Recipe 3/4 use
        # but enabled=False so they don't render in the side panel.
        'MFI_END_DTE'              : {'label': 'Financial Year End',        'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_STATEMENT_TYP'        : {'label': 'Statement Type',            'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_AUDITOR_NAME'         : {'label': 'Auditor',                   'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_QUALIFIED'            : {'label': 'Qualified Opinion',         'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_SALES'                : {'label': 'Sales Revenue',             'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_PNL_BEFORE_TAX'       : {'label': 'Profit Before Tax',         'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_PNL_AFT_TAX'          : {'label': 'Profit After Tax',          'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TOT_AST'              : {'label': 'Total Assets',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_CURR_AST'             : {'label': 'Current Assets',            'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_NON_CURR_AST'         : {'label': 'Non-Current Assets',        'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TOT_LBLTY'            : {'label': 'Total Liabilities',         'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_CURR_LBLTY'           : {'label': 'Current Liabilities',       'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_NON_CURR_LBLTY'       : {'label': 'Non-Current Liabilities',   'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TOT_EQUITY'           : {'label': 'Total Equity',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TOTAL_DEBT'           : {'label': 'Total Debt',                'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_ST_DEBT'              : {'label': 'Short-Term Debt',           'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_LT_DEBT'              : {'label': 'Long-Term Debt',            'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_EBITDA'               : {'label': 'EBITDA',                    'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_GEARING'              : {'label': 'Gearing Ratio',             'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_DCSR'                 : {'label': 'DSCR',                      'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TANGIBLE_NET_WORTH'   : {'label': 'Tangible Net Worth',        'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_ADJ_TNW'              : {'label': 'Adjusted TNW',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_GROSS_PNL'            : {'label': 'Gross Operating P&L',       'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_PRETAX_PNL_BEFORE_INT': {'label': 'Pre-tax P&L Before Int',    'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_COGS'                 : {'label': 'COGS',                      'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_DEBT_SERVICE'         : {'label': 'Debt Service',              'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_TARGET_CURCY_CODE'    : {'label': 'Target Currency',           'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_BASE_CURCY_CODE'      : {'label': 'Base Currency',             'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_MODEL_NAME'           : {'label': 'Model Name',                'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_SEG_DESC'             : {'label': 'Segment',                   'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_LENGTH_IN_MTH'        : {'label': 'Period Length (Months)',     'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_STATEMENT_STS'        : {'label': 'Statement Status',          'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},
        'MFI_PROC_DTE'             : {'label': 'Processing Date',           'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'mfifin'},

        # ── CIP collaterals -- standalone "CIP Collaterals" accordion ────────
        # Labels have the "CIP " prefix stripped because the accordion header
        # already says "CIP".
        'CIP_FAC_LIMIT_SGD'                  : {'label': 'Facility Limit',              'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_LOAN_BALANCE_SGD'               : {'label': 'Loan Balance',                'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_NPL_BALANCE_SGD'                : {'label': 'NPL Balance',                 'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_SEC_AMT'                        : {'label': 'Security Amount',             'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_SEC_EMV'                        : {'label': 'Estimated Market Value',      'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_SEC_FSV'                        : {'label': 'Forced Sale Value',           'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_SEC_FIV'                        : {'label': 'Fire Insurance Value',        'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_N_PROPERTIES'                   : {'label': 'No. Properties',              'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_N_ACC_TOTAL'                    : {'label': 'Total Accounts',              'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_N_ACC_OPEN'                     : {'label': 'Open Accounts',               'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_N_ACC_CLOSED'                   : {'label': 'Closed Accounts',             'enabled': True,  'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_EARLIEST_AC_OPN_DTE'            : {'label': 'Earliest Account Open Date',  'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_LATEST_AC_OPN_DTE'              : {'label': 'Latest Account Open Date',    'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_LATEST_DEFAULT_DTE'             : {'label': 'Latest Default Date',         'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'EARLIEST_OPEN_AC_OPN_DTE'  : {'label': 'Earliest Open Account Date',  'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'LATEST_OPEN_AC_OPN_DTE'    : {'label': 'Latest Open Account Date',    'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'EARLIEST_CLOSED_AC_OPN_DTE': {'label': 'Earliest Closed Account Date','enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'LATEST_AC_CLS_DTE'         : {'label': 'Latest Account Close Date',   'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_JTC_FLAG'                       : {'label': 'JTC Properties Count',        'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT'   : {'label': 'Owner Occupied Properties',   'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_PBD_OCCP_TYPE_TENANTED_COUNT'   : {'label': 'Tenanted Properties',         'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT'     : {'label': 'Business Ops Properties',     'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_PBD_OCCP_TYPE_VACANT_COUNT'     : {'label': 'Vacant Properties',           'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_FAC_PROC_DTE'                   : {'label': 'Facility Processing Date',    'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        'CIP_BALANCE_PROC_DTE'               : {'label': 'Balance Processing Date',     'enabled': False, 'trade_only': False, 'cpty': False, 'section': 'cipinfo'},
        
    }

    # ═════════════════════════════════════════════════════════════════════════
    # GRAPH FIELDS HELPER
    # ─────────────────────────────────────────────────────────────────────────
    # Returns the set of FIELD_CONFIG keys where enabled=True.
    # Used by js_core.py to filter node metadata before embedding in HTML.
    # Fields not in this set are excluded from the graph HTML entirely --
    # they only appear in Excel report (Recipe 3) and HTML report (Recipe 4).
    # ═════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_graph_fields(cls) -> set:
        return {k for k, v in cls.FIELD_CONFIG.items() if v.get('enabled', True)}

    # ═════════════════════════════════════════════════════════════════════════
    # EXCEL HEADER OVERRIDES  (Tier 1 single-source-of-truth)
    # ─────────────────────────────────────────────────────────────────────────
    # FIELD_CONFIG[k]['label'] is the *HTML side-panel* label. The Excel
    # screener (Recipe 3) historically had its own NODE_RENAME with slightly
    # different headers (e.g. trailing "(SGD)" suffix, "ACRA"/"MFI"/"CIP"
    # prefixes). Override here once -- get_excel_rename() falls back to the
    # HTML label when an entry isn't listed.
    #
    # Per-field `enabled_excel` (defaults to True) controls whether a field
    # ships to Excel at all -- set on the FIELD_CONFIG entry itself.
    # ═════════════════════════════════════════════════════════════════════════
    EXCEL_LABEL_OVERRIDES = {
        # ── internal ────────────────────────────────────────────────────────
        'FINAL_CLASSIFICATION'                   : 'Customer Segment',
        # ── overview ────────────────────────────────────────────────────────
        'entity_status_description'              : 'Entity Status',
        'EMIS Fiscal Year'                       : 'EMIS Fiscal Year',
        # ── facilities: trade ───────────────────────────────────────────────
        'TF_LCY_AVAIL_LMT'                       : 'Trade Available Limit (SGD)',
        'TF_LCY_AUTH_LMT'                        : 'Trade Authorised Limit (SGD)',
        'TF_LCY_TOT_OS'                          : 'Trade On-Balance Sheet Outstanding (SGD)',
        'TF_LCY_OBS_OS'                          : 'Trade Off-Balance Sheet Outstanding (SGD)',
        # ── facilities: balance sheet ───────────────────────────────────────
        'CASA'                                   : 'Current Account (SGD)',
        'FD'                                     : 'TD (SGD)',
        'STRCTD'                                 : 'Structured TD (SGD)',
        'DEP_BALANCES'                           : 'Total Deposit Balances (SGD)',
        'TR_LN'                                  : 'Trade Loan (SGD)',
        'NONTR_LN'                               : 'Non-Trade Loan (SGD)',
        'LN_BALANCES'                            : 'Total Loan Balances (SGD)',
        # ── credit status ───────────────────────────────────────────────────
        'is_watchlist'                           : 'Is Watchlist',
        'is_special_mention'                     : 'Is Special Mention (SMA)',
        'is_npl'                                 : 'Is NPL',
        # ── ACRA financials (prefix + SGD suffix) ───────────────────────────
        'FIN_FIN_YR_END_CY'                      : 'ACRA Financial Year End',
        'FIN_SALES_CY'                           : 'ACRA Sales Revenue (SGD)',
        'FIN_PROF_BEF_TAX_CY'                    : 'ACRA Profit Before Tax (SGD)',
        'FIN_CASH_BANK_BAL_CY'                   : 'ACRA Cash & Bank Balance (SGD)',
        'FIN_TRADE_CRED_CY'                      : 'ACRA Trade Creditors (SGD)',
        'FIN_TRADE_DEPT_CY'                      : 'ACRA Trade Debtors (SGD)',
        # ── ACRA charges (slight wording diff) ──────────────────────────────
        'CHARGE_ALLMONIESOWING_Y_COUNT'          : 'Charges - All Monies Owing (Y Count)',
        'CHARGE_ALLMONIESOWING_N_COUNT'          : 'Charges - All Monies Owing (N Count)',
        # ── EMIS percentages (prefix only) ──────────────────────────────────
        'EMIS Return on Assets / ROA (%)'        : 'EMIS ROA (%)',
        'EMIS Return on Equity / ROE (%)'        : 'EMIS ROE (%)',
        'EMIS Audited'                           : 'EMIS Audited',
        'EMIS Source'                            : 'EMIS Source',
        # ── MFI financials (MFI prefix + SGD/Months suffix) ─────────────────
        'MFI_END_DTE'                            : 'MFI Financial Year End',
        'MFI_STATEMENT_TYP'                      : 'MFI Statement Type',
        'MFI_AUDITOR_NAME'                       : 'MFI Auditor',
        'MFI_QUALIFIED'                          : 'MFI Qualified Opinion',
        'MFI_SEG_DESC'                           : 'MFI Segment',
        'MFI_MODEL_NAME'                         : 'MFI Model Name',
        'MFI_TARGET_CURCY_CODE'                  : 'MFI Target Currency',
        'MFI_BASE_CURCY_CODE'                    : 'MFI Base Currency',
        'MFI_LENGTH_IN_MTH'                      : 'MFI Period Length (Months)',
        'MFI_STATEMENT_STS'                      : 'MFI Statement Status',
        'MFI_PROC_DTE'                           : 'MFI Processing Date',
        'MFI_SALES'                              : 'MFI Sales Revenue (SGD)',
        'MFI_COGS'                               : 'MFI COGS (SGD)',
        'MFI_GROSS_PNL'                          : 'MFI Gross Operating P&L (SGD)',
        'MFI_PRETAX_PNL_BEFORE_INT'              : 'MFI Pre-Tax P&L Before Int (SGD)',
        'MFI_PNL_BEFORE_TAX'                     : 'MFI Profit Before Tax (SGD)',
        'MFI_PNL_AFT_TAX'                        : 'MFI Profit After Tax (SGD)',
        'MFI_EBITDA'                             : 'MFI EBITDA (SGD)',
        'MFI_TOT_AST'                            : 'MFI Total Assets (SGD)',
        'MFI_CURR_AST'                           : 'MFI Current Assets (SGD)',
        'MFI_NON_CURR_AST'                       : 'MFI Non-Current Assets (SGD)',
        'MFI_TOT_LBLTY'                          : 'MFI Total Liabilities (SGD)',
        'MFI_CURR_LBLTY'                         : 'MFI Current Liabilities (SGD)',
        'MFI_NON_CURR_LBLTY'                     : 'MFI Non-Current Liabilities (SGD)',
        'MFI_TOT_EQUITY'                         : 'MFI Total Equity (SGD)',
        'MFI_ST_DEBT'                            : 'MFI Short-Term Debt (SGD)',
        'MFI_LT_DEBT'                            : 'MFI Long-Term Debt (SGD)',
        'MFI_TOTAL_DEBT'                         : 'MFI Total Debt (SGD)',
        'MFI_DEBT_SERVICE'                       : 'MFI Debt Service (SGD)',
        'MFI_TANGIBLE_NET_WORTH'                 : 'MFI Tangible Net Worth (SGD)',
        'MFI_ADJ_TNW'                            : 'MFI Adjusted TNW (SGD)',
        'MFI_DCSR'                               : 'MFI DSCR',
        'MFI_GEARING'                            : 'MFI Gearing Ratio',
        # ── CIP collaterals (CIP prefix + SGD for amounts) ──────────────────
        'CIP_FAC_LIMIT_SGD'                      : 'CIP Facility Limit (SGD)',
        'CIP_LOAN_BALANCE_SGD'                   : 'CIP Loan Balance (SGD)',
        'CIP_NPL_BALANCE_SGD'                    : 'CIP NPL Balance (SGD)',
        'CIP_SEC_AMT'                            : 'CIP Security Amount (SGD)',
        'CIP_SEC_EMV'                            : 'CIP Estimated Market Value (SGD)',
        'CIP_SEC_FSV'                            : 'CIP Forced Sale Value (SGD)',
        'CIP_SEC_FIV'                            : 'CIP Fire Insurance Value (SGD)',
        'CIP_N_PROPERTIES'                       : 'CIP No. Properties',
        'CIP_N_ACC_TOTAL'                        : 'CIP Total Accounts',
        'CIP_N_ACC_OPEN'                         : 'CIP Open Accounts',
        'CIP_N_ACC_CLOSED'                       : 'CIP Closed Accounts',
        'CIP_EARLIEST_AC_OPN_DTE'                : 'CIP Earliest Account Open Date',
        'CIP_LATEST_AC_OPN_DTE'                  : 'CIP Latest Account Open Date',
        'CIP_LATEST_DEFAULT_DTE'                 : 'CIP Latest Default Date',
        'EARLIEST_OPEN_AC_OPN_DTE'               : 'CIP Earliest Open Account Date',
        'LATEST_OPEN_AC_OPN_DTE'                 : 'CIP Latest Open Account Date',
        'EARLIEST_CLOSED_AC_OPN_DTE'             : 'CIP Earliest Closed Account Date',
        'LATEST_AC_CLS_DTE'                      : 'CIP Latest Account Close Date',
        'CIP_JTC_FLAG'                           : 'CIP JTC Properties Count',
        'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT'       : 'CIP Owner Occupied Properties',
        'CIP_PBD_OCCP_TYPE_TENANTED_COUNT'       : 'CIP Tenanted Properties',
        'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT'         : 'CIP Business Ops Properties',
        'CIP_PBD_OCCP_TYPE_VACANT_COUNT'         : 'CIP Vacant Properties',
        'CIP_FAC_PROC_DTE'                       : 'CIP Facility Processing Date',
        'CIP_BALANCE_PROC_DTE'                   : 'CIP Balance Processing Date',
    }

    @classmethod
    def field_excel_label(cls, key: str) -> str:
        """Return the Excel header for a FIELD_CONFIG key.
        Falls back to FIELD_CONFIG[k]['label'] when no override is set."""
        cfg = cls.FIELD_CONFIG.get(key)
        if cfg is None:
            return key
        return cls.EXCEL_LABEL_OVERRIDES.get(key, cfg['label'])

    @classmethod
    def get_excel_rename(cls) -> dict:
        """{raw_col: excel_header} for every FIELD_CONFIG entry where
        enabled_excel != False (default True). Used by Recipe 3 to build
        NODE_RENAME — merge with per-source flow-metric renames there."""
        return {
            k: cls.field_excel_label(k)
            for k, v in cls.FIELD_CONFIG.items()
            if v.get('enabled_excel', True)
        }

    @classmethod
    def get_excel_field_keys(cls) -> list:
        """Ordered list of FIELD_CONFIG keys with enabled_excel != False."""
        return [
            k for k, v in cls.FIELD_CONFIG.items()
            if v.get('enabled_excel', True)
        ]

    # ═════════════════════════════════════════════════════════════════════════
    # SYSTEM FIELDS
    # ─────────────────────────────────────────────────────────────────────────
    # Fields always included in graph HTML regardless of FIELD_CONFIG.
    # These are used by graph logic (node colour, shape, labels, side panel
    # identity) and must never be filtered out even if not in FIELD_CONFIG.
    # ═════════════════════════════════════════════════════════════════════════

    SYSTEM_FIELDS = {
        'CIF_NO',
        'source_name',
        'FINAL_CLASSIFICATION',
        'IS_MAYBANK_CUSTOMER',
        'CUST_TYPE',
        'source_country',
        'CIF_ACTIVE_FLAG',
        'entity_name',
        'UEN',
        'node_source',
        'source_rsme',
        'source_tt',
        'source_fitas',
        'source_aa_paper',
        'source_fast',
        'source_giro',
    }

    # ═════════════════════════════════════════════════════════════════════════
    # FACILITY COLUMNS
    # ═════════════════════════════════════════════════════════════════════════

    FAC_COLS = [
        'CIF_NO',
        'N_AA',
        'N_FAC',
        'LATEST_ADT_CREATE_DTE',
        'TF_LCY_AVAIL_LMT',
        'TF_LCY_AUTH_LMT',
        'TF_LCY_TOT_OS',
        'TF_LCY_OBS_OS',
    ]

    FAC_RENAME = {
        'LATEST_ADT_CREATE_DTE': 'ADT_CREATION_DATE',
    }

    # ═════════════════════════════════════════════════════════════════════════
    # CREDIT SUMMARY RENAME MAP
    # ═════════════════════════════════════════════════════════════════════════

    CREDIT_SUMMARY_RENAME = {
        'CR_STS_DESC'          : 'credit_status',
        'STAGE_CLASSIFICATION' : 'impairment_stage',
        'RISK_GRADE'           : 'RISK_GRADE',
        'RATING'               : 'current_rating',
        'ORIGINAL_RATING'      : 'original_rating',
        'ORIGINAL_RATING_DATE' : 'original_rating_date',
        'WATCHLIST_FLG'        : 'is_watchlist',
        'SM_FLG'               : 'is_special_mention',
        'NPL_FLG'              : 'is_npl',
        'MTH_ON_BOOK'          : 'months_on_book',
        'FNL_FRR_RATING'       : 'facility_risk_rating',
        'FNL_BRR_RATING'       : 'borrower_risk_rating',
        'RATING_DTE'           : 'rating_date',
        'LATEST_DPD_MAX_BIN'   : 'latest_dpd_bucket',
        'TOT_DLQ_L12M'         : 'delinquency_count_12m',
    }

    # ═════════════════════════════════════════════════════════════════════════
    # ACRA FINANCIAL COLUMNS
    # ═════════════════════════════════════════════════════════════════════════

    ACRA_FIN_COLS = [
        'CIF_NO',
        'FIN_FIN_YR_END_CY',
        'FIN_SALES_CY',
        'FIN_PROF_BEF_TAX_CY',
        'FIN_CASH_BANK_BAL_CY',
        'FIN_TRADE_CRED_CY',
        'FIN_TRADE_DEPT_CY',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # ACRA CHARGES COLUMNS
    # ═════════════════════════════════════════════════════════════════════════

    ACRA_CHARGES_COLS = [
        'UEN',
        'N_CHARGES',
        'N_UNIQUE_CHARGEE',
        'EARLIEST_CHARGE_REG_DATE',
        'LATEST_CHARGE_REG_DATE',
        'CHARGE_SECURED_AMOUNT_SGD',
        'CHARGE_ALLMONIESOWING_Y_COUNT',
        'CHARGE_ALLMONIESOWING_N_COUNT',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # CIF_SEGM_MSTR ENRICHMENT COLUMNS
    # ═════════════════════════════════════════════════════════════════════════

    CIF_SEGM_MSTR_COLS = [
        'CIF_NO', 'CIF_NAME', 'ID_CODE', 'CNTRY_CODE', 'CIF_ACTIVE_FLAG',
        'SEGMENT', 'TC_DIV', 'TC_SEG',
        'FIRST_CA_OPN_DTE', 'RLTNSHP_TENURE', 'PRI_INDST_CODE', 'CIF_GROUP_NAME',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # EMIS COLUMNS (EMIS_cleaned.csv)
    # ═════════════════════════════════════════════════════════════════════════

    EMIS_COLS = [
        'UEN',
        'UEN_Old',
        'Country',
        'Company',
        'City',
        'Industry (EMIS Industries)',
        'Business Description/Products',
        'Key Executives',
        'Export',
        'Incorporation Date',
        'Number of Employees',
        'Listed/Unlisted',
        'Total Operating Revenue',
        'Operating Profit',
        'Profit before Income Tax',
        'Total Assets',
        'Free Cash Flow',
        'Net Cash Flow from (used in) Operating Activities',
        'Return on Assets (ROA) (%)',
        'Return on Equity (ROE) (%)',
        'Company ID',
        'Fiscal Year',
        'Audited',
        'Source',
    ]

    EMIS_RENAME = {
        'Country'                                           : 'EMIS Country',
        'Company'                                           : 'EMIS Company Name',
        'City'                                              : 'EMIS City',
        'Industry (EMIS Industries)'                        : 'EMIS Industry',
        'Business Description/Products'                     : 'EMIS Business Description',
        'Key Executives'                                    : 'EMIS Key Executives',
        'Export'                                            : 'EMIS Export',
        'Incorporation Date'                                : 'EMIS Incorporation Date',
        'Number of Employees'                               : 'EMIS Number of Employees',
        'Listed/Unlisted'                                   : 'EMIS Listed / Unlisted',
        'Total Operating Revenue'                           : 'EMIS Total Operating Revenue (USD)',
        'Operating Profit'                                  : 'EMIS Operating Profit (USD)',
        'Profit before Income Tax'                          : 'EMIS Profit Before Income Tax (USD)',
        'Total Assets'                                      : 'EMIS Total Assets (USD)',
        'Free Cash Flow'                                    : 'EMIS Free Cash Flow (USD)',
        'Net Cash Flow from (used in) Operating Activities' : 'EMIS Net Cash Flow from Operations (USD)',
        'Return on Assets (ROA) (%)'                        : 'EMIS Return on Assets / ROA (%)',
        'Return on Equity (ROE) (%)'                        : 'EMIS Return on Equity / ROE (%)',
        'Company ID'                                        : 'EMIS Company ID',
        'Fiscal Year'                                       : 'EMIS Fiscal Year',
        'Audited'                                           : 'EMIS Audited',
        'Source'                                            : 'EMIS Source',
    }

    EMIS_NUMERIC_COLS = [
        'EMIS Total Operating Revenue (USD)',
        'EMIS Operating Profit (USD)',
        'EMIS Profit Before Income Tax (USD)',
        'EMIS Total Assets (USD)',
        'EMIS Free Cash Flow (USD)',
        'EMIS Net Cash Flow from Operations (USD)',
        'EMIS Return on Assets / ROA (%)',
        'EMIS Return on Equity / ROE (%)',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # MFI COLUMNS (WY_RTB_MFI_DTL -- latest END_DTE per UEN)
    # *** new | join key is UEN -- direct UEN-to-UEN left join
    # All renamed with MFI_ prefix to avoid collision with other sources
    # ═════════════════════════════════════════════════════════════════════════

    MFI_COLS = [
        'UEN',
        'PROC_DTE',
        'SEG_DESC',
        'MODEL_NAME',
        'TARGET_CURCY_CODE',
        'BASE_CURCY_CODE',
        'END_DTE',
        'LENGTH_IN_MTH',
        'AUDITOR_NAME',
        'QUALIFIED',
        'STATEMENT_STS',
        'STATEMENT_TYP',
        'SALES',
        'COGS',
        'GROSS_OPERATING_PNL',
        'PRETAX_PNL_BEFORE_INT',
        'PNL_BEFORE_TAX',
        'PNL_AFT_TAX_EXTRAORDINARY_ITEM',
        'TOT_AST',
        'CURR_AST',
        'NON_CURR_AST',
        'TOT_LBLTY',
        'CURR_LBLTY',
        'NON_CURR_LBLTY',
        'TOT_EQUITY',
        'ST_DEBT',
        'LT_DEBT',
        'TOTAL_DEBT',
        'DEBT_SERVICE',
        'EBITDA',
        'DCSR',
        'TANGIBLE_NET_WORTH',
        'ADJ_TNW',
        'GEARING',
    ]

    MFI_RENAME = {
        'PROC_DTE'                      : 'MFI_PROC_DTE',
        'SEG_DESC'                      : 'MFI_SEG_DESC',
        'MODEL_NAME'                    : 'MFI_MODEL_NAME',
        'TARGET_CURCY_CODE'             : 'MFI_TARGET_CURCY_CODE',
        'BASE_CURCY_CODE'               : 'MFI_BASE_CURCY_CODE',
        'END_DTE'                       : 'MFI_END_DTE',
        'LENGTH_IN_MTH'                 : 'MFI_LENGTH_IN_MTH',
        'AUDITOR_NAME'                  : 'MFI_AUDITOR_NAME',
        'QUALIFIED'                     : 'MFI_QUALIFIED',
        'STATEMENT_STS'                 : 'MFI_STATEMENT_STS',
        'STATEMENT_TYP'                 : 'MFI_STATEMENT_TYP',
        'SALES'                         : 'MFI_SALES',
        'COGS'                          : 'MFI_COGS',
        'GROSS_OPERATING_PNL'           : 'MFI_GROSS_PNL',
        'PRETAX_PNL_BEFORE_INT'         : 'MFI_PRETAX_PNL_BEFORE_INT',
        'PNL_BEFORE_TAX'                : 'MFI_PNL_BEFORE_TAX',
        'PNL_AFT_TAX_EXTRAORDINARY_ITEM': 'MFI_PNL_AFT_TAX',
        'TOT_AST'                       : 'MFI_TOT_AST',
        'CURR_AST'                      : 'MFI_CURR_AST',
        'NON_CURR_AST'                  : 'MFI_NON_CURR_AST',
        'TOT_LBLTY'                     : 'MFI_TOT_LBLTY',
        'CURR_LBLTY'                    : 'MFI_CURR_LBLTY',
        'NON_CURR_LBLTY'                : 'MFI_NON_CURR_LBLTY',
        'TOT_EQUITY'                    : 'MFI_TOT_EQUITY',
        'ST_DEBT'                       : 'MFI_ST_DEBT',
        'LT_DEBT'                       : 'MFI_LT_DEBT',
        'TOTAL_DEBT'                    : 'MFI_TOTAL_DEBT',
        'DEBT_SERVICE'                  : 'MFI_DEBT_SERVICE',
        'EBITDA'                        : 'MFI_EBITDA',
        'DCSR'                          : 'MFI_DCSR',
        'TANGIBLE_NET_WORTH'            : 'MFI_TANGIBLE_NET_WORTH',
        'ADJ_TNW'                       : 'MFI_ADJ_TNW',
        'GEARING'                       : 'MFI_GEARING',
    }

    MFI_NUMERIC_COLS = [
        'MFI_SALES',
        'MFI_COGS',
        'MFI_GROSS_PNL',
        'MFI_PRETAX_PNL_BEFORE_INT',
        'MFI_PNL_BEFORE_TAX',
        'MFI_PNL_AFT_TAX',
        'MFI_TOT_AST',
        'MFI_CURR_AST',
        'MFI_NON_CURR_AST',
        'MFI_TOT_LBLTY',
        'MFI_CURR_LBLTY',
        'MFI_NON_CURR_LBLTY',
        'MFI_TOT_EQUITY',
        'MFI_ST_DEBT',
        'MFI_LT_DEBT',
        'MFI_TOTAL_DEBT',
        'MFI_DEBT_SERVICE',
        'MFI_EBITDA',
        'MFI_TANGIBLE_NET_WORTH',
        'MFI_ADJ_TNW',
    ]

    MFI_RATIO_COLS = [
        'MFI_DCSR',
        'MFI_GEARING',
    ]

    MFI_DATE_COLS = [
        'MFI_END_DTE',
        'MFI_PROC_DTE',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # CIP COLUMNS (CIP_Collaterals_Info_UEN_Base_df.feather)
    # *** new | join key is ID_CODE (UEN) -- direct UEN-to-UEN left join
    # ═════════════════════════════════════════════════════════════════════════

    CIP_COLS = [
        'ID_CODE',
        'CIP_EARLIEST_AC_OPN_DTE',
        'CIP_LATEST_AC_OPN_DTE',
        'CIP_N_ACC_TOTAL',
        'CIP_N_ACC_OPEN',
        'CIP_N_ACC_CLOSED',
        'CIP_FAC_PROC_DTE',
        'CIP_FAC_LIMIT_SGD',
        'CIP_BALANCE_PROC_DTE',
        'CIP_LOAN_BALANCE_SGD',
        'CIP_LATEST_DEFAULT_DTE',
        'CIP_NPL_BALANCE_SGD',
        'CIP_SEC_AMT',
        'CIP_SEC_EMV',
        'CIP_SEC_FSV',
        'CIP_SEC_FIV',
        'CIP_N_PROPERTIES',
        'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT',
        'CIP_PBD_OCCP_TYPE_TENANTED_COUNT',
        'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT',
        'CIP_PBD_OCCP_TYPE_VACANT_COUNT',
        'CIP_JTC_FLAG',
        'EARLIEST_OPEN_AC_OPN_DTE',
        'LATEST_OPEN_AC_OPN_DTE',
        'EARLIEST_CLOSED_AC_OPN_DTE',
        'LATEST_AC_CLS_DTE',
    ]

    CIP_NUMERIC_COLS = [
        'CIP_FAC_LIMIT_SGD',
        'CIP_LOAN_BALANCE_SGD',
        'CIP_NPL_BALANCE_SGD',
        'CIP_SEC_AMT',
        'CIP_SEC_EMV',
        'CIP_SEC_FSV',
        'CIP_SEC_FIV',
    ]

    CIP_INT_COLS = [
        'CIP_N_ACC_TOTAL',
        'CIP_N_ACC_OPEN',
        'CIP_N_ACC_CLOSED',
        'CIP_N_PROPERTIES',
        'CIP_JTC_FLAG',
        'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT',
        'CIP_PBD_OCCP_TYPE_TENANTED_COUNT',
        'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT',
        'CIP_PBD_OCCP_TYPE_VACANT_COUNT',
    ]

    CIP_DATE_COLS = [
        'CIP_EARLIEST_AC_OPN_DTE',
        'CIP_LATEST_AC_OPN_DTE',
        'CIP_FAC_PROC_DTE',
        'CIP_BALANCE_PROC_DTE',
        'CIP_LATEST_DEFAULT_DTE',
        'EARLIEST_OPEN_AC_OPN_DTE',
        'LATEST_OPEN_AC_OPN_DTE',
        'EARLIEST_CLOSED_AC_OPN_DTE',
        'LATEST_AC_CLS_DTE',
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # BALANCE SHEET COLUMNS
    # ═════════════════════════════════════════════════════════════════════════

    BALANCE_SHEET_COLS = [
        'CIF_NO', 'CASA', 'FD', 'STRCTD', 'DEP_BALANCES',
        'TR_LN', 'NONTR_LN', 'LN_BALANCES',
    ]
