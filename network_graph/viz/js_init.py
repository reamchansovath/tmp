# ── network_graph/viz/js_init.py ──────────────────────────────────────────────
# Initialization logic: restore localStorage state, auto-load last search.
# Physics is permanently disabled at network creation in builder.py --
# no physics management needed here.
#
# UEN COMPRESSION:
# - localStorage stores real UEN strings (LS_LAST, LS_HISTORY) -- unchanged
# - Auto-load: last.uen is real UEN string -- renderSearch encodes internally
# - Node existence check uses nodes.get(_e(uen)) since vis.js IDs are
#   now compressed string IDs, not raw UEN strings
# - initSearchIndex() removed -- PERF FIX 5 edge index was removed from
#   js_search.py in favour of direct edge data array iteration


def get_js_init():
    """
    Returns JavaScript code for initialization.

    Execution order:
    1. localStorage state restored (hops, history) -- synchronous
    2. t=100ms: auto-load last search

    Note: Physics is disabled at vis.Network creation in builder.py.
    The 1200ms delay previously here existed only to guarantee physics
    was off before renderSearch fired. With physics gone, 100ms is enough
    for the DOM to settle.

    UEN compression note:
    - last.uen from localStorage is always a real UEN string
    - renderSearch([last.uen], ...) encodes to compressed ID internally
    - nodes.get() must use _e(uen) since vis.js node IDs are compressed

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// INITIALIZATION - RESTORE FROM LOCALSTORAGE
// All init blocks below await __bootstrapReady first because they reference
// payloads that arrive only after gzip decompression completes.
// ══════════════════════════════════════════════════════════════════════════

// ── Restore hop count (no big-payload dependency -- runs immediately) ─────
(function() {
    try {
        var h = parseInt(localStorage.getItem(LS_HOPS));
        if (!isNaN(h) && h >= 1) {
            document.getElementById("hop-input").value = h;
            console.log("Restored hop value from localStorage:", h);
        }
    } catch(e) {
        console.error("Failed to restore hop value:", e);
    }
})();

// ── Restore history stack and button states (no big-payload dep) ──────────
(function() {
    try {
        var ph = JSON.parse(localStorage.getItem(LS_HISTORY));
        if (Array.isArray(ph) && ph.length > 0) {
            historyStack = ph;
            historyIndex = ph.length - 1;
            updateHistoryButtons();
            console.log("Restored history from localStorage:", ph.length, "items");
        }
    } catch(e) {
        console.error("Failed to restore history:", e);
    }
})();

// ── Auto-load last search + final init banner (BOTH need decompressed data)
// We chain off __bootstrapReady so they fire only after _UtoI / nodeMetaMap /
// companyList / etc. are populated. If decompression fails, surface the
// error in the page instead of silently doing nothing.
__bootstrapReady.then(function() {
    // Auto-load last search after a small DOM-settle delay
    setTimeout(function() {
        try {
            var last = JSON.parse(localStorage.getItem(LS_LAST));
            if (!last || !last.uen) return;

            var compId = _e(last.uen);
            if (compId === undefined) {
                console.warn("Auto-load: UEN not in compression map:", last.uen);
                return;
            }
            if (nodes.get(compId) === null) {
                console.warn("Auto-load: compressed ID not in vis.js dataset:", compId, "->", last.uen);
                return;
            }

            selectedIds = [last.uen];
            document.getElementById("hop-input").value = last.hops || 2;
            renderSelectedPill();
            renderSearch([last.uen], last.hops || 2, false);
            currentNode = last.uen;
            showNodeInfo(last.uen);
            console.log("Auto-loaded last search:", last.uen, "hops:", last.hops);
        } catch(e) {
            console.error("Failed to auto-load last search:", e);
        }
    }, 100);

    console.log("══════════════════════════════════════════════════════════════");
    console.log("Network graph initialized successfully");
    console.log("══════════════════════════════════════════════════════════════");
    console.log("Total nodes in dataset:", nodes.getIds().length);
    console.log("Total edges in dataset:", edges.getIds().length);
    console.log("RSME nodes:",      rsmeNodeIds.size);
    console.log("Payment nodes:",   paymentNodeIds.size);
    console.log("FAST nodes:",      fastNodeIds.size);
    console.log("GIRO nodes:",      giroNodeIds.size);
    console.log("FITAS nodes:",     fitasNodeIds.size);
    console.log("AA Paper nodes:",  aaPaperNodeIds.size);
    console.log("Company list:",    companyList.length);
    console.log("UEN map size:",    Object.keys(_UtoI).length);
    console.log("Default hops:",    document.getElementById("hop-input").value);
    console.log("══════════════════════════════════════════════════════════════");
}).catch(function(err) {
    console.error("Bootstrap failed:", err);
    var msg = document.createElement('div');
    msg.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#FFCC00;color:#000;padding:14px;font:600 13px sans-serif;z-index:99999;';
    msg.textContent = 'Failed to load graph data: ' + (err && err.message ? err.message : err) +
                      '. Browser may not support DecompressionStream (Chrome 80+, Edge 80+, Firefox 113+, Safari 16.4+).';
    document.body.appendChild(msg);
});
"""
