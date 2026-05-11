# ── network_graph/viz/js_search.py ────────────────────────────────────────────
# UEN COMPRESSION:
# - seedIds enters renderSearch as real UEN strings (external API)
# - Encoded to compressed string IDs once at renderSearch entry
# - All BFS, vis.js, depthMap, _visibleNodes operations use compressed IDs
# - selectedIds, currentNode, URL, localStorage always hold real UEN strings
# - companyList uses {id: compressed_id, name: real_name} -- dropdown decodes via _d()
#
# *** updated | edge visibility block now iterates Object.values(pairRelationshipMap)
#   instead of consolidatedEdgesData (removed). Filter flags read via abbreviated
#   keys: e.ir=inRsme, e['if']=inFitas, e.ia=inAA, e.it=inTT.
#   Edge IDs still use "consolidated_" + e.fr + "_" + e.to.
#   selfLoopEdgesData remains separate and unchanged.


def get_js_search():
    """
    Returns JavaScript code for search and rendering logic.
    BFS is the only search path.

    UEN COMPRESSION BOUNDARY in renderSearch:
    - seedIds (real UEN strings) encoded to seedCompIds at entry
    - All internal ops (BFS, layout, vis.js update) use compressed string IDs
    - addToHistory uses original seedIds[0] (real UEN string)
    - selectedIds always holds real UEN strings

    PERF FIX 1: queue.shift() O(n) replaced with pointer O(1)
    PERF FIX 2: layoutRadialTree receives depthMap from renderSearch -- no BFS rerun
    PERF FIX 3: layoutRadialTree uses hop rings from depthMap -- no adjacency traversal
    PERF FIX 4: diff-based hide/show against _visibleNodes/_visibleEdges

    *** updated | Edge visibility iterates Object.values(pairRelationshipMap).
    Filter flags read from abbreviated keys e.ir/e['if']/e.ia/e.it.
    Edge IDs: "consolidated_" + e.fr + "_" + e.to.
    consolidatedEdgesData removed entirely.

    Functions declared here:
    - removeSelection()       : clears search pill and selectedIds
    - renderSelectedPill()    : shows selected company name in search bar
    - renderSearchDropdown()  : shows matching companies in dropdown
    - selectCompany()         : fires search for a chosen UEN
    - renderSearch()          : main search + render function (hoisted)
    - layoutRadialTree()      : computes radial node positions from depthMap
    - updateURLState()        : pushes uen+hops to URL query params

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// SEARCH INFRASTRUCTURE
// ══════════════════════════════════════════════════════════════════════════

var dropdown    = document.getElementById("search-dropdown");
var searchInput = document.getElementById("company-search-input");
var searchTimeout = null;

// PERF FIX 4: track currently visible nodes/edges (compressed string IDs)
var _visibleNodes = new Set();
var _visibleEdges = new Set();

function removeSelection() {
    selectedIds = [];
    searchInput.style.display = "block";
    document.getElementById("selected-name-zone").style.display  = "none";
    document.getElementById("selected-clear-zone").style.display = "none";
    searchInput.value = "";
}

function renderSelectedPill() {
    if (selectedIds.length === 0) { removeSelection(); return; }
    var uid  = selectedIds[0];
    var id   = _e(uid);
    var name = idNameLookup[id] || uid;
    searchInput.style.display = "none";
    document.getElementById("selected-card-label").textContent    = name;
    document.getElementById("selected-name-zone").style.display   = "flex";
    document.getElementById("selected-clear-zone").style.display  = "flex";
}

function renderSearchDropdown(query) {
    if (!query || query.length < 2) { dropdown.style.display = "none"; return; }

    var q = query.toUpperCase();

    var matches = companyList.filter(function(c) {
        var realUEN = _d(c.id);
        return realUEN.toUpperCase().indexOf(q) !== -1 ||
               c.name.toUpperCase().indexOf(q) !== -1;
    }).slice(0, CFG.search_max_results);

    if (matches.length === 0) {
        dropdown.innerHTML =
            "<div style='padding:12px;font-size:12px;color:#aaa;'>No matches found.</div>";
    } else {
        dropdown.innerHTML = matches.map(function(c) {
            var realUEN = _d(c.id);
            return "<div class='dd-item' data-uen='" + escXml(realUEN) + "'>" +
                   "<div class='dd-name'>" + escXml(c.name)   + "</div>" +
                   "<div class='dd-uen'>"  + escXml(realUEN)  + "</div></div>";
        }).join("");

        dropdown.querySelectorAll(".dd-item").forEach(function(item) {
            item.addEventListener("mousedown", function(e) {
                e.preventDefault();
                selectCompany(this.dataset.uen);
            });
        });
    }

    var rect = searchInput.getBoundingClientRect();
    dropdown.style.top      = (rect.bottom + 4) + "px";
    dropdown.style.left     = rect.left + "px";
    dropdown.style.minWidth = rect.width + "px";
    dropdown.style.display  = "block";
}

function selectCompany(uen) {
    var hops = parseInt(document.getElementById("hop-input").value) || 2;
    removeSelection();
    selectedIds.push(uen);
    renderSelectedPill();
    renderSearch([uen], hops, true);
    currentNode = uen;
    showNodeInfo(uen);
    dropdown.style.display = "none";
    saveLastSearch(uen, hops);
}

// ── Event listeners ───────────────────────────────────────────────────────

searchInput.addEventListener("input", function() {
    clearTimeout(searchTimeout);
    document.getElementById("search-error").innerText = "";
    var query = this.value.trim();
    if (query.length < 2) { dropdown.style.display = "none"; return; }
    searchTimeout = setTimeout(function() {
        renderSearchDropdown(query);
    }, CFG.search_debounce_ms);
});

searchInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        var query = this.value.trim();
        if (query.length > 0 && companyList.length > 0) {
            var q = query.toUpperCase();
            var match = companyList.find(function(c) {
                var realUEN = _d(c.id);
                return realUEN.toUpperCase() === q ||
                       c.name.toUpperCase().indexOf(q) !== -1;
            });
            if (match) {
                selectCompany(_d(match.id));
            } else {
                document.getElementById("search-error").innerText = "No matching company found.";
            }
        }
    } else if (e.key === "Escape") {
        dropdown.style.display = "none";
    }
});

document.getElementById("selected-clear-zone").addEventListener("click", function() {
    removeSelection();
    dropdown.style.display = "none";
});

document.addEventListener("click", function(e) {
    if (!dropdown.contains(e.target) && e.target !== searchInput)
        dropdown.style.display = "none";
});

document.getElementById("hop-input").addEventListener("change", function() {
    try { localStorage.setItem(LS_HOPS, this.value); } catch(e) {}
});

document.getElementById("hop-input").addEventListener("input", function() {
    if (selectedIds.length === 0) return;
    clearTimeout(searchTimeout);
    var newHops = parseInt(this.value) || 2;
    searchTimeout = setTimeout(function() {
        renderSearch(selectedIds.slice(), newHops, false);
    }, 1000);
});

// ══════════════════════════════════════════════════════════════════════════
// SEARCH & RENDERING
// ══════════════════════════════════════════════════════════════════════════

function updateURLState(uen, hops) {
    if (typeof URLSearchParams === 'undefined') return;
    try {
        var url = new URL(window.location);
        if (uen) {
            url.searchParams.set('q', uen);
            url.searchParams.set('h', String(hops || 2));
        } else {
            url.searchParams.delete('q');
            url.searchParams.delete('h');
        }
        window.history.pushState({}, '', url);
    } catch(e) {}
}

renderSearch = function(seedIds, maxHops, addToHistory) {
    if (!seedIds || seedIds.length === 0) return;

    console.log("renderSearch:", seedIds, "hops:", maxHops);

    ensureAllNetworksInVis();

    // ── UEN COMPRESSION BOUNDARY ──────────────────────────────────────────
    var seedCompIds = seedIds
        .map(function(uid) { return _e(uid); })
        .filter(function(id) { return id !== undefined; });

    if (seedCompIds.length === 0) {
        document.getElementById("search-error").innerText = "Selected nodes not found in graph.";
        return;
    }

    var validCompIds = seedCompIds.filter(function(id) {
        return nodes.get(id) !== null;
    });
    if (validCompIds.length === 0) {
        document.getElementById("search-error").innerText = "Selected nodes not found in graph.";
        return;
    }

    // ── BFS using compressed string IDs ───────────────────────────────────
    var filt     = getFilters();
    var toShow   = new Set(validCompIds);
    var visited  = new Set();
    var depthMap = {};

    validCompIds.forEach(function(id) { depthMap[id] = 0; });

    var queue = validCompIds.map(function(id) { return {id: id, depth: 0}; });
    var ptr   = 0;

    while (ptr < queue.length) {
        var curr = queue[ptr++];
        if (visited.has(curr.id)) continue;
        visited.add(curr.id);
        if (curr.depth >= maxHops) continue;

        var neighbors = new Set();
        if (filt.rsme)
            (adjacencyMap[curr.id] || []).forEach(function(nb) { neighbors.add(nb); });
        if (filt.payment) {
            (paymentOutAdj[curr.id] || []).forEach(function(nb) { neighbors.add(nb); });
            (paymentInAdj[curr.id]  || []).forEach(function(nb) { neighbors.add(nb); });
        }
        if (filt.fitas) {
            (fitasOutAdj[curr.id] || []).forEach(function(nb) { neighbors.add(nb); });
            (fitasInAdj[curr.id]  || []).forEach(function(nb) { neighbors.add(nb); });
        }
        if (filt.aaPaper) {
            (aaPaperOutAdj[curr.id] || []).forEach(function(nb) { neighbors.add(nb); });
            (aaPaperInAdj[curr.id]  || []).forEach(function(nb) { neighbors.add(nb); });
        }

        var nextDepth = curr.depth + 1;
        neighbors.forEach(function(nb) {
            if (!visited.has(nb)) {
                toShow.add(nb);
                if (depthMap[nb] === undefined) depthMap[nb] = nextDepth;
                queue.push({id: nb, depth: nextDepth});
            }
        });
    }

    console.log("BFS complete:", toShow.size, "nodes, queue processed:", queue.length);

    // ── Country filter -- MY ──────────────────────────────────────────────
    if (!filt.showMY) {
        toShow.forEach(function(id) {
            var meta = nodeMetaMap[id] || {};
            if ((meta.source_country || '') === 'MY') toShow.delete(id);
        });
    }

    // ── Country filter -- SG ──────────────────────────────────────────────
    // Mirror of the MY branch above. Without this, deselecting Singapore in
    // the Countries dropdown was a no-op while a search was active because
    // renderSearch never re-checked SG visibility.
    if (!filt.showSG) {
        toShow.forEach(function(id) {
            var meta = nodeMetaMap[id] || {};
            if ((meta.source_country || '') === 'SG') toShow.delete(id);
        });
    }

    var arrToShow = Array.from(toShow);
    var positions = layoutRadialTree(arrToShow, validCompIds, maxHops, depthMap);

    // ── PERF FIX 4: diff-based node hide/show ─────────────────────────────
    var nodeUpdates = [];
    _visibleNodes.forEach(function(id) {
        if (!toShow.has(id))
            nodeUpdates.push({id: id, hidden: true});
    });
    arrToShow.forEach(function(id) {
        var pos = positions[id] || {x: 0, y: 0};
        nodeUpdates.push({id: id, x: pos.x, y: pos.y, hidden: false});
    });
    if (nodeUpdates.length > 0) nodes.update(nodeUpdates);
    _visibleNodes = toShow;

    // ── Edge visibility ───────────────────────────────────────────────────
    // *** updated | iterate Object.values(pairRelationshipMap) -- single source
    // of truth, consolidatedEdgesData removed. Filter flags read via abbreviated
    // keys: e.ir=inRsme, e['if']=inFitas (bracket -- reserved word), e.ia=inAA,
    // e.it=inTT. Edge IDs: "consolidated_" + e.fr + "_" + e.to.
    var edgesToShow = new Set();

    Object.values(pairRelationshipMap).forEach(function(e) {
        if (!toShow.has(e.fr) || !toShow.has(e.to)) return;
        var show = (filt.rsme    && !!e.ir)      ||
                   (filt.aaPaper && !!e.ia)      ||
                   (filt.fitas   && !!e['if'])   ||
                   (filt.payment && !!e.if_pay);
        if (show) edgesToShow.add("consolidated_" + e.fr + "_" + e.to);
    });

    if (filt.payment) {
        selfLoopEdgesData.forEach(function(e) {
            if (toShow.has(e.uen))
                edgesToShow.add("selfloop_" + e.uen);
        });
    }

    // PERF FIX 4: diff-based edge hide/show
    var edgeUpdates = [];
    _visibleEdges.forEach(function(eid) {
        if (!edgesToShow.has(eid)) edgeUpdates.push({id: eid, hidden: true});
    });
    edgesToShow.forEach(function(eid) {
        if (edges.get(eid)) edgeUpdates.push({id: eid, hidden: false});
    });
    if (edgeUpdates.length > 0) edges.update(edgeUpdates);
    _visibleEdges = edgesToShow;

    // Resize nodes relative to the new visible set so a search/hop change
    // recalibrates sizes against just the on-screen subgraph.
    if (typeof applyNodeSizing === "function") applyNodeSizing();

    if (arrToShow.length > 0) {
        network.fit({
            nodes: arrToShow,
            animation: {duration: 500, easingFunction: "easeInOutQuad"}
        });
    }

    if (addToHistory && seedIds.length === 1) {
        updateURLState(seedIds[0], maxHops);
        pushHistory(seedIds[0], maxHops);
    }
};

// ══════════════════════════════════════════════════════════════════════════
// RADIAL LAYOUT
// ══════════════════════════════════════════════════════════════════════════

function layoutRadialTree(nodeIds, centerIds, maxHops, depthMap) {
    var positions = {};

    if (centerIds.length === 1) {
        positions[centerIds[0]] = {x: 0, y: 0};
    } else {
        var aStep = (2 * Math.PI) / centerIds.length;
        centerIds.forEach(function(id, i) {
            var angle = i * aStep;
            positions[id] = {x: 100 * Math.cos(angle), y: 100 * Math.sin(angle)};
        });
    }

    var baseRadius      = 500;
    var radiusIncrement = 600;

    var hopRings = {};
    nodeIds.forEach(function(id) {
        var d = depthMap[id];
        if (d === undefined || d === 0) return;
        if (!hopRings[d]) hopRings[d] = [];
        hopRings[d].push(id);
    });

    // Sparsity factor: shrink the radius when the graph is small so vis.js
    // auto-fit zooms in further, making nodes and labels readable. Capped at
    // 1.0 (no shrink for dense graphs) and floored at 0.45 to keep tiny
    // graphs from collapsing onto the centre.
    var totalRingNodes = 0;
    for (var h = 1; h <= maxHops; h++) {
        totalRingNodes += (hopRings[h] || []).length;
    }
    var sparsityFactor = Math.max(0.45, Math.min(1.0, totalRingNodes / 30));

    for (var hop = 1; hop <= maxHops; hop++) {
        var ringNodes = hopRings[hop] || [];
        if (ringNodes.length === 0) continue;

        var crowdingFactor = Math.max(1, ringNodes.length / 20);
        var radius         = baseRadius + (hop - 1) * radiusIncrement * crowdingFactor;
        radius             = radius * sparsityFactor;
        var optimalNodes   = Math.floor(2 * Math.PI * radius / 150);

        if (ringNodes.length > optimalNodes)
            radius = radius * Math.sqrt(ringNodes.length / optimalNodes);

        var angleStep = (2 * Math.PI) / ringNodes.length;
        ringNodes.forEach(function(id, i) {
            var angle = i * angleStep;
            positions[id] = {
                x: radius * Math.cos(angle),
                y: radius * Math.sin(angle),
            };
        });
    }

    // Defensive fallback: any node in nodeIds without a position (depthMap
    // missing or === 0 while not a center) is placed on hop-ring 1 at a
    // deterministic angle derived from its id hash. Without this defense
    // such nodes would stack at the origin (the centre), making it appear
    // as if "some companies go to the centre" after toggling filters.
    var fallbackRadius = baseRadius * sparsityFactor;
    nodeIds.forEach(function(id) {
        if (positions[id]) return;
        var hash = 0;
        for (var k = 0; k < id.length; k++) {
            hash = ((hash << 5) - hash) + id.charCodeAt(k);
            hash |= 0;
        }
        var angle = ((hash >>> 0) / 0xffffffff) * 2 * Math.PI;
        positions[id] = {
            x: fallbackRadius * Math.cos(angle),
            y: fallbackRadius * Math.sin(angle),
        };
        console.warn(
            "layoutRadialTree: node had no depthMap entry, placed on fallback ring",
            "id=", id, "depth=", depthMap[id]
        );
    });

    return positions;
}

// ══════════════════════════════════════════════════════════════════════════
// URL-BASED SEARCH ON PAGE LOAD
// ══════════════════════════════════════════════════════════════════════════

// Defer until __bootstrapReady so companyList / _ItoU (used by _d) exist.
__bootstrapReady.then(function() {
    try {
        if (typeof URLSearchParams === 'undefined') return;
        var params = new URLSearchParams(window.location.search);
        var uen    = params.get('q');
        var hops   = parseInt(params.get('h')) || 2;

        if (!uen) return;

        var sanitizedUEN = uen.replace(/[<>"']/g, '').trim().toUpperCase();

        var exists = companyList.some(function(c) {
            return _d(c.id).toUpperCase() === sanitizedUEN;
        });

        if (exists) {
            try { localStorage.removeItem(LS_LAST); } catch(e) {}
            setTimeout(function() {
                selectedIds.push(sanitizedUEN);
                renderSelectedPill();
                renderSearch([sanitizedUEN], hops, false);
                currentNode = sanitizedUEN;
                showNodeInfo(sanitizedUEN);
                console.log("Loaded from URL:", sanitizedUEN, "hops:", hops);
            }, 500);
        } else {
            document.getElementById("search-error").innerText =
                "UEN from URL not found: " + sanitizedUEN;
            console.warn("URL parameter UEN not found:", sanitizedUEN);
        }
    } catch(e) {
        console.error("URL parameter loading error:", e);
    }
});
"""
