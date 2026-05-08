# ── network_graph/viz/js_sidepanel.py ─────────────────────────────────────────
# Side panel rendering logic for displaying node details and edge details.
# Handles accordion sections, badge rendering, neighbor cards,
# and edge click panel functions.
#
# UEN COMPRESSION:
# - showNodeInfo(uid) receives real UEN string (external API)
# - Encoded to compressed ID at entry -- all internal lookups use compressed ID
# - _nbCard receives compressed ID -- decodes via _d() for UEN display
# - Neighbor card click handlers decode via _d() before calling navigateToNode
# - navigateToNode(uid) always receives and stores real UEN string
# - Edge panel functions: edge.from/edge.to are compressed IDs
#   idNameLookup[edge.from] works directly (keyed by compressed ID)
#   Fallback uses _d(edge.from) so panel never shows raw "1","2" IDs
#
# OVERVIEW ORDER:
# - Driven entirely by FIELD_CONFIG insertion order for section="overview"
# - UEN is the only hardcoded row (not a meta field -- primary key)
# - To reorder overview fields, reorder entries in FIELD_CONFIG -- no JS change needed
#
# FACILITIES ORDER:
# - Explicit rendering: Authorised -> Available -> Outstanding (derived) ->
#   On-BS (indented) -> Off-BS (indented) -> Utilisation (derived)
#   then Banking: Total Loans -> Trade (indented) -> Non-Trade (indented)
#                 Total Deposits -> Current Acct (indented) -> TD (indented) -> Structured TD (indented)
#
# EMIS FINANCIALS:
# - Explicit order, fmtUSD() used for USD amount fields ($ not S$)
#
# *** updated | MFI financials section (section='mfifin') added
# *** updated | CIP collaterals section (section='cipinfo') added
# *** updated | fmtRatio() helper added for MFI ratio cols (DCSR, GEARING)
# *** note    | ACC_DEFAULT in js_core.py must include 'mfifin' and 'cipinfo' keys


def get_js_sidepanel():
    """
    Returns JavaScript code for side panel display.

    showEdgeInfo() design:
    - Card 1 (header): standalone dark rounded rectangle, #1C1C1C bg
        Directed (buyer->supplier): "Pays To" centered above arrow
        RSME-only: solid line separator
        Both-ways: "Both Ways" centered, unchanged
        Customer/Counterparty: role labels unchanged
    - Card 2 (body): white bg, 4 sections always rendered

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// SIDE PANEL HELPERS
// ══════════════════════════════════════════════════════════════════════════

function clearSidePanel() {
    document.getElementById("side-panel-content").innerHTML =
        "<p style='color:#aaa;font-size:13px;text-align:center;margin-top:40px;'>" +
        "Search a company to begin.</p>";
}

var BADGE_FIELDS = {
    impairment_stage  : "stage",
    is_watchlist      : "flag",
    is_special_mention: "flag",
    is_npl            : "flag",
};

// Per-source self-loop lookup maps (keyed by compressed UEN id)
// Built once at load time -- O(1) lookup for FITAS/Payment/All Txn summary
// accordions, which need separate self-transfer counts per source.
var _paymentSelfLoopMap = {};
if (typeof paymentSelfLoopEdgesData !== "undefined") {
    paymentSelfLoopEdgesData.forEach(function(e) { _paymentSelfLoopMap[e.uen] = e; });
}
var _fitasSelfLoopMap = {};
if (typeof fitasSelfLoopEdgesData !== "undefined") {
    fitasSelfLoopEdgesData.forEach(function(e) { _fitasSelfLoopMap[e.uen] = e; });
}
var _allTxnSelfLoopMap = {};
if (typeof allTxnSelfLoopEdgesData !== "undefined") {
    allTxnSelfLoopEdgesData.forEach(function(e) { _allTxnSelfLoopMap[e.uen] = e; });
}

function makeSegmentBadge(meta) {
    if (!meta || parseInt(meta.IS_MAYBANK_CUSTOMER) !== 1) return "";
    var seg    = (meta.FINAL_CLASSIFICATION || "").trim() || "Unknown";
    var colors = segmentColors[seg] || segmentColors["Unknown"] || {bg:"#eee",text:"#333"};
    return "<span style='background:" + colors.bg + ";color:" + colors.text +
           ";padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;" +
           "margin-left:4px;'>" + escXml(seg) + "</span>";
}

function makeExMaybankBadge(meta) {
    if (!meta) return "";
    var flag = meta.CIF_ACTIVE_FLAG;
    if (flag === null || flag === undefined) return "";
    if (parseInt(flag) === 0)
        return "<span style='background:#555;color:#FFD700;padding:3px 9px;" +
               "border-radius:4px;font-size:11px;font-weight:600;" +
               "margin-left:4px;'>Ex-Maybank</span>";
    return "";
}

function flagBadge(val) {
    var active = (val === 1);
    return "<span style='background:" + (active ? "#fadbd8" : "#e8e8e8") +
           ";color:" + (active ? "#922b21" : "#888") +
           ";padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;'>" +
           (active ? "Yes" : "No") + "</span>";
}

function stageBadge(val) {
    if (!val && val !== 0) return "-";
    var s  = val.toString().trim();
    var bg = "#e8e8e8", tc = "#555";
    if      (s.indexOf("1") !== -1) { bg = "#d5f5e3"; tc = "#1e8449"; }
    else if (s.indexOf("2") !== -1) { bg = "#fef3cd"; tc = "#856404"; }
    else if (s.indexOf("3") !== -1) { bg = "#fadbd8"; tc = "#922b21"; }
    return "<span style='background:" + bg + ";color:" + tc +
           ";padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;'>" +
           escXml(s) + "</span>";
}

function tRow(label, value) {
    return "<tr><td class='lbl'>" + escXml(label) +
           "</td><td class='val'>" + fmtVal(value) + "</td></tr>";
}

function tSection(label) {
    return "<tr class='sec-hdr'><td colspan='2'>" + escXml(label) + "</td></tr>";
}

function renderRow(k, meta) {
    if (!fieldConfig[k]) return "";
    var label = fieldConfig[k].label;
    var badge = BADGE_FIELDS[k];
    if (badge === "stage")
        return "<tr><td class='lbl'>" + escXml(label) +
               "</td><td class='val'>" + stageBadge(meta[k]) + "</td></tr>";
    if (badge === "flag")
        return "<tr><td class='lbl'>" + escXml(label) +
               "</td><td class='val'>" + flagBadge(meta[k]) + "</td></tr>";
    if (AMT_FIELDS.has(k))
        return "<tr><td class='lbl'>" + escXml(label) +
               "</td><td class='val'>" + fmtAmt(meta[k]) + "</td></tr>";
    return tRow(label, meta[k]);
}

function makeAccSection(id, title, content, isOpen) {
    return "<div style='margin-bottom:8px;'>" +
        "<div id='acc-hdr-" + id + "' class='acc-header " +
        (isOpen ? "open" : "closed") + "'>" +
        "<span>" + escXml(title) + "</span>" +
        "<span id='acc-arrow-" + id + "'>" +
        (isOpen ? "&#9660;" : "&#9654;") + "</span></div>" +
        "<div id='acc-body-" + id + "' style='display:" +
        (isOpen ? "block" : "none") + ";padding:4px 2px;'>" +
        content + "</div></div>";
}

function attachAccordion(id) {
    var hdr  = document.getElementById("acc-hdr-"   + id);
    var body = document.getElementById("acc-body-"  + id);
    var arr  = document.getElementById("acc-arrow-" + id);
    if (!hdr || !body) return;
    hdr.addEventListener("click", function() {
        var isOpen = body.style.display !== "none";
        body.style.display = isOpen ? "none" : "block";
        if (arr) arr.innerHTML = isOpen ? "&#9654;" : "&#9660;";
        hdr.className = isOpen ? "acc-header closed" : "acc-header open";
        setAccState(id, !isOpen);
    });
}

function _nbCard(cardId, nbId, borderColor) {
    var realUEN = _d(nbId);
    var name    = idNameLookup[nbId] || realUEN;
    return "<div id='" + cardId + "' class='nb-card' " +
           "style='border-left-color:" + borderColor + ";'>" +
           "<div class='nb-name'>" + escXml(name)    + "</div>" +
           "<div class='nb-uen'>"  + escXml(realUEN) + "</div></div>";
}

function _eRow(label, value) {
    return "<div style='display:flex;justify-content:space-between;align-items:flex-start;" +
           "padding:4px 0;font-size:13px;gap:8px;'>" +
           "<span style='color:#888;flex-shrink:0;white-space:nowrap;'>" + escXml(label) + "</span>" +
           "<span style='font-weight:500;color:#222;text-align:right;" +
           "word-break:break-word;max-width:65%;'>" + value + "</span></div>";
}

// fmtUSD -- for EMIS USD amount fields, uses $ not S$
function fmtUSD(val) {
    if (val === null || val === undefined) return "-";
    if (typeof val === "number" && isNaN(val)) return "-";
    if (val < 0) return "-$" + Math.abs(Math.round(val)).toLocaleString();
    return "$" + Math.round(val).toLocaleString();
}

// *** new | fmtRatio -- for MFI ratio cols (DCSR, Gearing) displayed as plain decimal
function fmtRatio(val) {
    if (val === null || val === undefined) return "-";
    if (typeof val === "number" && isNaN(val)) return "-";
    return parseFloat(val).toFixed(2);
}

// ══════════════════════════════════════════════════════════════════════════
// EDGE CLICK PANEL: UNIFIED
// ══════════════════════════════════════════════════════════════════════════

function showEdgeInfo(edge) {
    var rel      = _getPairRel(edge.from, edge.to);
    var nameFrom = idNameLookup[edge.from] || _d(edge.from);
    var nameTo   = idNameLookup[edge.to]   || _d(edge.to);

    var nameLeft, nameRight, roleLeft, roleRight, arrowHtml;
    var centerLabel;

    var isRSMEOnly = !rel || (rel && !rel['id']);
    var isBoth     = rel && !!rel.ib;
    var isDirected = !isRSMEOnly && !isBoth;

    if (isRSMEOnly) {
        if (rel && rel.cu) {
            nameLeft  = idNameLookup[rel.cu]  || _d(rel.cu)  || nameFrom;
            nameRight = idNameLookup[rel.cou] || _d(rel.cou) || nameTo;
        } else {
            nameLeft  = nameFrom;
            nameRight = nameTo;
        }
        roleLeft    = "Customer";
        roleRight   = "Counterparty";
        centerLabel = "";
        arrowHtml   = "<div style='height:2px;background:#E8860A;" +
                      "border-radius:2px;width:100%;margin:0 4px;'></div>";

    } else if (isBoth) {
        nameLeft    = nameFrom;
        nameRight   = nameTo;
        roleLeft    = "";
        roleRight   = "";
        centerLabel = "Both Ways";
        arrowHtml   = "<span style='color:#E8860A;font-size:22px;" +
                      "line-height:1;font-weight:700;'>&#8596;</span>";

    } else {
        var buyerId    = rel.bu;
        var supplierId = rel.su;
        nameLeft    = buyerId    ? (idNameLookup[buyerId]    || _d(buyerId))    : nameFrom;
        nameRight   = supplierId ? (idNameLookup[supplierId] || _d(supplierId)) : nameTo;
        roleLeft    = "";
        roleRight   = "";
        centerLabel = "Pays To";
        arrowHtml   = "<span style='color:#E8860A;font-size:22px;" +
                      "line-height:1;font-weight:700;'>&#10230;</span>";
    }

    var html = "<div style='background:#1C1C1C;border-radius:10px;" +
               "padding:14px 16px 12px;margin-bottom:6px;" +
               "box-shadow:0 2px 8px rgba(0,0,0,0.25);'>" +
               "<table style='width:100%;border-collapse:collapse;'>" +
               "<tr>" +
               "<td style='width:38%;text-align:right;padding-bottom:4px;'>" +
               (roleLeft
                   ? "<span style='font-size:10px;font-weight:700;color:#FFD966;" +
                     "letter-spacing:0.8px;text-transform:uppercase;'>" +
                     escXml(roleLeft) + "</span>"
                   : "") +
               "</td>" +
               "<td style='width:24%;text-align:center;padding-bottom:4px;'>" +
               (centerLabel
                   ? "<span style='font-size:10px;font-weight:700;color:#FFD966;" +
                     "letter-spacing:0.8px;text-transform:uppercase;'>" +
                     escXml(centerLabel) + "</span>"
                   : "") +
               "</td>" +
               "<td style='width:38%;text-align:left;padding-bottom:4px;'>" +
               (roleRight
                   ? "<span style='font-size:10px;font-weight:700;color:#FFD966;" +
                     "letter-spacing:0.8px;text-transform:uppercase;'>" +
                     escXml(roleRight) + "</span>"
                   : "") +
               "</td>" +
               "</tr>" +
               "<tr>" +
               "<td style='width:38%;text-align:right;vertical-align:middle;padding-right:8px;'>" +
               "<span style='font-size:12px;font-weight:700;color:#ffffff;" +
               "word-break:break-word;line-height:1.4;'>" + escXml(nameLeft) + "</span>" +
               "</td>" +
               "<td style='width:24%;text-align:center;vertical-align:middle;padding:0 2px;'>" +
               arrowHtml +
               "</td>" +
               "<td style='width:38%;text-align:left;vertical-align:middle;padding-left:8px;'>" +
               "<span style='font-size:12px;font-weight:700;color:#ffffff;" +
               "word-break:break-word;line-height:1.4;'>" + escXml(nameRight) + "</span>" +
               "</td>" +
               "</tr>" +
               "</table></div>";

    html += "<div style='background:#ffffff;border:1px solid #e0e0e0;" +
            "border-radius:10px;overflow:hidden;margin-bottom:12px;" +
            "box-shadow:0 1px 4px rgba(0,0,0,0.06);'>";

    var inAA   = rel ? !!rel.ia : !!(edge._aa_ab  || edge._aa_ba);
    var inRSME = rel ? !!rel.ir : !!(edge._rsme_ab || edge._rsme_ba);

    html += "<div style='background:#4A235A;padding:8px 14px;'>" +
            "<span style='font-size:10.5px;font-weight:700;color:#fff;" +
            "text-transform:uppercase;letter-spacing:0.5px;'>" +
            "Declared Counterparty Info</span></div>" +
            "<div style='display:flex;justify-content:space-between;" +
            "align-items:center;padding:8px 14px;" +
            "border-bottom:1px solid #f0f0f0;background:#fdf8ff;'>" +
            "<span style='font-size:11px;color:#555;'>AA Paper</span>" +
            "<span style='font-size:15px;font-weight:700;color:" +
            (inAA ? "#27ae60" : "#bbb") + ";'>" +
            (inAA ? "&#10003;" : "&#8212;") + "</span></div>" +
            "<div style='display:flex;justify-content:space-between;" +
            "align-items:center;padding:8px 14px;background:#fdf8ff;'>" +
            "<span style='font-size:11px;color:#555;'>" +
            "RSME Supplier/Buyer Checklist</span>" +
            "<span style='font-size:15px;font-weight:700;color:" +
            (inRSME ? "#27ae60" : "#bbb") + ";'>" +
            (inRSME ? "&#10003;" : "&#8212;") + "</span></div>";

    var inFitas = rel ? !!rel['if'] : !!(
        (edge._fitas_ab_count && edge._fitas_ab_count > 0) ||
        (edge._fitas_ba_count && edge._fitas_ba_count > 0)
    );
    var inPayment = rel ? !!rel.if_pay : !!edge._inPayment;

    var fitasTotalAmt = (rel && rel.fta != null) ? rel.fta : null;
    var paymentTotalAmt = (rel && rel._payment_total_amt != null) ? rel._payment_total_amt : null;
    var grandTotal = (rel && rel.gta != null) ? rel.gta : null;

    html += "<div style='background:#5D3A1A;padding:8px 14px;margin-top:1px;'>" +
            "<span style='font-size:10.5px;font-weight:700;color:#fff;" +
            "text-transform:uppercase;letter-spacing:0.5px;'>" +
            "Trade &amp; Payment Transactions</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 90px;" +
            "padding:5px 14px 3px;background:#fdf6f0;'>" +
            "<span style='font-size:10px;font-weight:700;color:#888;'>" +
            "Source</span>" +
            "<span style='font-size:10px;font-weight:700;color:#888;" +
            "text-align:right;'>Amount</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 90px;" +
            "padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;'>" +
            "<span style='font-size:11px;color:#555;'>Trade Transactions (FITAS)</span>" +
            "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
            (inFitas && fitasTotalAmt != null ? fmtAmt(fitasTotalAmt) : "-") +
            "</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 90px;" +
            "padding:6px 14px;border-top:1px solid #f0e8e0;background:#ffffff;'>" +
            "<span style='font-size:11px;color:#555;'>Payment Transactions (TT/MEPS/FAST/GIRO)</span>" +
            "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
            (inPayment && paymentTotalAmt != null ? fmtAmt(paymentTotalAmt) : "-") +
            "</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 90px;" +
            "padding:7px 14px;border-top:1px solid #d0c0b0;background:#f5ede4;'>" +
            "<span style='font-size:11px;font-weight:700;color:#222;'>Total</span>" +
            "<span style='font-size:11px;font-weight:700;color:#222;text-align:right;'>" +
            (grandTotal != null ? fmtAmt(grandTotal) : "-") +
            "</span></div>";

    var _PROD_LABELS = {
        lc: 'LC', tr: 'TR', sta: 'STA',
        exportlc: 'ExportLC', fbep: 'FBEP', oat: 'OAT', others: 'Others'
    };

    html += "<div style='background:#1A5C2B;padding:8px 14px;margin-top:1px;'>" +
            "<span style='font-size:10.5px;font-weight:700;color:#fff;" +
            "text-transform:uppercase;letter-spacing:0.5px;'>Trade Transactions (FITAS)</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
            "gap:4px;padding:5px 14px 3px;background:#f0f9f2;'>" +
            "<span style='font-size:10px;font-weight:700;color:#888;'>Product</span>" +
            "<span style='font-size:10px;font-weight:700;color:#888;" +
            "text-align:right;'>Count</span>" +
            "<span style='font-size:10px;font-weight:700;color:#888;" +
            "text-align:right;'>Amount</span></div>";

    if (inFitas && rel) {
        var fitasRows     = [];
        var fitasTotCount = 0;
        var fitasTotAmt   = 0;

        Object.keys(_PROD_LABELS).forEach(function(prod) {
            var cnt = rel['f_' + prod + '_c'];
            var amt = rel['f_' + prod + '_a'];
            if ((cnt != null && cnt !== 0) || (amt != null && amt !== 0)) {
                fitasRows.push({label: _PROD_LABELS[prod], count: cnt || 0, amt: amt || 0});
                fitasTotCount += (cnt || 0);
                fitasTotAmt   += (amt || 0);
            }
        });

        if (fitasRows.length > 0) {
            fitasRows.forEach(function(r) {
                html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                        "gap:4px;padding:6px 14px;border-top:1px solid #e0f0e4;'>" +
                        "<span style='font-size:11px;color:#555;'>" +
                        escXml(r.label) + "</span>" +
                        "<span style='font-size:11px;font-weight:600;color:#222;" +
                        "text-align:right;'>" + fmtVal(r.count) + "</span>" +
                        "<span style='font-size:11px;font-weight:600;color:#222;" +
                        "text-align:right;'>" + fmtAmt(r.amt) + "</span></div>";
            });
            html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                    "gap:4px;padding:6px 14px;border-top:1px solid #b8d8be;" +
                    "background:#d5eeda;'>" +
                    "<span style='font-size:11px;font-weight:700;color:#1A5C2B;'>" +
                    "Total</span>" +
                    "<span style='font-size:11px;font-weight:700;color:#1A5C2B;" +
                    "text-align:right;'>" + fmtVal(fitasTotCount) + "</span>" +
                    "<span style='font-size:11px;font-weight:700;color:#1A5C2B;" +
                    "text-align:right;'>" + fmtAmt(fitasTotAmt) + "</span></div>";
        } else {
            html += "<div style='padding:8px 14px;border-top:1px solid #e0f0e4;'>" +
                    "<span style='font-size:11px;color:#aaa;'>No product breakdown available</span>" +
                    "</div>";
        }
    } else {
        html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                "gap:4px;padding:6px 14px;border-top:1px solid #e0f0e4;'>" +
                "<span style='font-size:11px;color:#aaa;'>-</span>" +
                "<span style='font-size:11px;color:#aaa;text-align:right;'>-</span>" +
                "<span style='font-size:11px;color:#aaa;text-align:right;'>-</span>" +
                "</div>";
    }

    html += "<div style='background:#0C447C;padding:8px 14px;margin-top:1px;'>" +
            "<span style='font-size:10.5px;font-weight:700;color:#fff;" +
            "text-transform:uppercase;letter-spacing:0.5px;'>" +
            "Payment Transactions (TT/MEPS/FAST/GIRO)</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
            "gap:4px;padding:5px 14px 3px;background:#eef4fb;'>" +
            "<span style='font-size:10px;font-weight:700;color:#888;'>Flow</span>" +
            "<span style='font-size:10px;font-weight:700;color:#888;" +
            "text-align:right;'>Count</span>" +
            "<span style='font-size:10px;font-weight:700;color:#888;" +
            "text-align:right;'>Amount</span></div>";

    if (inPayment && rel) {
        var useLabelled = isDirected &&
                          (rel.payment_b2sc != null || rel.payment_b2sa != null);

        var rowOneLabel, rowTwoLabel;
        var rowOneCount, rowOneAmt, rowOnePct;
        var rowTwoCount, rowTwoAmt, rowTwoPct;
        var ttTotCount, ttTotAmtVal;

        if (useLabelled) {
            rowOneLabel = escXml(nameLeft)  + " &#8594; " + escXml(nameRight);
            rowTwoLabel = escXml(nameRight) + " &#8594; " + escXml(nameLeft);
            rowOneCount = rel.payment_b2sc; rowOneAmt = rel.payment_b2sa; rowOnePct = rel.payment_b2sp;
            rowTwoCount = rel.payment_s2bc; rowTwoAmt = rel.payment_s2ba; rowTwoPct = rel.payment_s2bp;
            ttTotCount  = rel._payment_total_count; ttTotAmtVal = rel._payment_total_amt;
        } else {
            rowOneLabel = escXml(nameLeft)  + " &#8594; " + escXml(nameRight);
            rowTwoLabel = escXml(nameRight) + " &#8594; " + escXml(nameLeft);
            rowOneCount = rel._payment_ab_count || null;
            rowOneAmt   = rel._payment_ab_amt   || null;
            rowTwoCount = rel._payment_ba_count || null;
            rowTwoAmt   = rel._payment_ba_amt   || null;
            rowOnePct   = null;
            rowTwoPct   = null;
            ttTotCount  = rel._payment_total_count || null;
            ttTotAmtVal = rel._payment_total_amt   || null;
        }

        html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                "gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;align-items:start;'>" +
                "<div><div style='font-size:11px;color:#555;'>" + rowOneLabel + "</div>" +
                (rowOnePct != null
                    ? "<div style='font-size:10px;color:#aaa;margin-top:1px;'>" +
                      fmtPct(rowOnePct) + " of total</div>"
                    : "") +
                "</div>" +
                "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                fmtVal(rowOneCount) + "</span>" +
                "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                fmtAmt(rowOneAmt) + "</span></div>";

        if (rowTwoCount != null || rowTwoAmt != null) {
            html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                    "gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;align-items:start;'>" +
                    "<div><div style='font-size:11px;color:#555;'>" + rowTwoLabel + "</div>" +
                    (rowTwoPct != null
                        ? "<div style='font-size:10px;color:#aaa;margin-top:1px;'>" +
                          fmtPct(rowTwoPct) + " of total</div>"
                        : "") +
                    "</div>" +
                    "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                    fmtVal(rowTwoCount) + "</span>" +
                    "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                    fmtAmt(rowTwoAmt) + "</span></div>";
        }

        html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                "gap:4px;padding:7px 14px;border-top:1px solid #b8d0e8;" +
                "background:#d0e4f4;'>" +
                "<span style='font-size:11px;font-weight:700;color:#0C447C;'>Total</span>" +
                "<span style='font-size:11px;font-weight:700;color:#0C447C;" +
                "text-align:right;'>" + fmtVal(ttTotCount) + "</span>" +
                "<span style='font-size:11px;font-weight:700;color:#0C447C;" +
                "text-align:right;'>" + fmtAmt(ttTotAmtVal) + "</span></div>";

    } else {
        html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
                "gap:4px;padding:6px 14px;border-top:1px solid #e4eef7;'>" +
                "<span style='font-size:11px;color:#aaa;'>-</span>" +
                "<span style='font-size:11px;color:#aaa;text-align:right;'>-</span>" +
                "<span style='font-size:11px;color:#aaa;text-align:right;'>-</span>" +
                "</div>";
    }

    html += "</div>";
    document.getElementById("side-panel-content").innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════
// EDGE CLICK PANEL: SELF-LOOP
// ══════════════════════════════════════════════════════════════════════════

function showSelfLoopInfo(edge) {
    // Visual parity with showEdgeInfo: dark header card on top, white body card
    // below with the same Trade & Payment Transactions summary table.
    // For a self-loop the sender and receiver are the same company, so the
    // header shows the company name once with a "Self-Transfer" label and a
    // loop glyph in place of the directional arrow.
    var name = idNameLookup[edge.from] || _d(edge.from);

    // The vis.js self-loop edge only carries the all-txn totals; per-source
    // FITAS / Payment counts live in their own lookup maps keyed by compressed
    // node id (built at the top of this file from *SelfLoopEdgesData arrays).
    var fitasEntry   = (typeof _fitasSelfLoopMap   !== "undefined") ? (_fitasSelfLoopMap[edge.from]   || {}) : {};
    var paymentEntry = (typeof _paymentSelfLoopMap !== "undefined") ? (_paymentSelfLoopMap[edge.from] || {}) : {};
    var fitasCount   = fitasEntry._fitas_count     || 0;
    var fitasAmt     = fitasEntry._fitas_amt       || 0;
    var paymentCount = paymentEntry._payment_count || 0;
    var paymentAmt   = paymentEntry._payment_amt   || 0;
    var hasFitas     = fitasCount   > 0 || fitasAmt   > 0;
    var hasPayment   = paymentCount > 0 || paymentAmt > 0;

    var totalAmt   = (edge._all_txn_amt   != null) ? edge._all_txn_amt
                                                   : (fitasAmt + paymentAmt);
    var totalCount = (edge._all_txn_count != null) ? edge._all_txn_count
                                                   : (fitasCount + paymentCount);

    // ── Header card (dark) ────────────────────────────────────────────────
    var html = "<div style='background:#1C1C1C;border-radius:10px;" +
               "padding:14px 16px 12px;margin-bottom:6px;" +
               "box-shadow:0 2px 8px rgba(0,0,0,0.25);'>" +
               "<table style='width:100%;border-collapse:collapse;'>" +
               // Top row -- centered "Self-Transfer" label (gold)
               "<tr><td style='text-align:center;padding-bottom:6px;'>" +
                 "<span style='font-size:10px;font-weight:700;color:#FFD966;" +
                 "letter-spacing:0.8px;text-transform:uppercase;'>" +
                 "Self-Transfer</span>" +
               "</td></tr>" +
               // Bottom row -- centered company name + loop glyph
               "<tr><td style='text-align:center;vertical-align:middle;'>" +
                 "<span style='font-size:12px;font-weight:700;color:#ffffff;" +
                 "line-height:1.4;'>" + escXml(name) + "</span>" +
                 "<span style='color:#E8860A;font-size:20px;line-height:1;" +
                 "font-weight:700;margin-left:10px;vertical-align:middle;'>" +
                 "&#8635;</span>" +
               "</td></tr>" +
               "</table>" +
               "</div>";

    // ── Body card (white) -- summary table ────────────────────────────────
    html += "<div style='background:#ffffff;border:1px solid #e0e0e0;" +
            "border-radius:10px;overflow:hidden;margin-bottom:12px;" +
            "box-shadow:0 1px 4px rgba(0,0,0,0.06);'>";

    // Trade & Payment Transactions block (matches directional panel)
    html += "<div style='background:#5D3A1A;padding:8px 14px;'>" +
              "<span style='font-size:10.5px;font-weight:700;color:#fff;" +
              "text-transform:uppercase;letter-spacing:0.5px;'>" +
              "Trade &amp; Payment Transactions</span></div>" +
            "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
              "gap:4px;padding:5px 14px 3px;background:#fdf6f0;'>" +
              "<span style='font-size:10px;font-weight:700;color:#888;'>Source</span>" +
              "<span style='font-size:10px;font-weight:700;color:#888;text-align:right;'>Count</span>" +
              "<span style='font-size:10px;font-weight:700;color:#888;text-align:right;'>Amount</span>" +
            "</div>";

    // FITAS row
    html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
              "gap:4px;padding:6px 14px;border-top:1px solid #f0e8e0;" +
              "background:#ffffff;'>" +
              "<span style='font-size:11px;color:#555;'>Trade (FITAS)</span>" +
              "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                (hasFitas ? fmtVal(fitasCount) : "-") + "</span>" +
              "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                (hasFitas ? fmtAmt(fitasAmt) : "-") + "</span>" +
            "</div>";

    // Payment row
    html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
              "gap:4px;padding:6px 14px;border-top:1px solid #f0e8e0;" +
              "background:#ffffff;'>" +
              "<span style='font-size:11px;color:#555;'>Payment (TT/MEPS/FAST/GIRO)</span>" +
              "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                (hasPayment ? fmtVal(paymentCount) : "-") + "</span>" +
              "<span style='font-size:11px;font-weight:600;color:#222;text-align:right;'>" +
                (hasPayment ? fmtAmt(paymentAmt) : "-") + "</span>" +
            "</div>";

    // Total row
    html += "<div style='display:grid;grid-template-columns:1fr 52px 90px;" +
              "gap:4px;padding:7px 14px;border-top:1px solid #d0c0b0;" +
              "background:#f5ede4;'>" +
              "<span style='font-size:11px;font-weight:700;color:#222;'>Total</span>" +
              "<span style='font-size:11px;font-weight:700;color:#222;text-align:right;'>" +
                fmtVal(totalCount) + "</span>" +
              "<span style='font-size:11px;font-weight:700;color:#222;text-align:right;'>" +
                fmtAmt(totalAmt) + "</span>" +
            "</div>";

    html += "</div>";

    document.getElementById("side-panel-content").innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════
// SHOW NODE INFO
// ══════════════════════════════════════════════════════════════════════════

var showNodeInfo = function(uid) {};

showNodeInfo = function(uid) {
    currentNode    = uid;
    var id         = _e(uid);
    var meta       = nodeMetaMap[id] || {};
    var ntype      = nodeTypeMap[id] || "Non-Maybank Customer";
    var typeColor  = getTypeColor(ntype);

    var fitasSummary         = fitasNodeSummary[id];
    var fitasSelfLoopPresent = fitasSelfLoopIds.has(id);
    var fitasSelfLoopEdge    = _fitasSelfLoopMap[id] || null;

    var hasFITAS = fitasSelfLoopPresent ||
        (!!fitasSummary && (
            (fitasSummary.fitas_ord_freq  || 0) > 0 ||
            (fitasSummary.fitas_bene_freq || 0) > 0
        ));

    var hasRSME    = rsmeNodeIds.has(id);
    var hasAAPaper = aaPaperNodeIds.has(id);
    var isMaybank  = (ntype !== "Non-Maybank Customer");
    var isTrade    = (ntype === "Maybank Trade Customer");
    var accS       = getAccStates();
    var entityName = idNameLookup[id] || uid;

    // ── Overview ──────────────────────────────────────────────────────────
    var overviewContent = "<table class='info-table'>" + tSection("Entity Info") +
        tRow("UEN", uid) +
        Object.keys(fieldConfig)
            .filter(function(k) { return fieldConfig[k].section === "overview"; })
            .map(function(k)    { return renderRow(k, meta); })
            .join("") + "</table>";

    // ── Data Sources ──────────────────────────────────────────────────────
    var hasFast = fastNodeIds.has(id);
    var hasGiro = giroNodeIds.has(id);
    var hasTT   = consolTTNodeIds.has(id);

    var dsContent =
        "<table class='info-table' style='margin-top:4px;'>" +
        "<tr style='background:#f5f5f5;'>" +
        "<td class='lbl' style='font-weight:700;color:#333;'>Source</td>" +
        "<td class='val'> </td></tr>" +
        "<tr><td class='lbl'>RSME Buyer/Supplier Checklist</td>" +
        "<td class='val' style='color:" + (hasRSME ? "#27ae60" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasRSME ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "<tr><td class='lbl'>AA Paper</td>" +
        "<td class='val' style='color:" + (hasAAPaper ? "#8b4513" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasAAPaper ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "<tr><td class='lbl'>FITAS</td>" +
        "<td class='val' style='color:" + (hasFITAS ? "#6f42c1" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasFITAS ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "<tr><td class='lbl'>TT</td>" +
        "<td class='val' style='color:" + (hasTT ? "#2980b9" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasTT ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "<tr><td class='lbl'>FAST</td>" +
        "<td class='val' style='color:" + (hasFast ? "#1A5276" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasFast ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "<tr><td class='lbl'>GIRO</td>" +
        "<td class='val' style='color:" + (hasGiro ? "#1E8449" : "#bbb") +
        ";font-size:15px;font-weight:700;'>" + (hasGiro ? "&#10003;" : "&#8212;") + "</td></tr>" +
        "</table>";

    // ── Payment Transactions Summary (TT/MEPS/FAST/GIRO only) ─────────────
    var paymentSummaryContent = "";
    var paymentSummary        = paymentNodeSummary[id];
    var paymentSelfLoopEdge   = _paymentSelfLoopMap[id] || null;
    var paymentSelfLoopPresent = !!paymentSelfLoopEdge ||
        (typeof paymentSelfLoopIds !== "undefined" && paymentSelfLoopIds.has(id));
    var hasPayment = paymentSelfLoopPresent ||
        (!!paymentSummary && (
            (paymentSummary.payment_ord_freq  || 0) > 0 ||
            (paymentSummary.payment_bene_freq || 0) > 0
        ));

    if (hasPayment) {
        var payHasExternal = !!paymentSummary &&
            ((paymentSummary.payment_ord_freq || 0) > 0 ||
             (paymentSummary.payment_bene_freq || 0) > 0);
        if (allTxnLatestDate) {
            paymentSummaryContent +=
                "<p style='font-size:10px;color:#888;margin:4px 0 8px;" +
                "padding-left:2px;'>Latest Payment record: " +
                escXml(allTxnLatestDate) + "</p>";
        }
        if (payHasExternal) {
            paymentSummaryContent +=
                "<div class='tt-card-ord'><div class='tt-title'>&#8594; As Sender</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + fmtVal(paymentSummary.payment_ord_freq||0) + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + fmtAmt(paymentSummary.payment_ord_amt||0) + "</span></div></div>" +
                "<div class='tt-card-bene'><div class='tt-title'>&#8592; As Receiver</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + fmtVal(paymentSummary.payment_bene_freq||0) + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + fmtAmt(paymentSummary.payment_bene_amt||0) + "</span></div></div>";
        }
        if (paymentSelfLoopPresent) {
            paymentSummaryContent +=
                "<div style='background:#F5F0FF;border-left:3px solid #7F77DD;" +
                "border-radius:6px;padding:10px 12px;margin-bottom:6px;'>" +
                "<div style='font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;'>" +
                "&#8635; Self-transfer (Payment)</div>" +
                "<div class='tt-row'><span>Transaction count</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtVal((paymentSelfLoopEdge && paymentSelfLoopEdge._payment_count) || 0) + "</span></div>" +
                "<div class='tt-row'><span>Transaction amount</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtAmt((paymentSelfLoopEdge && paymentSelfLoopEdge._payment_amt) || 0) + "</span></div></div>";
        }
    }

    // ── FITAS Summary ─────────────────────────────────────────────────────
    var fitasSummaryContent = "";
    if (hasFITAS) {
        var fitasHasExternal = !!fitasSummary &&
            ((fitasSummary.fitas_ord_freq || 0) > 0 ||
             (fitasSummary.fitas_bene_freq || 0) > 0);

        if (fitasLatestDate) {
            fitasSummaryContent +=
                "<p style='font-size:10px;color:#888;margin:4px 0 8px;" +
                "padding-left:2px;'>Latest FITAS record: " + escXml(fitasLatestDate) + "</p>";
        }
        if (fitasHasExternal) {
            var fitasOrdFreq  = fitasSummary.fitas_ord_freq  || 0;
            var fitasOrdAmt   = fitasSummary.fitas_ord_amt   || 0;
            var fitasBeneFreq = fitasSummary.fitas_bene_freq || 0;
            var fitasBeneAmt  = fitasSummary.fitas_bene_amt  || 0;
            fitasSummaryContent +=
                "<div class='tt-card-ord'><div class='tt-title'>&#8594; As Sender</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + (fitasOrdFreq > 0 ? fmtVal(fitasOrdFreq) : "-") + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + (fitasOrdAmt > 0 ? fmtAmt(fitasOrdAmt) : "-") + "</span></div></div>" +
                "<div class='tt-card-bene'><div class='tt-title'>&#8592; As Receiver</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + (fitasBeneFreq > 0 ? fmtVal(fitasBeneFreq) : "-") + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + (fitasBeneAmt > 0 ? fmtAmt(fitasBeneAmt) : "-") + "</span></div></div>";
        }
        if (fitasSelfLoopPresent) {
            fitasSummaryContent +=
                "<div style='background:#F5F0FF;border-left:3px solid #7F77DD;" +
                "border-radius:6px;padding:10px 12px;margin-bottom:6px;'>" +
                "<div style='font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;'>" +
                "&#8635; Self-transfer (FITAS)</div>" +
                "<div class='tt-row'><span>Transaction count</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtVal((fitasSelfLoopEdge && fitasSelfLoopEdge._fitas_count) || 0) + "</span></div>" +
                "<div class='tt-row'><span>Transaction amount</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtAmt((fitasSelfLoopEdge && fitasSelfLoopEdge._fitas_amt) || 0) + "</span></div></div>";
        }
    }

    // ── All Transactions Summary (FITAS + TT/MEPS/FAST/GIRO) ──────────────
    // Always show whenever either FITAS or Payment has activity -- the
    // All Transactions accordion is the union view of both, so the user
    // expects it to appear whenever either contributes.
    var allTxnSummaryContent = "";
    var allTxnSummary        = (typeof allTxnNodeSummary !== "undefined")
                                   ? allTxnNodeSummary[id] : null;
    var allTxnSelfLoopEdge   = _allTxnSelfLoopMap[id] || null;
    var allTxnSelfLoopPresent = !!allTxnSelfLoopEdge || allTxnSelfLoopIds.has(id);
    var hasAllTxn = hasFITAS || hasPayment;

    if (hasAllTxn) {
        var allTxnHasExternal = !!allTxnSummary &&
            ((allTxnSummary.all_txn_ord_freq || 0) > 0 ||
             (allTxnSummary.all_txn_bene_freq || 0) > 0);
        if (allTxnLatestDate) {
            allTxnSummaryContent +=
                "<p style='font-size:10px;color:#888;margin:4px 0 8px;" +
                "padding-left:2px;'>Latest record: " +
                escXml(allTxnLatestDate) + "</p>";
        }
        if (allTxnHasExternal) {
            allTxnSummaryContent +=
                "<div class='tt-card-ord'><div class='tt-title'>&#8594; As Sender</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + fmtVal(allTxnSummary.all_txn_ord_freq||0) + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + fmtAmt(allTxnSummary.all_txn_ord_amt||0) + "</span></div></div>" +
                "<div class='tt-card-bene'><div class='tt-title'>&#8592; As Receiver</div>" +
                "<div class='tt-row'><span>Transactions</span>" +
                "<span class='tt-val'>" + fmtVal(allTxnSummary.all_txn_bene_freq||0) + "</span></div>" +
                "<div class='tt-row'><span>Total Amount</span>" +
                "<span class='tt-val'>" + fmtAmt(allTxnSummary.all_txn_bene_amt||0) + "</span></div></div>";
        }
        if (allTxnSelfLoopPresent) {
            allTxnSummaryContent +=
                "<div style='background:#F5F0FF;border-left:3px solid #7F77DD;" +
                "border-radius:6px;padding:10px 12px;margin-bottom:6px;'>" +
                "<div style='font-size:12px;font-weight:700;color:#3C3489;margin-bottom:6px;'>" +
                "&#8635; Self-transfer (all sources)</div>" +
                "<div class='tt-row'><span>Transaction count</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtVal((allTxnSelfLoopEdge && allTxnSelfLoopEdge._all_txn_count) || 0) + "</span></div>" +
                "<div class='tt-row'><span>Transaction amount</span>" +
                "<span style='font-weight:600;color:#3C3489;'>" +
                fmtAmt((allTxnSelfLoopEdge && allTxnSelfLoopEdge._all_txn_amt) || 0) + "</span></div></div>";
        }
    }

    // ── Facilities ────────────────────────────────────────────────────────
    var facilitiesContent = "";
    if (isMaybank) {
        facilitiesContent = "<table class='info-table'>";

        if (isTrade) {
            facilitiesContent += tSection("Trade Facility Summary");
            facilitiesContent += "<tr><td class='lbl'>Authorised Limit</td>" +
                "<td class='val'>" + fmtAmt(meta['TF_LCY_AUTH_LMT']) + "</td></tr>";
            facilitiesContent += "<tr><td class='lbl'>Available Limit</td>" +
                "<td class='val'>" + fmtAmt(meta['TF_LCY_AVAIL_LMT']) + "</td></tr>";

            var totOS       = (meta['TF_LCY_TOT_OS'] != null) ? meta['TF_LCY_TOT_OS'] : null;
            var obsOS       = (meta['TF_LCY_OBS_OS'] != null) ? meta['TF_LCY_OBS_OS'] : null;
            var outstanding = (totOS != null || obsOS != null)
                ? ((totOS || 0) + (obsOS || 0)) : null;

            facilitiesContent += "<tr><td class='lbl' style='font-weight:600;'>" +
                "Outstanding Balance</td>" +
                "<td class='val' style='font-weight:600;'>" +
                (outstanding != null ? fmtAmt(outstanding) : "-") + "</td></tr>";
            facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
                "On-Balance Sheet</td><td class='val'>" + fmtAmt(totOS) + "</td></tr>";
            facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
                "Off-Balance Sheet</td><td class='val'>" + fmtAmt(obsOS) + "</td></tr>";

            var auth    = meta['TF_LCY_AUTH_LMT'];
            var utilPct = (outstanding != null && auth != null && auth > 0)
                ? (outstanding / auth * 100).toFixed(1) + "%" : "-";
            facilitiesContent += "<tr><td class='lbl'>Utilisation</td>" +
                "<td class='val'>" + utilPct + "</td></tr>";
        }

        facilitiesContent += tSection("Banking Balances");

        var trLn    = meta['TR_LN']    != null ? meta['TR_LN']    : null;
        var nonTrLn = meta['NONTR_LN'] != null ? meta['NONTR_LN'] : null;
        var totLn   = (trLn != null || nonTrLn != null)
            ? ((trLn || 0) + (nonTrLn || 0)) : null;
        facilitiesContent += "<tr><td class='lbl' style='font-weight:600;'>Total Loans</td>" +
            "<td class='val' style='font-weight:600;'>" +
            (totLn != null ? fmtAmt(totLn) : "-") + "</td></tr>";
        facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
            "Trade Loans</td><td class='val'>" + fmtAmt(trLn) + "</td></tr>";
        facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
            "Non-Trade Loans</td><td class='val'>" + fmtAmt(nonTrLn) + "</td></tr>";

        var casa   = meta['CASA']   != null ? meta['CASA']   : null;
        var fd     = meta['FD']     != null ? meta['FD']     : null;
        var strctd = meta['STRCTD'] != null ? meta['STRCTD'] : null;
        var totDep = (casa != null || fd != null || strctd != null)
            ? ((casa || 0) + (fd || 0) + (strctd || 0)) : null;
        facilitiesContent += "<tr><td class='lbl' style='font-weight:600;'>Total Deposits</td>" +
            "<td class='val' style='font-weight:600;'>" +
            (totDep != null ? fmtAmt(totDep) : "-") + "</td></tr>";
        facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
            "Current Account</td><td class='val'>" + fmtAmt(casa) + "</td></tr>";
        facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
            "Time Deposits</td><td class='val'>" + fmtAmt(fd) + "</td></tr>";
        facilitiesContent += "<tr><td class='lbl' style='padding-left:16px;color:#aaa;'>" +
            "Structured TD</td><td class='val'>" + fmtAmt(strctd) + "</td></tr>";

        facilitiesContent += "</table>";
    }

    // ── Credit Status ─────────────────────────────────────────────────────
    var creditContent = "";
    if (isMaybank) {
        var CSUB = [
            {header: "Risk Flags",
             keys: ["is_watchlist","is_special_mention","is_npl"]},
            {header: "Credit Profile",
             keys: ["impairment_stage","RISK_GRADE","credit_status",
                    "borrower_risk_rating","rating_date"]},
            {header: "Payment Conduct",
             keys: ["months_on_book","latest_dpd_bucket","delinquency_count_12m"]},
        ];
        creditContent = "<table class='info-table'>";
        CSUB.forEach(function(sub) {
            var rows = sub.keys
                .filter(function(k) { return !!fieldConfig[k]; })
                .map(function(k)    { return renderRow(k, meta); })
                .join("");
            if (rows) creditContent += tSection(sub.header) + rows;
        });
        creditContent += "</table>";
    }

    // ── Financials (ACRA + EMIS + MFI) ────────────────────────────────────
    // MFI moved here as a third subsection (was a standalone accordion before).
    var acraFinF = Object.keys(fieldConfig).filter(function(k) {
        return fieldConfig[k].section === "acrafin";
    });
    var emisFinF = Object.keys(fieldConfig).filter(function(k) {
        return fieldConfig[k].section === "emisfin";
    });
    // MFI: only fields with enabled !== false render. Used for the MFI
    // subsection inside Financials.
    var mfiFinF = Object.keys(fieldConfig).filter(function(k) {
        return fieldConfig[k].section === "mfifin"
            && fieldConfig[k].enabled !== false;
    });
    var hasMFI = mfiFinF.some(function(k) { return meta[k] != null; });

    var finContent = "<table class='info-table'>";
    if (isMaybank && acraFinF.length > 0) {
        finContent += tSection("ACRA");
        acraFinF.forEach(function(k) { finContent += renderRow(k, meta); });
    }

    if (emisFinF.length > 0) {
        finContent += tSection("EMIS");
        var _emisOrder = [
            'EMIS Fiscal Year',
            'EMIS Total Operating Revenue (USD)',
            'EMIS Operating Profit (USD)',
            'EMIS Profit Before Income Tax (USD)',
            'EMIS Total Assets (USD)',
            'EMIS Free Cash Flow (USD)',
            'EMIS Net Cash Flow from Operations (USD)',
            'EMIS Return on Assets / ROA (%)',
            'EMIS Return on Equity / ROE (%)',
            'EMIS Audited',
            'EMIS Source',
        ];
        var _emisUSD = new Set([
            'EMIS Total Operating Revenue (USD)',
            'EMIS Operating Profit (USD)',
            'EMIS Profit Before Income Tax (USD)',
            'EMIS Total Assets (USD)',
            'EMIS Free Cash Flow (USD)',
            'EMIS Net Cash Flow from Operations (USD)',
        ]);
        _emisOrder.forEach(function(k) {
            if (!fieldConfig[k]) return;
            var label = fieldConfig[k].label;
            if (_emisUSD.has(k)) {
                finContent += "<tr><td class='lbl'>" + escXml(label) +
                    "</td><td class='val'>" + fmtUSD(meta[k]) + "</td></tr>";
            } else {
                finContent += renderRow(k, meta);
            }
        });
    }

    // MFI subsection: MFI_END_DTE first, then the P&L fields in order.
    if (hasMFI) {
        finContent += tSection("MFI");
        var _mfiOrder = [
            'MFI_END_DTE',
            'MFI_SALES', 'MFI_COGS', 'MFI_GROSS_PNL',
            'MFI_PRETAX_PNL_BEFORE_INT', 'MFI_PNL_BEFORE_TAX',
            'MFI_PNL_AFT_TAX', 'MFI_EBITDA',
        ];
        _mfiOrder.forEach(function(k) {
            if (!fieldConfig[k] || fieldConfig[k].enabled === false) return;
            finContent += renderRow(k, meta);
        });
    }
    finContent += "</table>";
    var hasFinancials = (isMaybank && acraFinF.length > 0) || emisFinF.length > 0 || hasMFI;

    // *** new | CIP Collaterals section
    // Driven by fieldConfig section='cipinfo'.
    // Amount cols use fmtAmt (SGD), count cols use fmtVal.
    // Only shown if at least one CIP field is non-null.
    var cipFinF = Object.keys(fieldConfig).filter(function(k) {
        return fieldConfig[k].section === "cipinfo";
    });
    var hasCIP = cipFinF.some(function(k) {
        return meta[k] != null;
    });

    var cipContent = "<table class='info-table'>";
    if (hasCIP && cipFinF.length > 0) {
        // Facility & loan sub-section
        var _cipFacOrder = [
            'CIP_FAC_LIMIT_SGD', 'CIP_LOAN_BALANCE_SGD', 'CIP_NPL_BALANCE_SGD',
        ];
        var cipFacRows = _cipFacOrder.filter(function(k) { return !!fieldConfig[k]; })
            .map(function(k) { return renderRow(k, meta); }).join("");
        if (cipFacRows) {
            cipContent += tSection("CIP Facility & Loan");
            cipContent += cipFacRows;
        }

        // Security / collateral sub-section
        var _cipSecOrder = [
            'CIP_SEC_AMT', 'CIP_SEC_EMV', 'CIP_SEC_FSV', 'CIP_SEC_FIV',
            'CIP_N_PROPERTIES',
        ];
        var cipSecRows = _cipSecOrder.filter(function(k) { return !!fieldConfig[k]; })
            .map(function(k) { return renderRow(k, meta); }).join("");
        if (cipSecRows) {
            cipContent += tSection("CIP Collateral");
            cipContent += cipSecRows;
        }

        // Account counts sub-section
        var _cipAccOrder = [
            'CIP_N_ACC_TOTAL', 'CIP_N_ACC_OPEN', 'CIP_N_ACC_CLOSED',
        ];
        var cipAccRows = _cipAccOrder.filter(function(k) { return !!fieldConfig[k]; })
            .map(function(k) { return renderRow(k, meta); }).join("");
        if (cipAccRows) {
            cipContent += tSection("CIP Accounts");
            cipContent += cipAccRows;
        }
    } else {
        cipContent += "<tr><td colspan='2' style='color:#aaa;font-size:11px;" +
                      "text-align:center;padding:12px;'>No CIP data available</td></tr>";
    }
    cipContent += "</table>";

    // ── Network adjacency maps ────────────────────────────────────────────
    var rsmeNbs        = adjacencyMap[id]    || [];
    var fitasOutNbs    = fitasOutAdj[id]      || [];
    var fitasInNbs     = fitasInAdj[id]       || [];
    var aaPaperOutNbs  = aaPaperOutAdj[id]    || [];
    var aaPaperInNbs   = aaPaperInAdj[id]     || [];

    var rsmeNetContent = "";
    if (rsmeNbs.length === 0) {
        rsmeNetContent = "<p style='color:#aaa;font-size:12px;text-align:center;margin-top:8px;'>No RSME connections.</p>";
    } else {
        rsmeNbs.forEach(function(nbId) {
            rsmeNetContent += _nbCard("nbcard-rsme-" + nbId, nbId,
                getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
        });
    }

    var paymentOutNbs = paymentOutAdj[id] || [];
    var paymentInNbs  = paymentInAdj[id]  || [];
    var paymentNetContent = "";
    if (paymentOutNbs.length === 0 && paymentInNbs.length === 0) {
        paymentNetContent = "<p style='color:#aaa;font-size:12px;text-align:center;margin-top:8px;'>No Payment connections.</p>";
    } else {
        if (paymentOutNbs.length > 0) {
            paymentNetContent += "<div style='font-size:12px;font-weight:600;color:#2980b9;margin:8px 0 4px;'>&#8594; Sends to (" + paymentOutNbs.length + ")</div>";
            paymentOutNbs.forEach(function(nbId) {
                paymentNetContent += _nbCard("nbcard-payment-out-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (paymentInNbs.length > 0) {
            paymentNetContent += "<div style='font-size:12px;font-weight:600;color:#27ae60;margin:8px 0 4px;'>&#8592; Receives from (" + paymentInNbs.length + ")</div>";
            paymentInNbs.forEach(function(nbId) {
                paymentNetContent += _nbCard("nbcard-payment-in-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (allTxnSelfLoopIds.has(id)) {
            paymentNetContent += "<div style='background:#f0f0f0;border-radius:6px;padding:6px 10px;margin-top:6px;font-size:11px;color:#555;'>&#8635; Self-transfer detected</div>";
        }
    }

    var fitasNetContent = "";
    if (fitasOutNbs.length === 0 && fitasInNbs.length === 0) {
        fitasNetContent = "<p style='color:#aaa;font-size:12px;text-align:center;margin-top:8px;'>No FITAS connections.</p>";
    } else {
        if (fitasOutNbs.length > 0) {
            fitasNetContent += "<div style='font-size:12px;font-weight:600;color:#6f42c1;margin:8px 0 4px;'>&#8594; Sends to (" + fitasOutNbs.length + ")</div>";
            fitasOutNbs.forEach(function(nbId) {
                fitasNetContent += _nbCard("nbcard-fitas-out-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (fitasInNbs.length > 0) {
            fitasNetContent += "<div style='font-size:12px;font-weight:600;color:#6f42c1;margin:8px 0 4px;'>&#8592; Receives from (" + fitasInNbs.length + ")</div>";
            fitasInNbs.forEach(function(nbId) {
                fitasNetContent += _nbCard("nbcard-fitas-in-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (fitasSelfLoopIds.has(id)) {
            fitasNetContent += "<div style='background:#f0f0f0;border-radius:6px;padding:6px 10px;margin-top:6px;font-size:11px;color:#555;'>&#8635; Self-transfer detected</div>";
        }
    }

    var aaPaperNetContent = "";
    if (aaPaperOutNbs.length === 0 && aaPaperInNbs.length === 0) {
        aaPaperNetContent = "<p style='color:#aaa;font-size:12px;text-align:center;margin-top:8px;'>No AA Paper connections.</p>";
    } else {
        if (aaPaperOutNbs.length > 0) {
            aaPaperNetContent += "<div style='font-size:12px;font-weight:600;color:#8b4513;margin:8px 0 4px;'>&#8594; Suppliers (" + aaPaperOutNbs.length + ")</div>";
            aaPaperOutNbs.forEach(function(nbId) {
                aaPaperNetContent += _nbCard("nbcard-aapaper-out-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (aaPaperInNbs.length > 0) {
            aaPaperNetContent += "<div style='font-size:12px;font-weight:600;color:#8b4513;margin:8px 0 4px;'>&#8592; Buyers (" + aaPaperInNbs.length + ")</div>";
            aaPaperInNbs.forEach(function(nbId) {
                aaPaperNetContent += _nbCard("nbcard-aapaper-in-" + nbId, nbId,
                    getTypeColor(nodeTypeMap[nbId] || "Non-Maybank Customer"));
            });
        }
        if (aaPaperSelfLoopIds.has(id)) {
            aaPaperNetContent += "<div style='background:#f0f0f0;border-radius:6px;padding:6px 10px;margin-top:6px;font-size:11px;color:#555;'>&#8635; Self-relationship detected</div>";
        }
    }

    // ── Risk badge ────────────────────────────────────────────────────────
    var riskBadge = "";
    if (isMaybank) {
        if (meta.is_npl === 1)
            riskBadge = "<span style='background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;'>NPL</span>";
        else if (meta.is_special_mention === 1)
            riskBadge = "<span style='background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;'>SMA</span>";
        else if (meta.is_watchlist === 1)
            riskBadge = "<span style='background:#c0392b;color:#fff;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:600;margin-left:4px;'>Watchlist</span>";
    }

    // ── Unique total connections (Set union across all sources) ───────────
    var aaPaperNbs = Array.from(new Set(aaPaperOutNbs.concat(aaPaperInNbs)));
    var _allNbSet  = new Set();
    rsmeNbs.forEach(function(x) { _allNbSet.add(x); });
    paymentOutNbs.forEach(function(x) { _allNbSet.add(x); });
    paymentInNbs.forEach(function(x) { _allNbSet.add(x); });
    fitasOutNbs.forEach(function(x) { _allNbSet.add(x); });
    fitasInNbs.forEach(function(x) { _allNbSet.add(x); });
    aaPaperOutNbs.forEach(function(x) { _allNbSet.add(x); });
    aaPaperInNbs.forEach(function(x) { _allNbSet.add(x); });
    var totalNbs = _allNbSet.size;

    // ── Render ────────────────────────────────────────────────────────────
    document.getElementById("side-panel-content").innerHTML =
        "<div id='main-company-card' class='company-main-card'>" +
        "<div class='cn'>" + escXml(entityName) + "</div>" +
        "<div class='cu'>" + escXml(uid) + "</div></div>" +
        "<div style='display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:10px;'>" +
        "<span style='background:" + typeColor + ";color:#fff;padding:3px 9px;border-radius:4px;" +
        "font-size:11px;font-weight:600;'>" + escXml(ntype) + "</span>" +
        makeSegmentBadge(meta) + makeExMaybankBadge(meta) + riskBadge + "</div>" +
        "<p style='margin:0 0 10px;font-size:12px;color:#555;'><b>" + totalNbs +
        "</b> total unique relationship" + (totalNbs !== 1 ? "s" : "") + "</p>" +
        makeAccSection("overview",    "Overview",              overviewContent,       accS.overview) +
        makeAccSection("datasources", "Data Sources",          dsContent,             accS.datasources) +
        (hasFITAS    ? makeAccSection("fitas_summary",    "Trade Transactions (FITAS) Summary",
                                      fitasSummaryContent,    accS.fitas_summary) : "") +
        (hasPayment  ? makeAccSection("payment_summary", "Payment Transactions (TT/MEPS/FAST/GIRO) Summary",
                                      paymentSummaryContent, accS.payment_summary) : "") +
        (hasAllTxn   ? makeAccSection("all_txn_summary", "All Transactions (FITAS + TT/MEPS/FAST/GIRO) Summary",
                                      allTxnSummaryContent,   accS.all_txn_summary) : "") +
        (isMaybank   ? makeAccSection("facilities",       "Facilities with Maybank",
                                      facilitiesContent,      accS.facilities) : "") +
        (isMaybank   ? makeAccSection("creditstatus",     "Customer Credit Status",
                                      creditContent,          accS.creditstatus) : "") +
        (hasFinancials ? makeAccSection("financials",     "Financials",
                                        finContent,            accS.financials) : "") +
        makeAccSection("cipinfo",     "CIP Collaterals",       cipContent,            accS.cipinfo || false) +
        makeAccSection("network_rsme",
            "RSME Buyer/Supplier Network (" + rsmeNbs.length + ")",
            rsmeNetContent, accS.network_rsme) +
        makeAccSection("network_fitas",
            "Trade Transactions (FITAS) Network (" + Array.from(new Set(fitasOutNbs.concat(fitasInNbs))).length + ")",
            fitasNetContent, accS.network_fitas) +
        makeAccSection("network_payment",
            "Payment Transactions (TT/MEPS/FAST/GIRO) Network (" + Array.from(new Set(paymentOutNbs.concat(paymentInNbs))).length + ")",
            paymentNetContent, accS.network_payment) +
        makeAccSection("network_aa_paper",
            "AA Paper Network (" + aaPaperNbs.length + ")",
            aaPaperNetContent, accS.network_aa_paper);

    ["overview","datasources","fitas_summary","payment_summary","all_txn_summary",
     "facilities","creditstatus","financials","cipinfo",
     "network_rsme","network_fitas","network_payment",
     "network_aa_paper"].forEach(attachAccordion);

    document.getElementById("main-company-card")
        .addEventListener("click", function() { navigateToNode(uid); });

    rsmeNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-rsme-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    paymentOutNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-payment-out-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    paymentInNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-payment-in-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    fitasOutNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-fitas-out-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    fitasInNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-fitas-in-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    aaPaperOutNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-aapaper-out-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
    aaPaperInNbs.forEach(function(nbId) {
        var el = document.getElementById("nbcard-aapaper-in-" + nbId);
        if (el) el.addEventListener("click", function() { navigateToNode(_d(nbId)); });
    });
};

var navigateToNode = function(uid) {};

navigateToNode = function(uid) {
    var maxHops = parseInt(document.getElementById("hop-input").value.trim(), 10) || 2;
    removeSelection();
    selectedIds.push(uid);
    renderSelectedPill();
    renderSearch([uid], maxHops, true);
    currentNode = uid;
    showNodeInfo(uid);
    saveLastSearch(uid, maxHops);
};
"""
