# ── network_graph/pipeline/classifier.py ─────────────────────────────────────
# Derives customer type, segment, and Maybank status for any enriched node table.
# Works on both RSME and TT nodes identically after enrichment.

import pandas as pd
import numpy as np
import math


class Classifier:
    """
    Applies business classification rules to enriched node dataframes.
    Produces: CUST_TYPE, FINAL_CLASSIFICATION, IS_MAYBANK_CUSTOMER
    """

    def __init__(self, config):
        self.config = config

    def classify(self, df: pd.DataFrame,
                 cif_col: str = 'CIF_NO',
                 has_trade_fac_col: str = '_has_trade_fac') -> pd.DataFrame:
        """
        Apply all classification derivations to an enriched node dataframe.

        Parameters
        ----------
        df                : enriched node dataframe
        cif_col           : name of the CIF number column
        has_trade_fac_col : name of the boolean trade facility flag column

        Returns
        -------
        Dataframe with CUST_TYPE, IS_MAYBANK_CUSTOMER,
        RFS_CLASSIFICATION, FINAL_CLASSIFICATION added.
        """
        df = df.copy()

        # FIX: vectorised derivations replace four df.apply() calls.
        # Reduces ~4 * N Python function calls to pandas C-level operations.

        # ── CIF validity mask ──────────────────────────────────────────────
        cif_valid = (
            df[cif_col].notna() &
            ~df[cif_col].astype(str).str.strip().isin(['', 'nan'])
        )

        # ── CIF_ACTIVE_FLAG numeric mask (handles non-numeric strings) ─────
        cif_flag_numeric = pd.to_numeric(
            df['CIF_ACTIVE_FLAG'] if 'CIF_ACTIVE_FLAG' in df.columns
            else pd.Series(np.nan, index=df.index),
            errors='coerce'
        )
        is_active = cif_flag_numeric == 1

        # ── IS_MAYBANK_CUSTOMER ────────────────────────────────────────────
        df['IS_MAYBANK_CUSTOMER'] = (cif_valid & is_active).astype(int)

        # ── RFS_CLASSIFICATION (vectorised) ───────────────────────────────
        tc_div = df['TC_DIV'].astype(str).str.strip() if 'TC_DIV' in df.columns \
                 else pd.Series('', index=df.index)
        tc_seg = df['TC_SEG'].astype(str).str.strip() if 'TC_SEG' in df.columns \
                 else pd.Series('', index=df.index)

        rfs_mask = tc_div == 'RFS'
        rfs_class = pd.Series('Unknown', index=df.index)
        rfs_class = rfs_class.where(~(rfs_mask & tc_seg.isin(['CMG', 'PRIVATE WEALTH'])), 'BB')
        rfs_class = rfs_class.where(~(rfs_mask & tc_seg.isin(['RFS OTHER', 'RSME'])), 'RSME')
        rfs_class = rfs_class.where(~(rfs_mask & (tc_seg == 'SME+')), 'SME+')
        df['RFS_CLASSIFICATION'] = rfs_class

        # ── FINAL_CLASSIFICATION ───────────────────────────────────────────
        # FIX: apply SEGMENT_REMAP so "Conglomerates"/"GLC" etc. map to
        # "Large Cap" and get the correct badge colour in the side panel.
        # Previously remap_segment() was defined but never called here.
        seg_raw = df['SEGMENT'].astype(str).str.strip() if 'SEGMENT' in df.columns \
                  else pd.Series('', index=df.index)
        # *** fix | exclude '<NA>' (pandas NA stringified) and 'NaN'/'None'
        # as well. Previously only 'nan' was filtered; pd.NA values would
        # leak through as the literal string '<NA>'.
        seg_valid_mask = (
            df['SEGMENT'].notna() &
            (seg_raw != '') &
            (~seg_raw.str.lower().isin(['nan', '<na>', 'none', 'null']))
        ) if 'SEGMENT' in df.columns else pd.Series(False, index=df.index)

        # Apply remap where segment is valid, fallback to RFS_CLASSIFICATION
        df['FINAL_CLASSIFICATION'] = df['RFS_CLASSIFICATION'].copy()
        if seg_valid_mask.any():
            remapped = seg_raw[seg_valid_mask].map(
                lambda v: self.config.SEGMENT_REMAP.get(v, v)
            )
            df.loc[seg_valid_mask, 'FINAL_CLASSIFICATION'] = remapped

        # ── CUST_TYPE ──────────────────────────────────────────────────────
        is_maybank   = cif_valid & is_active
        has_trade    = df[has_trade_fac_col].fillna(False).astype(bool) \
                       if has_trade_fac_col in df.columns \
                       else pd.Series(False, index=df.index)

        df['CUST_TYPE'] = 'Non-Maybank Customer'
        df.loc[is_maybank & ~has_trade, 'CUST_TYPE'] = 'Maybank Non-Trade Customer'
        df.loc[is_maybank &  has_trade, 'CUST_TYPE'] = 'Maybank Trade Customer'

        # Remove the internal flag column
        df = df.drop(columns=[has_trade_fac_col], errors='ignore')

        return df

    def remap_segment(self, val) -> str:
        """
        Apply SEGMENT_REMAP to a raw segment value.
        Returns 'Unknown' for empty/null values.
        """
        if not val or isinstance(val, float) or str(val).strip() == '':
            return 'Unknown'
        return self.config.SEGMENT_REMAP.get(str(val).strip(), str(val).strip())

    @staticmethod
    def safe_cif_flag(val):
        """
        Clean CIF_ACTIVE_FLAG to int safely.
        None = unknown, 0 = inactive (ex-Maybank), 1 = active Maybank.
        Used for single-value cleaning outside of classify().
        """
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    # ── Private classification logic ──────────────────────────────────────────
    # Kept for reference and single-row use cases (e.g. unit testing).
    # classify() now uses vectorised equivalents for performance.

    @staticmethod
    def _derive_is_maybank(cif_no, cif_active_flag) -> int:
        """1 if the customer has an active Maybank CIF, else 0."""
        in_cif = pd.notna(cif_no) and str(cif_no).strip() not in ('', 'nan')
        try:
            is_active = pd.notna(cif_active_flag) and float(cif_active_flag) == 1
        except (TypeError, ValueError):
            is_active = False
        return 1 if (in_cif and is_active) else 0

    @staticmethod
    def _derive_rfs_classification(tc_div, tc_seg) -> str:
        """Derive segment from TC_DIV and TC_SEG for RFS customers."""
        tc_div = str(tc_div).strip() if pd.notna(tc_div) else ''
        tc_seg = str(tc_seg).strip() if pd.notna(tc_seg) else ''
        if tc_div == 'RFS' and tc_seg in ('CMG', 'PRIVATE WEALTH'): return 'BB'
        if tc_div == 'RFS' and tc_seg in ('RFS OTHER', 'RSME'):     return 'RSME'
        if tc_div == 'RFS' and tc_seg == 'SME+':                    return 'SME+'
        return 'Unknown'

    @staticmethod
    def _derive_final_classification(segment, rfs_classification) -> str:
        """Use SEGMENT if available, else fall back to RFS_CLASSIFICATION."""
        if pd.notna(segment) and str(segment).strip() and str(segment).strip() != 'nan':
            return str(segment).strip()
        return rfs_classification

    @staticmethod
    def _derive_cust_type(cif_no, cif_active_flag, has_trade_fac) -> str:
        """Three-way classification: Trade / Non-Trade / Non-Maybank."""
        in_cif = pd.notna(cif_no) and str(cif_no).strip() not in ('', 'nan')
        try:
            is_active = pd.notna(cif_active_flag) and float(cif_active_flag) == 1
        except (TypeError, ValueError):
            is_active = False
        is_maybank = in_cif and is_active
        if is_maybank and has_trade_fac:       return 'Maybank Trade Customer'
        elif is_maybank and not has_trade_fac: return 'Maybank Non-Trade Customer'
        else:                                  return 'Non-Maybank Customer'
