# ── network_graph/viz/js_export.py ───────────────────────────────────────────
# Export current visible subgraph as a self-contained HTML file for sharing.
# Faithfully replicates the main app's vis.js style and click behaviour.
#
# *** updated | showEdgeInfo unified -- same as js_sidepanel.py
# *** updated | mini pairRelationshipMap exported for visible pairs only
# *** updated | totalNbs uses Set union for unique count
# *** updated | removed showUndirectedEdgeInfo / showDirectedEdgeInfo
# *** updated | MFI financials section added to showNodeInfo
# *** updated | CIP collaterals section added to showNodeInfo
# *** updated | ACC_DEFAULT includes mfifin and cipinfo
# *** updated | fmtRatio() helper added for MFI ratio cols


def get_js_export():
    return r"""
// ══════════════════════════════════════════════════════════════════════════
// EXPORT CURRENT VIEW
// ══════════════════════════════════════════════════════════════════════════

(function() {
    var _btn = document.getElementById("export-btn");
    if (!_btn) {
        console.error("[Export] export-btn element missing -- handler not wired.");
        return;
    }
    _btn.addEventListener("click", function() {
        console.log("[Export] button clicked");
        exportCurrentView();
    });
})();

function exportCurrentView() {
    console.log("[Export] exportCurrentView() entered. _visibleNodes.size =",
        (_visibleNodes && _visibleNodes.size) || 0);

    if (!_visibleNodes || _visibleNodes.size === 0) {
        alert("Nothing to export. Please search for a company first.");
        return;
    }

    var btn = document.getElementById("export-btn");
    btn.disabled    = true;
    btn.textContent = "Exporting...";

    try {
        var visibleArr = Array.from(_visibleNodes);
        var toShow     = new Set(visibleArr);
        console.log("[Export] visible nodes:", visibleArr.length, "edges:", _visibleEdges.size);

        // ── 1. Accurate canvas positions ──────────────────────────────────
        var positions = network.getPositions(visibleArr);

        // ── 2. Collect node data ──────────────────────────────────────────
        var xnodes = [];
        var xmeta  = {}, xtypes = {}, xnames = {}, xuens = {};
        var xttsum = {}, xfsum  = {}, xpsum = {}, xasum = {};

        visibleArr.forEach(function(id) {
            var vn  = nodes.get(id);
            if (!vn) return;
            var pos = positions[id] || {x: 0, y: 0};
            var uen = _d(id);
            var nt  = nodeTypeMap[id] || "Non-Maybank Customer";
            var nm  = idNameLookup[id] || uen;
            var mt  = nodeMetaMap[id]  || {};
            var col = nt === "Maybank Trade Customer"     ? colorTradeMB    :
                      nt === "Maybank Non-Trade Customer" ? colorNonTradeMB :
                      colorNonMB;
            var shp = (mt.source_country === "MY") ? "square" : "dot";

            xnodes.push({id: id, uen: uen, name: nm, type: nt,
                color: col, shape: shp, size: vn.size || 10,
                x: pos.x, y: pos.y});
            xmeta[id]  = mt;
            xtypes[id] = nt;
            xnames[id] = nm;
            xuens[id]  = uen;
            xttsum[id] = consolTTNodeSummary[id] || null;
            xfsum[id]  = fitasNodeSummary[id]    || null;
            xpsum[id]  = (typeof paymentNodeSummary !== "undefined" ? paymentNodeSummary[id] : null) || null;
            xasum[id]  = (typeof allTxnNodeSummary  !== "undefined" ? allTxnNodeSummary[id]  : null) || null;
        });

        // ── 3. Collect edge data from vis.js DataSet ──────────────────────
        var xedges = [];
        _visibleEdges.forEach(function(eid) {
            var e = edges.get(eid);
            if (!e) return;
            xedges.push({
                id             : e.id,
                from           : e.from,
                to             : e.to,
                _rsmeOnly      : e._rsmeOnly      || false,
                _isBoth        : e._isBoth        || false,
                _isSelfLoop    : e._isSelfLoop     || false,
                _inRsme        : e._inRsme         || false,
                _inFitas       : e._inFitas        || false,
                _inAA          : e._inAA           || false,
                _inTT          : e._inTT           || false,
                _inPayment     : e._inPayment      || false,
                _isUndirected  : e._isUndirected   || false,
                _isDirected    : e._isDirected     || false,
                _rsme_ab       : e._rsme_ab        || false,
                _rsme_ba       : e._rsme_ba        || false,
                _aa_ab         : e._aa_ab          || false,
                _aa_ba         : e._aa_ba          || false,
                _fitas_ab_count: e._fitas_ab_count || 0,
                _fitas_ab_amt  : e._fitas_ab_amt   || 0,
                _fitas_ba_count: e._fitas_ba_count || 0,
                _fitas_ba_amt  : e._fitas_ba_amt   || 0,
                _tt_ab_count   : e._tt_ab_count    || 0,
                _tt_ab_amt     : e._tt_ab_amt      || 0,
                _tt_ba_count   : e._tt_ba_count    || 0,
                _tt_ba_amt     : e._tt_ba_amt      || 0,
                _tt_total_count: e._tt_total_count || 0,
                _tt_net_amt    : e._tt_net_amt     || 0,
                _all_txn_count : e._all_txn_count  || 0,
                _all_txn_amt   : e._all_txn_amt    || 0,
                _baseWidth     : e._baseWidth      || 1,
            });
        });

        // ── 4. Mini adjacency maps from pairRelationshipMap ───────────────
        var radj   = {}, ttout  = {}, ttin   = {};
        var fitout = {}, fitin  = {}, aaout  = {}, aain = {};
        var rsmeIds = [], ttIds  = [], fitIds = [], aaIds = [];
        var ttself  = [], fitself= [], aaself = [];

        function _adj(map, a, b) {
            if (!map[a]) map[a] = [];
            if (map[a].indexOf(b) < 0) map[a].push(b);
        }

        Object.values(pairRelationshipMap).forEach(function(e) {
            if (!toShow.has(e.fr) || !toShow.has(e.to)) return;
            if (!_visibleEdges.has("consolidated_" + e.fr + "_" + e.to)) return;

            if (e.ir) {
                _adj(radj, e.fr, e.to); _adj(radj, e.to, e.fr);
                if (rsmeIds.indexOf(e.fr)  < 0) rsmeIds.push(e.fr);
                if (rsmeIds.indexOf(e.to)  < 0) rsmeIds.push(e.to);
            }
            if (e.ia) {
                if (e._aa_ab) { _adj(aaout, e.fr, e.to); _adj(aain, e.to, e.fr); }
                if (e._aa_ba) { _adj(aaout, e.to, e.fr); _adj(aain, e.fr, e.to); }
                if (aaIds.indexOf(e.fr) < 0) aaIds.push(e.fr);
                if (aaIds.indexOf(e.to) < 0) aaIds.push(e.to);
            }
            if (e['if']) {
                if (e._fitas_ab_count > 0) { _adj(fitout, e.fr, e.to); _adj(fitin, e.to, e.fr); }
                if (e._fitas_ba_count > 0) { _adj(fitout, e.to, e.fr); _adj(fitin, e.fr, e.to); }
                if (fitIds.indexOf(e.fr) < 0) fitIds.push(e.fr);
                if (fitIds.indexOf(e.to) < 0) fitIds.push(e.to);
            }
            if (e.if_pay) {
                _adj(ttout, e.fr, e.to); _adj(ttin, e.to, e.fr);
                if (ttIds.indexOf(e.fr) < 0) ttIds.push(e.fr);
                if (ttIds.indexOf(e.to) < 0) ttIds.push(e.to);
            }
        });

        selfLoopEdgesData.forEach(function(e) {
            if (!toShow.has(e.uen)) return;
            if (!_visibleEdges.has("selfloop_" + e.uen)) return;
            if (ttIds.indexOf(e.uen)  < 0) ttIds.push(e.uen);
            if (ttself.indexOf(e.uen) < 0) ttself.push(e.uen);
        });
        fitasSelfLoopIds.forEach(function(id) {
            if (toShow.has(id)) {
                if (fitIds.indexOf(id)  < 0) fitIds.push(id);
                if (fitself.indexOf(id) < 0) fitself.push(id);
            }
        });
        aaPaperSelfLoopIds.forEach(function(id) {
            if (toShow.has(id)) {
                if (aaIds.indexOf(id)  < 0) aaIds.push(id);
                if (aaself.indexOf(id) < 0) aaself.push(id);
            }
        });

        // FAST / GIRO / Payment: derive directly from canonical sets filtered
        // to the visible subgraph. Matches the main app's `fastNodeIds.has(id)`
        // / `giroNodeIds.has(id)` Data Sources checks. (We do not iterate
        // edges for these because FAST/GIRO are sub-types of Payment, and
        // edge-flag membership would miss self-loop-only nodes.)
        var fastIds = [], giroIds = [];
        if (typeof fastNodeIds !== "undefined") {
            fastNodeIds.forEach(function(id) {
                if (toShow.has(id)) fastIds.push(id);
            });
        }
        if (typeof giroNodeIds !== "undefined") {
            giroNodeIds.forEach(function(id) {
                if (toShow.has(id)) giroIds.push(id);
            });
        }

        // ── 4b. Mini pairRelationshipMap for visible pairs only ───────────
        var xpairs = {};
        _visibleEdges.forEach(function(eid) {
            if (eid.indexOf("selfloop_") === 0) return;
            var e = edges.get(eid);
            if (!e) return;
            var key = [parseInt(e.from), parseInt(e.to)].sort(function(a,b){return a-b;}).join('_');
            var rel = pairRelationshipMap[key];
            if (rel) xpairs[key] = rel;
        });

        // ── 5. CFG edge values needed in export ───────────────────────────
        var xcfg = {
            rsme_edge_color                  : CFG.rsme_edge_color,
            rsme_edge_opacity                : CFG.rsme_edge_opacity,
            rsme_edge_highlight_color        : CFG.rsme_edge_highlight_color,
            rsme_edge_highlight_opacity      : CFG.rsme_edge_highlight_opacity,
            rsme_edge_highlight_mult         : CFG.rsme_edge_highlight_mult,
            consol_tt_edge_color             : CFG.consol_tt_edge_color,
            consol_tt_edge_opacity           : CFG.consol_tt_edge_opacity,
            consol_tt_edge_highlight_color   : CFG.consol_tt_edge_highlight_color,
            consol_tt_edge_highlight_opacity : CFG.consol_tt_edge_highlight_opacity,
            consol_tt_edge_smooth_roundness  : CFG.consol_tt_edge_smooth_roundness,
        };

        // ── 6. Focal company + filename ───────────────────────────────────
        var focalUEN  = currentNode || null;
        var focalName = focalUEN ? (idNameLookup[_e(focalUEN)] || focalUEN) : "";
        var now       = new Date();
        var dd        = String(now.getDate()).padStart(2,"0");
        var mm        = String(now.getMonth()+1).padStart(2,"0");
        var yyyy      = now.getFullYear();
        var dateStr   = dd + mm + yyyy;
        var filename  = "MEXT_" + focalName.replace(/[^a-zA-Z0-9]/g,"_").slice(0,40)
                        + "_" + dateStr + ".html";

        // ── 7. Serialise all into one payload ─────────────────────────────
        // ── Per-source self-loop maps for visible nodes ───────────────────
        var xpsl = {}, xfsl = {}, xasl = {};
        if (typeof paymentSelfLoopEdgesData !== "undefined") {
            paymentSelfLoopEdgesData.forEach(function(e) {
                if (toShow.has(e.uen)) xpsl[e.uen] = e;
            });
        }
        if (typeof fitasSelfLoopEdgesData !== "undefined") {
            fitasSelfLoopEdgesData.forEach(function(e) {
                if (toShow.has(e.uen)) xfsl[e.uen] = e;
            });
        }
        if (typeof allTxnSelfLoopEdgesData !== "undefined") {
            allTxnSelfLoopEdgesData.forEach(function(e) {
                if (toShow.has(e.uen)) xasl[e.uen] = e;
            });
        }

        var payload = JSON.stringify({
            nodes  : xnodes,
            edges  : xedges,
            meta   : xmeta,
            types  : xtypes,
            names  : xnames,
            uens   : xuens,
            ttsum  : xttsum,
            fsum   : xfsum,
            psum   : xpsum,
            asum   : xasum,
            psl    : xpsl,
            fsl    : xfsl,
            asl    : xasl,
            rsmeIds: rsmeIds,
            ttIds  : ttIds,
            fitIds : fitIds,
            aaIds  : aaIds,
            fastIds: fastIds,
            giroIds: giroIds,
            ttself : ttself,
            fitself: fitself,
            aaself : aaself,
            radj   : radj,
            ttout  : ttout,
            ttin   : ttin,
            fitout : fitout,
            fitin  : fitin,
            aaout  : aaout,
            aain   : aain,
            pairs  : xpairs,
            cfg    : xcfg,
            fc     : fieldConfig,
            af     : Array.from(AMT_FIELDS),
            sc     : segmentColors,
            colors : {trade: colorTradeMB, nontrade: colorNonTradeMB,
                      nonmb: colorNonMB,   my: colorMalaysian},
            focal  : {name: focalName, uen: focalUEN},
            date   : dateStr,
            nc     : xnodes.length,
            ec     : xedges.length,
        });

        // ── 8. Build + download ───────────────────────────────────────────
        // Blob URL + <a download> -- cross-browser file delivery without
        // requiring any server round-trip.
        var html = buildExportHTML(payload, filename);
        var blob = new Blob([html], {type:"text/html;charset=utf-8"});
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement("a");
        a.href = url; a.download = filename;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function(){ URL.revokeObjectURL(url); }, 2000);
        console.log("[Export]", filename, xnodes.length+"n", xedges.length+"e");

    } catch(err) {
        console.error("[Export] FAILED:", err);
        console.error(err.stack);
        alert("Export failed: " + (err && err.message ? err.message : String(err)));
    } finally {
        btn.disabled = false;
        btn.textContent = "Export View";
    }
}

// ══════════════════════════════════════════════════════════════════════════
// BUILD EXPORT HTML
// ══════════════════════════════════════════════════════════════════════════

function buildExportHTML(payloadJson, filename) {
    var p = [];

    p.push('<!DOCTYPE html>');
    p.push('<html lang="en"><head>');
    p.push('<meta charset="UTF-8">');
    p.push('<meta name="viewport" content="width=device-width,initial-scale=1.0">');
    p.push('<title>M-EXT Export<\/title>');
    p.push('<script src="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js"><\/script>');
    p.push('<style>');
    p.push('*{box-sizing:border-box;margin:0;padding:0;}');
    p.push('html,body{font-family:Inter,"Segoe UI",Arial,sans-serif;background:#FBBA00;overflow:hidden;}');
    p.push('#tb{position:fixed;top:0;left:0;right:0;z-index:9999;background:#1C1C1C;');
    p.push('  padding:8px 20px;display:flex;align-items:center;justify-content:space-between;');
    p.push('  border-bottom:3px solid #FBBA00;height:54px;}');
    p.push('.tbl{display:flex;align-items:center;gap:12px;}');
    p.push('.tb-brand{font-size:16px;font-weight:700;color:#FBBA00;}');
    p.push('.tb-sep{width:1px;height:24px;background:#333;}');
    p.push('.tb-co{font-size:13px;font-weight:600;color:#fff;}');
    p.push('.tb-uen{font-size:11px;color:#666;}');
    p.push('.tbr{text-align:right;}');
    p.push('.tb-meta{font-size:10px;color:#555;}');
    p.push('.tb-conf{font-size:9px;font-weight:700;color:#FBBA00;letter-spacing:1px;text-transform:uppercase;margin-top:3px;}');
    p.push('#graph-card{position:fixed;top:54px;left:0;right:284px;bottom:32px;background:#FAFAFA;}');
    p.push('#mynetwork{width:100%;height:100%;}');
    p.push('#side-panel{position:fixed;top:54px;right:0;bottom:32px;width:284px;');
    p.push('  background:#fff;overflow-y:auto;padding:14px;border-left:1px solid #E8E8E8;');
    p.push('  font-family:Inter,"Segoe UI",Arial,sans-serif;}');
    p.push('#foot{position:fixed;bottom:0;left:0;right:0;height:32px;background:#fff;');
    p.push('  border-top:1px solid #e0e0e0;display:flex;align-items:center;');
    p.push('  justify-content:center;font-size:11px;font-weight:600;color:#cc0000;letter-spacing:0.3px;}');
    p.push('.company-main-card{background:#1C1C1C;border-radius:8px;padding:10px 12px;');
    p.push('  margin-bottom:10px;cursor:pointer;transition:opacity 0.15s;}');
    p.push('.company-main-card:hover{opacity:0.85;}');
    p.push('.company-main-card .cn{font-size:13px;font-weight:700;color:#fff;line-height:1.4;}');
    p.push('.company-main-card .cu{font-size:11px;color:#FBBA00;margin-top:2px;}');
    p.push('.nb-card{background:#fff;border-left:3px solid #FBBA00;border-radius:6px;');
    p.push('  padding:7px 10px;margin-bottom:6px;box-shadow:0 1px 4px rgba(0,0,0,0.07);');
    p.push('  cursor:pointer;transition:box-shadow 0.15s,transform 0.15s;}');
    p.push('.nb-card:hover{box-shadow:0 4px 12px rgba(0,0,0,0.14);transform:translateY(-1px);}');
    p.push('.nb-card .nb-name{font-size:12px;font-weight:600;color:#1C1C1C;line-height:1.3;}');
    p.push('.nb-card .nb-uen{font-size:10px;color:#888;margin-top:2px;}');
    p.push('.tt-card-ord{background:#EAF4FF;border-left:3px solid #2980b9;border-radius:6px;padding:10px 12px;margin-bottom:6px;}');
    p.push('.tt-card-bene{background:#EAFAF1;border-left:3px solid #27ae60;border-radius:6px;padding:10px 12px;margin-bottom:6px;}');
    p.push('.tt-card-ord .tt-title{font-size:12px;font-weight:700;color:#1a5276;margin-bottom:6px;}');
    p.push('.tt-card-bene .tt-title{font-size:12px;font-weight:700;color:#1e8449;margin-bottom:6px;}');
    p.push('.tt-row{display:flex;justify-content:space-between;font-size:11px;color:#555;margin-top:3px;}');
    p.push('.tt-card-ord .tt-val{font-weight:600;color:#1a5276;}');
    p.push('.tt-card-bene .tt-val{font-weight:600;color:#1e8449;}');
    p.push('.acc-header{display:flex;justify-content:space-between;align-items:center;');
    p.push('  padding:8px 10px;border-radius:6px;font-size:12px;font-weight:600;color:#333;');
    p.push('  cursor:pointer;user-select:none;transition:background 0.12s;border:none;}');
    p.push('.acc-header.closed{background:#C8C8C8;}');
    p.push('.acc-header.open{background:#FBDE6A;color:#1C1C1C;}');
    p.push('.info-table{width:100%;border-collapse:collapse;margin-top:4px;}');
    p.push('.info-table td{padding:5px 6px;font-size:11px;vertical-align:top;}');
    p.push('.info-table .lbl{color:#888;width:52%;}');
    p.push('.info-table .val{color:#1C1C1C;font-weight:500;text-align:right;}');
    p.push('.info-table .sec-hdr td{padding:6px 6px 3px;font-size:11px;font-weight:700;');
    p.push('  color:#555;background:#F5F5F5;border-top:1px solid #eee;}');
    p.push('.info-table tr:nth-child(even) td{background:#FAFAFA;}');
    p.push('#mynetwork{border:none !important;}');
    p.push('div.vis-network{border:none !important;}');
    // Legend dot + edge-shape primitives (shared between source page and export)
    p.push('.legend-dot{display:inline-block;width:7px;height:7px;border-radius:50%;vertical-align:middle;flex-shrink:0;}');
    p.push('.legend-line-rsme{display:inline-block;width:18px;height:0;border-top:2px solid #2f8744;vertical-align:middle;flex-shrink:0;}');
    p.push('.legend-line-directed{display:inline-flex;align-items:center;vertical-align:middle;flex-shrink:0;}');
    p.push('.legend-line-directed-shaft{display:inline-block;width:14px;height:2px;background:#2980b9;border-radius:1px 0 0 1px;}');
    p.push('.legend-line-directed-arrow{display:inline-block;width:0;height:0;border-top:4px solid transparent;border-bottom:4px solid transparent;border-left:5px solid #2980b9;}');
    p.push('.legend-line-both{display:inline-flex;align-items:center;vertical-align:middle;flex-shrink:0;}');
    p.push('.legend-line-both-arrowl{display:inline-block;width:0;height:0;border-top:4px solid transparent;border-bottom:4px solid transparent;border-right:5px solid #2980b9;}');
    p.push('.legend-line-both-shaft{display:inline-block;width:10px;height:2px;background:#2980b9;}');
    p.push('.legend-line-both-arrowr{display:inline-block;width:0;height:0;border-top:4px solid transparent;border-bottom:4px solid transparent;border-left:5px solid #2980b9;}');
    p.push('.legend-line-selfloop{display:inline-block;width:10px;height:10px;border:2px solid #2980b9;border-radius:50%;border-right-color:transparent;vertical-align:middle;flex-shrink:0;}');
    // Floating legend panel (collapsible <details>)
    p.push('#graph-legend{position:absolute;top:12px;left:12px;z-index:100;background:rgba(255,255,255,0.96);border:1px solid #E8E8E8;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.10);font-family:Inter,"Segoe UI",Arial,sans-serif;user-select:none;max-width:200px;font-size:10px;color:#333;}');
    p.push('#graph-legend > summary{display:flex;justify-content:space-between;align-items:center;padding:5px 9px;cursor:pointer;list-style:none;gap:10px;}');
    p.push('#graph-legend > summary::-webkit-details-marker{display:none;}');
    p.push('#graph-legend > summary::marker{display:none;content:"";}');
    p.push('#graph-legend[open] > summary{border-bottom:1px solid #EEE;}');
    p.push('#graph-legend .legend-title{font-weight:700;font-size:9.5px;color:#1C1C1C;letter-spacing:0.04em;text-transform:uppercase;}');
    p.push('#graph-legend .legend-toggle{color:#888;font-size:8.5px;line-height:1;}');
    p.push('#graph-legend .legend-toggle::before{content:"\\25B8";}');
    p.push('#graph-legend[open] .legend-toggle::before{content:"\\25BE";}');
    p.push('#graph-legend .legend-body{padding:6px 9px 8px;}');
    p.push('#graph-legend .legend-section-title{font-size:8.5px;font-weight:700;color:#888;letter-spacing:0.05em;text-transform:uppercase;margin:0 0 3px;}');
    p.push('#graph-legend .legend-section-title:not(:first-child){margin-top:6px;}');
    p.push('#graph-legend .legend-item{display:flex;align-items:center;gap:5px;font-size:10px;color:#333;margin-bottom:2px;}');
    p.push('#graph-legend .legend-item:last-child{margin-bottom:0;}');
    p.push('<\/style><\/head><body>');

    p.push('<div id="tb">');
    p.push('  <div class="tbl"><span class="tb-brand">M-EXT<\/span><div class="tb-sep"><\/div>');
    p.push('    <div><div class="tb-co" id="tb-co"><\/div><div class="tb-uen" id="tb-uen"><\/div><\/div><\/div>');
    p.push('  <div class="tbr"><div class="tb-meta" id="tb-meta"><\/div><div class="tb-conf">Strictly Confidential<\/div><\/div>');
    p.push('<\/div>');
    p.push('<div id="graph-card"><div id="mynetwork"><\/div>');
    p.push('  <details id="graph-legend">');
    p.push('    <summary>');
    p.push('      <span class="legend-title">Legend<\/span>');
    p.push('      <span class="legend-toggle"><\/span>');
    p.push('    <\/summary>');
    p.push('    <div class="legend-body">');
    p.push('      <div class="legend-section-title">Customer Type<\/div>');
    p.push('      <div class="legend-item"><span class="legend-dot" style="background:' + colorTradeMB    + ';"><\/span>Maybank Trade<\/div>');
    p.push('      <div class="legend-item"><span class="legend-dot" style="background:' + colorNonTradeMB + ';"><\/span>Maybank Non-Trade<\/div>');
    p.push('      <div class="legend-item"><span class="legend-dot" style="background:' + colorNonMB      + ';"><\/span>Non-Maybank<\/div>');
    p.push('      <div class="legend-item"><span class="legend-dot" style="background:' + colorMalaysian  + ';border-radius:2px;"><\/span>Malaysian Entity<\/div>');
    p.push('      <div class="legend-section-title">Edge Type<\/div>');
    p.push('      <div class="legend-item"><span class="legend-line-rsme"><\/span>RSME only<\/div>');
    p.push('      <div class="legend-item"><span class="legend-line-directed"><span class="legend-line-directed-shaft"><\/span><span class="legend-line-directed-arrow"><\/span><\/span>FITAS / AA / Payment<\/div>');
    p.push('      <div class="legend-item"><span class="legend-line-both"><span class="legend-line-both-arrowl"><\/span><span class="legend-line-both-shaft"><\/span><span class="legend-line-both-arrowr"><\/span><\/span>Both ways<\/div>');
    p.push('      <div class="legend-item"><span class="legend-line-selfloop"><\/span>Self-transfer<\/div>');
    p.push('    <\/div>');
    p.push('  <\/details>');
    p.push('<\/div>');
    p.push('<div id="side-panel"><div id="side-panel-content">');
    p.push('  <p style="color:#aaa;font-size:13px;text-align:center;margin-top:40px;">Click a node to view details.<\/p>');
    p.push('<\/div><\/div>');
    p.push('<div id="foot">&#128274; Internal Use Only &mdash; Strictly Confidential &mdash; Maybank M-EXT &mdash; Do not redistribute<\/div>');

    p.push('<script>');

    p.push('var _PL = ' + payloadJson + ';');
    p.push('var META    = _PL.meta;');
    p.push('var TYPES   = _PL.types;');
    p.push('var NAMES   = _PL.names;');
    p.push('var UENS    = _PL.uens;');
    p.push('var TTSUM   = _PL.ttsum;');
    p.push('var FSUM    = _PL.fsum;');
    p.push('var PSUM    = _PL.psum||{};');
    p.push('var ASUM    = _PL.asum||{};');
    p.push('var PSL     = _PL.psl||{};');
    p.push('var FSL     = _PL.fsl||{};');
    p.push('var ASL     = _PL.asl||{};');
    p.push('var RADJ    = _PL.radj;');
    p.push('var TTOUT   = _PL.ttout;');
    p.push('var TTIN    = _PL.ttin;');
    p.push('var FITOUT  = _PL.fitout;');
    p.push('var FITIN   = _PL.fitin;');
    p.push('var AAOUT   = _PL.aaout;');
    p.push('var AAIN    = _PL.aain;');
    p.push('var rsmeNodeIds         = new Set(_PL.rsmeIds);');
    p.push('var consolTTNodeIds     = new Set(_PL.ttIds);');
    p.push('var fitasNodeIds        = new Set(_PL.fitIds);');
    p.push('var aaPaperNodeIds      = new Set(_PL.aaIds);');
    // *** new | FAST/GIRO node-membership sets so the Data Sources panel in
    // the exported HTML shows the same 6 rows as the main app.
    p.push('var fastNodeIds         = new Set(_PL.fastIds||[]);');
    p.push('var giroNodeIds         = new Set(_PL.giroIds||[]);');
    p.push('var consolTTSelfLoopIds = new Set(_PL.ttself);');
    p.push('var fitasSelfLoopIds    = new Set(_PL.fitself);');
    p.push('var aaPaperSelfLoopIds  = new Set(_PL.aaself);');
    p.push('var CFG             = _PL.cfg;');
    p.push('var fieldConfig     = _PL.fc;');
    p.push('var AMT_FIELDS      = new Set(_PL.af);');
    p.push('var segmentColors   = _PL.sc;');
    p.push('var colorTradeMB    = _PL.colors.trade;');
    p.push('var colorNonTradeMB = _PL.colors.nontrade;');
    p.push('var colorNonMB      = _PL.colors.nonmb;');
    p.push('var colorMalaysian  = _PL.colors.my;');
    p.push('var consolTTNodeSummary = TTSUM;');
    p.push('var fitasNodeSummary    = FSUM;');
    p.push('var paymentNodeSummary  = PSUM;');
    p.push('var allTxnNodeSummary   = ASUM;');
    p.push('var idNameLookup        = NAMES;');
    p.push('var nodeMetaMap         = META;');
    p.push('var nodeTypeMap         = TYPES;');
    p.push('var adjacencyMap        = RADJ;');
    p.push('var consolTTOutAdj      = TTOUT;');
    p.push('var consolTTInAdj       = TTIN;');
    p.push('var fitasOutAdj         = FITOUT;');
    p.push('var fitasInAdj          = FITIN;');
    p.push('var aaPaperOutAdj       = AAOUT;');
    p.push('var aaPaperInAdj        = AAIN;');
    p.push('var currentNode = null;');

    p.push('var pairRelationshipMap = _PL.pairs;');
    p.push('function _getPairRel(idA,idB){var key=[parseInt(idA),parseInt(idB)].sort(function(a,b){return a-b;}).join("_");return pairRelationshipMap[key]||null;}');
    p.push('function fmtPct(v){if(v===null||v===undefined)return"-";return v.toFixed(1)+"%";}');
    // *** new | fmtRatio for MFI ratio cols
    p.push('function fmtRatio(v){if(v===null||v===undefined)return"-";if(typeof v==="number"&&isNaN(v))return"-";return parseFloat(v).toFixed(2);}');

    p.push('function _d(id){ return UENS[id] || id; }');
    p.push('var _UREV={}; Object.keys(UENS).forEach(function(k){_UREV[UENS[k]]=k;});');
    p.push('function _e(uid){ return _UREV[uid] || uid; }');

    p.push('function escXml(s){if(!s)return"";return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/\'/g,"&#39;");}');
    p.push('function fmtVal(v){if(v===null||v===undefined)return"-";if(typeof v==="string")return v.trim()||"-";if(typeof v==="number")return v.toLocaleString(undefined,{maximumFractionDigits:0});return String(v).trim()||"-";}');
    p.push('function fmtAmt(v){if(v===null||v===undefined)return"-";if(v<0)return"-S$"+Math.abs(Math.round(v)).toLocaleString();return"S$"+Math.round(v).toLocaleString();}');
    p.push('function fmtUSD(v){if(v===null||v===undefined)return"-";if(typeof v==="number"&&isNaN(v))return"-";if(v<0)return"-$"+Math.abs(Math.round(v)).toLocaleString();return"$"+Math.round(v).toLocaleString();}');
    p.push('function getTypeColor(t){if(t==="Maybank Trade Customer")return colorTradeMB;if(t==="Maybank Non-Trade Customer")return colorNonTradeMB;return colorNonMB;}');
    p.push('function flagBadge(v){var a=(v===1);return"<span style=\'background:"+(a?"#fadbd8":"#e8e8e8")+";color:"+(a?"#922b21":"#888")+";padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;\'>"+(a?"Yes":"No")+"<\/span>";}');
    p.push('function stageBadge(v){if(!v&&v!==0)return"-";var s=v.toString().trim(),bg="#e8e8e8",tc="#555";if(s.indexOf("1")!==-1){bg="#d5f5e3";tc="#1e8449";}else if(s.indexOf("2")!==-1){bg="#fef3cd";tc="#856404";}else if(s.indexOf("3")!==-1){bg="#fadbd8";tc="#922b21";}return"<span style=\'background:"+bg+";color:"+tc+";padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;\'>"+escXml(s)+"<\/span>";}');
    p.push('function tRow(l,v){return"<tr><td class=\'lbl\'>"+escXml(l)+"<\/td><td class=\'val\'>"+fmtVal(v)+"<\/td><\/tr>";}');
    p.push('function tSection(l){return"<tr class=\'sec-hdr\'><td colspan=\'2\'>"+escXml(l)+"<\/td><\/tr>";}');
    p.push('function renderRow(k,meta){if(!fieldConfig[k])return"";var label=fieldConfig[k].label;if(k==="impairment_stage")return"<tr><td class=\'lbl\'>"+escXml(label)+"<\/td><td class=\'val\'>"+stageBadge(meta[k])+"<\/td><\/tr>";if(k==="is_watchlist"||k==="is_special_mention"||k==="is_npl")return"<tr><td class=\'lbl\'>"+escXml(label)+"<\/td><td class=\'val\'>"+flagBadge(meta[k])+"<\/td><\/tr>";if(AMT_FIELDS.has(k))return"<tr><td class=\'lbl\'>"+escXml(label)+"<\/td><td class=\'val\'>"+fmtAmt(meta[k])+"<\/td><\/tr>";return tRow(label,meta[k]);}');

    p.push('var _accSt={};');
    // *** updated | mfifin removed from ACC_DEFAULT (now a subsection of financials)
    p.push('var ACC_DEFAULT={overview:true,datasources:false,fitas_summary:false,payment_summary:false,all_txn_summary:false,facilities:false,creditstatus:false,financials:false,cipinfo:false,network_rsme:false,network_fitas:false,network_payment:false,network_aa_paper:false};');
    p.push('function getAccStates(){return Object.assign({},ACC_DEFAULT,_accSt);}');
    p.push('function setAccState(id,v){_accSt[id]=v;}');
    p.push('function makeAccSection(id,title,content,isOpen){');
    p.push('  return"<div style=\'margin-bottom:8px;\'>"+');
    p.push('  "<div id=\'acc-hdr-"+id+"\' class=\'acc-header "+(isOpen?"open":"closed")+"\'>"+');
    p.push('  "<span>"+escXml(title)+"<\/span>"+');
    p.push('  "<span id=\'acc-arrow-"+id+"\'>"+(isOpen?"&#9660;":"&#9654;")+"<\/span><\/div>"+');
    p.push('  "<div id=\'acc-body-"+id+"\' style=\'display:"+(isOpen?"block":"none")+";padding:4px 2px;\'>"+content+"<\/div><\/div>";}');
    p.push('function attachAccordion(id){');
    p.push('  var hdr=document.getElementById("acc-hdr-"+id);');
    p.push('  var body=document.getElementById("acc-body-"+id);');
    p.push('  var arr=document.getElementById("acc-arrow-"+id);');
    p.push('  if(!hdr||!body)return;');
    p.push('  hdr.addEventListener("click",function(){');
    p.push('    var isOpen=body.style.display!=="none";');
    p.push('    body.style.display=isOpen?"none":"block";');
    p.push('    if(arr)arr.innerHTML=isOpen?"&#9654;":"&#9660;";');
    p.push('    hdr.className=isOpen?"acc-header closed":"acc-header open";');
    p.push('    setAccState(id,!isOpen);});');
    p.push('}');

    p.push('function _nbCard(cardId,nbId,borderColor){');
    p.push('  var uen=_d(nbId), nm=idNameLookup[nbId]||uen;');
    p.push('  return"<div id=\'"+cardId+"\' class=\'nb-card\' style=\'border-left-color:"+borderColor+";\'>"+');
    p.push('  "<div class=\'nb-name\'>"+escXml(nm)+"<\/div>"+');
    p.push('  "<div class=\'nb-uen\'>"+escXml(uen)+"<\/div><\/div>";}');

    p.push('function _eRow(l,v){return"<div style=\'display:flex;justify-content:space-between;align-items:flex-start;padding:4px 0;font-size:13px;gap:8px;\'>"+');
    p.push('  "<span style=\'color:#888;flex-shrink:0;white-space:nowrap;\'>"+escXml(l)+"<\/span>"+');
    p.push('  "<span style=\'font-weight:500;color:#222;text-align:right;word-break:break-word;max-width:65%;\'>"+v+"<\/span><\/div>";}');

    p.push('function clearSidePanel(){document.getElementById("side-panel-content").innerHTML="<p style=\'color:#aaa;font-size:13px;text-align:center;margin-top:40px;\'>Click a node to view details.<\/p>";}');
    p.push('function makeSegmentBadge(meta){if(!meta||parseInt(meta.IS_MAYBANK_CUSTOMER)!==1)return"";var seg=(meta.FINAL_CLASSIFICATION||"").trim()||"Unknown";var colors=segmentColors[seg]||segmentColors["Unknown"]||{bg:"#eee",text:"#333"};return"<span style=\'background:"+colors.bg+";color:"+colors.text+";padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;\'>"+escXml(seg)+"<\/span>";}');
    p.push('function makeExMaybankBadge(meta){if(!meta)return"";var flag=meta.CIF_ACTIVE_FLAG;if(flag===null||flag===undefined)return"";if(parseInt(flag)===0)return"<span style=\'background:#555;color:#FFD700;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;\'>Ex-Maybank<\/span>";return"";}');

    // unified showEdgeInfo
    p.push('function showEdgeInfo(edge){');
    p.push('  var rel=_getPairRel(edge.from,edge.to);');
    p.push('  var nameFrom=idNameLookup[edge.from]||_d(edge.from),nameTo=idNameLookup[edge.to]||_d(edge.to);');
    p.push('  var nameLeft,nameRight,roleLeft,roleRight,arrowHtml,centerLabel;');
    p.push('  var isRSMEOnly=!rel||(rel&&!rel["id"]);');
    p.push('  var isBoth=rel&&!!rel.ib;');
    p.push('  var isDirected=!isRSMEOnly&&!isBoth;');
    p.push('  if(isRSMEOnly){');
    p.push('    if(rel&&rel.cu){nameLeft=idNameLookup[rel.cu]||_d(rel.cu)||nameFrom;nameRight=idNameLookup[rel.cou]||_d(rel.cou)||nameTo;}');
    p.push('    else{nameLeft=nameFrom;nameRight=nameTo;}');
    p.push('    roleLeft="Customer";roleRight="Counterparty";centerLabel="";');
    p.push('    arrowHtml="<div style=\'height:2px;background:#E8860A;border-radius:2px;width:100%;margin:0 4px;\'><\/div>";');
    p.push('  }else if(isBoth){');
    p.push('    nameLeft=nameFrom;nameRight=nameTo;roleLeft="";roleRight="";centerLabel="Both Ways";');
    p.push('    arrowHtml="<span style=\'color:#E8860A;font-size:22px;line-height:1;font-weight:700;\'>&#8596;<\/span>";');
    p.push('  }else{');
    p.push('    var buyerId=rel.bu,supplierId=rel.su;');
    p.push('    nameLeft=buyerId?(idNameLookup[buyerId]||_d(buyerId)):nameFrom;');
    p.push('    nameRight=supplierId?(idNameLookup[supplierId]||_d(supplierId)):nameTo;');
    p.push('    roleLeft="";roleRight="";centerLabel="Pays To";');
    p.push('    arrowHtml="<span style=\'color:#E8860A;font-size:22px;line-height:1;font-weight:700;\'>&#10230;<\/span>";');
    p.push('  }');
    p.push('  var html="<div style=\'background:#1C1C1C;border-radius:10px;padding:14px 16px 12px;margin-bottom:6px;box-shadow:0 2px 8px rgba(0,0,0,0.25);\'>"+');
    p.push('    "<table style=\'width:100%;border-collapse:collapse;\'>"+');
    p.push('    "<tr><td style=\'width:38%;text-align:right;padding-bottom:4px;\'>"+(roleLeft?"<span style=\'font-size:10px;font-weight:700;color:#FFD966;letter-spacing:0.8px;text-transform:uppercase;\'>"+escXml(roleLeft)+"<\/span>":"")+"<\/td>"+');
    p.push('    "<td style=\'width:24%;text-align:center;padding-bottom:4px;\'>"+(centerLabel?"<span style=\'font-size:10px;font-weight:700;color:#FFD966;letter-spacing:0.8px;text-transform:uppercase;\'>"+escXml(centerLabel)+"<\/span>":"")+"<\/td>"+');
    p.push('    "<td style=\'width:38%;text-align:left;padding-bottom:4px;\'>"+(roleRight?"<span style=\'font-size:10px;font-weight:700;color:#FFD966;letter-spacing:0.8px;text-transform:uppercase;\'>"+escXml(roleRight)+"<\/span>":"")+"<\/td><\/tr>"+');
    p.push('    "<tr><td style=\'width:38%;text-align:right;vertical-align:middle;padding-right:8px;\'>"+');
    p.push('    "<span style=\'font-size:12px;font-weight:700;color:#ffffff;word-break:break-word;line-height:1.4;\'>"+escXml(nameLeft)+"<\/span><\/td>"+');
    p.push('    "<td style=\'width:24%;text-align:center;vertical-align:middle;padding:0 2px;\'>"+arrowHtml+"<\/td>"+');
    p.push('    "<td style=\'width:38%;text-align:left;vertical-align:middle;padding-left:8px;\'>"+');
    p.push('    "<span style=\'font-size:12px;font-weight:700;color:#ffffff;word-break:break-word;line-height:1.4;\'>"+escXml(nameRight)+"<\/span><\/td><\/tr><\/table><\/div>";');
    p.push('  html+="<div style=\'background:#ffffff;border:1px solid #e0e0e0;border-radius:10px;overflow:hidden;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,0.06);\'>";');
    p.push('  var inAA=rel?!!rel.ia:!!(edge._aa_ab||edge._aa_ba);');
    p.push('  var inRSME=rel?!!rel.ir:!!(edge._rsme_ab||edge._rsme_ba);');
    p.push('  html+="<div style=\'background:#4A235A;padding:8px 14px;\'>"+');
    p.push('    "<span style=\'font-size:10.5px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:0.5px;\'>Declared Counterparty Info<\/span><\/div>"+');
    p.push('    "<div style=\'display:flex;justify-content:space-between;align-items:center;padding:8px 14px;border-bottom:1px solid #f0f0f0;background:#fdf8ff;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#555;\'>AA Paper<\/span>"+');
    p.push('    "<span style=\'font-size:15px;font-weight:700;color:"+(inAA?"#27ae60":"#bbb")+";\'>"+(inAA?"&#10003;":"&#8212;")+"<\/span><\/div>"+');
    p.push('    "<div style=\'display:flex;justify-content:space-between;align-items:center;padding:8px 14px;background:#fdf8ff;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#555;\'>RSME Supplier/Buyer Checklist<\/span>"+');
    p.push('    "<span style=\'font-size:15px;font-weight:700;color:"+(inRSME?"#27ae60":"#bbb")+";\'>"+(inRSME?"&#10003;":"&#8212;")+"<\/span><\/div>";');
    p.push('  var inFitas=rel?!!rel["if"]:!!((edge._fitas_ab_count&&edge._fitas_ab_count>0)||(edge._fitas_ba_count&&edge._fitas_ba_count>0));');
    p.push('  var inPayment=rel?!!rel.if_pay:!!edge._inPayment;');
    p.push('  var fitasTotalAmt=(rel&&rel.fta!=null)?rel.fta:null;');
    p.push('  var paymentTotalAmt=(rel&&rel._payment_total_amt!=null)?rel._payment_total_amt:null;');
    p.push('  var grandTotal=(rel&&rel.gta!=null)?rel.gta:null;');
    p.push('  html+="<div style=\'background:#5D3A1A;padding:8px 14px;margin-top:1px;\'>"+');
    p.push('    "<span style=\'font-size:10.5px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:0.5px;\'>Trade &amp; Payment Transactions<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 90px;padding:5px 14px 3px;background:#fdf6f0;\'>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;\'>Source<\/span>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Amount<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 90px;padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#555;\'>Trade Transactions (FITAS)<\/span>"+');
    p.push('    "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(inFitas&&fitasTotalAmt!=null?fmtAmt(fitasTotalAmt):"-")+"<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 90px;padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#555;\'>Payment Transactions (TT/MEPS/FAST/GIRO)<\/span>"+');
    p.push('    "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(inPayment&&paymentTotalAmt!=null?fmtAmt(paymentTotalAmt):"-")+"<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 90px;padding:7px 14px;border-top:1px solid #d0c0b0;background:#f5ede4;\'>"+');
    p.push('    "<span style=\'font-size:11px;font-weight:700;color:#222;\'>Total<\/span>"+');
    p.push('    "<span style=\'font-size:11px;font-weight:700;color:#222;text-align:right;\'>"+(grandTotal!=null?fmtAmt(grandTotal):"-")+"<\/span><\/div>";');
    p.push('  var _PROD_LABELS={lc:"LC",tr:"TR",sta:"STA",exportlc:"ExportLC",fbep:"FBEP",oat:"OAT",others:"Others"};');
    p.push('  html+="<div style=\'background:#1A5C2B;padding:8px 14px;margin-top:1px;\'>"+');
    p.push('    "<span style=\'font-size:10.5px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:0.5px;\'>Trade Transactions (FITAS)<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:5px 14px 3px;background:#f0f9f2;\'>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;\'>Product<\/span>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Count<\/span>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Amount<\/span><\/div>";');
    p.push('  if(inFitas&&rel){');
    p.push('    var fitasRows=[],fitasTotCount=0,fitasTotAmt=0;');
    p.push('    Object.keys(_PROD_LABELS).forEach(function(prod){');
    p.push('      var cnt=rel["f_"+prod+"_c"],amt=rel["f_"+prod+"_a"];');
    p.push('      if((cnt!=null&&cnt!==0)||(amt!=null&&amt!==0)){fitasRows.push({label:_PROD_LABELS[prod],count:cnt||0,amt:amt||0});fitasTotCount+=(cnt||0);fitasTotAmt+=(amt||0);}');
    p.push('    });');
    p.push('    if(fitasRows.length>0){');
    p.push('      fitasRows.forEach(function(r){');
    p.push('        html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #e0f0e4;\'>"+');
    p.push('          "<span style=\'font-size:11px;color:#555;\'>"+escXml(r.label)+"<\/span>"+');
    p.push('          "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtVal(r.count)+"<\/span>"+');
    p.push('          "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtAmt(r.amt)+"<\/span><\/div>";');
    p.push('      });');
    p.push('      html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #b8d8be;background:#d5eeda;\'>"+');
    p.push('        "<span style=\'font-size:11px;font-weight:700;color:#1A5C2B;\'>Total<\/span>"+');
    p.push('        "<span style=\'font-size:11px;font-weight:700;color:#1A5C2B;text-align:right;\'>"+fmtVal(fitasTotCount)+"<\/span>"+');
    p.push('        "<span style=\'font-size:11px;font-weight:700;color:#1A5C2B;text-align:right;\'>"+fmtAmt(fitasTotAmt)+"<\/span><\/div>";');
    p.push('    }else{html+="<div style=\'padding:8px 14px;border-top:1px solid #e0f0e4;\'>"+');
    p.push('      "<span style=\'font-size:11px;color:#aaa;\'>No product breakdown available<\/span><\/div>";}');
    p.push('  }else{html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #e0f0e4;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;\'>-<\/span>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;text-align:right;\'>-<\/span>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;text-align:right;\'>-<\/span><\/div>";}');
    p.push('  html+="<div style=\'background:#0C447C;padding:8px 14px;margin-top:1px;\'>"+');
    p.push('    "<span style=\'font-size:10.5px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:0.5px;\'>Payment Transactions (TT/MEPS/FAST/GIRO)<\/span><\/div>"+');
    p.push('    "<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:5px 14px 3px;background:#eef4fb;\'>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;\'>Flow<\/span>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Count<\/span>"+');
    p.push('    "<span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Amount<\/span><\/div>";');
    p.push('  if(inPayment&&rel){');
    p.push('    var useLabelled=isDirected&&(rel.payment_b2sc!=null||rel.payment_b2sa!=null);');
    p.push('    var rowOneLabel,rowTwoLabel,rowOneCount,rowOneAmt,rowOnePct,rowTwoCount,rowTwoAmt,rowTwoPct,ttTotCount,ttTotAmtVal;');
    p.push('    if(useLabelled){');
    p.push('      rowOneLabel=escXml(nameLeft)+" &#8594; "+escXml(nameRight);');
    p.push('      rowTwoLabel=escXml(nameRight)+" &#8594; "+escXml(nameLeft);');
    p.push('      rowOneCount=rel.payment_b2sc;rowOneAmt=rel.payment_b2sa;rowOnePct=rel.payment_b2sp;');
    p.push('      rowTwoCount=rel.payment_s2bc;rowTwoAmt=rel.payment_s2ba;rowTwoPct=rel.payment_s2bp;');
    p.push('      ttTotCount=rel._payment_total_count;ttTotAmtVal=rel._payment_total_amt;');
    p.push('    }else{');
    p.push('      rowOneLabel=escXml(nameLeft)+" &#8594; "+escXml(nameRight);');
    p.push('      rowTwoLabel=escXml(nameRight)+" &#8594; "+escXml(nameLeft);');
    p.push('      rowOneCount=rel._payment_ab_count||null;rowOneAmt=rel._payment_ab_amt||null;');
    p.push('      rowTwoCount=rel._payment_ba_count||null;rowTwoAmt=rel._payment_ba_amt||null;');
    p.push('      rowOnePct=null;rowTwoPct=null;');
    p.push('      ttTotCount=rel._payment_total_count||null;');
    p.push('      ttTotAmtVal=rel._payment_total_amt||null;');
    p.push('    }');
    p.push('    html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;align-items:start;\'>"+');
    p.push('      "<div><div style=\'font-size:11px;color:#555;\'>"+rowOneLabel+"<\/div>"+(rowOnePct!=null?"<div style=\'font-size:10px;color:#aaa;margin-top:1px;\'>"+fmtPct(rowOnePct)+" of total<\/div>":"")+"<\/div>"+');
    p.push('      "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtVal(rowOneCount)+"<\/span>"+');
    p.push('      "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtAmt(rowOneAmt)+"<\/span><\/div>";');
    p.push('    if(rowTwoCount!=null||rowTwoAmt!=null){');
    p.push('      html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;align-items:start;\'>"+');
    p.push('        "<div><div style=\'font-size:11px;color:#555;\'>"+rowTwoLabel+"<\/div>"+(rowTwoPct!=null?"<div style=\'font-size:10px;color:#aaa;margin-top:1px;\'>"+fmtPct(rowTwoPct)+" of total<\/div>":"")+"<\/div>"+');
    p.push('        "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtVal(rowTwoCount)+"<\/span>"+');
    p.push('        "<span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+fmtAmt(rowTwoAmt)+"<\/span><\/div>";}');
    p.push('    html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:7px 14px;border-top:1px solid #b8d0e8;background:#d0e4f4;\'>"+');
    p.push('      "<span style=\'font-size:11px;font-weight:700;color:#0C447C;\'>Total<\/span>"+');
    p.push('      "<span style=\'font-size:11px;font-weight:700;color:#0C447C;text-align:right;\'>"+fmtVal(ttTotCount)+"<\/span>"+');
    p.push('      "<span style=\'font-size:11px;font-weight:700;color:#0C447C;text-align:right;\'>"+fmtAmt(ttTotAmtVal)+"<\/span><\/div>";');
    p.push('  }else{html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;\'>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;\'>-<\/span>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;text-align:right;\'>-<\/span>"+');
    p.push('    "<span style=\'font-size:11px;color:#aaa;text-align:right;\'>-<\/span><\/div>";}');
    p.push('  html+="<\/div>";');
    p.push('  document.getElementById("side-panel-content").innerHTML=html;}');

    // *** updated | self-loop panel mirrors directional showEdgeInfo style:
    // dark header card on top, white body card with the FITAS / Payment /
    // Total summary table below.
    p.push('function showSelfLoopInfo(edge){');
    p.push('  var name=idNameLookup[edge.from]||_d(edge.from);');
    // Self-loop edge only has _all_txn_* totals; per-source FITAS / Payment
    // counts live in FSL / PSL lookup maps (set up from _PL.fsl / _PL.psl).
    p.push('  var fitasEntry=(typeof FSL!=="undefined"&&FSL[edge.from])?FSL[edge.from]:{};');
    p.push('  var paymentEntry=(typeof PSL!=="undefined"&&PSL[edge.from])?PSL[edge.from]:{};');
    p.push('  var fitasCount=fitasEntry._fitas_count||0;var fitasAmt=fitasEntry._fitas_amt||0;');
    p.push('  var paymentCount=paymentEntry._payment_count||0;var paymentAmt=paymentEntry._payment_amt||0;');
    p.push('  var hasFitas=fitasCount>0||fitasAmt>0;var hasPayment=paymentCount>0||paymentAmt>0;');
    p.push('  var totalAmt=(edge._all_txn_amt!=null)?edge._all_txn_amt:(fitasAmt+paymentAmt);');
    p.push('  var totalCount=(edge._all_txn_count!=null)?edge._all_txn_count:(fitasCount+paymentCount);');
    // Header card (dark) -- centered "Self-Transfer" label + company name + loop glyph
    p.push('  var html="<div style=\'background:#1C1C1C;border-radius:10px;padding:14px 16px 12px;margin-bottom:6px;box-shadow:0 2px 8px rgba(0,0,0,0.25);\'>"+');
    p.push('    "<table style=\'width:100%;border-collapse:collapse;\'>"+');
    p.push('    "<tr><td style=\'text-align:center;padding-bottom:6px;\'>"+');
    p.push('      "<span style=\'font-size:10px;font-weight:700;color:#FFD966;letter-spacing:0.8px;text-transform:uppercase;\'>Self-Transfer<\/span>"+');
    p.push('    "<\/td><\/tr>"+');
    p.push('    "<tr><td style=\'text-align:center;vertical-align:middle;\'>"+');
    p.push('      "<span style=\'font-size:12px;font-weight:700;color:#ffffff;line-height:1.4;\'>"+escXml(name)+"<\/span>"+');
    p.push('      "<span style=\'color:#E8860A;font-size:20px;line-height:1;font-weight:700;margin-left:10px;vertical-align:middle;\'>&#8635;<\/span>"+');
    p.push('    "<\/td><\/tr>"+');
    p.push('    "<\/table><\/div>";');
    // Body card (white) -- summary table
    p.push('  html+="<div style=\'background:#ffffff;border:1px solid #e0e0e0;border-radius:10px;overflow:hidden;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,0.06);\'>";');
    p.push('  html+="<div style=\'background:#5D3A1A;padding:8px 14px;\'><span style=\'font-size:10.5px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:0.5px;\'>Trade &amp; Payment Transactions<\/span><\/div>";');
    p.push('  html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:5px 14px 3px;background:#fdf6f0;\'><span style=\'font-size:10px;font-weight:700;color:#888;\'>Source<\/span><span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Count<\/span><span style=\'font-size:10px;font-weight:700;color:#888;text-align:right;\'>Amount<\/span><\/div>";');
    p.push('  html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;\'><span style=\'font-size:11px;color:#555;\'>Trade (FITAS)<\/span><span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(hasFitas?fmtVal(fitasCount):"-")+"<\/span><span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(hasFitas?fmtAmt(fitasAmt):"-")+"<\/span><\/div>";');
    p.push('  html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;\'><span style=\'font-size:11px;color:#555;\'>Payment (TT/MEPS/FAST/GIRO)<\/span><span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(hasPayment?fmtVal(paymentCount):"-")+"<\/span><span style=\'font-size:11px;font-weight:600;color:#222;text-align:right;\'>"+(hasPayment?fmtAmt(paymentAmt):"-")+"<\/span><\/div>";');
    p.push('  html+="<div style=\'display:grid;grid-template-columns:1fr 52px 90px;gap:4px;padding:7px 14px;border-top:1px solid #d0c0b0;background:#f5ede4;\'><span style=\'font-size:11px;font-weight:700;color:#222;\'>Total<\/span><span style=\'font-size:11px;font-weight:700;color:#222;text-align:right;\'>"+fmtVal(totalCount)+"<\/span><span style=\'font-size:11px;font-weight:700;color:#222;text-align:right;\'>"+fmtAmt(totalAmt)+"<\/span><\/div>";');
    p.push('  html+="<\/div>";');
    p.push('  document.getElementById("side-panel-content").innerHTML=html;}');

    // ── showNodeInfo ──────────────────────────────────────────────────────
    p.push('var showNodeInfo = function(uid){');
    p.push('  currentNode=uid;');
    p.push('  var id=_e(uid),meta=META[id]||{},ntype=TYPES[id]||"Non-Maybank Customer";');
    p.push('  var typeColor=getTypeColor(ntype);');
    p.push('  var paymentSummary=PSUM[id]||null,fitasSummary=FSUM[id]||null,allTxnSummary=ASUM[id]||null;');
    p.push('  var paymentSelfLoopEdge=PSL[id]||null;');
    p.push('  var fitasSelfLoopEdge=FSL[id]||null;');
    p.push('  var allTxnSelfLoopEdge=ASL[id]||null;');
    p.push('  var paymentSelfLoopPresent=!!paymentSelfLoopEdge;');
    p.push('  var fitasSelfLoopPresent=!!fitasSelfLoopEdge||fitasSelfLoopIds.has(id);');
    p.push('  var allTxnSelfLoopPresent=!!allTxnSelfLoopEdge;');
    p.push('  var hasPayment=paymentSelfLoopPresent||(!!paymentSummary&&((paymentSummary.payment_ord_freq||0)>0||(paymentSummary.payment_bene_freq||0)>0));');
    p.push('  var hasFITAS=fitasSelfLoopPresent||(!!fitasSummary&&((fitasSummary.fitas_ord_freq||0)>0||(fitasSummary.fitas_bene_freq||0)>0));');
    p.push('  var hasAllTxn=hasFITAS||hasPayment;');
    p.push('  var hasRSME=rsmeNodeIds.has(id),hasAAPaper=aaPaperNodeIds.has(id),hasTT=consolTTNodeIds.has(id);');
    p.push('  var hasFAST=fastNodeIds.has(id),hasGIRO=giroNodeIds.has(id);');
    p.push('  var isMaybank=(ntype!=="Non-Maybank Customer"),isTrade=(ntype==="Maybank Trade Customer");');
    p.push('  var accS=getAccStates();');
    p.push('  var entityName=idNameLookup[id]||uid;');

    p.push('  var overviewContent="<table class=\'info-table\'>"+tSection("Entity Info")+tRow("UEN",uid)+');
    p.push('  Object.keys(fieldConfig).filter(function(k){return fieldConfig[k].section==="overview";}).map(function(k){return renderRow(k,meta);}).join("")+"<\/table>";');

    // Data Sources panel: 6 rows in the same order/colors as the main app
    // (js_sidepanel.py:683-700) -- RSME, AA Paper, FITAS, TT, FAST, GIRO.
    p.push('  var dsContent="<table class=\'info-table\' style=\'margin-top:4px;\'>"+');
    p.push('  "<tr style=\'background:#f5f5f5;\'><td class=\'lbl\' style=\'font-weight:700;color:#333;\'>Source<\/td><td class=\'val\'> <\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>RSME Buyer/Supplier Checklist<\/td><td class=\'val\' style=\'color:"+(hasRSME?"#27ae60":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasRSME?"&#10003;":"&#8212;")+"<\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>AA Paper<\/td><td class=\'val\' style=\'color:"+(hasAAPaper?"#8b4513":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasAAPaper?"&#10003;":"&#8212;")+"<\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>FITAS<\/td><td class=\'val\' style=\'color:"+(hasFITAS?"#6f42c1":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasFITAS?"&#10003;":"&#8212;")+"<\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>TT<\/td><td class=\'val\' style=\'color:"+(hasTT?"#2980b9":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasTT?"&#10003;":"&#8212;")+"<\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>FAST<\/td><td class=\'val\' style=\'color:"+(hasFAST?"#1A5276":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasFAST?"&#10003;":"&#8212;")+"<\/td><\/tr>"+');
    p.push('  "<tr><td class=\'lbl\'>GIRO<\/td><td class=\'val\' style=\'color:"+(hasGIRO?"#1E8449":"#bbb")+";font-size:15px;font-weight:700;\'>"+(hasGIRO?"&#10003;":"&#8212;")+"<\/td><\/tr><\/table>";');

    p.push('  var paymentSummaryContent="";');
    p.push('  if(hasPayment){var payHasExt=!!paymentSummary&&((paymentSummary.payment_ord_freq||0)>0||(paymentSummary.payment_bene_freq||0)>0);');
    p.push('    if(payHasExt){paymentSummaryContent+="<div class=\'tt-card-ord\'><div class=\'tt-title\'>&#8594; As Sender<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(paymentSummary.payment_ord_freq||0)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(paymentSummary.payment_ord_amt||0)+"<\/span><\/div><\/div>"+');
    p.push('      "<div class=\'tt-card-bene\'><div class=\'tt-title\'>&#8592; As Receiver<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(paymentSummary.payment_bene_freq||0)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(paymentSummary.payment_bene_amt||0)+"<\/span><\/div><\/div>";}');
    p.push('    if(paymentSelfLoopPresent){var psc=(paymentSelfLoopEdge&&paymentSelfLoopEdge._payment_count)||0,psa=(paymentSelfLoopEdge&&paymentSelfLoopEdge._payment_amt)||0;');
    p.push('      paymentSummaryContent+="<div style=\'background:#F5F0FF;border-left:3px solid #7F77DD;border-radius:6px;padding:10px 12px;margin-bottom:6px;\'>"+');
    p.push('      "<div style=\'font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;\'>&#8635; Self-transfer (Payment)<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction count<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtVal(psc)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction amount<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtAmt(psa)+"<\/span><\/div><\/div>";}}');

    p.push('  var fitasSummaryContent="";');
    p.push('  if(hasFITAS){var foe=!!fitasSummary&&((fitasSummary.fitas_ord_freq||0)>0),fbe=!!fitasSummary&&((fitasSummary.fitas_bene_freq||0)>0);');
    p.push('    if(foe)fitasSummaryContent+="<div class=\'tt-card-ord\'><div class=\'tt-title\'>&#8594; As Sender<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(fitasSummary.fitas_ord_freq)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(fitasSummary.fitas_ord_amt)+"<\/span><\/div><\/div>";');
    p.push('    if(fbe)fitasSummaryContent+="<div class=\'tt-card-bene\'><div class=\'tt-title\'>&#8592; As Receiver<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(fitasSummary.fitas_bene_freq)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(fitasSummary.fitas_bene_amt)+"<\/span><\/div><\/div>";');
    p.push('    if(fitasSelfLoopPresent){var fsc=(fitasSelfLoopEdge&&fitasSelfLoopEdge._fitas_count)||0,fsa=(fitasSelfLoopEdge&&fitasSelfLoopEdge._fitas_amt)||0;');
    p.push('      fitasSummaryContent+="<div style=\'background:#F5F0FF;border-left:3px solid #7F77DD;border-radius:6px;padding:10px 12px;margin-bottom:6px;\'>"+');
    p.push('      "<div style=\'font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;\'>&#8635; Self-transfer (FITAS)<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction count<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtVal(fsc)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction amount<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtAmt(fsa)+"<\/span><\/div><\/div>";}}');

    p.push('  var allTxnSummaryContent="";');
    p.push('  if(hasAllTxn){var atxnHasExt=!!allTxnSummary&&((allTxnSummary.all_txn_ord_freq||0)>0||(allTxnSummary.all_txn_bene_freq||0)>0);');
    p.push('    if(atxnHasExt){allTxnSummaryContent+="<div class=\'tt-card-ord\'><div class=\'tt-title\'>&#8594; As Sender<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(allTxnSummary.all_txn_ord_freq||0)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(allTxnSummary.all_txn_ord_amt||0)+"<\/span><\/div><\/div>"+');
    p.push('      "<div class=\'tt-card-bene\'><div class=\'tt-title\'>&#8592; As Receiver<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transactions<\/span><span class=\'tt-val\'>"+fmtVal(allTxnSummary.all_txn_bene_freq||0)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Total Amount<\/span><span class=\'tt-val\'>"+fmtAmt(allTxnSummary.all_txn_bene_amt||0)+"<\/span><\/div><\/div>";}');
    p.push('    if(allTxnSelfLoopPresent){var asc=(allTxnSelfLoopEdge&&allTxnSelfLoopEdge._all_txn_count)||0,asa=(allTxnSelfLoopEdge&&allTxnSelfLoopEdge._all_txn_amt)||0;');
    p.push('      allTxnSummaryContent+="<div style=\'background:#F5F0FF;border-left:3px solid #7F77DD;border-radius:6px;padding:10px 12px;margin-bottom:6px;\'>"+');
    p.push('      "<div style=\'font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;\'>&#8635; Self-transfer (all sources)<\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction count<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtVal(asc)+"<\/span><\/div>"+');
    p.push('      "<div class=\'tt-row\'><span>Transaction amount<\/span><span style=\'font-weight:600;color:#3C3489;\'>"+fmtAmt(asa)+"<\/span><\/div><\/div>";}}');

    p.push('  var facilitiesContent="";');
    p.push('  if(isMaybank){');
    p.push('    facilitiesContent="<table class=\'info-table\'>";');
    p.push('    if(isTrade){');
    p.push('      facilitiesContent+=tSection("Trade Facility Summary");');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\'>Authorised Limit<\/td><td class=\'val\'>"+fmtAmt(meta["TF_LCY_AUTH_LMT"])+"<\/td><\/tr>";');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\'>Available Limit<\/td><td class=\'val\'>"+fmtAmt(meta["TF_LCY_AVAIL_LMT"])+"<\/td><\/tr>";');
    p.push('      var totOS=(meta["TF_LCY_TOT_OS"]!=null)?meta["TF_LCY_TOT_OS"]:null;');
    p.push('      var obsOS=(meta["TF_LCY_OBS_OS"]!=null)?meta["TF_LCY_OBS_OS"]:null;');
    p.push('      var outstanding=(totOS!=null||obsOS!=null)?((totOS||0)+(obsOS||0)):null;');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\' style=\'font-weight:600;\'>Outstanding Balance<\/td><td class=\'val\' style=\'font-weight:600;\'>"+(outstanding!=null?fmtAmt(outstanding):"-")+"<\/td><\/tr>";');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>On-Balance Sheet<\/td><td class=\'val\'>"+fmtAmt(totOS)+"<\/td><\/tr>";');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Off-Balance Sheet<\/td><td class=\'val\'>"+fmtAmt(obsOS)+"<\/td><\/tr>";');
    p.push('      var auth=meta["TF_LCY_AUTH_LMT"];');
    p.push('      var utilPct=(outstanding!=null&&auth!=null&&auth>0)?(outstanding/auth*100).toFixed(1)+"%":"-";');
    p.push('      facilitiesContent+="<tr><td class=\'lbl\'>Utilisation<\/td><td class=\'val\'>"+utilPct+"<\/td><\/tr>";');
    p.push('    }');
    p.push('    facilitiesContent+=tSection("Banking Balances");');
    p.push('    var trLn=(meta["TR_LN"]!=null)?meta["TR_LN"]:null;');
    p.push('    var nonTrLn=(meta["NONTR_LN"]!=null)?meta["NONTR_LN"]:null;');
    p.push('    var totLn=(trLn!=null||nonTrLn!=null)?((trLn||0)+(nonTrLn||0)):null;');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'font-weight:600;\'>Total Loans<\/td><td class=\'val\' style=\'font-weight:600;\'>"+(totLn!=null?fmtAmt(totLn):"-")+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Trade Loans<\/td><td class=\'val\'>"+fmtAmt(trLn)+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Non-Trade Loans<\/td><td class=\'val\'>"+fmtAmt(nonTrLn)+"<\/td><\/tr>";');
    p.push('    var casa=(meta["CASA"]!=null)?meta["CASA"]:null;');
    p.push('    var fd=(meta["FD"]!=null)?meta["FD"]:null;');
    p.push('    var strctd=(meta["STRCTD"]!=null)?meta["STRCTD"]:null;');
    p.push('    var totDep=(casa!=null||fd!=null||strctd!=null)?((casa||0)+(fd||0)+(strctd||0)):null;');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'font-weight:600;\'>Total Deposits<\/td><td class=\'val\' style=\'font-weight:600;\'>"+(totDep!=null?fmtAmt(totDep):"-")+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Current Account<\/td><td class=\'val\'>"+fmtAmt(casa)+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Time Deposits<\/td><td class=\'val\'>"+fmtAmt(fd)+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<tr><td class=\'lbl\' style=\'padding-left:16px;color:#aaa;\'>Structured TD<\/td><td class=\'val\'>"+fmtAmt(strctd)+"<\/td><\/tr>";');
    p.push('    facilitiesContent+="<\/table>";}');

    p.push('  var creditContent="";');
    p.push('  if(isMaybank){var CSUB=[{header:"Risk Flags",keys:["is_watchlist","is_special_mention","is_npl"]},{header:"Credit Profile",keys:["impairment_stage","RISK_GRADE","credit_status","borrower_risk_rating","rating_date"]},{header:"Payment Conduct",keys:["months_on_book","latest_dpd_bucket","delinquency_count_12m"]}];');
    p.push('    creditContent="<table class=\'info-table\'>";');
    p.push('    CSUB.forEach(function(sub){var rows=sub.keys.filter(function(k){return!!fieldConfig[k];}).map(function(k){return renderRow(k,meta);}).join("");if(rows)creditContent+=tSection(sub.header)+rows;});');
    p.push('    creditContent+="<\/table>";}');

    p.push('  var acraF=Object.keys(fieldConfig).filter(function(k){return fieldConfig[k].section==="acrafin";});');
    p.push('  var emisF=Object.keys(fieldConfig).filter(function(k){return fieldConfig[k].section==="emisfin";});');
    p.push('  var mfiF=Object.keys(fieldConfig).filter(function(k){return fieldConfig[k].section==="mfifin"&&fieldConfig[k].enabled!==false;});');
    p.push('  var hasMFI=mfiF.some(function(k){return meta[k]!=null;});');
    p.push('  var finContent="<table class=\'info-table\'>";');
    p.push('  if(isMaybank&&acraF.length>0){finContent+=tSection("ACRA");acraF.forEach(function(k){finContent+=renderRow(k,meta);});}');
    p.push('  if(emisF.length>0){');
    p.push('    finContent+=tSection("EMIS");');
    p.push('    var _emisOrder=["EMIS Fiscal Year","EMIS Total Operating Revenue (USD)","EMIS Operating Profit (USD)","EMIS Profit Before Income Tax (USD)","EMIS Total Assets (USD)","EMIS Free Cash Flow (USD)","EMIS Net Cash Flow from Operations (USD)","EMIS Return on Assets / ROA (%)","EMIS Return on Equity / ROE (%)","EMIS Audited","EMIS Source"];');
    p.push('    var _emisUSD={"EMIS Total Operating Revenue (USD)":1,"EMIS Operating Profit (USD)":1,"EMIS Profit Before Income Tax (USD)":1,"EMIS Total Assets (USD)":1,"EMIS Free Cash Flow (USD)":1,"EMIS Net Cash Flow from Operations (USD)":1};');
    p.push('    _emisOrder.forEach(function(k){');
    p.push('      if(!fieldConfig[k])return;');
    p.push('      var label=fieldConfig[k].label;');
    p.push('      if(_emisUSD[k])finContent+="<tr><td class=\'lbl\'>"+escXml(label)+"<\/td><td class=\'val\'>"+fmtUSD(meta[k])+"<\/td><\/tr>";');
    p.push('      else finContent+=renderRow(k,meta);');
    p.push('    });');
    p.push('  }');
    // MFI subsection inside Financials -- MFI_END_DTE first, then 7 P&L fields.
    p.push('  if(hasMFI){');
    p.push('    finContent+=tSection("MFI");');
    p.push('    var _mfiOrder=["MFI_END_DTE","MFI_SALES","MFI_COGS","MFI_GROSS_PNL","MFI_PRETAX_PNL_BEFORE_INT","MFI_PNL_BEFORE_TAX","MFI_PNL_AFT_TAX","MFI_EBITDA"];');
    p.push('    _mfiOrder.forEach(function(k){if(!fieldConfig[k]||fieldConfig[k].enabled===false)return;finContent+=renderRow(k,meta);});');
    p.push('  }');
    p.push('  finContent+="<\/table>";');
    p.push('  var hasFinancials=(isMaybank&&acraF.length>0)||emisF.length>0||hasMFI;');

    // *** new | CIP collaterals section
    p.push('  var cipFinF=Object.keys(fieldConfig).filter(function(k){return fieldConfig[k].section==="cipinfo";});');
    p.push('  var hasCIP=cipFinF.some(function(k){return meta[k]!=null;});');
    p.push('  var cipContent="<table class=\'info-table\'>";');
    p.push('  if(hasCIP&&cipFinF.length>0){');
    p.push('    var _cipFacOrder=["CIP_FAC_LIMIT_SGD","CIP_LOAN_BALANCE_SGD","CIP_NPL_BALANCE_SGD"];');
    p.push('    var cipFacRows=_cipFacOrder.filter(function(k){return!!fieldConfig[k];}).map(function(k){return renderRow(k,meta);}).join("");');
    p.push('    if(cipFacRows){cipContent+=tSection("CIP Facility & Loan")+cipFacRows;}');
    p.push('    var _cipSecOrder=["CIP_SEC_AMT","CIP_SEC_EMV","CIP_SEC_FSV","CIP_SEC_FIV","CIP_N_PROPERTIES"];');
    p.push('    var cipSecRows=_cipSecOrder.filter(function(k){return!!fieldConfig[k];}).map(function(k){return renderRow(k,meta);}).join("");');
    p.push('    if(cipSecRows){cipContent+=tSection("CIP Collateral")+cipSecRows;}');
    p.push('    var _cipAccOrder=["CIP_N_ACC_TOTAL","CIP_N_ACC_OPEN","CIP_N_ACC_CLOSED"];');
    p.push('    var cipAccRows=_cipAccOrder.filter(function(k){return!!fieldConfig[k];}).map(function(k){return renderRow(k,meta);}).join("");');
    p.push('    if(cipAccRows){cipContent+=tSection("CIP Accounts")+cipAccRows;}');
    p.push('  }else{cipContent+="<tr><td colspan=\'2\' style=\'color:#aaa;font-size:11px;text-align:center;padding:12px;\'>No CIP data available<\/td><\/tr>";}');
    p.push('  cipContent+="<\/table>";');

    p.push('  var rsmeNbs=adjacencyMap[id]||[],ttOutNbs=consolTTOutAdj[id]||[],ttInNbs=consolTTInAdj[id]||[];');
    p.push('  var fitOutNbs=fitasOutAdj[id]||[],fitInNbs=fitasInAdj[id]||[];');
    p.push('  var aaOutNbs=aaPaperOutAdj[id]||[],aaInNbs=aaPaperInAdj[id]||[];');
    p.push('  var rsmeNetC="";');
    p.push('  if(!rsmeNbs.length)rsmeNetC="<p style=\'color:#aaa;font-size:12px;text-align:center;margin-top:8px;\'>No RSME connections.<\/p>";');
    p.push('  else rsmeNbs.forEach(function(nb){rsmeNetC+=_nbCard("nbcard-rsme-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});');
    p.push('  var ttNetC="";');
    p.push('  if(!ttOutNbs.length&&!ttInNbs.length)ttNetC="<p style=\'color:#aaa;font-size:12px;text-align:center;margin-top:8px;\'>No Payment connections.<\/p>";');
    p.push('  else{if(ttOutNbs.length){ttNetC+="<div style=\'font-size:12px;font-weight:600;color:#2980b9;margin:8px 0 4px;\'>&#8594; Sends to ("+ttOutNbs.length+")<\/div>";ttOutNbs.forEach(function(nb){ttNetC+=_nbCard("nbcard-ttout-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}');
    p.push('    if(ttInNbs.length){ttNetC+="<div style=\'font-size:12px;font-weight:600;color:#27ae60;margin:8px 0 4px;\'>&#8592; Receives from ("+ttInNbs.length+")<\/div>";ttInNbs.forEach(function(nb){ttNetC+=_nbCard("nbcard-ttin-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}}');
    p.push('  var fitNetC="";');
    p.push('  if(!fitOutNbs.length&&!fitInNbs.length)fitNetC="<p style=\'color:#aaa;font-size:12px;text-align:center;margin-top:8px;\'>No FITAS connections.<\/p>";');
    p.push('  else{if(fitOutNbs.length){fitNetC+="<div style=\'font-size:12px;font-weight:600;color:#6f42c1;margin:8px 0 4px;\'>&#8594; Sends to ("+fitOutNbs.length+")<\/div>";fitOutNbs.forEach(function(nb){fitNetC+=_nbCard("nbcard-fitout-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}');
    p.push('    if(fitInNbs.length){fitNetC+="<div style=\'font-size:12px;font-weight:600;color:#6f42c1;margin:8px 0 4px;\'>&#8592; Receives from ("+fitInNbs.length+")<\/div>";fitInNbs.forEach(function(nb){fitNetC+=_nbCard("nbcard-fitin-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}}');
    p.push('  var aaNetC="";');
    p.push('  if(!aaOutNbs.length&&!aaInNbs.length)aaNetC="<p style=\'color:#aaa;font-size:12px;text-align:center;margin-top:8px;\'>No AA Paper connections.<\/p>";');
    p.push('  else{if(aaOutNbs.length){aaNetC+="<div style=\'font-size:12px;font-weight:600;color:#8b4513;margin:8px 0 4px;\'>&#8594; Suppliers ("+aaOutNbs.length+")<\/div>";aaOutNbs.forEach(function(nb){aaNetC+=_nbCard("nbcard-aaout-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}');
    p.push('    if(aaInNbs.length){aaNetC+="<div style=\'font-size:12px;font-weight:600;color:#8b4513;margin:8px 0 4px;\'>&#8592; Buyers ("+aaInNbs.length+")<\/div>";aaInNbs.forEach(function(nb){aaNetC+=_nbCard("nbcard-aain-"+nb,nb,getTypeColor(TYPES[nb]||"Non-Maybank Customer"));});}}');
    p.push('  var riskBadge="";');
    p.push('  if(isMaybank){if(meta.is_npl===1)riskBadge="<span style=\'background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;\'>NPL<\/span>";');
    p.push('    else if(meta.is_special_mention===1)riskBadge="<span style=\'background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;\'>SMA<\/span>";');
    p.push('    else if(meta.is_watchlist===1)riskBadge="<span style=\'background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;\'>Watchlist<\/span>";}');

    p.push('  var aaNbs=Array.from(new Set(aaOutNbs.concat(aaInNbs)));');
    p.push('  var _allNbSet=new Set();');
    p.push('  rsmeNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  ttOutNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  ttInNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  fitOutNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  fitInNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  aaOutNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  aaInNbs.forEach(function(x){_allNbSet.add(x);});');
    p.push('  var totalNbs=_allNbSet.size;');

    p.push('  document.getElementById("side-panel-content").innerHTML=');
    p.push('    "<div id=\'main-company-card\' class=\'company-main-card\'>"+');
    p.push('    "<div class=\'cn\'>"+escXml(entityName)+"<\/div>"+');
    p.push('    "<div class=\'cu\'>"+escXml(uid)+"<\/div><\/div>"+');
    p.push('    "<div style=\'display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:10px;\'>"+');
    p.push('    "<span style=\'background:"+typeColor+";color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;\'>"+escXml(ntype)+"<\/span>"+');
    p.push('    makeSegmentBadge(meta)+makeExMaybankBadge(meta)+riskBadge+"<\/div>"+');
    // *** updated | "total unique relationships"
    p.push('    "<p style=\'margin:0 0 10px;font-size:12px;color:#555;\'><b>"+totalNbs+"<\/b> total unique relationship"+(totalNbs!==1?"s":"")+"<\/p>"+');
    p.push('    makeAccSection("overview","Overview",overviewContent,accS.overview)+');
    p.push('    makeAccSection("datasources","Data Sources",dsContent,accS.datasources)+');
    p.push('    (hasFITAS?makeAccSection("fitas_summary","Trade Transactions (FITAS) Summary",fitasSummaryContent,accS.fitas_summary):"")+');
    p.push('    (hasPayment?makeAccSection("payment_summary","Payment Transactions (TT/MEPS/FAST/GIRO) Summary",paymentSummaryContent,accS.payment_summary):"")+');
    p.push('    (hasAllTxn?makeAccSection("all_txn_summary","All Transactions (FITAS + TT/MEPS/FAST/GIRO) Summary",allTxnSummaryContent,accS.all_txn_summary):"")+');
    p.push('    (isMaybank?makeAccSection("facilities","Facilities with Maybank",facilitiesContent,accS.facilities):"")+');
    p.push('    (isMaybank?makeAccSection("creditstatus","Customer Credit Status",creditContent,accS.creditstatus):"")+');
    p.push('    (hasFinancials?makeAccSection("financials","Financials",finContent,accS.financials):"")+');
    // *** updated | standalone MFI accordion removed; MFI now lives inside Financials.
    p.push('    makeAccSection("cipinfo","CIP Collaterals",cipContent,accS.cipinfo)+');
    p.push('    makeAccSection("network_rsme","RSME Buyer/Supplier Network ("+rsmeNbs.length+")",rsmeNetC,accS.network_rsme)+');
    p.push('    makeAccSection("network_payment","Payment Transactions (TT/MEPS/FAST/GIRO) Network ("+Array.from(new Set(ttOutNbs.concat(ttInNbs))).length+")",ttNetC,accS.network_payment)+');
    p.push('    makeAccSection("network_fitas","Trade Transactions (FITAS) Network ("+Array.from(new Set(fitOutNbs.concat(fitInNbs))).length+")",fitNetC,accS.network_fitas)+');
    p.push('    makeAccSection("network_aa_paper","AA Paper Network ("+aaNbs.length+")",aaNetC,accS.network_aa_paper);');
    // *** updated | attachAccordion list -- mfifin removed (rolled into financials)
    p.push('  ["overview","datasources","fitas_summary","payment_summary","all_txn_summary","facilities","creditstatus","financials","cipinfo","network_rsme","network_fitas","network_payment","network_aa_paper"].forEach(attachAccordion);');
    p.push('  document.getElementById("main-company-card").addEventListener("click",function(){showNodeInfo(uid);});');
    p.push('  rsmeNbs.forEach(function(nb){var el=document.getElementById("nbcard-rsme-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  ttOutNbs.forEach(function(nb){var el=document.getElementById("nbcard-ttout-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  ttInNbs.forEach(function(nb){var el=document.getElementById("nbcard-ttin-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  fitOutNbs.forEach(function(nb){var el=document.getElementById("nbcard-fitout-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  fitInNbs.forEach(function(nb){var el=document.getElementById("nbcard-fitin-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  aaOutNbs.forEach(function(nb){var el=document.getElementById("nbcard-aaout-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('  aaInNbs.forEach(function(nb){var el=document.getElementById("nbcard-aain-"+nb);if(el)el.addEventListener("click",function(){showNodeInfo(_d(nb));});});');
    p.push('};');

    p.push('var VN = new vis.DataSet(_PL.nodes.map(function(n){');
    p.push('  return{id:n.id,label:n.name,font:{color:"#000000",size:13},');
    p.push('    color:{background:n.color,border:"#555555",highlight:{background:n.color,border:"#555555"}},');
    p.push('    shape:n.shape,size:n.size,x:n.x,y:n.y,physics:false,hidden:false};');
    p.push('}));');

    p.push('var VE = new vis.DataSet(_PL.edges.map(function(e){');
    p.push('  var o={id:e.id,from:e.from,to:e.to};');
    p.push('  var keys=Object.keys(e).filter(function(k){return k.charAt(0)==="_";});');
    p.push('  keys.forEach(function(k){o[k]=e[k];});');
    p.push('  if(e._isSelfLoop){');
    p.push('    o.color={color:CFG.consol_tt_edge_color,opacity:CFG.consol_tt_edge_opacity,highlight:CFG.consol_tt_edge_highlight_color};');
    p.push('    o.width=2;o._baseWidth=2;');
    p.push('    o.arrows={to:{enabled:false}};');
    p.push('    o.selfReference={size:20,angle:Math.PI/4};');
    p.push('    o.smooth={enabled:true,type:"curvedCW",roundness:0.5};');
    p.push('    o.dashes=false;');
    p.push('  } else if(e._rsmeOnly){');
    p.push('    o.color={color:CFG.rsme_edge_color,opacity:CFG.rsme_edge_opacity,highlight:CFG.rsme_edge_highlight_color};');
    p.push('    o.width=e._baseWidth||1;o._baseWidth=e._baseWidth||1;');
    p.push('    o.arrows={to:{enabled:false}};');
    p.push('    o.smooth={enabled:false};');
    p.push('    o.dashes=false;');
    p.push('  } else if(e._isBoth){');
    p.push('    o.color={color:CFG.consol_tt_edge_color,opacity:CFG.consol_tt_edge_opacity,highlight:CFG.consol_tt_edge_highlight_color};');
    p.push('    o.width=e._baseWidth||1;o._baseWidth=e._baseWidth||1;');
    p.push('    o.arrows={to:{enabled:true,scaleFactor:0.6},from:{enabled:true,scaleFactor:0.6}};');
    p.push('    o.smooth={enabled:false};');
    p.push('    o.dashes=false;');
    p.push('  } else {');
    p.push('    o.color={color:CFG.consol_tt_edge_color,opacity:CFG.consol_tt_edge_opacity,highlight:CFG.consol_tt_edge_highlight_color};');
    p.push('    o.width=e._baseWidth||1;o._baseWidth=e._baseWidth||1;');
    p.push('    o.arrows={to:{enabled:true,scaleFactor:0.6}};');
    p.push('    o.smooth={enabled:false};');
    p.push('    o.dashes=false;');
    p.push('  }');
    p.push('  o.hidden=false;');
    p.push('  return o;');
    p.push('}));');

    p.push('var nodes=VN, edges=VE;');
    p.push('var container=document.getElementById("mynetwork");');
    p.push('var network=new vis.Network(container,{nodes:VN,edges:VE},{');
    p.push('  physics:{enabled:false},');
    p.push('  interaction:{hover:false,navigationButtons:false,keyboard:false,');
    p.push('    multiselect:false,selectable:true,selectConnectedEdges:false,zoomSpeed:0.5},');
    p.push('  nodes:{shape:"dot",font:{size:13}},');
    p.push('  edges:{chosen:false}});');
    p.push('network.setOptions({edges:{chosen:false}});');
    p.push('network.once("afterDrawing",function(){network.fit({animation:{duration:600,easingFunction:"easeInOutQuad"}});});');
    p.push('(function(){var gc=document.getElementById("graph-card"),vis=document.getElementById("mynetwork");');
    p.push('  if(gc&&vis){vis.style.cssText="width:100%;height:100%;border-radius:0;background:#FAFAFA;border:none;";gc.appendChild(vis);}})();');
    p.push('(function(){var f=_PL.focal,d=_PL.date;var disp=d.slice(0,2)+"/"+d.slice(2,4)+"/"+d.slice(4);');
    p.push('  document.getElementById("tb-co").textContent=f.name||"Network Export";');
    p.push('  document.getElementById("tb-uen").textContent=f.uen||"";');
    p.push('  document.getElementById("tb-meta").textContent=_PL.nc+" nodes \u00b7 "+_PL.ec+" edges \u00b7 Exported: "+disp;');
    p.push('})();');

    p.push('function resetEdgeColors(){');
    p.push('  var upd=edges.get().filter(function(e){return!e.hidden;}).map(function(e){');
    p.push('    return{id:e.id,width:e._baseWidth!==undefined?e._baseWidth:(e.width||1),');
    p.push('      color:e._rsmeOnly');
    p.push('        ?{color:CFG.rsme_edge_color,opacity:CFG.rsme_edge_opacity}');
    p.push('        :{color:CFG.consol_tt_edge_color,opacity:CFG.consol_tt_edge_opacity}};});');
    p.push('  edges.update(upd);}');

    p.push('var _lastH=null,_lastHE=null;');
    p.push('function _resetLastEdgeHL(){if(_lastHE===null)return;var e=edges.get(_lastHE);if(e){');
    p.push('  edges.update({id:_lastHE,width:e._baseWidth!==undefined?e._baseWidth:(e.width||1),');
    p.push('    color:e._rsmeOnly');
    p.push('      ?{color:CFG.rsme_edge_color,opacity:CFG.rsme_edge_opacity}');
    p.push('      :{color:CFG.consol_tt_edge_color,opacity:CFG.consol_tt_edge_opacity}});}_lastHE=null;}');
    // *** updated | shadow halo removed -- vis.js's built-in selectNodes
    // is the only selection visual; saves a nodes.update per click + the
    // GPU-expensive blur on canvas redraw.
    p.push('function highlightNode(id){_resetLastEdgeHL();if(_lastH!==null){resetEdgeColors();}if(!id){_lastH=null;return;}');
    p.push('  var upd=[];edges.get().forEach(function(e){if(e.hidden)return;if(e.from!==id&&e.to!==id)return;');
    p.push('    var bw=e._baseWidth!==undefined?e._baseWidth:(e.width||1);');
    p.push('    if(e._rsmeOnly)bw=bw*CFG.rsme_edge_highlight_mult;');
    p.push('    upd.push({id:e.id,width:bw,color:{');
    p.push('      color:e._rsmeOnly?CFG.rsme_edge_highlight_color:CFG.consol_tt_edge_highlight_color,');
    p.push('      opacity:e._rsmeOnly?CFG.rsme_edge_highlight_opacity:CFG.consol_tt_edge_highlight_opacity}});});');
    p.push('  edges.update(upd);_lastH=id;}');

    p.push('network.on("click",function(params){');
    p.push('  if(params.nodes.length>0){');
    p.push('    var cid=params.nodes[0],uid=_d(cid);');
    p.push('    _resetLastEdgeHL();highlightNode(cid);currentNode=uid;showNodeInfo(uid);network.selectNodes([cid]);');
    p.push('  } else if(params.edges.length>0){');
    p.push('    if(_lastH!==null){_lastH=null;}');
    p.push('    resetEdgeColors();');
    p.push('    var eid=params.edges[0],edge=edges.get(eid);');
    p.push('    if(edge){');
    p.push('      var bw=edge._baseWidth!==undefined?edge._baseWidth:(edge.width||1);');
    p.push('      if(edge._rsmeOnly)bw=bw*CFG.rsme_edge_highlight_mult;');
    p.push('      edges.update({id:eid,width:bw,color:{');
    p.push('        color:edge._rsmeOnly?CFG.rsme_edge_highlight_color:CFG.consol_tt_edge_highlight_color,');
    p.push('        opacity:edge._rsmeOnly?CFG.rsme_edge_highlight_opacity:CFG.consol_tt_edge_highlight_opacity}});');
    p.push('      _lastHE=eid;');
    p.push('      if(edge._isSelfLoop)showSelfLoopInfo(edge);');
    p.push('      else showEdgeInfo(edge);}');
    p.push('  } else {');
    p.push('    _resetLastEdgeHL();if(_lastH!==null){_lastH=null;}resetEdgeColors();clearSidePanel();}');
    p.push('});');

    p.push('network.on("doubleClick",function(params){if(params.nodes.length>0)showNodeInfo(_d(params.nodes[0]));});');

    p.push('<\/script><\/body><\/html>');
    return p.join('\n');
}
"""
