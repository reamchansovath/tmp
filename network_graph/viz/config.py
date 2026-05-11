# ── network_graph/viz/config.py ────────────────────────────────────────────────
# Visual configuration for the network graph.
# Controls styling, layout, and interaction parameters.
#
# To add a new config value:
#   1. Add the class attribute below
#   2. Add the corresponding line in to_js_object()
#   3. Reference as CFG.<key> in the relevant JS module


class VizConfig:
    """
    Configuration for network graph visualization parameters.
    Separate from NetworkGraphConfig to isolate visual tuning.

    Edge architecture (pairRelationshipMap -- single source of truth):
    - RSME-only  : solid green (#2f8744), straight line, no arrow
    - directed   : solid blue, straight line, single arrow at to
                   (covers Payment combined + FITAS + AA Paper directed)
    - both-ways  : solid blue, straight line, arrows both ends
    - selfloop   : blue loop (All-Txn / Payment-combined self-transfer)

    All consolidated edges use smooth: {enabled: false} (straight lines).
    rsme_edge_smooth / rsme_edge_smooth_type / rsme_edge_smooth_roundness
    retained in CFG for export HTML compat but not used in main injection.
    """

    # ── Default view ──────────────────────────────────────────────────────────
    default_top_n = 0              # 0 = blank canvas on load

    # ── Node sizing ───────────────────────────────────────────────────────────
    node_size_min               = 10
    node_size_max               = 50

    # ── Selected-node visual feedback ────────────────────────────────────────
    # *** updated | Halo shadow removed entirely (was a 25px gold blur).
    # Selection feedback now comes from vis.js's built-in selectNodes visual
    # plus the side-panel content swap. Shadow constants kept here only as
    # documentation of what used to live in CFG; the related JS branches
    # in js_network.py / js_export.py / js_reset.py have all been removed.

    # ── Search ────────────────────────────────────────────────────────────────
    search_max_results = 10
    search_debounce_ms = 200

    # ── RSME-only edges ───────────────────────────────────────────────────────
    # *** updated | color changed to #2f8744 (solid green, no dashes)
    # Dashes removed -- js_network.py sets dashes:false on _rsmeOnly branch.
    # All edges straight (smooth disabled) via pairRelationshipMap injection.
    rsme_edge_color             = "#2f8744"
    rsme_edge_opacity           = 0.7
    rsme_edge_highlight_color   = "#2f8744"
    rsme_edge_highlight_opacity = 1.0
    rsme_edge_highlight_mult    = 2.0
    rsme_edge_width             = 1
    # Retained for export HTML compat -- not used in main injection
    rsme_edge_smooth            = False
    rsme_edge_smooth_type       = "curvedCCW"
    rsme_edge_smooth_roundness  = 0.07

    # ── Directed / both-ways edges (Payment combined + FITAS + AA Paper) ─────
    # Blue, straight line, arrow direction from pairRelationshipMap.ib flag.
    # Constant prefix `consol_tt_edge_*` is legacy -- now applied to all
    # directed edge classes (Payment, FITAS, AA Paper), not just TT.
    consol_tt_edge_color             = "#2980b9"
    consol_tt_edge_opacity           = 0.6
    consol_tt_edge_highlight_color   = "#2980b9"
    consol_tt_edge_highlight_opacity = 1.0
    consol_tt_edge_smooth            = False
    consol_tt_edge_smooth_type       = "curvedCW"
    consol_tt_edge_smooth_roundness  = 0.14

    def to_js_object(self) -> str:
        """Serialise config to a JavaScript CFG object literal for embedding in HTML."""
        return f"""
var CFG = {{
    default_top_n                    : {self.default_top_n},
    node_size_min                    : {self.node_size_min},
    node_size_max                    : {self.node_size_max},
    search_max_results               : {self.search_max_results},
    search_debounce_ms               : {self.search_debounce_ms},
    rsme_edge_color                  : "{self.rsme_edge_color}",
    rsme_edge_opacity                : {self.rsme_edge_opacity},
    rsme_edge_highlight_color        : "{self.rsme_edge_highlight_color}",
    rsme_edge_highlight_opacity      : {self.rsme_edge_highlight_opacity},
    rsme_edge_highlight_mult         : {self.rsme_edge_highlight_mult},
    rsme_edge_width                  : {self.rsme_edge_width},
    rsme_edge_smooth                 : {str(self.rsme_edge_smooth).lower()},
    rsme_edge_smooth_type            : "{self.rsme_edge_smooth_type}",
    rsme_edge_smooth_roundness       : {self.rsme_edge_smooth_roundness},
    consol_tt_edge_color             : "{self.consol_tt_edge_color}",
    consol_tt_edge_opacity           : {self.consol_tt_edge_opacity},
    consol_tt_edge_highlight_color   : "{self.consol_tt_edge_highlight_color}",
    consol_tt_edge_highlight_opacity : {self.consol_tt_edge_highlight_opacity},
    consol_tt_edge_smooth            : {str(self.consol_tt_edge_smooth).lower()},
    consol_tt_edge_smooth_type       : "{self.consol_tt_edge_smooth_type}",
    consol_tt_edge_smooth_roundness  : {self.consol_tt_edge_smooth_roundness}
}};
"""
