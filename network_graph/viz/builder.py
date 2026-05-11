# ── network_graph/viz/builder.py ──────────────────────────────────────────────
# HTML Builder - Generates complete visualization HTML without PyVis.
# Builds pure HTML with empty vis.js canvas and embedded JavaScript.
# No neighbor cache -- in-browser BFS from adjacency maps handles all searches.
#
# UEN COMPRESSION (Option A):
# All internal data structures use short string IDs ("1", "2", ...) instead of
# raw UEN strings ("202012345C"). A single _UtoI/_ItoU map in JS handles
# encode/decode at the boundary. External API (search, URL, localStorage,
# selectedIds) always uses real UEN strings -- encoding happens once at
# renderSearch entry, decoding happens only when displaying to user.
#
# Compression helpers live in compression.py (not here) to avoid circular
# import: builder.py -> js_core.py -> builder.py

import re
import math
import datetime
from .js_payloads  import JSPayloadBuilder
from .html_styles  import get_toolbar_html
from .js_core      import get_js_core
from .js_filters   import get_js_filters
from .js_search    import get_js_search
from .js_sidepanel import get_js_sidepanel
from .js_network   import get_js_network
from .js_history   import get_js_history
from .js_reset     import get_js_reset
from .js_init      import get_js_init
from .js_export    import get_js_export
from .compression  import (
    build_uen_mapping, validate_compression,
    c_key, c_key_listval, c_list,
    c_edges_from_to, c_selfloop_edges,
)


class HTMLBuilder:
    """
    Builds complete HTML visualization without PyVis dependency.

    Architecture:
    - NO PyVis, NO NetworkX, NO neighbor cache
    - Physics permanently disabled -- layoutRadialTree handles positioning
    - Render-time edge classification (driven by pairRelationshipMap built
      in js_core.py from relationship_df):
        * RSME-only  : pair appears in RSME AND NOT in payment/FITAS/AA.
                       Rendered green, straight, NO arrow.
                       (`ro` flag; see js_core.py rsme_only logic.)
        * both-ways  : `is_both=True` from RelationshipBuilder.
                       Blue, straight, arrows on both ends. (`ib` flag.)
        * directed   : everything else (FITAS, AA Paper, Payment combined =
                       TT+FAST+GIRO, or any mix). Blue, straight, single
                       arrow at "to". Per-source TT / FITAS directed sets
                       are also produced for the side-panel breakdowns.
        * self-loop  : All-Txn (Payment combined + FITAS) self-transfers,
                       with per-source FITAS / Payment / TT lookup maps
                       for the side panel.
    - The build-time `undirected_edges_df` is a pair-symmetric aggregation
      table (keyed by frozenset({src, tgt})), NOT the set of rendered
      undirected edges -- that distinction is decided later by the
      RSME-only flag in pairRelationshipMap.
    - UEN compression  : internal data uses short string IDs, external API
                         always uses real UEN strings
    """

    def __init__(self, config, viz_config):
        self.config          = config
        self.viz_config      = viz_config
        self.payload_builder = JSPayloadBuilder(config)

    def build(self,
              rsme_adjacency,
              rsme_degree_map,
              original_sizes_js,
              node_type_js,
              node_meta_js,
              id_name_lookup_js,
              original_labels_js,
              rsme_source,
              consol_tt_source,
              fitas_source,
              aa_paper_source,
              fast_source,
              giro_source,
              consol_tt_node_summary_js,
              fitas_node_summary_js,
              fast_node_summary_js,
              giro_node_summary_js,
              payment_node_summary_js,
              all_txn_node_summary_js,
              consol_tt_metric_ranges,
              fitas_metric_ranges,
              fast_metric_ranges,
              giro_metric_ranges,
              payment_metric_ranges,
              all_txn_metric_ranges,
              undirected_edges_js,
              directed_edges_js,
              selfloop_edges_js,
              payment_directed_edges_js,
              payment_selfloop_edges_js,
              fitas_selfloop_edges_js,
              all_txn_selfloop_edges_js,
              all_txn_latest_date,
              logo_b64=None,
              relationship_df=None):
        """
        Build complete HTML with 4 networks: RSME, TT, FITAS, AA Paper.

        Parameters
        ----------
        rsme_adjacency            : dict  {uen: [neighbor_uens]}
        rsme_degree_map           : dict  {uen: degree}
        original_sizes_js         : dict  {uen: size_value}
        node_type_js              : dict  {uen: customer_type}
        node_meta_js              : dict  {uen: {field: value}}
        id_name_lookup_js         : dict  {uen: company_name}
        original_labels_js        : dict  {uen: display_label}
        rsme_source               : RSMESource
        consol_tt_source          : ConsolTTSource
        fitas_source              : FITASSource
        aa_paper_source           : AAPaperSource
        consol_tt_node_summary_js : dict  TT transaction summary per node
        fitas_node_summary_js     : dict  FITAS transaction summary per node
        consol_tt_metric_ranges   : dict  TT metric ranges for node sizing
        fitas_metric_ranges       : dict  FITAS metric ranges for node sizing
        undirected_edges_js       : list  pair-symmetric aggregation table
                                          (RSME + AA + FITAS counts, keyed
                                          by sorted-pair). Render-time class
                                          is decided by pairRelationshipMap
                                          flags, NOT by membership here.
        directed_edges_js         : list  TT net flow edge dicts
        selfloop_edges_js         : list  TT self-transfer dicts
        logo_b64                  : str, optional  base64-encoded logo
        relationship_df           : pd.DataFrame, optional  one row per pair
                                    from RelationshipBuilder -- used to embed
                                    pairRelationshipMap in JS for edge panel

        Returns
        -------
        str : complete HTML document
        """

        cfg = self.config
        viz = self.viz_config
        sj  = self.payload_builder.safe_json

        # *** updated | store relationship_df on self for _build_combined_js
        self._relationship_df = relationship_df

        # ── Build UEN compression mapping ─────────────────────────────────
        print("Building UEN compression mapping...")
        uen_to_id, id_to_uen = build_uen_mapping(
            id_name_lookup_js = id_name_lookup_js,
            rsme_adjacency    = rsme_adjacency,
            consol_tt_source  = consol_tt_source,
            fitas_source      = fitas_source,
            aa_paper_source   = aa_paper_source,
            fast_source       = fast_source,
            giro_source       = giro_source,
        )
        validate_compression(
            uen_to_id         = uen_to_id,
            id_name_lookup_js = id_name_lookup_js,
            consol_tt_source  = consol_tt_source,
            fitas_source      = fitas_source,
            aa_paper_source   = aa_paper_source,
            fast_source       = fast_source,
            giro_source       = giro_source,
        )
        print(f"  UEN mapping: {len(uen_to_id):,} UENs -> string IDs 1..{len(uen_to_id)}")

        toolbar_html = get_toolbar_html(cfg, logo_b64)

        combined_js = self._build_combined_js(
            rsme_adjacency            = rsme_adjacency,
            rsme_degree_map           = rsme_degree_map,
            original_sizes_js         = original_sizes_js,
            node_type_js              = node_type_js,
            node_meta_js              = node_meta_js,
            id_name_lookup_js         = id_name_lookup_js,
            original_labels_js        = original_labels_js,
            rsme_source               = rsme_source,
            consol_tt_source          = consol_tt_source,
            fitas_source              = fitas_source,
            aa_paper_source           = aa_paper_source,
            fast_source               = fast_source,
            giro_source               = giro_source,
            consol_tt_node_summary_js = consol_tt_node_summary_js,
            fitas_node_summary_js     = fitas_node_summary_js,
            fast_node_summary_js      = fast_node_summary_js,
            giro_node_summary_js      = giro_node_summary_js,
            payment_node_summary_js   = payment_node_summary_js,
            all_txn_node_summary_js   = all_txn_node_summary_js,
            consol_tt_metric_ranges   = consol_tt_metric_ranges,
            fitas_metric_ranges       = fitas_metric_ranges,
            fast_metric_ranges        = fast_metric_ranges,
            giro_metric_ranges        = giro_metric_ranges,
            payment_metric_ranges     = payment_metric_ranges,
            all_txn_metric_ranges     = all_txn_metric_ranges,
            undirected_edges_js       = undirected_edges_js,
            directed_edges_js         = directed_edges_js,
            selfloop_edges_js         = selfloop_edges_js,
            payment_directed_edges_js = payment_directed_edges_js,
            payment_selfloop_edges_js = payment_selfloop_edges_js,
            fitas_selfloop_edges_js   = fitas_selfloop_edges_js,
            all_txn_selfloop_edges_js = all_txn_selfloop_edges_js,
            all_txn_latest_date       = all_txn_latest_date,
            uen_to_id                 = uen_to_id,
            id_to_uen                 = id_to_uen,
        )

        # ── Control character scan ─────────────────────────────────────────
        bad_matches = list(re.finditer(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', combined_js))
        if bad_matches:
            raise ValueError(
                f"ABORT: {len(bad_matches)} bad control chars in JS. "
                f"First at pos {bad_matches[0].start()}: "
                f"{hex(ord(combined_js[bad_matches[0].start()]))}"
            )

        # ── Size reduction report ──────────────────────────────────────────
        orig_id_name_size = len(sj(id_name_lookup_js))
        comp_id_name_size = len(sj(c_key(id_name_lookup_js, uen_to_id)))
        reduction_pct     = (1 - comp_id_name_size / orig_id_name_size) * 100
        print(f"  idNameLookup: {orig_id_name_size:,} -> {comp_id_name_size:,} bytes "
              f"({reduction_pct:.1f}% reduction)")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Corporate Network Graph - Maybank</title>
    <!-- Poppins-700 only -- used for the M-EXT wordmark to match Recipe 4 RM report. -->
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: #f8f9fa;
        }}
        #mynetwork {{
            width: 100%;
            height: 100vh;
            background: #FAFAFA;
        }}
    </style>
</head>
<body>
{toolbar_html}
<div id="mynetwork"></div>

<script type="text/javascript">
// ══════════════════════════════════════════════════════════════════════════
// INITIALIZE EMPTY VIS.JS NETWORK
// Physics permanently disabled -- layoutRadialTree handles all positioning.
// selectConnectedEdges disabled -- prevents vis.js re-rendering all
// connected edges on every node click (significant perf win on dense graphs).
// ══════════════════════════════════════════════════════════════════════════
(function() {{
    var container = document.getElementById('mynetwork');
    var data = {{
        nodes: new vis.DataSet([]),
        edges: new vis.DataSet([])
    }};
    var options = {{
        nodes: {{
            shape: 'dot',
            font: {{ size: 10, color: '#000000' }},
            borderWidth: 1,
            shadow: false,
        }},
        edges: {{
            width: 1,
            smooth: {{ enabled: false }},
            arrows: {{ to: {{ enabled: false }} }},
            shadow: false,
        }},
        physics: {{
            enabled: false,
        }},
        interaction: {{
            hover               : false,
            navigationButtons   : false,
            keyboard            : false,
            multiselect         : false,
            selectable          : true,
            selectConnectedEdges: false,
            zoomSpeed           : 0.5,  // half the default scroll-zoom rate
        }},
    }};

    var network = new vis.Network(container, data, options);
    var nodes   = data.nodes;
    var edges   = data.edges;

    window.network = network;
    window.nodes   = nodes;
    window.edges   = edges;

    console.log("Empty vis.js network initialized (blank canvas, physics off)");
}})();

// ══════════════════════════════════════════════════════════════════════════
// LOAD ALL JAVASCRIPT MODULES
// ══════════════════════════════════════════════════════════════════════════
{combined_js}
</script>
</body>
</html>"""

        # ── Sanity checks ──────────────────────────────────────────────────
        for marker in ("waitForVis", "renderSearch", "exportCurrentView"):
            if marker not in combined_js:
                raise ValueError(f"ERROR: JavaScript marker missing: {marker}")

        print(f"HTMLBuilder: {len(html)/1024/1024:.2f} MB  "
              f"built at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")

        return html

    def _build_combined_js(self,
                            rsme_adjacency,
                            rsme_degree_map,
                            original_sizes_js,
                            node_type_js,
                            node_meta_js,
                            id_name_lookup_js,
                            original_labels_js,
                            rsme_source,
                            consol_tt_source,
                            fitas_source,
                            aa_paper_source,
                            fast_source,
                            giro_source,
                            consol_tt_node_summary_js,
                            fitas_node_summary_js,
                            fast_node_summary_js,
                            giro_node_summary_js,
                            payment_node_summary_js,
                            all_txn_node_summary_js,
                            consol_tt_metric_ranges,
                            fitas_metric_ranges,
                            fast_metric_ranges,
                            giro_metric_ranges,
                            payment_metric_ranges,
                            all_txn_metric_ranges,
                            undirected_edges_js,
                            directed_edges_js,
                            selfloop_edges_js,
                            payment_directed_edges_js,
                            payment_selfloop_edges_js,
                            fitas_selfloop_edges_js,
                            all_txn_selfloop_edges_js,
                            all_txn_latest_date,
                            uen_to_id,
                            id_to_uen):
        """
        Assemble combined JavaScript from all module files.

        Module order matters:
        - js_core      : data payloads, _UtoI/_ItoU maps, _e()/_d() -- must come first
        - js_filters   : filter checkboxes and node sizing
        - js_search    : search input, dropdown, renderSearch
        - js_sidepanel : showNodeInfo, navigateToNode, edge info panels
        - js_export    : export current view button handler
        - js_network   : ensureAllNetworksInVis, click handlers
        - js_history   : back/forward navigation
        - js_reset     : reset button
        - js_init      : localStorage restore, auto-load last search
        """

        cfg = self.config
        viz = self.viz_config
        sj  = self.payload_builder.safe_json

        js_core = get_js_core(
            config                    = cfg,
            rsme_adjacency            = rsme_adjacency,
            rsme_degree_map           = rsme_degree_map,
            original_sizes_js         = original_sizes_js,
            node_type_js              = node_type_js,
            node_meta_js              = node_meta_js,
            id_name_lookup_js         = id_name_lookup_js,
            original_labels_js        = original_labels_js,
            rsme_source               = rsme_source,
            consol_tt_source          = consol_tt_source,
            fitas_source              = fitas_source,
            aa_paper_source           = aa_paper_source,
            fast_source               = fast_source,
            giro_source               = giro_source,
            consol_tt_node_summary_js = consol_tt_node_summary_js,
            fitas_node_summary_js     = fitas_node_summary_js,
            fast_node_summary_js      = fast_node_summary_js,
            giro_node_summary_js      = giro_node_summary_js,
            payment_node_summary_js   = payment_node_summary_js,
            all_txn_node_summary_js   = all_txn_node_summary_js,
            consol_tt_metric_ranges   = consol_tt_metric_ranges,
            fitas_metric_ranges       = fitas_metric_ranges,
            fast_metric_ranges        = fast_metric_ranges,
            giro_metric_ranges        = giro_metric_ranges,
            payment_metric_ranges     = payment_metric_ranges,
            all_txn_metric_ranges     = all_txn_metric_ranges,
            undirected_edges_js       = undirected_edges_js,
            directed_edges_js         = directed_edges_js,
            selfloop_edges_js         = selfloop_edges_js,
            payment_directed_edges_js = payment_directed_edges_js,
            payment_selfloop_edges_js = payment_selfloop_edges_js,
            fitas_selfloop_edges_js   = fitas_selfloop_edges_js,
            all_txn_selfloop_edges_js = all_txn_selfloop_edges_js,
            all_txn_latest_date       = all_txn_latest_date,
            uen_to_id                 = uen_to_id,
            id_to_uen                 = id_to_uen,
            safe_json                 = sj,
            # *** updated | pass relationship_df stored on self
            relationship_df           = getattr(self, '_relationship_df', None),
        )

        js_filters   = get_js_filters()
        js_search    = get_js_search()
        js_sidepanel = get_js_sidepanel()
        js_export    = get_js_export()
        js_network   = get_js_network()
        js_history   = get_js_history()
        js_reset     = get_js_reset()
        js_init      = get_js_init()

        return f"""
{viz.to_js_object()}

// ══════════════════════════════════════════════════════════════════════════
// FUNCTION DECLARATIONS (HOISTING FIX)
// ══════════════════════════════════════════════════════════════════════════

var renderSearch;
var applyFilters;
var showNodeInfo;
var navigateToNode;
var ensureAllNetworksInVis;
var resetAll;

function waitForVis(callback) {{
    if (typeof window.nodes   !== "undefined" &&
        typeof window.edges   !== "undefined" &&
        typeof window.network !== "undefined" &&
        window.network !== null &&
        typeof window.network.body !== "undefined") {{
        window.visNodes   = window.nodes;
        window.visEdges   = window.edges;
        window.visNetwork = window.network;
        callback();
    }} else {{
        setTimeout(function() {{ waitForVis(callback); }}, 100);
    }}
}}

waitForVis(function() {{

var nodes   = window.visNodes;
var edges   = window.visEdges;
var network = window.visNetwork;

{js_core}

{js_filters}

{js_search}

{js_sidepanel}

{js_export}

{js_network}

{js_history}

{js_reset}

{js_init}

}});
"""
