# ── network_graph/viz/js_history.py ───────────────────────────────────────────
# History navigation: back/forward buttons, history dropdown, localStorage.
#
# UEN COMPRESSION:
# - historyStack stores real UEN strings throughout -- no change needed
# - pushHistory(uen, hops): uen = real UEN string -- correct
# - fireHistoryEntry: entry.uen = real UEN string -- correct
# - FIX: companyList.find updated -- companyList now has {id, name} not {uen, name}
#   Use _d(c.id) === uen to find the matching entry


def get_js_history():
    """
    Returns JavaScript code for history management.

    Handles:
    - pushHistory: adds a new entry, trims to max 10, persists to localStorage
    - fireHistoryEntry: restores a past search state
    - updateHistoryButtons: enables/disables back/forward buttons
    - hist-btn dropdown: shows clickable history list

    UEN compression note:
    - All history entries store real UEN strings (not compressed IDs)
    - companyList now has {id, name} -- name lookup uses _d(c.id) for comparison

    Returns
    -------
    str : JavaScript code block
    """

    return """
// ══════════════════════════════════════════════════════════════════════════
// HISTORY MANAGEMENT
// ══════════════════════════════════════════════════════════════════════════

var histDropdown = document.getElementById("hist-dropdown");

function pushHistory(uen, hops) {
    // uen = real UEN string (external API -- never compressed ID)

    // Truncate forward history when a new search fires mid-stack
    if (historyIndex < historyStack.length - 1)
        historyStack = historyStack.slice(0, historyIndex + 1);

    // Deduplicate: skip if same uen+hops as the current top entry
    if (historyStack.length > 0) {
        var last = historyStack[historyStack.length - 1];
        if (last.uen === uen && last.hops === hops) {
            updateHistoryButtons();
            return;
        }
    }

    // FIX: companyList now has {id, name} not {uen, name}
    // Decode compressed id via _d() to compare with real UEN string
    var entry = companyList.find(function(c) { return _d(c.id) === uen; });
    historyStack.push({uen: uen, name: entry ? entry.name : uen, hops: hops});

    // Cap stack at 10 entries
    if (historyStack.length > 10) historyStack.shift();

    historyIndex = historyStack.length - 1;
    updateHistoryButtons();
    try { localStorage.setItem(LS_HISTORY, JSON.stringify(historyStack)); } catch(e) {}
}

function fireHistoryEntry(entry) {
    // entry.uen = real UEN string -- renderSearch/showNodeInfo encode internally
    removeSelection();
    selectedIds.push(entry.uen);
    renderSelectedPill();
    document.getElementById("hop-input").value = entry.hops;
    renderSearch([entry.uen], entry.hops, false);
    currentNode = entry.uen;
    showNodeInfo(entry.uen);
    updateHistoryButtons();
    saveLastSearch(entry.uen, entry.hops);
}

function updateHistoryButtons() {
    var b = document.getElementById("hist-back-btn");
    var f = document.getElementById("hist-fwd-btn");
    if (b) {
        b.disabled      = historyIndex <= 0;
        b.style.opacity = historyIndex > 0 ? "1" : "0.35";
    }
    if (f) {
        var canFwd      = historyIndex < historyStack.length - 1;
        f.disabled      = !canFwd;
        f.style.opacity = canFwd ? "1" : "0.35";
    }
}

document.getElementById("hist-back-btn").addEventListener("click", function() {
    if (historyIndex <= 0) return;
    historyIndex--;
    fireHistoryEntry(historyStack[historyIndex]);
});

document.getElementById("hist-fwd-btn").addEventListener("click", function() {
    if (historyIndex >= historyStack.length - 1) return;
    historyIndex++;
    fireHistoryEntry(historyStack[historyIndex]);
});

document.getElementById("hist-btn").addEventListener("click", function() {
    if (histDropdown.style.display === "block") {
        histDropdown.style.display = "none";
        return;
    }

    if (historyStack.length === 0) {
        histDropdown.innerHTML =
            "<div style='padding:12px;font-size:12px;color:#aaa;'>No history yet.</div>";
    } else {
        // Render newest first (reverse order)
        // e.uen = real UEN string -- displayed as-is to user
        histDropdown.innerHTML = historyStack.slice().reverse().map(function(e, i) {
            var ai = historyStack.length - 1 - i;
            return "<div class='hist-item' data-idx='" + ai + "' style='" +
                   (ai === historyIndex ? "background:#FEF9EC;font-weight:600;" : "") + "'>" +
                   "<div style='font-size:12px;color:#222;'>" + escXml(e.name) + "</div>" +
                   "<div style='font-size:10px;color:#aaa;'>" +
                   escXml(e.uen) + " &middot; " + e.hops + " hops</div></div>";
        }).join("");
    }

    var rect = document.getElementById("hist-btn").getBoundingClientRect();
    histDropdown.style.top     = (rect.bottom + 4) + "px";
    histDropdown.style.left    = rect.left + "px";
    histDropdown.style.display = "block";

    histDropdown.querySelectorAll(".hist-item").forEach(function(item) {
        item.addEventListener("mousedown", function(e) {
            e.preventDefault();
            historyIndex = parseInt(this.dataset.idx);
            fireHistoryEntry(historyStack[historyIndex]);
            histDropdown.style.display = "none";
        });
    });
});

// FIX: use .closest("#hist-btn") instead of strict e.target equality.
document.addEventListener("click", function(e) {
    if (!histDropdown.contains(e.target) && !e.target.closest("#hist-btn"))
        histDropdown.style.display = "none";
});
"""
