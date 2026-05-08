# ── network_graph/viz/compression.py ──────────────────────────────────────────
# UEN compression helpers -- standalone module to avoid circular imports.
# builder.py and js_core.py both import from here.


def build_uen_mapping(id_name_lookup_js, rsme_adjacency,
                      consol_tt_source, fitas_source, aa_paper_source,
                      fast_source, giro_source):
    """
    Build bidirectional UEN <-> string-ID mapping covering every UEN that
    appears as a key OR value across all data structures.
    IDs start at "1" -- avoids falsy "0" edge case in JS.
    Sorted input ensures deterministic mapping.
    Returns (uen_to_id, id_to_uen) -- both string-keyed dicts.
    """
    all_uens = set()

    all_uens.update(str(u) for u in id_name_lookup_js.keys())

    all_uens.update(str(u) for u in rsme_adjacency.keys())
    for neighbors in rsme_adjacency.values():
        all_uens.update(str(n) for n in neighbors)

    for src in (consol_tt_source, fitas_source, aa_paper_source,
                fast_source, giro_source):
        all_uens.update(str(u) for u in src.active_uens)
        all_uens.update(str(u) for u in src.self_loop_ids)

    all_uens = {u for u in all_uens if u and u not in ('nan', 'None', '', 'none')}

    sorted_uens = sorted(all_uens)
    uen_to_id   = {uen: str(i + 1) for i, uen in enumerate(sorted_uens)}
    id_to_uen   = {str(i + 1): uen for i, uen in enumerate(sorted_uens)}

    return uen_to_id, id_to_uen


def validate_compression(uen_to_id, id_name_lookup_js,
                         consol_tt_source, fitas_source, aa_paper_source,
                         fast_source, giro_source):
    """Hard raises if any UEN is missing from the map."""
    missing = []
    for u in id_name_lookup_js.keys():
        if str(u) not in uen_to_id:
            missing.append(('id_name_lookup', str(u)))
    for label, src in [('consol_tt', consol_tt_source),
                       ('fitas',     fitas_source),
                       ('aa_paper',  aa_paper_source),
                       ('fast',      fast_source),
                       ('giro',      giro_source)]:
        for u in src.active_uens:
            if str(u) not in uen_to_id:
                missing.append((label, str(u)))
    if missing:
        raise ValueError(
            f"ABORT: {len(missing)} UENs missing from compression map. "
            f"First 5: {missing[:5]}"
        )
    print(f"  Compression validation passed: {len(uen_to_id):,} UENs mapped")


def c_key(d, uen_to_id):
    """Compress dict with UEN string keys -> string-ID keys. Values unchanged."""
    out = {}
    for k, v in d.items():
        cid = uen_to_id.get(str(k))
        if cid is None:
            continue
        out[cid] = v
    return out


def c_key_listval(d, uen_to_id):
    """Compress dict with UEN keys and list-of-UEN values."""
    out = {}
    for k, vals in d.items():
        cid = uen_to_id.get(str(k))
        if cid is None:
            continue
        out[cid] = [uen_to_id[str(v)] for v in vals if str(v) in uen_to_id]
    return out


def c_list(lst, uen_to_id):
    """Compress list of UEN strings to list of string IDs."""
    return [uen_to_id[str(u)] for u in lst if str(u) in uen_to_id]


def c_edges_from_to(edges, uen_to_id):
    """Compress edge list with from/to UEN fields to string IDs."""
    out = []
    for e in edges:
        cf = uen_to_id.get(str(e['from']))
        ct = uen_to_id.get(str(e['to']))
        if cf is None or ct is None:
            continue
        out.append({**e, 'from': cf, 'to': ct})
    return out


def c_selfloop_edges(edges, uen_to_id):
    """Compress selfloop edge list with uen field."""
    out = []
    for e in edges:
        cid = uen_to_id.get(str(e['uen']))
        if cid is None:
            continue
        out.append({**e, 'uen': cid})
    return out
