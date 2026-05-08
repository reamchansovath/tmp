# ── network_graph/exporters.py ────────────────────────────────────────────────
# Exports all pipeline outputs to Dataiku datasets and folders.
# Add new export targets here when new datasets are needed.
#
# Usage in Recipe 1:
#   exporter = DatasetExporter(cfg)
#   exporter.export_datasets(df_subnetwork_summary, df_node_info, df_edges_info)
#
# Usage in Recipe 2 (single file):
#   exporter.export_html(html_str)
#   exporter.export_minify_html(html_str)
#
# Usage in Recipe 2 (multiple files with custom names):
#   exporter.export_html(html_str, filename='MEXT_NETWORK_full.html')
#   exporter.export_minify_html(html_str, filename='MEXT_NETWORK_full_minified.html')

import numpy as np
import pandas as pd
import dataiku
import minify_html


class DatasetExporter:
    """
    Writes pipeline outputs to Dataiku datasets and folders.
    Centralises all export logic so recipes stay clean.
    """

    def __init__(self, config):
        self.config = config

    def export_all(self,
                   df_subnetwork_summary: pd.DataFrame,
                   df_node_info: pd.DataFrame,
                   df_edges_info: pd.DataFrame,
                   html_str: str):
        """Export all outputs in one call."""
        self.export_datasets(df_subnetwork_summary, df_node_info, df_edges_info)
        self.export_html(html_str)
        self.export_minify_html(html_str)

    def export_datasets(self,
                        df_subnetwork_summary: pd.DataFrame,
                        df_node_info: pd.DataFrame,
                        df_edges_info: pd.DataFrame):
        """Export the three output datasets to Dataiku."""
        self._export_dataset(df_subnetwork_summary, self.config.DATASET_SUBNETWORK_SUMMARY)
        self._export_dataset(df_node_info,          self.config.DATASET_NODE_INFO)
        self._export_dataset(df_edges_info,         self.config.DATASET_EDGE_INFO)

    def export_html(self, html_str: str, filename: str = None) -> None:
        """
        Upload HTML to FOLDER_VIZ.
        filename defaults to config.OUTPUT_HTML if not provided.
        """
        target = filename if filename is not None else self.config.OUTPUT_HTML
        self._export_html(html_str, target)

    def export_minify_html(self, html_str: str, filename: str = None) -> None:
        """
        Minify and upload HTML to FOLDER_VIZ.
        filename defaults to config.OUTPUT_HTML_MINIFY if not provided.
        """
        target = filename if filename is not None else self.config.OUTPUT_HTML_MINIFY
        self._export_minify_html(html_str, target)

    # ── Private methods ───────────────────────────────────────────────────

    def _export_dataset(self, df: pd.DataFrame, dataset_name: str):
        """Write a dataframe to a Dataiku dataset with schema inference."""
        df = self._clean_for_export(df)
        ds = dataiku.Dataset(dataset_name)
        ds.write_with_schema(df)
        print(f"Exported {dataset_name}: {len(df):,} rows  {df.shape[1]} cols")

    def _export_html(self, html_str: str, target: str) -> None:
        """Upload the HTML file to FOLDER_VIZ under target filename."""
        folder = dataiku.Folder(self.config.FOLDER_VIZ)
        folder.upload_stream(target, html_str.encode('utf-8'))
        print(f"Uploaded {target}: {len(html_str)/1024/1024:.2f} MB")

    def _export_minify_html(self, html_str: str, target: str) -> None:
        """Minify and upload the HTML file to FOLDER_VIZ under target filename.

        NOTE: minify_js is intentionally OFF. The minify-js engine inside
        minify_html converts single-quoted JS strings to template literals
        and corrupts backslash escapes in the process -- specifically, it
        rewrites '<\/title>' (one backslash, evaluates to </title>) as
        `<\\/title>` (two backslashes, evaluates to <\/title> with a literal
        backslash). That broken evaluation cascades into buildExportHTML and
        produces export files with literal \n and <\/tag> bytes everywhere.
        HTML and CSS minification are kept on -- they save most of the size
        and don't have this hazard.
        """
        minified = minify_html.minify(
            html_str,
            minify_js=False,
            minify_css=True,
            keep_closing_tags=True,
        )
        folder = dataiku.Folder(self.config.FOLDER_VIZ)
        folder.upload_stream(target, minified.encode('utf-8'))
        print(f"Uploaded {target}: {len(minified)/1024/1024:.2f} MB  "
              f"(saved {(len(html_str) - len(minified))/1024/1024:.2f} MB)")

    @staticmethod
    def _clean_for_export(df: pd.DataFrame) -> pd.DataFrame:
        """
        Replace NaN/Inf with None across all columns.
        Required before writing to Dataiku datasets.

        FIX: original only cleaned float-dtype columns, missing:
        - numpy float32/float64 (dtype is np.float64, not Python float)
        - object-dtype columns containing Python float NaN values
        - pd.NA in nullable integer/boolean columns

        Uses vectorised pandas replace + where for all dtypes at once.
        """
        df = df.copy()

        # Step 1: replace inf/-inf with NaN across all numeric columns
        df = df.replace([np.inf, -np.inf], np.nan)

        # Step 2: replace NaN/pd.NA with None (Python None serialises
        # correctly to Dataiku's null representation)
        df = df.where(pd.notna(df), other=None)

        return df
