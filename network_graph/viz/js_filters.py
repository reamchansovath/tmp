# ── network_graph/viz/js_filters.py ───────────────────────────────────────────
# Filter controls for showing/hiding networks and resizing nodes.
# Handles checkbox filters and node sizing dropdown logic.
#
# UEN COMPRESSION: no functional changes needed.
# - nodes.getIds() returns compressed string IDs (nodes added with compressed IDs)
# - e.from / e.to in edges.get() are compressed string IDs
# - All map lookups (nodeMetaMap, degreeMap etc) keyed by compressed ID -- correct
# - consolTTNodeIds / fitasNodeIds / rsmeNodeIds Sets contain compressed IDs -- correct
# - selectedIds holds real UEN strings -- renderSearch encodes internally -- correct
#
# EDGE ARCHITECTURE NOTE:
# applyFilters() reads from edges.get() (vis.js DataSet), NOT pairRelationshipMap.
# The vis.js DataSet entries carry _inRsme/_inFitas/_inAA/_inPayment flags set
# by js_network.py when injecting edges from pairRelationshipMap. Filter logic
# is therefore unchanged -- it always operated on the vis.js DataSet layer.
#
# PERF FIX 4 SYNC: applyFilters() updates _visibleNodes/_visibleEdges at the
# end of both branches so renderSearch diff is accurate after filter changes.


def get_js_filters():
    """
    Returns JavaScript code for filter controls and node sizing.

    Handles:
    - Network visibility filters (RSME, AA Paper, FITAS, Payment)
    - Malaysian / Singapore entity filter (show/hide MY/SG nodes)
    - Node size metric selection (connections, all_txn_sent, all_txn_received)
    - Filter application and node resizing logic

    Edge visibility logic:
    - Reads _inRsme/_inFitas/_inAA/_inPayment from vis.js DataSet edges.
    - These flags are set by js_network.py during edge injection from
      pairRelationshipMap (consolidated source of truth).
    - Edge is visible if ANY of its enabled source flags is checked.
    - Self-loops (_isSelfLoop) are controlled by the Payment filter
      (and FITAS once FITAS self-loops are added).

    PERF FIX 4 SYNC:
    applyFilters() syncs _visibleNodes/_visibleEdges after every visibility
    change so the diff logic in renderSearch starts from accurate state.

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// FILTER CONTROLS
// ══════════════════════════════════════════════════════════════════════════
//
// Filter state lives in two Sets backing the multi-select dropdowns:
// _selectedSources    -> {'rsme','aaPaper','fitas','consolTT'}  (default: all)
// _selectedCountries  -> {'SG','MY'}                            (default: all)
// getFilters() shape is unchanged so applyFilters() doesn't care where the
// state comes from.
// ══════════════════════════════════════════════════════════════════════════

var _selectedSources   = new Set(['rsme', 'aaPaper', 'fitas', 'payment']);
var _selectedCountries = new Set(['SG', 'MY']);
var _selectedNodeSize  = 'connections';   // 'connections' | 'all_txn_sent' | 'all_txn_received'

function getFilters() {
    return {
        rsme    : _selectedSources.has('rsme'),
        aaPaper : _selectedSources.has('aaPaper'),
        fitas   : _selectedSources.has('fitas'),
        payment : _selectedSources.has('payment'),
        showMY  : _selectedCountries.has('MY'),
        showSG  : _selectedCountries.has('SG'),
    };
}

var applyFilters = function() {};

applyFilters = function() {
    var filt = getFilters();

    // ── All source filters unchecked -- hide everything ───────────────────
    if (!filt.rsme && !filt.aaPaper && !filt.fitas && !filt.payment) {
        nodes.update(nodes.getIds().map(function(nid) { return {id: nid, hidden: true}; }));
        edges.update(edges.getIds().map(function(eid) { return {id: eid, hidden: true}; }));

        _visibleNodes = new Set();
        _visibleEdges = new Set();

        network.redraw();
        return;
    }

    // ── Determine which edges are visible under current filters ───────────
    // Reads _inRsme/_inFitas/_inAA/_inTT from vis.js DataSet edges.
    // These flags are mapped from pairRelationshipMap abbreviated keys
    // (ir/if/ia/it) during edge injection in js_network.py.
    // Self-loops now span all 4 sources (TT/MEPS/FAST/GIRO/FITAS). Visible
    // if either Payment or FITAS filter is on. AA Paper / RSME self-loops are
    // not drawn (no transaction count/amount available on those sources).
    var edgeCounts = {};

    var edgeUpd = edges.get().map(function(e) {
        var visible = false;

        if (e._isSelfLoop) {
            visible = filt.payment || filt.fitas;
        } else {
            visible = (filt.rsme    && !!e._inRsme)    ||
                      (filt.aaPaper && !!e._inAA)      ||
                      (filt.fitas   && !!e._inFitas)   ||
                      (filt.payment && !!e._inPayment);
        }

        // MY filter -- hide edge if either endpoint is MY and MY is hidden
        if (visible && !filt.showMY) {
            var fromMeta = nodeMetaMap[e.from] || {};
            var toMeta   = nodeMetaMap[e.to]   || {};
            if ((fromMeta.source_country || '') === 'MY' ||
                (toMeta.source_country   || '') === 'MY') {
                visible = false;
            }
        }

        // SG filter -- hide edge if either endpoint is SG and SG is hidden
        // (new capability vs. the old "Include MY" toggle)
        if (visible && !filt.showSG) {
            var fromMetaSG = nodeMetaMap[e.from] || {};
            var toMetaSG   = nodeMetaMap[e.to]   || {};
            if ((fromMetaSG.source_country || '') === 'SG' ||
                (toMetaSG.source_country   || '') === 'SG') {
                visible = false;
            }
        }

        if (visible) {
            edgeCounts[e.from] = (edgeCounts[e.from] || 0) + 1;
            edgeCounts[e.to]   = (edgeCounts[e.to]   || 0) + 1;
        }
        return {id: e.id, hidden: !visible};
    });
    edges.update(edgeUpd);

    // Hide nodes with no visible edges
    var visNodeSet = new Set(Object.keys(edgeCounts));
    nodes.update(nodes.getIds().map(function(nid) {
        return {id: nid, hidden: !visNodeSet.has(nid)};
    }));

    // PERF FIX 4 SYNC: update _visibleNodes and _visibleEdges to reflect
    // what applyFilters just made visible. Without this, renderSearch diffs
    // against stale sets and fails to hide nodes on the next search.
    _visibleNodes = visNodeSet;
    _visibleEdges = new Set();
    edgeUpd.forEach(function(e) {
        if (!e.hidden) _visibleEdges.add(e.id);
    });

    // Resize nodes relative to the new visible set so sizes always reflect
    // what's currently on screen.
    applyNodeSizing();

    network.redraw();
};

// ══════════════════════════════════════════════════════════════════════════
// NODE SIZING
// ══════════════════════════════════════════════════════════════════════════
//
// Absolute log-scale sizing (NOT normalised to visible set). Picking this
// over relative sizing because relative sizing stretches tiny value gaps
// (e.g. 6 vs 7 connections) across the full size range, exaggerating the
// visual difference. Absolute log keeps similar values visually similar
// and only opens up a real gap when values are orders of magnitude apart.
//
// Formula:   size = clamp(MIN_SZ + log1p(value / scale) * factor, MIN_SZ, MAX_SZ)
//
// Per-metric scale + factor are tuned so:
//   - connections: 6 vs 7 differ by ~0.5 px; 1 vs 50 differ by ~14 px
//   - amounts:     S$10k vs S$11k differ by ~0.4 px; S$10k vs S$10M by ~21 px
//
// Sizing is recomputed on every search/hops/filter change so newly-visible
// nodes get sized correctly, but the formula is value-driven so absolute
// scale stays consistent regardless of which subset is on screen.
//
// Metrics:
//   connections      = unique-neighbor count across all sources
//   all_txn_sent     = allTxnNodeSummary[id].all_txn_ord_amt
//   all_txn_received = allTxnNodeSummary[id].all_txn_bene_amt
// ══════════════════════════════════════════════════════════════════════════

function _allSourcesNeighborSet(nid) {
    var s = new Set();
    (adjacencyMap[nid]      || []).forEach(function(x) { s.add(x); });
    (paymentOutAdj[nid]     || []).forEach(function(x) { s.add(x); });
    (paymentInAdj[nid]      || []).forEach(function(x) { s.add(x); });
    (fitasOutAdj[nid]       || []).forEach(function(x) { s.add(x); });
    (fitasInAdj[nid]        || []).forEach(function(x) { s.add(x); });
    (aaPaperOutAdj[nid]     || []).forEach(function(x) { s.add(x); });
    (aaPaperInAdj[nid]      || []).forEach(function(x) { s.add(x); });
    return s;
}

function _nodeMetricValue(nid, metric) {
    if (metric === "connections") {
        return _allSourcesNeighborSet(nid).size;
    }
    var sum = (typeof allTxnNodeSummary !== "undefined") ? allTxnNodeSummary[nid] : null;
    if (!sum) return 0;
    if (metric === "all_txn_sent")     return Number(sum.all_txn_ord_amt)  || 0;
    if (metric === "all_txn_received") return Number(sum.all_txn_bene_amt) || 0;
    return 0;
}

// Per-metric absolute scaling: { scale, factor }
//   final size = MIN_SZ + log1p(value / scale) * factor  (clamped)
// Tuned so that close values look close, far-apart values look distinct.
var _SIZE_PARAMS = {
    connections      : { scale: 1,    factor: 5.5 },
    all_txn_sent     : { scale: 1000, factor: 3.0 },
    all_txn_received : { scale: 1000, factor: 3.0 },
};

function _absoluteSize(value, metric) {
    var MIN_SZ = CFG.node_size_min;
    var MAX_SZ = CFG.node_size_max;
    if (!(value > 0)) return MIN_SZ;
    var p = _SIZE_PARAMS[metric] || _SIZE_PARAMS.connections;
    var sz = MIN_SZ + Math.log1p(value / p.scale) * p.factor;
    if (sz < MIN_SZ) return MIN_SZ;
    if (sz > MAX_SZ) return MAX_SZ;
    return Math.round(sz);
}

function getNodeSize(nid) {
    return _absoluteSize(_nodeMetricValue(nid, _selectedNodeSize), _selectedNodeSize);
}

function applyNodeSizing() {
    var metric = _selectedNodeSize;

    // Apply to all non-hidden nodes. We don't depend on _visibleNodes here
    // because absolute sizing doesn't need the visible set, but we still
    // skip hidden nodes to avoid unnecessary DataSet writes.
    var upd = [];
    nodes.getIds().forEach(function(nid) {
        var n = nodes.get(nid);
        if (!n || n.hidden) return;
        upd.push({id: nid, size: _absoluteSize(_nodeMetricValue(nid, metric), metric)});
    });
    if (upd.length > 0) nodes.update(upd);
}

// Initial-render helpers used by js_network.py. Use the same absolute formula
// keyed off the default metric so the first paint already has correct sizes.
function _initialSize(nid) {
    return _absoluteSize(_nodeMetricValue(nid, _selectedNodeSize), _selectedNodeSize);
}
function getPaymentNodeSize(nid, metric) { return _initialSize(nid); }
function getFITASNodeSize(nid, metric)   { return _initialSize(nid); }
function getRSMENodeSize(nid, metric)    { return _initialSize(nid); }

// ══════════════════════════════════════════════════════════════════════════
// MULTI-SELECT DROPDOWN UI
// (trigger label + click-outside-to-close + checkbox change handlers)
// ══════════════════════════════════════════════════════════════════════════

function _renderTriggerLabel(filterKey) {
    var labelEl = document.getElementById('dd-' + filterKey + '-label');
    if (!labelEl) return;
    var set     = (filterKey === 'sources') ? _selectedSources : _selectedCountries;
    var total   = (filterKey === 'sources') ? 4 : 2;
    var allLbl  = (filterKey === 'sources') ? 'All Sources' : 'All Countries';
    if (set.size === total)  labelEl.textContent = allLbl;
    else if (set.size === 0) labelEl.textContent = 'None';
    else                     labelEl.textContent = set.size + ' selected';
}

function _renderNodeSizeLabel() {
    var labels = {
        connections     : 'Connections',
        all_txn_sent    : 'Total Sent (All Txn)',
        all_txn_received: 'Total Received (All Txn)',
    };
    var el = document.getElementById('dd-nodesize-label');
    if (el) el.textContent = labels[_selectedNodeSize] || _selectedNodeSize;
}

function _onFilterStateChange() {
    _renderTriggerLabel('sources');
    _renderTriggerLabel('countries');
    if (selectedIds.length > 0) {
        renderSearch(
            selectedIds.slice(),
            parseInt(document.getElementById('hop-input').value) || 2,
            false
        );
    } else {
        applyFilters();
    }
}

// ── Wire up dropdown triggers ─────────────────────────────────────────────
['sources', 'countries', 'nodesize'].forEach(function(key) {
    var trigger = document.getElementById('dd-' + key + '-trigger');
    var panel   = document.getElementById('dd-' + key + '-panel');
    if (!trigger || !panel) return;

    trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        // Close any other open dropdown so only one is open at a time
        document.querySelectorAll('.tb-dd-panel.open').forEach(function(p) {
            if (p !== panel) p.classList.remove('open');
        });
        document.querySelectorAll('.tb-dd-trigger.open').forEach(function(t) {
            if (t !== trigger) t.classList.remove('open');
        });
        panel.classList.toggle('open');
        trigger.classList.toggle('open');
    });
});

// ── Click outside any dropdown closes them all ────────────────────────────
document.addEventListener('click', function(e) {
    if (e.target && e.target.closest && e.target.closest('.tb-dropdown')) return;
    document.querySelectorAll('.tb-dd-panel.open').forEach(function(p) {
        p.classList.remove('open');
    });
    document.querySelectorAll('.tb-dd-trigger.open').forEach(function(t) {
        t.classList.remove('open');
    });
});

// ── Checkbox toggles inside dropdowns ─────────────────────────────────────
document.querySelectorAll('#dd-sources-panel input[type=checkbox]').forEach(function(cb) {
    cb.addEventListener('change', function() {
        var key = cb.getAttribute('data-source');
        if (cb.checked) _selectedSources.add(key);
        else            _selectedSources.delete(key);
        _onFilterStateChange();
    });
});
document.querySelectorAll('#dd-countries-panel input[type=checkbox]').forEach(function(cb) {
    cb.addEventListener('change', function() {
        var key = cb.getAttribute('data-country');
        if (cb.checked) _selectedCountries.add(key);
        else            _selectedCountries.delete(key);
        _onFilterStateChange();
    });
});

// ── Node-size radio change (single-select dropdown, auto-closes on pick) ──
document.querySelectorAll('#dd-nodesize-panel input[type=radio]').forEach(function(rb) {
    rb.addEventListener('change', function() {
        if (!rb.checked) return;
        _selectedNodeSize = rb.getAttribute('data-value');
        _renderNodeSizeLabel();
        applyNodeSizing();
        // Single-select panels close themselves once the user picks a value
        var panel   = document.getElementById('dd-nodesize-panel');
        var trigger = document.getElementById('dd-nodesize-trigger');
        if (panel)   panel.classList.remove('open');
        if (trigger) trigger.classList.remove('open');
    });
});

// ── Initial paint ─────────────────────────────────────────────────────────
_renderTriggerLabel('sources');
_renderTriggerLabel('countries');
_renderNodeSizeLabel();
"""
