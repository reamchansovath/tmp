# ── network_graph/viz/html_styles.py ──────────────────────────────────────────
# HTML structure and CSS styles for the network graph visualization.
# Extracts all presentation logic from builder.py for easier maintenance.
#
# DOM ID contract: every id defined here must match what the JS modules
# reference via document.getElementById(). Do not rename IDs without
# updating the corresponding JS file.


def get_toolbar_html(config, logo_b64=None) -> str:
    """
    Returns the complete HTML structure for toolbar, filters, and side panel.

    Parameters
    ----------
    config   : NetworkGraphConfig instance
    logo_b64 : Optional base64-encoded logo PNG image

    Returns
    -------
    str : Complete HTML string ready to inject into <body>
    """

    YELLOW      = "#FBBA00"
    TOOLBAR_BG  = "#1C1C1C"
    PAGE_BG     = "#FBBA00"
    CARD_BG     = "#FFFFFF"
    CARD_BORDER = "#E8E8E8"
    CARD_SHADOW = "0 4px 16px rgba(0,0,0,0.10)"
    BTN_BG      = "#E0E0E0"
    BTN_TEXT    = "#333333"
    GRAPH_BG    = "#FAFAFA"

    # *** updated | RSME edges are now solid green -- legend must match
    EDGE_GREEN  = "#2f8744"   # matches VizConfig.rsme_edge_color
    EDGE_BLUE   = "#2980b9"   # directed / both-ways / self-loop edges

    CANVAS_TOP    = "135px"
    CANVAS_BOTTOM = "40px"

    PANEL_WIDTH   = "340px"
    GRAPH_RIGHT   = "372px"   # PANEL_WIDTH (340) + 16px gap on each side (32)

    logo_tag = (
        f"<img src='data:image/png;base64,{logo_b64}' "
        f"style='height:28px;vertical-align:middle;margin-right:6px;'/>"
        if logo_b64
        else f"<span style='color:{YELLOW};font-weight:700;margin-right:8px;'>Maybank</span>"
    )

    return f"""
<style>
html, body {{ margin:0; padding:0; background:{PAGE_BG};
    font-family:Inter,'Segoe UI',Arial,sans-serif; overflow:hidden; }}

#loadingBar {{ display:none !important; }}
#mynetwork {{ border:none !important; background:{GRAPH_BG} !important; }}
div.vis-network {{ border:none !important; }}

/* ── Toolbar ── */
#rm-toolbar {{ position:fixed; top:0; left:0; right:0; z-index:9999;
    background:{TOOLBAR_BG}; padding:18px 22px 20px;
    display:flex; flex-direction:column; gap:12px;
    box-shadow:0 2px 8px rgba(0,0,0,0.25); }}

/* Row 1: logo + node size + search + hop + buttons */
#toolbar-row {{ display:flex; align-items:center; gap:10px; flex-wrap:nowrap;
    min-height:28px; }}
#toolbar-brand {{ font-size:15px; font-weight:700; color:#ffffff;
    white-space:nowrap; margin-right:10px; flex-shrink:0;
    display:flex; align-items:center; }}
.tb-divider {{ width:1px; height:22px; background:#444;
    margin:0 4px; flex-shrink:0; }}

/* Row 2: filters */
#toolbar-filters {{ display:flex; align-items:center; gap:12px;
    padding-top:8px; border-top:1px solid #333; flex-wrap:nowrap;
    min-height:28px; }}
.tb-filter-label {{ font-size:11px; color:#aaa; white-space:nowrap;
    font-weight:600; letter-spacing:0.04em; flex-shrink:0; }}
.tb-check-label {{ display:flex; align-items:center; gap:5px;
    cursor:pointer; font-size:12px; color:#fff;
    white-space:nowrap; flex-shrink:0; }}
.tb-check-label input {{ cursor:pointer; width:14px; height:14px;
    flex-shrink:0; }}

/* Floating legend pinned to top-left of the graph card.
   Uses <details> for native open/close, no JS needed. */
.legend-dot {{ display:inline-block; width:7px; height:7px;
    border-radius:50%; margin-right:0; vertical-align:middle;
    flex-shrink:0; }}
#graph-legend {{ position:absolute; top:12px; left:12px; z-index:100;
    background:rgba(255,255,255,0.96); border:1px solid {CARD_BORDER};
    border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.10);
    font-family:Inter,'Segoe UI',Arial,sans-serif; user-select:none;
    max-width:200px; font-size:10px; color:#333; }}
#graph-legend > summary {{ display:flex; justify-content:space-between;
    align-items:center; padding:5px 9px; cursor:pointer; list-style:none;
    gap:10px; }}
#graph-legend > summary::-webkit-details-marker {{ display:none; }}
#graph-legend > summary::marker {{ display:none; content:''; }}
#graph-legend[open] > summary {{ border-bottom:1px solid #EEE; }}
#graph-legend .legend-title {{ font-weight:700; font-size:9.5px;
    color:#1C1C1C; letter-spacing:0.04em; text-transform:uppercase; }}
#graph-legend .legend-toggle {{ color:#888; font-size:8.5px;
    line-height:1; }}
#graph-legend .legend-toggle::before {{ content:"\\25B8"; }}
#graph-legend[open] .legend-toggle::before {{ content:"\\25BE"; }}
#graph-legend .legend-body {{ padding:6px 9px 8px; }}
#graph-legend .legend-section-title {{ font-size:8.5px; font-weight:700;
    color:#888; letter-spacing:0.05em; text-transform:uppercase;
    margin:0 0 3px; }}
#graph-legend .legend-section-title:not(:first-child) {{ margin-top:6px; }}
#graph-legend .legend-item {{ display:flex; align-items:center; gap:5px;
    font-size:10px; color:#333; margin-bottom:2px; }}
#graph-legend .legend-item:last-child {{ margin-bottom:0; }}

/* ── Edge legend elements ─────────────────────────────────────────────────
   legend-line-rsme    : solid GREEN line, no arrow -- RSME-only pairs
   legend-line-directed: solid blue line + single arrowhead -- FITAS/AA/TT
   legend-line-both    : solid blue line + double arrowhead -- both ways
   legend-line-selfloop: blue loop circle -- TT self-transfer
   ──────────────────────────────────────────────────────────────────── */

/* *** updated | RSME-only: solid green, no arrow (was dashed blue) */
.legend-line-rsme {{
    display:inline-block; width:18px; height:0px;
    border-top:2px solid {EDGE_GREEN};
    margin-right:0; vertical-align:middle; flex-shrink:0; }}

/* Directed (FITAS/AA/TT): solid blue + single right arrow */
.legend-line-directed {{
    display:inline-flex; align-items:center;
    margin-right:0; vertical-align:middle; flex-shrink:0; }}
.legend-line-directed-shaft {{
    display:inline-block; width:14px; height:2px;
    background:{EDGE_BLUE}; border-radius:1px 0 0 1px; }}
.legend-line-directed-arrow {{
    display:inline-block; width:0; height:0;
    border-top:4px solid transparent;
    border-bottom:4px solid transparent;
    border-left:5px solid {EDGE_BLUE}; }}

/* Both ways: double-headed arrow (left arrow + shaft + right arrow) */
.legend-line-both {{
    display:inline-flex; align-items:center;
    margin-right:0; vertical-align:middle; flex-shrink:0; }}
.legend-line-both-arrowl {{
    display:inline-block; width:0; height:0;
    border-top:4px solid transparent;
    border-bottom:4px solid transparent;
    border-right:5px solid {EDGE_BLUE}; }}
.legend-line-both-shaft {{
    display:inline-block; width:10px; height:2px;
    background:{EDGE_BLUE}; }}
.legend-line-both-arrowr {{
    display:inline-block; width:0; height:0;
    border-top:4px solid transparent;
    border-bottom:4px solid transparent;
    border-left:5px solid {EDGE_BLUE}; }}

/* Self-loop: small blue circle */
.legend-line-selfloop {{
    display:inline-block; width:10px; height:10px;
    border:2px solid {EDGE_BLUE}; border-radius:50%;
    border-right-color:transparent;
    margin-right:0; vertical-align:middle; flex-shrink:0; }}

/* ── Search box ── */
#search-input-wrapper {{ display:flex; align-items:center; background:#ffffff;
    border-radius:6px; overflow:hidden; min-width:240px; max-width:380px;
    box-sizing:border-box; height:30px; flex:1; }}
#company-search-input {{ border:none; outline:none; font-size:12px; flex:1;
    padding:0 10px; height:100%; background:transparent; color:#222;
    font-family:Inter,'Segoe UI',Arial,sans-serif; display:block; }}
#company-search-input::placeholder {{ color:#aaa; }}
#selected-name-zone {{ display:none; align-items:center; flex:1;
    background:#E8E8E8; height:100%; padding:0 10px; overflow:hidden; }}
#selected-card-label {{ font-size:12px; font-weight:500; color:#1C1C1C;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
#selected-clear-zone {{ display:none; align-items:center;
    justify-content:center; background:#cc0000; height:100%;
    width:30px; flex-shrink:0; cursor:pointer; transition:background 0.15s; }}
#selected-clear-zone:hover {{ background:#aa0000; }}
#selected-clear-zone span {{ color:#ffffff; font-size:13px;
    font-weight:700; line-height:1; }}

/* ── Hop count input ── */
#hop-input {{ padding:0 8px; border:none; border-radius:6px;
    font-size:12px; width:42px; height:30px; text-align:center;
    outline:none; background:#ffffff; color:#222;
    font-family:Inter,'Segoe UI',Arial,sans-serif;
    box-sizing:border-box; flex-shrink:0; }}

/* ── Toolbar buttons ── */
.tb-btn {{ padding:0 10px; height:28px; border:none; border-radius:5px;
    font-size:11.5px; cursor:pointer;
    font-family:Inter,'Segoe UI',Arial,sans-serif;
    transition:background 0.15s; white-space:nowrap; flex-shrink:0;
    background:{BTN_BG}; color:{BTN_TEXT}; }}
.tb-btn:hover    {{ background:#d0d0d0; }}
.tb-btn:disabled {{ opacity:0.35; cursor:default; }}

/* ── Export button ── */
#export-btn {{ background:{YELLOW}; color:#1C1C1C; font-weight:700; }}
#export-btn:hover {{ background:#e0a800; }}
#export-btn:disabled {{ opacity:0.35; cursor:default; }}

/* ── Search and history dropdowns ── */
#search-dropdown, #hist-dropdown {{ position:fixed; background:#fff;
    border:1px solid #ddd; border-radius:8px; max-height:260px;
    overflow-y:auto; z-index:99999;
    box-shadow:0 6px 18px rgba(0,0,0,0.13);
    display:none; min-width:340px; }}
.dd-item {{ padding:9px 14px; cursor:pointer;
    border-bottom:1px solid #f0f0f0; font-size:12px; }}
.dd-item:last-child {{ border-bottom:none; }}
.dd-item:hover  {{ background:#f9f5e7; }}
.dd-item .dd-name {{ font-weight:600; color:#222; }}
.dd-item .dd-uen  {{ color:#999; font-size:11px; margin-top:2px; }}
.hist-item {{ padding:9px 14px; cursor:pointer;
    border-bottom:1px solid #f0f0f0; font-size:12px; }}
.hist-item:last-child {{ border-bottom:none; }}
.hist-item:hover {{ background:#f9f5e7; }}

/* ── Graph canvas card ── */
#graph-card {{ position:fixed; top:{CANVAS_TOP}; left:16px; right:{GRAPH_RIGHT};
    bottom:{CANVAS_BOTTOM}; background:{GRAPH_BG}; border-radius:12px;
    border:1px solid {CARD_BORDER}; box-shadow:{CARD_SHADOW};
    overflow:hidden; z-index:100; }}

/* ── Side panel ── */
#side-panel {{ position:fixed; top:{CANVAS_TOP}; right:16px;
    bottom:{CANVAS_BOTTOM}; width:{PANEL_WIDTH};
    background:{CARD_BG}; border-radius:12px;
    border:1px solid {CARD_BORDER}; box-shadow:{CARD_SHADOW};
    overflow-y:auto; z-index:9998; padding:14px;
    box-sizing:border-box;
    font-family:Inter,'Segoe UI',Arial,sans-serif; }}

/* ── Side panel: company header card ── */
.company-main-card {{ background:{TOOLBAR_BG}; border-radius:8px;
    padding:10px 12px; margin-bottom:10px;
    box-shadow:0 2px 6px rgba(0,0,0,0.15);
    cursor:pointer; transition:opacity 0.15s; }}
.company-main-card:hover {{ opacity:0.85; }}
.company-main-card .cn {{ font-size:13px; font-weight:700;
    color:#ffffff; line-height:1.4; }}
.company-main-card .cu {{ font-size:11px; color:{YELLOW}; margin-top:2px; }}

/* ── Side panel: neighbour cards ── */
.nb-card {{ background:#ffffff; border-left:3px solid {YELLOW};
    border-radius:6px; padding:7px 10px; margin-bottom:6px;
    box-shadow:0 1px 4px rgba(0,0,0,0.07); cursor:pointer;
    transition:box-shadow 0.15s, transform 0.15s; }}
.nb-card:hover {{ box-shadow:0 4px 12px rgba(0,0,0,0.14);
    transform:translateY(-1px); }}
.nb-card .nb-name {{ font-size:12px; font-weight:600;
    color:#1C1C1C; line-height:1.3; }}
.nb-card .nb-uen  {{ font-size:10px; color:#888; margin-top:2px; }}

/* ── TT/FITAS transaction summary cards ── */
.tt-card-ord  {{ background:#EAF4FF; border-left:3px solid #2980b9;
    border-radius:6px; padding:10px 12px; margin-bottom:6px; }}
.tt-card-bene {{ background:#EAFAF1; border-left:3px solid #27ae60;
    border-radius:6px; padding:10px 12px; margin-bottom:6px; }}
.tt-card-ord  .tt-title {{ font-size:12px; font-weight:700;
    color:#1a5276; margin-bottom:6px; }}
.tt-card-bene .tt-title {{ font-size:12px; font-weight:700;
    color:#1e8449; margin-bottom:6px; }}
.tt-row {{ display:flex; justify-content:space-between;
    font-size:11px; color:#555; margin-top:3px; }}
.tt-card-ord  .tt-val {{ font-weight:600; color:#1a5276; }}
.tt-card-bene .tt-val {{ font-weight:600; color:#1e8449; }}

/* ── Accordion sections ── */
.acc-header {{ display:flex; justify-content:space-between;
    align-items:center; padding:8px 10px; border-radius:6px;
    font-size:12px; font-weight:600; color:#333; cursor:pointer;
    user-select:none; transition:background 0.12s; border:none; }}
.acc-header.closed {{ background:#C8C8C8; }}
.acc-header.open   {{ background:#FBDE6A; color:#1C1C1C; }}
.acc-header:hover  {{ filter:brightness(0.97); }}

/* ── Info table inside accordion sections ── */
.info-table {{ width:100%; border-collapse:collapse; margin-top:4px; }}
.info-table td {{ padding:5px 6px; font-size:11px; vertical-align:top; }}
.info-table .lbl {{ color:#888; width:52%; }}
.info-table .val {{ color:#1C1C1C; font-weight:500; text-align:right; }}
.info-table .sec-hdr td {{ padding:6px 6px 3px; font-size:11px;
    font-weight:700; color:#555; background:#F5F5F5;
    border-top:1px solid #eee; }}
.info-table tr:nth-child(even) td {{ background:#FAFAFA; }}

/* ── Search error message ── */
#search-error {{ color:#ff4444; font-size:11px;
    align-self:center; flex-shrink:0; }}

/* ── Multi-select dropdown filters ───────────────────────────────────────
   Replaces the flat checkbox row. Two dropdown components (Sources +
   Countries) feed _selectedSources / _selectedCountries Sets in
   js_filters; pills below show currently-selected items with an x to
   deselect; Clear-all link drops everything (graph-empty state). */

.tb-dropdown {{ position:relative; flex-shrink:0; }}

.tb-dd-trigger {{
    display:flex; align-items:center; gap:6px;
    background:#2A2A2A; border:1px solid #3A3A3A; border-radius:6px;
    color:#fff; font-size:12px; padding:0 10px; cursor:pointer;
    height:30px; min-width:140px;
    font-family:Inter,'Segoe UI',Arial,sans-serif;
}}
.tb-dd-trigger:hover {{ background:#333; }}
.tb-dd-trigger.open {{ border-color:#A78BFA;
    box-shadow:0 0 0 2px rgba(167,139,250,0.20); }}
.tb-dd-icon {{ font-size:13px; opacity:0.85; flex-shrink:0; }}
.tb-dd-label {{ flex:1; text-align:left; white-space:nowrap; }}
.tb-dd-chevron {{ font-size:10px; color:#aaa; flex-shrink:0; }}

.tb-dd-panel {{
    display:none; position:absolute; top:calc(100% + 4px); left:0;
    background:#1F1F1F; border:1px solid #3A3A3A; border-radius:6px;
    padding:6px; min-width:200px; z-index:10000;
    box-shadow:0 8px 24px rgba(0,0,0,0.4);
}}
.tb-dd-panel.open {{ display:block; }}
.tb-dd-panel label {{
    display:flex; align-items:center; gap:8px;
    padding:6px 8px; border-radius:4px; cursor:pointer;
    color:#fff; font-size:12px;
}}
.tb-dd-panel label:hover {{ background:#2A2A2A; }}
.tb-dd-panel input[type="checkbox"] {{
    margin:0; cursor:pointer; flex-shrink:0;
    width:14px; height:14px;
}}

</style>

<div id="rm-toolbar">

  <!-- Row 1: Logo + Node size dropdown + buttons -->
  <div id="toolbar-row">
    <span id="toolbar-brand">{logo_tag}
      <span style="margin-left:2px;margin-right:6px;">&#10022;</span>
      <span style="color:{YELLOW};font-weight:700;font-size:17px;">M-EXT</span>
      <span style="color:#9A9A9A;font-weight:500;font-size:12px;margin-left:7px;letter-spacing:0.2px;">Maybank Ecosystem eXchange Topology</span>
    </span>
    <div class="tb-divider"></div>

    <!-- Node Size dropdown (single-select; matches the row-2 dropdowns) -->
    <span class="tb-filter-label">Node size:</span>
    <div class="tb-dropdown" data-filter="nodesize">
      <button class="tb-dd-trigger" id="dd-nodesize-trigger" type="button">
        <span class="tb-dd-label" id="dd-nodesize-label">Connections</span>
        <span class="tb-dd-chevron">&#9662;</span>
      </button>
      <div class="tb-dd-panel" id="dd-nodesize-panel">
        <label><input type="radio" name="nodesize" data-value="connections" checked> Connections</label>
        <label><input type="radio" name="nodesize" data-value="all_txn_sent"> Total Sent (All Txn)</label>
        <label><input type="radio" name="nodesize" data-value="all_txn_received"> Total Received (All Txn)</label>
      </div>
    </div>

    <div class="tb-divider"></div>
    <button id="reset-btn"     class="tb-btn">Reset</button>
    <button id="hist-back-btn" class="tb-btn" disabled>&#8635;</button>
    <button id="hist-fwd-btn"  class="tb-btn" disabled>&#8634;</button>
    <button id="hist-btn"      class="tb-btn">History</button>
    <div class="tb-divider"></div>
    <button id="export-btn"    class="tb-btn"
            title="Export current view as a self-contained HTML for sharing">
      Export View
    </button>
    <span id="search-error"></span>
  </div>

  <!-- Row 2: Source + Country dropdowns + active filter pills + Clear all -->
  <div id="toolbar-filters">
    <span class="tb-filter-label">Filters:</span>

    <!-- Data Sources dropdown -->
    <div class="tb-dropdown" data-filter="sources">
      <button class="tb-dd-trigger" id="dd-sources-trigger" type="button">
        <span class="tb-dd-icon">&#x26C1;</span>
        <span class="tb-dd-label" id="dd-sources-label">All Sources</span>
        <span class="tb-dd-chevron">&#9662;</span>
      </button>
      <div class="tb-dd-panel" id="dd-sources-panel">
        <label><input type="checkbox" data-source="fitas"    checked> FITAS</label>
        <label><input type="checkbox" data-source="aaPaper"  checked> AA Paper</label>
        <label><input type="checkbox" data-source="payment" checked> Payment Transactions (TT/MEPS/FAST/GIRO)</label>
        <label><input type="checkbox" data-source="rsme"     checked> RSME</label>
      </div>
    </div>

    <!-- Countries dropdown -->
    <div class="tb-dropdown" data-filter="countries">
      <button class="tb-dd-trigger" id="dd-countries-trigger" type="button">
        <span class="tb-dd-icon">&#x1F310;</span>
        <span class="tb-dd-label" id="dd-countries-label">All Countries</span>
        <span class="tb-dd-chevron">&#9662;</span>
      </button>
      <div class="tb-dd-panel" id="dd-countries-panel">
        <label><input type="checkbox" data-country="SG" checked> Singapore</label>
        <label><input type="checkbox" data-country="MY" checked> Malaysia</label>
      </div>
    </div>

    <div class="tb-divider"></div>

    <!-- Company search box (relocated from row 1) -->
    <div id="search-input-wrapper">
      <input id="company-search-input" type="text"
             placeholder="Search company name or UEN..."
             autocomplete="off"/>
      <div id="selected-name-zone">
        <span id="selected-card-label"></span>
      </div>
      <div id="selected-clear-zone" title="Clear">
        <span>&#x2715;</span>
      </div>
    </div>

    <!-- Hop count input (relocated from row 1) -->
    <input id="hop-input" type="number" min="1" value="2"
           title="Hop count"/>
  </div>

  <!-- (Row 3 removed: legend moved to floating panel inside #graph-card) -->

</div>

<div id="search-dropdown"></div>
<div id="hist-dropdown"></div>
<div id="graph-card">
  <details id="graph-legend">
    <summary>
      <span class="legend-title">Legend</span>
      <span class="legend-toggle"></span>
    </summary>
    <div class="legend-body">
      <div class="legend-section-title">Customer Type</div>
      <div class="legend-item">
        <span class="legend-dot" style="background:{config.COLOR_TRADE_MB};"></span>
        Maybank Trade
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:{config.COLOR_NON_TRADE_MB};"></span>
        Maybank Non-Trade
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:{config.COLOR_NON_MB};"></span>
        Non-Maybank
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:{config.COLOR_MALAYSIAN};border-radius:2px;"></span>
        Malaysian Entity
      </div>
      <div class="legend-section-title">Edge Type</div>
      <div class="legend-item">
        <span class="legend-line-rsme"></span>
        RSME only
      </div>
      <div class="legend-item">
        <span class="legend-line-directed">
          <span class="legend-line-directed-shaft"></span>
          <span class="legend-line-directed-arrow"></span>
        </span>
        FITAS / AA / Payment
      </div>
      <div class="legend-item">
        <span class="legend-line-both">
          <span class="legend-line-both-arrowl"></span>
          <span class="legend-line-both-shaft"></span>
          <span class="legend-line-both-arrowr"></span>
        </span>
        Both ways
      </div>
      <div class="legend-item">
        <span class="legend-line-selfloop"></span>
        Self-transfer
      </div>
    </div>
  </details>
</div>
<div id="side-panel">
  <div id="side-panel-content">
    <p style="color:#aaa;font-size:13px;text-align:center;margin-top:40px;">
      Search a company to begin.
    </p>
  </div>
</div>
<div style="position:fixed;bottom:0;left:0;right:0;z-index:99999;
    background:#ffffff;text-align:center;padding:5px 16px;
    font-size:11px;font-weight:600;color:#cc0000;
    letter-spacing:0.3px;border-top:1px solid #e0e0e0;
    font-family:Inter,'Segoe UI',Arial,sans-serif;">
  &#128274; Internal Use Only. This tool contains Confidential data.
  Unauthorised disclosure or external sharing is strictly prohibited.
</div>
"""
