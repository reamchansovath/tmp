# ── network_graph/sources/rsme_source.py ─────────────────────────────────────
# Handles loading and cleaning of RSME Buyer/Supplier (LC/BG) data.
# Nodes: BOR_INFO (borrowers/buyers) + DTL (counterparties/suppliers)
# Edges: CHK_DTL joined to BOR and DTL -- one edge per BOR/SUP pair

import pandas as pd
from .base_source import BaseSource


class RSMESource(BaseSource):
    """
    RSME Buyer/Supplier data source.
    Produces nodes from BOR_INFO and DTL,
    and edges from CHK_DTL joining them together.
    """

    def __init__(self, config, rsme_harm_folder, main_folder):
        """
        Parameters
        ----------
        config           : NetworkGraphConfig instance
        rsme_harm_folder : Dataiku Folder object for RSME harmonized data
        main_folder      : Dataiku Folder object for FOLDER_MAIN (CHK_DTL)
        """
        super().__init__(config, main_folder=main_folder)
        self.rsme_harm_folder = rsme_harm_folder

        self.bor_info_df    = None
        self.chk_dtl_df     = None
        self.dtl_updated_df = None

    def load(self) -> 'RSMESource':
        """Load all RSME files from harmonized folder + main folder."""
        cfg = self.config

        self.bor_info_df    = self._load_file(self.rsme_harm_folder, cfg.RSME_FILES['bor_info'])
        self.dtl_updated_df = self._load_file(self.rsme_harm_folder, cfg.RSME_FILES['dtl'])
        self.chk_dtl_df     = self._load_file(self.main_folder,      cfg.FILES['chk_dtl'])

        self._clean_ids()
        print(f"RSMESource loaded: "
              f"BOR={len(self.bor_info_df):,}  "
              f"DTL={len(self.dtl_updated_df):,}  "
              f"CHK={len(self.chk_dtl_df):,}")
        return self

    def _clean_ids(self):
        """Clean key ID columns -- strip whitespace and HTML entities."""
        self.bor_info_df['BOR_ID_NUM']         = self._clean_id(self.bor_info_df['BOR_ID_NUM'])
        self.bor_info_df['BOR_CIF_NUM']        = self._clean_id(self.bor_info_df['BOR_CIF_NUM'])
        self.bor_info_df['ADT_APP_ID']         = self._clean_id(self.bor_info_df['ADT_APP_ID'])
        self.dtl_updated_df['SUP_BYR_ID_NUM']  = self._clean_id(self.dtl_updated_df['SUP_BYR_ID_NUM'])
        self.dtl_updated_df['SUP_BYR_CHK_ID']  = self._clean_id(self.dtl_updated_df['SUP_BYR_CHK_ID'])
        self.dtl_updated_df['CIF_NO']           = self._clean_id(self.dtl_updated_df['CIF_NO'])
        self.chk_dtl_df['ADT_APP_ID']           = self._clean_id(self.chk_dtl_df['ADT_APP_ID'])
        self.chk_dtl_df['SUP_BYR_CHK_ID']       = self._clean_id(self.chk_dtl_df['SUP_BYR_CHK_ID'])

    def get_nodes(self) -> pd.DataFrame:
        """
        Returns all unique nodes from BOR and DTL combined.
        BOR nodes: buyers/borrowers. DTL nodes: suppliers/counterparties.
        BOR takes priority for shared UENs.
        """
        bor_nodes = (
            self.bor_info_df[['BOR_ID_NUM', 'BOR_CIF_NUM', 'CIF_NAME', 'CNTRY_CODE']]
            .drop_duplicates(subset='BOR_ID_NUM')
            .rename(columns={
                'BOR_ID_NUM'  : 'UEN',
                'BOR_CIF_NUM' : 'CIF_NO',
                'CIF_NAME'    : 'source_name',
                'CNTRY_CODE'  : 'source_country',
            })
            .assign(source='RSME_BOR')
        )

        dtl_nodes = (
            self.dtl_updated_df[['SUP_BYR_ID_NUM', 'CIF_NO', 'SUP_BYR_NAME', 'CNTRY_CODE']]
            .drop_duplicates(subset='SUP_BYR_ID_NUM')
            .rename(columns={
                'SUP_BYR_ID_NUM' : 'UEN',
                'SUP_BYR_NAME'   : 'source_name',
                'CNTRY_CODE'     : 'source_country',
            })
            .assign(source='RSME_DTL')
        )

        # BOR takes priority (placed last so keep='last' selects it)
        all_nodes = pd.concat([dtl_nodes, bor_nodes], ignore_index=True)
        all_nodes = all_nodes.drop_duplicates(subset='UEN', keep='last')
        all_nodes['CIF_NO']         = self._clean_id(all_nodes['CIF_NO'])
        all_nodes['source_name']    = all_nodes['source_name'].fillna('')
        all_nodes['source_country'] = all_nodes['source_country'].fillna('')

        print(f"RSMESource nodes: BOR={len(bor_nodes):,}  DTL={len(dtl_nodes):,}  "
              f"combined unique={len(all_nodes):,}")
        return all_nodes

    def get_edges(self) -> pd.DataFrame:
        """
        Returns all RSME edges by joining CHK_DTL -> DTL -> BOR.
        One row per unique BOR/SUP pair.
        No transaction metadata -- RSME represents relationship existence only.
        """
        edges_raw = (
            self.chk_dtl_df
            .merge(self.dtl_updated_df, on='SUP_BYR_CHK_ID', how='left')
            .merge(self.bor_info_df,    on='ADT_APP_ID',      how='left')
        )

        edges = (
            edges_raw
            .dropna(subset=['SUP_BYR_ID_NUM', 'BOR_ID_NUM'])
            .drop_duplicates(subset=['BOR_ID_NUM', 'SUP_BYR_ID_NUM'], keep='first')
            .rename(columns={
                'BOR_ID_NUM'     : 'SOURCE_UEN',
                'SUP_BYR_ID_NUM' : 'TARGET_UEN',
            })
            [['SOURCE_UEN', 'TARGET_UEN']]
            .assign(
                edge_source = 'RSME',
                txn_count   = None,
                txn_amt     = None,
            )
            .reset_index(drop=True)
        )

        print(f"RSMESource edges: {len(edges):,} unique BOR/SUP pairs")
        return edges
