# ── network_graph/__init__.py ─────────────────────────────────────────────────
from .config                    import NetworkGraphConfig
from .sources.base_source       import BaseSource
from .sources.rsme_source       import RSMESource
from .sources.consol_tt_source  import ConsolTTSource
from .sources.fitas_source      import FITASSource
from .sources.aa_paper_source   import AAPaperSource
from .sources.fast_giro_source  import FastGiroSource
from .pipeline.enricher         import Enricher
from .pipeline.classifier       import Classifier
from .viz.config                import VizConfig
from .viz.js_payloads           import JSPayloadBuilder
from .viz.builder               import HTMLBuilder
from .exporters                 import DatasetExporter

# Package-level alias so callers can do `from network_graph import INVALID_IDS`.
INVALID_IDS = BaseSource.INVALID_IDS
