# ── network_graph/viz/js_reset.py ─────────────────────────────────────────────
# Reset button logic - blank canvas, no default view.
#
# UEN COMPRESSION:
# - nodes.getIds() returns compressed string IDs -- used as id in update, correct
# - edges.getIds() returns edge ID strings ("undirected_1_2" etc) -- correct
# - _lastHighlighted stores compressed string ID -- correct
# - FIX 1: _visibleNodes and _visibleEdges cleared on reset to avoid stale
#   diff state in next renderSearch call
# - FIX 2: _lastHighlightedEdge cleared on reset
# - Default view: rsmeNodeIds contains compressed IDs, degreeMap keyed by
#   compressed ID, e.from/e.to are compressed IDs -- all correct


def get_js_reset():
    """
    Returns JavaScript code for reset functionality.

    Handles:
    - Reset button click handler
    - Hide ALL nodes and edges (blank canvas)
    - Clearing all state, selections, history, and localStorage

    UEN compression note:
    - nodes.getIds() / edges.getIds() return compressed IDs -- correct
    - _visibleNodes / _visibleEdges cleared to avoid stale diff on next search
    - _lastHighlightedEdge cleared alongside _lastHighlighted

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// RESET FUNCTIONALITY
// ══════════════════════════════════════════════════════════════════════════

var resetAll = function() {};

resetAll = function() {
    // Clear search pill and selectedIds
    removeSelection();

    // Close any open dropdowns
    var dropdown     = document.getElementById("search-dropdown");
    var histDropdown = document.getElementById("hist-dropdown");
    if (dropdown)     dropdown.style.display     = "none";
    if (histDropdown) histDropdown.style.display = "none";

    // Clear error message
    document.getElementById("search-error").innerText = "";

    // Clear history stack and update button states
    historyStack = [];
    historyIndex = -1;
    updateHistoryButtons();

    // Clear persisted state from localStorage
    try {
        localStorage.removeItem(LS_LAST);
        localStorage.removeItem(LS_HISTORY);
    } catch(e) {}

    // Clear node highlight -- _lastHighlighted is compressed string ID
    if (_lastHighlighted !== null) {
        nodes.update({id: _lastHighlighted, shadow: {enabled: false}});
        _lastHighlighted = null;
    }

    // FIX 2: clear edge highlight state alongside node highlight
    _lastHighlightedEdge = null;

    // Hide all nodes and edges -- blank canvas
    // nid / eid from getIds() are compressed string IDs -- correct
    nodes.update(nodes.getIds().map(function(nid) {
        return {id: nid, hidden: true};
    }));
    edges.update(edges.getIds().map(function(eid) {
        return {id: eid, hidden: true};
    }));

    // FIX 1: clear _visibleNodes and _visibleEdges so next renderSearch
    // diffs from a clean state instead of the last search's compressed IDs.
    // Without this, renderSearch would waste update calls trying to hide
    // nodes/edges that resetAll already hid.
    _visibleNodes = new Set();
    _visibleEdges = new Set();

    // Note: resetEdgeColors() not called here -- after hiding all edges it
    // would be a no-op (visible edge filter returns nothing). Colors are
    // restored correctly the next time renderSearch shows edges.
    network.redraw();
    clearSidePanel();
};

document.getElementById("reset-btn").addEventListener("click", resetAll);

// ══════════════════════════════════════════════════════════════════════════
// DEFAULT VIEW ON LOAD
// Currently disabled -- CFG.default_top_n = 0 means blank canvas on load.
// To enable a default view showing the top-N highest-degree RSME nodes,
// set default_top_n > 0 in VizConfig.
// rsmeNodeIds contains compressed string IDs -- degreeMap keyed by
// compressed ID -- e.from/e.to are compressed IDs -- all correct.
// ══════════════════════════════════════════════════════════════════════════

// Wait for compressed payloads (rsmeNodeIds, degreeMap) before reading them.
// Today CFG.default_top_n = 0 so this is a no-op anyway, but the wrap means
// flipping the config in viz/config.py won't reintroduce a null-deref crash.
__bootstrapReady.then(function() {
    if (CFG.default_top_n <= 0) return;

    // id = compressed string ID from rsmeNodeIds Set
    var ranked = [];
    rsmeNodeIds.forEach(function(id) {
        ranked.push({id: id, deg: degreeMap[id] || 0});
    });
    ranked.sort(function(a, b) { return b.deg - a.deg; });

    var topIds = new Set(ranked.slice(0, CFG.default_top_n).map(function(x) { return x.id; }));

    nodes.update(nodes.getIds().map(function(id) {
        return {id: id, hidden: !topIds.has(id)};
    }));
    // Edges carry _inRsme/_inPayment/_inFITAS/_inAAPaper flags;
    // RSME default-view shows undirected RSME-only edges between top-N nodes.
    edges.update(edges.get().map(function(e) {
        var visible = !!e._inRsme && !e._isSelfLoop &&
                      topIds.has(e.from) && topIds.has(e.to);
        return {id: e.id, hidden: !visible};
    }));

    network.fit({animation: false});
});
"""
