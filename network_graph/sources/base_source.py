# ── network_graph/sources/base_source.py ─────────────────────────────────────
# Abstract base class that every data source must implement.
#
# To add a new data source:
#   1. Create a new file e.g. guarantee_source.py
#   2. Subclass BaseSource
#   3. Implement load(), get_nodes(), get_edges()

from abc import ABC, abstractmethod
import io
import pandas as pd


class BaseSource(ABC):
    """
    Standard interface for all data sources.

    Every source must produce:
    - A node table with at minimum: UEN, CIF_NO, source
    - An edge table with at minimum: SOURCE_UEN, TARGET_UEN, edge_source
    """

    # Canonical "this is not a real ID" set. Hoisted from per-file _INVALID_IDS
    # constants in every source/pipeline module. Use via BaseSource.INVALID_IDS
    # (or import the package-level alias from `network_graph`).
    INVALID_IDS = frozenset({'', 'nan', 'none', 'None', 'NaN', 'NAN'})

    def __init__(self, config, main_folder, acra_folder=None):
        self.config      = config
        self.main_folder = main_folder
        self.acra_folder = acra_folder

    @abstractmethod
    def load(self) -> 'BaseSource':
        """Load raw data. Must return self to allow chaining."""
        pass

    @abstractmethod
    def get_nodes(self) -> pd.DataFrame:
        """
        Returns standardised node table with at minimum:
        UEN, CIF_NO, source, source_name, source_country
        """
        pass

    @abstractmethod
    def get_edges(self) -> pd.DataFrame:
        """
        Returns standardised edge table with at minimum:
        SOURCE_UEN, TARGET_UEN, edge_source, txn_count, txn_amt
        """
        pass

    def _compute_positions(self):
        """
        No-op. Node positions are computed at search time by
        layoutRadialTree() in js_search.js -- pre-computing them
        in Python serves no purpose.
        Subclasses should not override this.
        """
        self.positions = {}

    def _load_file(self, folder, filename: str, **kwargs) -> pd.DataFrame:
        """Generic file loader: CSV, Excel, Feather."""
        ext = filename.split('.')[-1].lower()
        with folder.get_download_stream(filename) as f:
            if ext == 'csv':
                return pd.read_csv(f, **kwargs)
            elif ext in ('xlsx', 'xls'):
                return pd.read_excel(io.BytesIO(f.read()), **kwargs)
            elif ext == 'feather':
                return pd.read_feather(io.BytesIO(f.read()), **kwargs)
            else:
                raise ValueError(f"Unsupported file extension: {ext}")

    @staticmethod
    def _clean_id(series: pd.Series) -> pd.Series:
        """
        Strip whitespace and remove HTML entities from ID columns.

        *** fix | when an ID column comes in as numeric (int64/float64),
        plain `astype(str)` produces "12345" for ints but "12345.0" for
        floats -- breaking joins against string-typed UEN columns elsewhere.
        Coerce floats to int representation when the value is whole, and
        keep the rest as plain strings.
        """
        if pd.api.types.is_float_dtype(series):
            # Whole-number floats -> ints; NaN -> '' (downstream filters drop)
            cleaned = series.where(
                series.isna(),
                series.fillna(0).astype('Int64')
            ).astype(str).str.replace('<NA>', '', regex=False)
        else:
            cleaned = series.astype(str)
        return (
            cleaned
            .str.strip()
            .str.replace('&#8206;', '', regex=False)
        )
