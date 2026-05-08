# ── network_graph/viz/js_network.py ──────────────────────────────────────────
# UEN COMPRESSION:
# - All vis.js node IDs are compressed string IDs ("1", "2", ...)
# - nodeMetaMap, nodeTypeMap, originalLabels, originalSizes all keyed by compressed ID
# - Click handler decodes compressed ID -> real UEN before calling showNodeInfo/navigateToNode
# - currentNode stores real UEN string (external API)
# - highlightNode takes compressed string ID (vis.js internal)
#
# EDGE ARCHITECTURE (updated):
# - pairRelationshipMap : single source of truth, iterated via Object.values()
#     for vis.js injection. Fields read from map abbreviated keys:
#       e.fr=from  e.to=to  e.ro=rsmeOnly  e.ib=isBoth  e.wb=width
#       e.ir=inRsme  e['if']=inFitas  e.ia=inAA  e.it=inTT
#     ('if' requires bracket notation -- reserved word in JS)
# - selfLoopEdgesData : TT self-transfers, injected separately, unchanged
# - consolidatedEdgesData removed entirely
#
# EDGE COLORS (updated):
# - RSME-only : CFG.rsme_edge_color (#2f8744 green), solid, no arrow, no dashes
# - All others: CFG.consol_tt_edge_color (blue), solid, arrows per direction
# - resetEdgeColors() and highlightNode() branch on _rsmeOnly for correct color


def get_js_network():
    """
    Returns JavaScript code for network interaction and edge management.

    Edge visual styles read from pairRelationshipMap abbreviated fields:
    - e.ro=true : solid green (CFG.rsme_edge_color), no arrow, no dashes
    - e.ib=true : solid blue, arrows at both ends
    - default   : solid blue, single arrow at to
    All straight lines (smooth disabled).
    Self-loops: smooth CW (required for loop render), blue, unchanged.

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// INJECT ALL 4 NETWORK NODES + EDGES INTO VIS DATASET
// All node IDs are compressed string IDs.
// All nodes and edges added with hidden: true -- blank canvas on load.
// ══════════════════════════════════════════════════════════════════════════

var _allNetworksBuilt = false;

function ensureAllNetworksInVis() {
    if (_allNetworksBuilt) return;
    _allNetworksBuilt = true;

    var existingIds  = new Set(nodes.getIds());
    var existingEids = new Set(edges.getIds());

    function _nodeColorShape(id) {
        var meta = nodeMetaMap[id] || {};
        var color, shape;
        if ((meta.source_country || '') === 'MY') {
            color = colorMalaysian; shape = 'square';
        } else {
            color = getTypeColor(nodeTypeMap[id] || "Non-Maybank Customer");
            shape = 'dot';
        }
        return {color: color, shape: shape};
    }

    function _nodeLabel(id) {
        var lbl = originalLabels[id];
        return (lbl != null && lbl !== '') ? lbl : _d(id);
    }

    // ── Add RSME nodes ────────────────────────────────────────────────────
    var rsmeNodesToAdd = [];
    rsmeNodeIds.forEach(function(id) {
        if (existingIds.has(id)) return;
        var cs = _nodeColorShape(id);
        rsmeNodesToAdd.push({
            id    : id,
            label : _nodeLabel(id),
            font  : {color: "#000000", size: 13},
            color : {background: cs.color, border: "#555555",
                     highlight: {background: cs.color, border: "#555555"}},
            shape : cs.shape,
            size  : getRSMENodeSize(id, _selectedNodeSize),
            x: 0, y: 0,
            hidden: true,
        });
        existingIds.add(id);
    });
    if (rsmeNodesToAdd.length > 0) nodes.add(rsmeNodesToAdd);

    // ── Add Payment nodes (TT + FAST + GIRO union) ───────────────────────
    var paymentNodesToAdd = [];
    paymentNodeIds.forEach(function(id) {
        if (existingIds.has(id)) return;
        var cs = _nodeColorShape(id);
        paymentNodesToAdd.push({
            id    : id,
            label : _nodeLabel(id),
            font  : {color: "#000000", size: 13},
            color : {background: cs.color, border: "#555555",
                     highlight: {background: cs.color, border: "#555555"}},
            shape : cs.shape,
            size  : getPaymentNodeSize(id, _selectedNodeSize),
            x: 0, y: 0,
            hidden: true,
        });
        existingIds.add(id);
    });
    if (paymentNodesToAdd.length > 0) nodes.add(paymentNodesToAdd);

    // ── Add FITAS nodes ───────────────────────────────────────────────────
    var fitasToAdd = [];
    fitasNodeIds.forEach(function(id) {
        if (existingIds.has(id)) return;
        var cs = _nodeColorShape(id);
        fitasToAdd.push({
            id    : id,
            label : _nodeLabel(id),
            font  : {color: "#000000", size: 13},
            color : {background: cs.color, border: "#555555",
                     highlight: {background: cs.color, border: "#555555"}},
            shape : cs.shape,
            size  : getFITASNodeSize(id, _selectedNodeSize),
            x: 0, y: 0,
            hidden: true,
        });
        existingIds.add(id);
    });
    if (fitasToAdd.length > 0) nodes.add(fitasToAdd);

    // ── Add AA Paper nodes ────────────────────────────────────────────────
    var aaPaperToAdd = [];
    aaPaperNodeIds.forEach(function(id) {
        if (existingIds.has(id)) return;
        var cs = _nodeColorShape(id);
        aaPaperToAdd.push({
            id    : id,
            label : _nodeLabel(id),
            font  : {color: "#000000", size: 13},
            color : {background: cs.color, border: "#555555",
                     highlight: {background: cs.color, border: "#555555"}},
            shape : cs.shape,
            size  : getSize(id),
            x: 0, y: 0,
            hidden: true,
        });
        existingIds.add(id);
    });
    if (aaPaperToAdd.length > 0) nodes.add(aaPaperToAdd);

    // ── Add consolidated edges from pairRelationshipMap ───────────────────
    // *** updated | RSME-only edges now use CFG.rsme_edge_color (green),
    // solid line (dashes:false), no arrow. All others use CFG.consol_tt_edge_color.
    var consolidatedToAdd = [];
    Object.values(pairRelationshipMap).forEach(function(e) {
        var eid = "consolidated_" + e.fr + "_" + e.to;
        if (existingEids.has(eid)) return;

        var isRsmeOnly = !!e.ro;
        var isBoth     = !!e.ib;

        var arrowConfig;
        if (isRsmeOnly) {
            arrowConfig = {to: {enabled: false}};
        } else if (isBoth) {
            arrowConfig = {
                to  : {enabled: true, scaleFactor: 0.6},
                from: {enabled: true, scaleFactor: 0.6},
            };
        } else {
            arrowConfig = {to: {enabled: true, scaleFactor: 0.6}};
        }

        // *** updated | RSME-only: green color, full opacity, no dashes
        // All others: blue color, standard opacity
        var edgeColor = isRsmeOnly
            ? {
                color    : CFG.rsme_edge_color,
                opacity  : CFG.rsme_edge_opacity,
                highlight: CFG.rsme_edge_highlight_color,
              }
            : {
                color    : CFG.consol_tt_edge_color,
                opacity  : CFG.consol_tt_edge_opacity,
                highlight: CFG.consol_tt_edge_highlight_color,
              };

        consolidatedToAdd.push({
            id              : eid,
            from            : e.fr,
            to              : e.to,
            _rsmeOnly       : isRsmeOnly,
            _isBoth         : isBoth,
            _inRsme         : !!e.ir,
            _inFitas        : !!e['if'],
            _inAA           : !!e.ia,
            _inTT           : !!e.it,
            _inFAST         : !!e.if_fa,
            _inGIRO         : !!e.if_gi,
            _inPayment      : !!e.if_pay,
            _isUndirected   : isRsmeOnly,
            _isDirected     : !isRsmeOnly,
            _isSelfLoop     : false,
            _rsme_ab        : e._rsme_ab        || false,
            _rsme_ba        : e._rsme_ba        || false,
            _aa_ab          : e._aa_ab          || false,
            _aa_ba          : e._aa_ba          || false,
            _fitas_ab_count : e._fitas_ab_count || 0,
            _fitas_ab_amt   : e._fitas_ab_amt   || 0,
            _fitas_ba_count : e._fitas_ba_count || 0,
            _fitas_ba_amt   : e._fitas_ba_amt   || 0,
            _tt_ab_count    : e._tt_ab_count    || 0,
            _tt_ab_amt      : e._tt_ab_amt      || 0,
            _tt_ba_count    : e._tt_ba_count    || 0,
            _tt_ba_amt      : e._tt_ba_amt      || 0,
            _tt_total_count : e._tt_total_count || 0,
            _tt_net_amt     : e._tt_net_amt     || 0,
            _baseWidth      : e.wb || 1,
            color           : edgeColor,
            width           : e.wb || 1,
            arrows          : arrowConfig,
            smooth          : {enabled: false},
            // *** updated | dashes:false for all edges including RSME-only (now green solid)
            dashes          : false,
            hidden          : true,
        });
        existingEids.add(eid);
    });
    if (consolidatedToAdd.length > 0) edges.add(consolidatedToAdd);

    // ── Add self-loop edges (TT self-transfers) ───────────────────────────
    var selfLoopToAdd = [];
    selfLoopEdgesData.forEach(function(e) {
        var eid = "selfloop_" + e.uen;
        if (existingEids.has(eid)) return;
        selfLoopToAdd.push({
            id           : eid,
            from         : e.uen,
            to           : e.uen,
            _isSelfLoop  : true,
            _rsmeOnly    : false,
            _isBoth      : false,
            _inPayment   : true,
            _all_txn_count : e._all_txn_count || 0,
            _all_txn_amt   : e._all_txn_amt   || 0,
            _baseWidth   : 2,
            color        : {
                color    : CFG.consol_tt_edge_color,
                opacity  : CFG.consol_tt_edge_opacity,
                highlight: CFG.consol_tt_edge_highlight_color,
            },
            width        : 2,
            arrows       : {to: {enabled: false}},
            selfReference: {size: 20, angle: Math.PI / 4},
            smooth       : {enabled: true, type: "curvedCW", roundness: 0.5},
            dashes       : false,
            hidden       : true,
        });
        existingEids.add(eid);
    });
    if (selfLoopToAdd.length > 0) edges.add(selfLoopToAdd);
}

ensureAllNetworksInVis();

// ══════════════════════════════════════════════════════════════════════════
// EDGE COLOR MANAGEMENT
// *** updated | RSME-only edges use CFG.rsme_edge_color (green).
// All other edges use CFG.consol_tt_edge_color (blue).
// Branch on _rsmeOnly in all color reset/highlight paths.
// ══════════════════════════════════════════════════════════════════════════

function _edgeRestColor(e) {
    // *** helper | returns the at-rest color object for any edge
    if (e._rsmeOnly) {
        return {
            color  : CFG.rsme_edge_color,
            opacity: CFG.rsme_edge_opacity,
        };
    }
    return {
        color  : CFG.consol_tt_edge_color,
        opacity: CFG.consol_tt_edge_opacity,
    };
}

function resetEdgeColors() {
    var upd = edges.get()
        .filter(function(e) { return !e.hidden; })
        .map(function(e) {
            return {
                id   : e.id,
                width: e._baseWidth !== undefined ? e._baseWidth : (e.width || 1),
                color: _edgeRestColor(e),
            };
        });
    edges.update(upd);
}

// ══════════════════════════════════════════════════════════════════════════
// NODE HIGHLIGHTING
// ══════════════════════════════════════════════════════════════════════════

var _lastHighlighted     = null;
var _lastHighlightedEdge = null;

function _resetLastEdgeHighlight() {
    if (_lastHighlightedEdge === null) return;
    var e = edges.get(_lastHighlightedEdge);
    if (e) {
        edges.update({
            id   : _lastHighlightedEdge,
            width: e._baseWidth !== undefined ? e._baseWidth : (e.width || 1),
            // *** updated | restore correct color per edge type
            color: _edgeRestColor(e),
        });
    }
    _lastHighlightedEdge = null;
}

function highlightNode(id) {
    _resetLastEdgeHighlight();
    if (_lastHighlighted !== null) {
        nodes.update({id: _lastHighlighted, shadow: {enabled: false}});
        resetEdgeColors();
    }
    if (!id) { _lastHighlighted = null; return; }

    // Glow colour matches the node's own background colour so each customer
    // type / Malaysian square gets a halo in its own brand colour. Falls
    // back to CFG default if the node has no readable colour.
    var _nodeForGlow = nodes.get(id);
    var glowColor    = (_nodeForGlow && _nodeForGlow.color && _nodeForGlow.color.background)
                       ? _nodeForGlow.color.background
                       : CFG.node_selected_shadow_color;
    nodes.update({id: id, shadow: {
        enabled: true,
        color  : glowColor,
        size   : CFG.node_selected_shadow_size,
        x      : 0,
        y      : 0,
    }});

    var upd = [];
    edges.get().forEach(function(e) {
        if (e.hidden) return;
        if (e.from !== id && e.to !== id) return;
        var bw = e._baseWidth !== undefined ? e._baseWidth : (e.width || 1);
        if (e._rsmeOnly) bw = bw * CFG.rsme_edge_highlight_mult;
        // *** updated | RSME-only uses rsme highlight color, others use tt highlight color
        upd.push({
            id   : e.id,
            width: bw,
            color: {
                color  : e._rsmeOnly
                         ? CFG.rsme_edge_highlight_color
                         : CFG.consol_tt_edge_highlight_color,
                opacity: e._rsmeOnly
                         ? CFG.rsme_edge_highlight_opacity
                         : CFG.consol_tt_edge_highlight_opacity,
            },
        });
    });
    edges.update(upd);
    _lastHighlighted = id;
}

// ══════════════════════════════════════════════════════════════════════════
// NETWORK CLICK HANDLERS
// ══════════════════════════════════════════════════════════════════════════

network.setOptions({ edges: { chosen: false } });

network.on("click", function(params) {
    if (params.nodes.length > 0) {
        var clickedId  = params.nodes[0];
        var clickedUid = _d(clickedId);

        _resetLastEdgeHighlight();
        highlightNode(clickedId);
        currentNode = clickedUid;
        showNodeInfo(clickedUid);
        network.selectNodes([clickedId]);
        console.log("Node clicked:", clickedId, "->", clickedUid);

    } else if (params.edges.length > 0) {
        if (_lastHighlighted !== null) {
            nodes.update({id: _lastHighlighted, shadow: {enabled: false}});
            _lastHighlighted = null;
        }
        resetEdgeColors();

        var eid  = params.edges[0];
        var edge = edges.get(eid);
        if (edge) {
            var bw = edge._baseWidth !== undefined ? edge._baseWidth : (edge.width || 1);
            if (edge._rsmeOnly) bw = bw * CFG.rsme_edge_highlight_mult;
            // *** updated | edge click highlight also branches on _rsmeOnly
            edges.update({
                id   : eid,
                width: bw,
                color: {
                    color  : edge._rsmeOnly
                             ? CFG.rsme_edge_highlight_color
                             : CFG.consol_tt_edge_highlight_color,
                    opacity: edge._rsmeOnly
                             ? CFG.rsme_edge_highlight_opacity
                             : CFG.consol_tt_edge_highlight_opacity,
                },
            });
            _lastHighlightedEdge = eid;

            if (edge._isSelfLoop) {
                showSelfLoopInfo(edge);
            } else {
                showEdgeInfo(edge);
            }

            console.log("Edge clicked:", eid,
                "rsmeOnly:", !!edge._rsmeOnly,
                "isBoth:",   !!edge._isBoth);
        }

    } else {
        _resetLastEdgeHighlight();
        if (_lastHighlighted !== null) {
            nodes.update({id: _lastHighlighted, shadow: {enabled: false}});
            _lastHighlighted = null;
        }
        resetEdgeColors();
        clearSidePanel();
    }
});

network.on("doubleClick", function(params) {
    if (params.nodes.length > 0) {
        var clickedId = params.nodes[0];
        navigateToNode(_d(clickedId));
        console.log("Node double-clicked:", clickedId, "->", _d(clickedId));
    }
});
"""
