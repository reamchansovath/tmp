# ── network_graph/viz/js_payloads.py ─────────────────────────────────────────
# Serialises all Python data into JSON payloads ready for injection into JS.
# Handles type cleaning, null stripping, and safe JSON encoding.

import json
import re
import math
import pandas as pd
from ..pipeline.enricher import Enricher


class JSPayloadBuilder:
    """
    Builds and serialises all JS data payloads from Python objects.

    Primary public interface:
    - safe_json(obj)             : JSON-encodes any object safely for <script> embedding
    - build_node_meta(df, types) : builds cleaned nodeMetaMap dict for JS side panel
    """

    def __init__(self, config):
        self.config = config

    @staticmethod
    def safe_json(obj) -> str:
        """
        JSON-encode an object safe for embedding in a <script> tag.
        - Strips ASCII control characters that survive json.dumps
        - Escapes </ to prevent script tag injection
        - Forces ASCII encoding to avoid Unicode JS line terminators (U+2028/U+2029)
        - Handles pd.NA and numpy scalars defensively
        """
        def _clean(o):
            # FIX: handle pd.NA before any other check to avoid TypeError
            if o is pd.NA:
                return None
            if isinstance(o, str):
                return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', o)
            elif isinstance(o, dict):
                return {_clean(k): _clean(v) for k, v in o.items()}
            elif isinstance(o, list):
                return [_clean(i) for i in o]
            elif hasattr(o, 'item'):
                # numpy scalar (int64, float64 etc) -- convert to Python native
                return o.item()
            return o

        return (
            json.dumps(_clean(obj), ensure_ascii=True)
            .replace('</', '<\\/')
        )

    def build_node_meta(self, enriched_nodes_df: pd.DataFrame,
                        node_type_dict: dict) -> dict:
        """
        Build node metadata dict with field-type-aware cleaning.

        Only fields in FIELD_CONFIG or the explicit keep set are included
        to avoid bloating the HTML payload with internal pipeline columns.

        Parameters
        ----------
        enriched_nodes_df : enriched and classified node dataframe with UEN index
        node_type_dict    : {uen: customer_type}

        Returns
        -------
        dict : {uen: {field: cleaned_value}}
        """
        node_meta_raw = enriched_nodes_df.set_index('UEN').to_dict('index')

        result = {}
        for nid, meta in node_meta_raw.items():
            node_type = node_type_dict.get(nid, 'Non-Maybank Customer')
            cleaned   = self._clean_meta(nid, meta, node_type)

            # FIX: guard pd.isna() with try/except -- it raises ValueError on
            # array-like values (e.g. lists), and TypeError on some custom types
            final = {}
            for k, v in cleaned.items():
                try:
                    is_null = (v is pd.NA) or pd.isna(v)
                except (TypeError, ValueError):
                    is_null = False
                final[k] = None if is_null else v

            if final:
                result[nid] = final

        return result

    def _clean_meta(self, nid: str, meta: dict, node_type: str) -> dict:
        """
        Apply field-type-aware cleaning to metadata fields.

        Only processes fields in FIELD_CONFIG or the explicit keep set,
        skipping internal pipeline columns that would bloat the HTML payload.

        New EMIS columns:
        - SGD amount cols (e.g. 'EMIS Total Operating Revenue (SGD)') are in
          Enricher.AMT_COLS -- handled by clean_amt(), no x1M scaling needed
          (new EMIS_cleaned.csv amounts are already in absolute SGD)
        - % cols (e.g. 'EMIS Return on Assets / ROA (%)') fall through to
          plain value passthrough -- rendered as float by fmtVal() in JS
        - String/text cols are in Enricher.STRING_COLS -- handled by clean_string()

        Old emis_* special cases (x1M scaling, emis_fiscal_year) removed --
        those column names no longer exist after migration to EMIS_cleaned.csv.
        """
        AMT_COLS    = Enricher.AMT_COLS
        INT_COLS    = Enricher.INT_COLS
        FLAG_COLS   = Enricher.FLAG_COLS
        DATE_COLS   = Enricher.DATE_COLS
        STRING_COLS = Enricher.STRING_COLS

        # Columns needed by JS side panel beyond FIELD_CONFIG
        KEEP_COLS = (
            set(self.config.FIELD_CONFIG.keys()) | {
                'source_name', 'source_country', 'CIF_NO',
                'CUST_TYPE', 'FINAL_CLASSIFICATION',
                'IS_MAYBANK_CUSTOMER', 'CIF_ACTIVE_FLAG',
                'postal_code', 'SSIC_CODE',
            }
        )

        cleaned = {}

        for k, val in meta.items():

            # Skip internal pipeline columns not needed by JS
            if k not in KEEP_COLS:
                continue

            # Null checks -- handle both float NaN and pd.NA
            if isinstance(val, float) and math.isnan(val):
                cleaned[k] = None
                continue
            if val is pd.NA:
                cleaned[k] = None
                continue

            # Field-type-aware cleaning
            if k == 'postal_code':
                cleaned[k] = Enricher.clean_postal(val)
            elif k == 'SSIC_CODE':
                cleaned[k] = Enricher.clean_ssic(val)
            elif k == 'TOTAL_TRADE_FAC_OUTSTD_BALANCE':
                # Legacy column -- abs() applied since stored as negative
                v = Enricher.clean_amt(val)
                cleaned[k] = abs(v) if v is not None else None
            elif k in AMT_COLS:
                # Covers all SGD amount cols including new EMIS * (SGD) cols.
                # No x1M scaling -- new EMIS data is already in absolute SGD.
                cleaned[k] = Enricher.clean_amt(val)
            elif k in INT_COLS:
                cleaned[k] = Enricher.clean_int(val)
            elif k in FLAG_COLS:
                cleaned[k] = Enricher.clean_flag(val)
            elif k in DATE_COLS:
                cleaned[k] = Enricher.clean_date(val)
            elif k in STRING_COLS:
                cleaned[k] = Enricher.clean_string(val)
            else:
                # Passthrough -- includes EMIS % cols (ROA, ROE) which are
                # already cast to float in enricher._load_emis() and
                # rendered by fmtVal() in JS without special formatting
                cleaned[k] = None if val is None else val

        return cleaned
