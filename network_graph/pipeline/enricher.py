# ── network_graph/pipeline/enricher.py ───────────────────────────────────────
# Generic enrichment pipeline applied to ALL node tables regardless of source.
# Joins: CIF segm mstr, credit summary, ACRA financial, ACRA entity, SSIC lookup,
#        facility summary, balance sheet, EMIS financials, ACRA charges,
#        MFI financials, CIP collaterals.
#
# To add a new enrichment source:
#   1. Add a _load_* method
#   2. Call it in load_reference_data()
#   3. Add the merge step in enrich()

import pandas as pd
import numpy as np
import math
import io


class Enricher:
    """
    Applies standard enrichment joins to any node dataframe.
    Expects nodes to have at minimum: UEN, CIF_NO, source
    """

    # ── Column type sets used by JSPayloadBuilder._clean_meta ────────────────
    # Add new columns to the appropriate set when extending FIELD_CONFIG.

    AMT_COLS = {
        'TF_LCY_AVAIL_LMT', 'TF_LCY_AUTH_LMT',
        'TF_LCY_TOT_OS', 'TF_LCY_OBS_OS',
        'FIN_SALES_CY', 'FIN_PROF_BEF_TAX_CY', 'FIN_CASH_BANK_BAL_CY',
        'FIN_TRADE_CRED_CY', 'FIN_TRADE_DEPT_CY',
        # Balance sheet
        'CASA', 'FD', 'STRCTD', 'DEP_BALANCES', 'TR_LN', 'NONTR_LN', 'LN_BALANCES',
        # EMIS USD amount cols
        'EMIS Total Operating Revenue (USD)',
        'EMIS Operating Profit (USD)',
        'EMIS Profit Before Income Tax (USD)',
        'EMIS Total Assets (USD)',
        'EMIS Free Cash Flow (USD)',
        'EMIS Net Cash Flow from Operations (USD)',
        # ACRA charges amount
        'CHARGE_SECURED_AMOUNT_SGD',
        # *** new | MFI financial amounts (SGD)
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
        # *** new | CIP financial amounts (SGD)
        'CIP_FAC_LIMIT_SGD',
        'CIP_LOAN_BALANCE_SGD',
        'CIP_NPL_BALANCE_SGD',
        'CIP_SEC_AMT',
        'CIP_SEC_EMV',
        'CIP_SEC_FSV',
        'CIP_SEC_FIV',
    }

    INT_COLS = {
        'months_on_book', 'delinquency_count_12m',
        'borrower_risk_rating', 'RLTNSHP_TENURE',
        # ACRA charges counts
        'N_CHARGES', 'N_UNIQUE_CHARGEE',
        'CHARGE_ALLMONIESOWING_Y_COUNT', 'CHARGE_ALLMONIESOWING_N_COUNT',
        # *** new | MFI period length
        'MFI_LENGTH_IN_MTH',
        # *** new | CIP integer counts
        'CIP_N_ACC_TOTAL',
        'CIP_N_ACC_OPEN',
        'CIP_N_ACC_CLOSED',
        'CIP_N_PROPERTIES',
        'CIP_JTC_FLAG',
        'CIP_PBD_OCCP_TYPE_OWNOCCPD_COUNT',
        'CIP_PBD_OCCP_TYPE_TENANTED_COUNT',
        'CIP_PBD_OCCP_TYPE_BIZOPS_COUNT',
        'CIP_PBD_OCCP_TYPE_VACANT_COUNT',
    }

    STRING_COLS = {
        'latest_dpd_bucket', 'credit_status', 'impairment_stage', 'RISK_GRADE',
        'current_rating', 'original_rating', 'FINAL_CLASSIFICATION',
        'CNTRY_CODE', 'MAS610_INDST_DESC', 'BIZ_TYP_DESC',
        'facility_risk_rating', 'entity_type_description',
        'entity_status_description', 'entity_name',
        # EMIS string cols
        'EMIS Country', 'EMIS Company Name', 'EMIS City', 'EMIS Industry',
        'EMIS Business Description', 'EMIS Key Executives', 'EMIS Export',
        'EMIS Incorporation Date', 'EMIS Number of Employees',
        'EMIS Listed / Unlisted', 'EMIS Company ID',
        'EMIS Fiscal Year', 'EMIS Audited', 'EMIS Source',
        # CIF group
        'CIF_GROUP_NAME',
        # *** new | MFI string cols
        'MFI_SEG_DESC',
        'MFI_MODEL_NAME',
        'MFI_TARGET_CURCY_CODE',
        'MFI_BASE_CURCY_CODE',
        'MFI_AUDITOR_NAME',
        'MFI_QUALIFIED',
        'MFI_STATEMENT_STS',
        'MFI_STATEMENT_TYP',
    }

    FLAG_COLS = {
        'IS_MAYBANK_CUSTOMER', 'is_watchlist', 'is_special_mention', 'is_npl',
    }

    DATE_COLS = {
        'original_rating_date', 'rating_date', 'ADT_CREATION_DATE',
        'FIN_FIN_YR_END_CY', 'FIRST_CA_OPN_DTE',
        # ACRA charges dates
        'EARLIEST_CHARGE_REG_DATE', 'LATEST_CHARGE_REG_DATE',
        # *** new | MFI dates
        'MFI_END_DTE',
        'MFI_PROC_DTE',
        # *** new | CIP dates
        'CIP_EARLIEST_AC_OPN_DTE',
        'CIP_LATEST_AC_OPN_DTE',
        'CIP_FAC_PROC_DTE',
        'CIP_BALANCE_PROC_DTE',
        'CIP_LATEST_DEFAULT_DTE',
        'EARLIEST_OPEN_AC_OPN_DTE',
        'LATEST_OPEN_AC_OPN_DTE',
        'EARLIEST_CLOSED_AC_OPN_DTE',
        'LATEST_AC_CLS_DTE',
    }

    def __init__(self, config, enrichment_folder, acra_folder, emis_folder,
                 main_folder, acra_charges_folder=None, cip_folder=None):
        self.config                = config
        self.enrichment_folder     = enrichment_folder
        self.acra_folder           = acra_folder
        self.emis_folder           = emis_folder
        self.main_folder           = main_folder
        # optional -- gracefully skipped if not provided
        self.acra_charges_folder   = acra_charges_folder
        # *** new | optional CIP collaterals folder
        self.cip_folder            = cip_folder

        self._cif_segm_mstr       = None
        self._credit_clean        = None
        self._acra_fin_clean      = None
        self._acra_df             = None
        self._ssic_lookup         = None
        self._fac_clean           = None
        self._fac_cif_set         = None
        self._emis_new_map        = None
        self._emis_old_map        = None
        self._emis_patch_cols     = None
        self._balance_sheet_clean = None
        self._acra_charges_clean  = None
        # *** new | MFI and CIP reference tables
        self._mfi_clean           = None
        self._cip_clean           = None

    def load_reference_data(self) -> 'Enricher':
        """
        Load all reference tables used for enrichment.
        Call this once before running enrich().
        """
        self._load_cif_segm_mstr()
        self._load_credit()
        self._load_acra_fin()
        self._load_acra_entity()
        self._load_ssic()
        self._load_fac()
        self._load_emis()
        self._load_balance_sheet()
        self._load_acra_charges()
        # *** new | MFI and CIP
        self._load_mfi()
        self._load_cip()
        print("Enricher: all reference data loaded.")
        return self

    def _load_file(self, folder, filename: str, **kwargs) -> pd.DataFrame:
        """Generic file loader supporting CSV, Excel, Feather, and zipped CSV."""
        ext = filename.split('.')[-1].lower()
        with folder.get_download_stream(filename) as f:
            if ext == 'csv':
                return pd.read_csv(f, **kwargs)
            elif ext in ('xlsx', 'xls'):
                return pd.read_excel(io.BytesIO(f.read()), **kwargs)
            elif ext == 'feather':
                return pd.read_feather(io.BytesIO(f.read()), **kwargs)
            elif ext == 'zip':
                import zipfile
                with zipfile.ZipFile(io.BytesIO(f.read())) as z:
                    csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
                    with z.open(csv_name) as csv_f:
                        return pd.read_csv(csv_f, **kwargs)
            else:
                raise ValueError(
                    f"Unsupported file extension '{ext}' for file: {filename}"
                )

    def _load_cif_segm_mstr(self):
        """Load and clean the CIF segment master reference table."""
        cfg  = self.config
        df   = self._load_file(self.enrichment_folder, cfg.ENRICHMENT_FILES['cif_segm_mstr'])
        cols = [c for c in cfg.CIF_SEGM_MSTR_COLS if c in df.columns]
        self._cif_segm_mstr = (
            df[cols]
            .assign(CIF_NO=lambda x: x['CIF_NO'].astype(str).str.strip())
            .drop_duplicates(subset='CIF_NO', keep='first')
        )
        print(f"  cif_segm_mstr: {len(self._cif_segm_mstr):,} rows")

    def _load_credit(self):
        """Load and clean the credit summary reference table."""
        cfg    = self.config
        df     = self._load_file(self.enrichment_folder, cfg.ENRICHMENT_FILES['credit_summary'])
        rename = cfg.CREDIT_SUMMARY_RENAME
        cols   = ['CIF_NO'] + [c for c in rename if c in df.columns]
        self._credit_clean = (
            df[cols]
            .rename(columns=rename)
            .drop_duplicates(subset='CIF_NO', keep='first')
            .assign(CIF_NO=lambda x: x['CIF_NO'].astype(str).str.strip())
        )
        print(f"  credit_clean: {len(self._credit_clean):,} rows")

    def _load_acra_fin(self):
        """Load and clean the ACRA financial statements reference table."""
        cfg  = self.config
        df   = self._load_file(self.enrichment_folder, cfg.ENRICHMENT_FILES['acra_fin'])
        cols = [c for c in cfg.ACRA_FIN_COLS if c in df.columns]
        self._acra_fin_clean = (
            df[cols]
            .assign(CIF_NO=lambda x: x['CIF_NO'].astype(str).str.strip())
            .drop_duplicates(subset='CIF_NO', keep='first')
        )
        print(f"  acra_fin_clean: {len(self._acra_fin_clean):,} rows")

    def _load_acra_entity(self):
        """Load the ACRA entity info (entity name, type, status, postal code, SSIC)."""
        self._acra_df = self._load_file(self.acra_folder, self.config.FILE_ACRA)
        self._acra_df['postal_code'] = (
            self._acra_df['postal_code'].astype(str).str.zfill(6)
        )
        print(f"  acra_df: {len(self._acra_df):,} rows")

    def _load_ssic(self):
        """Load the SSIC business type master for sector/industry lookup."""
        cfg = self.config
        df  = self._load_file(self.main_folder, cfg.FILES['biz_typ'])
        df['BIZ_TYP_CODE'] = (
            pd.to_numeric(df['BIZ_TYP_CODE'], errors='coerce')
            .astype('Int64').astype(str).str.zfill(5)
            .replace('<NA>', pd.NA)
        )
        self._ssic_lookup = (
            df[['BIZ_TYP_CODE', 'MAS610_INDST_DESC', 'BIZ_TYP_DESC']]
            .dropna(subset=['BIZ_TYP_CODE'])
            .drop_duplicates(subset='BIZ_TYP_CODE', keep='first')
        )
        print(f"  ssic_lookup: {len(self._ssic_lookup):,} rows")

    def _load_fac(self):
        """Load and clean the facility summary reference table."""
        cfg = self.config
        df  = self._load_file(self.enrichment_folder, cfg.ENRICHMENT_FILES['fac_summary'])
        df['CIF_NO'] = df['CIF_NO'].astype(str).str.strip()
        cols = [c for c in cfg.FAC_COLS if c in df.columns]
        self._fac_clean = (
            df[cols]
            .rename(columns=cfg.FAC_RENAME)
            .drop_duplicates(subset='CIF_NO', keep='first')
        )
        self._fac_cif_set = set(self._fac_clean['CIF_NO'].unique())
        print(f"  fac_clean: {len(self._fac_clean):,} rows")

    def _load_emis(self):
        """
        Load and clean EMIS_cleaned.csv financial data.

        Two lookup maps for maximum coverage across SG and MY entities:
        - _emis_new_map : keyed by new UEN format
        - _emis_old_map : keyed by UEN_Old (old UEN format, MY entities)

        No scaling -- amounts are already in absolute USD values.
        Numeric cols cast using config.EMIS_NUMERIC_COLS.
        Latest fiscal year per UEN kept.
        """
        cfg = self.config
        df  = self._load_file(
            self.emis_folder, cfg.EMIS_FILE,
            dtype=str, keep_default_na=False, na_values=['', ' ']
        )

        cols_to_read = [c for c in cfg.EMIS_COLS if c in df.columns]
        df = df[cols_to_read].copy()

        rename = {k: v for k, v in cfg.EMIS_RENAME.items() if k in df.columns}
        df = df.rename(columns=rename)

        for col in cfg.EMIS_NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'EMIS Fiscal Year' in df.columns:
            df = df.sort_values('EMIS Fiscal Year', ascending=False, na_position='last')

        join_keys = {'UEN', 'UEN_Old'}
        self._emis_patch_cols = [c for c in df.columns if c not in join_keys]

        if 'UEN' in df.columns:
            df['UEN'] = df['UEN'].astype(str).str.strip()
            self._emis_new_map = (
                df.dropna(subset=['UEN'])
                .drop_duplicates(subset=['UEN'], keep='first')
                .set_index('UEN')
                [self._emis_patch_cols]
            )
        else:
            self._emis_new_map = pd.DataFrame(columns=self._emis_patch_cols)

        if 'UEN_Old' in df.columns:
            df['UEN_Old'] = df['UEN_Old'].astype(str).str.strip()
            self._emis_old_map = (
                df.dropna(subset=['UEN_Old'])
                .drop_duplicates(subset=['UEN_Old'], keep='first')
                .set_index('UEN_Old')
                [self._emis_patch_cols]
            )
        else:
            self._emis_old_map = pd.DataFrame(columns=self._emis_patch_cols)

        print(f"  emis new UEN map: {len(self._emis_new_map):,} entries")
        print(f"  emis old UEN map: {len(self._emis_old_map):,} entries")
        print(f"  emis patch cols:  {len(self._emis_patch_cols)}")

    def _load_balance_sheet(self):
        """Load and clean the customer balance sheet reference table."""
        cfg  = self.config
        df   = self._load_file(
            self.enrichment_folder, cfg.ENRICHMENT_FILES['balance_sheet']
        )
        cols = [c for c in cfg.BALANCE_SHEET_COLS if c in df.columns]
        self._balance_sheet_clean = (
            df[cols]
            .assign(CIF_NO=lambda x: x['CIF_NO'].astype(str).str.strip())
            .drop_duplicates(subset='CIF_NO', keep='first')
        )
        print(f"  balance_sheet_clean: {len(self._balance_sheet_clean):,} rows")

    def _load_acra_charges(self):
        """
        Load ACRA charges processed data.
        Join key is UEN (not CIF_NO) -- direct UEN-to-UEN left join.
        Gracefully skipped if acra_charges_folder not provided.
        """
        if self.acra_charges_folder is None:
            print("  acra_charges: folder not provided -- skipped")
            return

        cfg  = self.config
        cols = cfg.ACRA_CHARGES_COLS

        df = self._load_file(self.acra_charges_folder, cfg.ACRA_CHARGES_FILE)

        cols_present = [c for c in cols if c in df.columns]
        missing_cols = set(cols) - set(cols_present)
        if missing_cols:
            print(f"  acra_charges: missing columns {missing_cols} -- will be null")

        df = df[cols_present].copy()
        df['UEN'] = df['UEN'].astype(str).str.strip().str.upper()

        for col in ('N_CHARGES', 'N_UNIQUE_CHARGEE',
                    'CHARGE_ALLMONIESOWING_Y_COUNT', 'CHARGE_ALLMONIESOWING_N_COUNT'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'CHARGE_SECURED_AMOUNT_SGD' in df.columns:
            df['CHARGE_SECURED_AMOUNT_SGD'] = pd.to_numeric(
                df['CHARGE_SECURED_AMOUNT_SGD'], errors='coerce'
            )

        for col in ('EARLIEST_CHARGE_REG_DATE', 'LATEST_CHARGE_REG_DATE'):
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].where(
                    df[col].str.match(r'^\d{4}-\d{2}-\d{2}$', na=False),
                    other=None
                )

        self._acra_charges_clean = (
            df.drop_duplicates(subset='UEN', keep='first')
        )
        print(f"  acra_charges_clean: {len(self._acra_charges_clean):,} rows")

    def _load_mfi(self):
        """
        *** new | Load MFI financial statements data.

        Source: WY_RTB_MFI_DTL.csv from FOLDER_ENRICHMENT (LU4uOH1G).
        Dedup: sort by UEN + END_DTE descending, keep latest row per UEN.
        Join key: UEN -- direct UEN-to-UEN left join.
        All columns renamed with MFI_ prefix to avoid collision.
        Applies to ALL nodes (SG + MY).
        Gracefully skipped if 'mfi' key not in ENRICHMENT_FILES.
        """
        cfg = self.config

        if 'mfi' not in cfg.ENRICHMENT_FILES:
            print("  mfi: not configured in ENRICHMENT_FILES -- skipped")
            return

        try:
            df = self._load_file(
                self.enrichment_folder,
                cfg.ENRICHMENT_FILES['mfi'],
                dtype=str,
                keep_default_na=False,
                na_values=['', ' '],
            )
        except Exception as e:
            print(f"  mfi: failed to load -- {e} -- skipped")
            return

        # Normalise UEN
        if 'UEN' not in df.columns:
            print("  mfi: UEN column not found -- skipped")
            return

        df['UEN'] = df['UEN'].astype(str).str.strip().str.upper()

        # Keep only expected columns that exist
        cols_to_keep = ['UEN'] + [
            c for c in cfg.MFI_COLS if c != 'UEN' and c in df.columns
        ]
        missing_mfi = set(cfg.MFI_COLS) - set(df.columns)
        if missing_mfi:
            print(f"  mfi: missing columns {missing_mfi} -- will be null")
        df = df[cols_to_keep].copy()

        # Parse END_DTE for accurate dedup sorting
        if 'END_DTE' in df.columns:
            df['_END_DTE_DT'] = pd.to_datetime(
                df['END_DTE'],
                format='%d%b%Y:%H:%M:%S',
                errors='coerce'
            )
            df = (
                df.sort_values(
                    by=['UEN', '_END_DTE_DT'],
                    ascending=[True, False],
                    na_position='last'
                )
                .drop_duplicates(subset='UEN', keep='first')
                .drop(columns=['_END_DTE_DT'])
            )
        else:
            df = df.drop_duplicates(subset='UEN', keep='first')

        # Numeric casts
        for col in cfg.MFI_NUMERIC_COLS:
            raw_col = {v: k for k, v in cfg.MFI_RENAME.items()}.get(col, col)
            if raw_col in df.columns:
                df[raw_col] = pd.to_numeric(df[raw_col], errors='coerce')

        # Ratio cols (float, not rounded)
        for col in cfg.MFI_RATIO_COLS:
            raw_col = {v: k for k, v in cfg.MFI_RENAME.items()}.get(col, col)
            if raw_col in df.columns:
                df[raw_col] = pd.to_numeric(df[raw_col], errors='coerce')

        # Rename all columns using MFI_RENAME (excludes UEN)
        rename = {k: v for k, v in cfg.MFI_RENAME.items() if k in df.columns}
        df = df.rename(columns=rename)

        self._mfi_clean = df.set_index('UEN')
        print(f"  mfi_clean: {len(self._mfi_clean):,} rows  "
              f"({len(self._mfi_clean.columns)} cols after rename)")

    def _load_cip(self):
        """
        *** new | Load CIP collaterals UEN-level aggregated data.

        Source: CIP_Collaterals_Info_UEN_Base_df.feather from FOLDER_CIP (pD0HDxZR).
        Join key: ID_CODE (UEN) -- direct UEN-to-UEN left join.
        Applies to ALL nodes (SG + MY).
        Gracefully skipped if cip_folder not provided.
        """
        if self.cip_folder is None:
            print("  cip: folder not provided -- skipped")
            return

        cfg = self.config

        try:
            df = self._load_file(self.cip_folder, cfg.CIP_FILE)
        except Exception as e:
            print(f"  cip: failed to load -- {e} -- skipped")
            return

        if 'ID_CODE' not in df.columns:
            print("  cip: ID_CODE column not found -- skipped")
            return

        # Normalise join key
        df['ID_CODE'] = df['ID_CODE'].astype(str).str.strip().str.upper()

        # Keep only expected columns that exist
        cols_to_keep = ['ID_CODE'] + [
            c for c in cfg.CIP_COLS if c != 'ID_CODE' and c in df.columns
        ]
        missing_cip = set(cfg.CIP_COLS) - set(df.columns)
        if missing_cip:
            print(f"  cip: missing columns {missing_cip} -- will be null")
        df = df[cols_to_keep].copy()

        # Numeric casts
        for col in cfg.CIP_NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        for col in cfg.CIP_INT_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Date cols -- parse to datetime then store as string YYYY-MM-DD
        # clean_date() will handle display formatting
        for col in cfg.CIP_DATE_COLS:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors='coerce')
                df[col] = parsed.dt.strftime('%Y-%m-%d').where(parsed.notna(), other=None)

        self._cip_clean = (
            df.drop_duplicates(subset='ID_CODE', keep='first')
            .set_index('ID_CODE')
        )
        print(f"  cip_clean: {len(self._cip_clean):,} rows  "
              f"({len(self._cip_clean.columns)} cols)")

    @staticmethod
    def _pad_ssic(series: pd.Series) -> pd.Series:
        """Zero-pad numeric SSIC codes to 5 digits."""
        numeric    = pd.to_numeric(series, errors='coerce')
        valid_mask = numeric.notna()
        result     = pd.Series(pd.NA, index=series.index, dtype=object)
        result[valid_mask] = (
            numeric[valid_mask].astype(int).astype(str).str.zfill(5)
        )
        return result

    def enrich(self, nodes_df: pd.DataFrame,
               uen_col: str = 'UEN',
               cif_col: str = 'CIF_NO') -> pd.DataFrame:
        """
        Enrichment pipeline for all nodes.

        SG-specific enrichment (ACRA entity, ACRA financials, credit, SSIC,
        facilities, balance sheet) only applied where source_country == 'SG'.

        Applied to ALL nodes (SG + MY):
        - EMIS financials
        - ACRA charges (UEN join)
        - MFI financials (UEN join)
        - CIP collaterals (UEN join)
        """
        df = nodes_df.copy()
        df[cif_col] = df[cif_col].astype(str).str.strip()

        # ── Step 1: CIF_SEGM_MSTR enrichment (primary: CIF, fallback: UEN) ──
        df = df.merge(
            self._cif_segm_mstr, left_on=cif_col, right_on='CIF_NO',
            how='left', suffixes=('', '_segm')
        )
        df = df.drop(columns=[c for c in df.columns if c.endswith('_segm')])

        missing = (
            df['CIF_ACTIVE_FLAG'].isna()
            if 'CIF_ACTIVE_FLAG' in df.columns
            else pd.Series(True, index=df.index)
        )
        if missing.any():
            uen_lookup = self._cif_segm_mstr.rename(
                columns={c: c + '_uen'
                         for c in self._cif_segm_mstr.columns if c != 'ID_CODE'}
            )
            df = df.merge(uen_lookup, left_on=uen_col, right_on='ID_CODE', how='left')
            for col in self._cif_segm_mstr.columns:
                if col == 'ID_CODE':
                    continue
                uen_col_name = col + '_uen'
                if uen_col_name in df.columns:
                    df[col] = df[col].combine_first(df[uen_col_name])
                    df = df.drop(columns=[uen_col_name])

        # ── Split SG vs non-SG ────────────────────────────────────────────────
        sg_mask = (df['source_country'] == 'SG') if 'source_country' in df.columns \
                  else pd.Series(False, index=df.index)
        df_sg     = df[sg_mask].copy()
        df_non_sg = df[~sg_mask].copy()

        # ── Step 2: Credit summary (SG only) ──────────────────────────────────
        if len(df_sg) > 0:
            df_sg = df_sg.merge(
                self._credit_clean, left_on=cif_col, right_on='CIF_NO',
                how='left', suffixes=('', '_credit')
            )
            df_sg = df_sg.drop(
                columns=[c for c in df_sg.columns if c.endswith('_credit')]
            )

        # ── Step 3: ACRA financial (SG only) ──────────────────────────────────
        if len(df_sg) > 0:
            df_sg = df_sg.merge(
                self._acra_fin_clean, left_on=cif_col, right_on='CIF_NO',
                how='left', suffixes=('', '_acrafin')
            )
            df_sg = df_sg.drop(
                columns=[c for c in df_sg.columns if c.endswith('_acrafin')]
            )

        # ── Step 4: ACRA entity (SG only) ─────────────────────────────────────
        if len(df_sg) > 0:
            df_sg = df_sg.merge(
                self._acra_df[[
                    'uen', 'entity_name', 'entity_type_description',
                    'entity_status_description', 'postal_code', 'primary_ssic_code'
                ]],
                left_on=uen_col, right_on='uen', how='left'
            )
            df_sg = df_sg.drop(columns=['uen'], errors='ignore')

        # ── Entity name fallback chain (SG only) ──────────────────────────────
        if len(df_sg) > 0:
            for src_col in ('matched_name', 'SUP_BYR_NAME', 'CIF_NAME'):
                if src_col in df_sg.columns:
                    df_sg['entity_name'] = df_sg['entity_name'].combine_first(
                        df_sg[src_col].replace('', pd.NA)
                    )

        # ── Step 5: SSIC lookup (SG only) ─────────────────────────────────────
        if len(df_sg) > 0:
            df_sg['primary_ssic_code'] = self._pad_ssic(df_sg['primary_ssic_code'])
            df_sg = df_sg.rename(columns={'primary_ssic_code': 'SSIC_CODE'})
            df_sg = df_sg.merge(
                self._ssic_lookup,
                left_on='SSIC_CODE', right_on='BIZ_TYP_CODE', how='left'
            )
            df_sg = df_sg.drop(columns=['BIZ_TYP_CODE'], errors='ignore')

        # ── Step 6: Facility summary (SG only) ────────────────────────────────
        if len(df_sg) > 0:
            df_sg = df_sg.merge(
                self._fac_clean, left_on=cif_col, right_on='CIF_NO',
                how='left', suffixes=('', '_fac')
            )
            df_sg = df_sg.drop(
                columns=[c for c in df_sg.columns if c.endswith('_fac')]
            )

        # ── Step 6b: Balance sheet (SG only) ──────────────────────────────────
        if len(df_sg) > 0:
            df_sg = df_sg.merge(
                self._balance_sheet_clean, left_on=cif_col, right_on='CIF_NO',
                how='left', suffixes=('', '_bs')
            )
            df_sg = df_sg.drop(
                columns=[c for c in df_sg.columns if c.endswith('_bs')]
            )

        # ── Merge SG and non-SG back together ─────────────────────────────────
        df = pd.concat([df_sg, df_non_sg], ignore_index=True)

        df['_has_trade_fac'] = df[cif_col].isin(self._fac_cif_set)

        # ── Step 7: EMIS financial data (ALL nodes -- SG + MY) ────────────────
        if self._emis_patch_cols:
            df = df.merge(
                self._emis_new_map,
                left_on=uen_col, right_index=True,
                how='left', suffixes=('', '_emis')
            )
            df = df.drop(
                columns=[c for c in df.columns if c.endswith('_emis')],
                errors='ignore'
            )

            first_emis_col = self._emis_patch_cols[0]
            still_missing  = df[first_emis_col].isna()
            n_missing      = still_missing.sum()

            if n_missing > 0 and len(self._emis_old_map) > 0:
                df_filled = (
                    df.loc[still_missing, [uen_col]]
                    .merge(
                        self._emis_old_map,
                        left_on=uen_col, right_index=True,
                        how='left'
                    )
                )
                df.loc[still_missing, self._emis_patch_cols] = (
                    df_filled[self._emis_patch_cols].values
                )
                n_filled = df.loc[still_missing, first_emis_col].notna().sum()
                print(f"  EMIS pass 1 (new UEN):  {len(df) - n_missing:,} filled")
                print(f"  EMIS pass 2 (UEN_Old):  {n_filled:,} / {n_missing:,} filled")
            else:
                print(f"  EMIS pass 1 (new UEN):  {df[first_emis_col].notna().sum():,} filled")

        # ── Step 8: ACRA charges (ALL nodes -- UEN join) ──────────────────────
        if self._acra_charges_clean is not None:
            charge_cols = [c for c in self.config.ACRA_CHARGES_COLS if c != 'UEN']
            df = df.merge(
                self._acra_charges_clean[['UEN'] + charge_cols],
                left_on=uen_col, right_on='UEN',
                how='left', suffixes=('', '_charges')
            )
            df = df.drop(
                columns=['UEN_charges'] +
                        [c for c in df.columns if c.endswith('_charges')],
                errors='ignore'
            )
            n_matched = df['N_CHARGES'].notna().sum()
            print(f"  acra_charges: {n_matched:,} / {len(df):,} nodes matched")
        else:
            print("  acra_charges: not loaded -- skipped")

        # ── Step 9: MFI financials (ALL nodes -- UEN join) ────────────────────
        if self._mfi_clean is not None:
            mfi_cols = list(self._mfi_clean.columns)
            df = df.merge(
                self._mfi_clean[mfi_cols],
                left_on=uen_col, right_index=True,
                how='left', suffixes=('', '_mfi')
            )
            df = df.drop(
                columns=[c for c in df.columns if c.endswith('_mfi')],
                errors='ignore'
            )
            n_mfi = df['MFI_SALES'].notna().sum() if 'MFI_SALES' in df.columns else 0
            print(f"  mfi: {n_mfi:,} / {len(df):,} nodes matched")
        else:
            print("  mfi: not loaded -- skipped")

        # ── Step 10: CIP collaterals (ALL nodes -- UEN join via ID_CODE) ───────
        if self._cip_clean is not None:
            cip_cols = list(self._cip_clean.columns)
            df = df.merge(
                self._cip_clean[cip_cols],
                left_on=uen_col, right_index=True,
                how='left', suffixes=('', '_cip')
            )
            df = df.drop(
                columns=[c for c in df.columns if c.endswith('_cip')],
                errors='ignore'
            )
            n_cip = df['CIP_LOAN_BALANCE_SGD'].notna().sum() \
                    if 'CIP_LOAN_BALANCE_SGD' in df.columns else 0
            print(f"  cip: {n_cip:,} / {len(df):,} nodes matched")
        else:
            print("  cip: not loaded -- skipped")

        # Remove any duplicate columns from merge residue
        df = df.loc[:, ~df.columns.duplicated(keep='first')]

        return df

    # ── Value cleaning methods -- used by JSPayloadBuilder._clean_meta ────────

    @staticmethod
    def clean_postal(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        s = str(val).strip().split('.')[0]
        return s.zfill(6) if s and s not in ('nan', 'None', '') else None

    @staticmethod
    def clean_ssic(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        s = str(val).strip().split('.')[0]
        if not s or s in ('nan', 'None', ''): return None
        return s.zfill(5) if s.isdigit() else s

    @staticmethod
    def clean_amt(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        try:    return int(round(float(val)))
        except: return None

    @staticmethod
    def clean_int(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        try:    return int(val)
        except: return None

    @staticmethod
    def clean_flag(val):
        if val is None or val is pd.NA: return 0
        if isinstance(val, float) and math.isnan(val): return 0
        if isinstance(val, bool): return int(val)
        if isinstance(val, (int, float)): return 1 if val else 0
        return 1 if str(val).strip().upper() in ('1', 'Y', 'YES', 'TRUE') else 0

    @staticmethod
    def clean_date(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        try:
            if pd.isna(val): return None
        except (TypeError, ValueError):
            pass

        if hasattr(val, 'strftime'):
            return val.strftime('%d %b %Y')

        s = str(val).strip()
        if not s or s in ('nan', 'None', 'NaT', ''):
            return None

        # Format 1: SAS datetime  02NOV2004:00:00:00
        if ':' in s and len(s) > 9:
            try:
                return pd.to_datetime(
                    s.split(':')[0].strip(), format='%d%b%Y'
                ).strftime('%d %b %Y')
            except Exception:
                pass

        # Format 2: ISO with timezone  2025-03-20T10:48:31.000000+0000
        if 'T' in s:
            try:
                return pd.to_datetime(s).strftime('%d %b %Y')
            except Exception:
                pass

        # Format 3: Simple SAS date  28FEB2026
        if len(s) == 9 and s[2:5].isalpha():
            try:
                return pd.to_datetime(s, format='%d%b%Y').strftime('%d %b %Y')
            except Exception:
                pass

        # Format 4: DD/MM/YYYY
        if '/' in s:
            try:
                return pd.to_datetime(s, format='%d/%m/%Y').strftime('%d %b %Y')
            except Exception:
                pass

        # Format 5: YYYY-MM-DD (covers ACRA charges and CIP date format)
        if '-' in s:
            try:
                return pd.to_datetime(s).strftime('%d %b %Y')
            except Exception:
                pass

        try:
            return pd.to_datetime(s).strftime('%d %b %Y')
        except Exception:
            return s

    @staticmethod
    def clean_string(val):
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        s = str(val).strip()
        return s if s and s not in ('nan', 'None', 'NaT') else None

    @staticmethod
    def clean_year(val):
        """Convert fiscal year to string without decimals (2025.0 -> '2025')."""
        if val is None or val is pd.NA: return None
        if isinstance(val, float) and math.isnan(val): return None
        try:    return str(int(float(val)))
        except: return None
