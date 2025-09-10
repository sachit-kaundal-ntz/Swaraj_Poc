import json


def find_table_by_id(data, table_id):
    """Return table dict by id or None."""
    return next(
        (t for t in data.get("extracted_data", {}).get("tables", []) if t.get("id") == table_id),
        None,
    )

def format_cell_reason(cell):
    """Format a table cell into 'LABEL = VALUE UNIT (tol: ...)' style."""
    if not cell:
        return ""
    label = str(cell.get("label", "")).strip()
    value = cell.get("value", "")
    unit = cell.get("unit", "")
    tolerance = cell.get("tolerance", "")
    parts = []
    if label:
        parts.append(label)
    if value not in (None, ""):
        parts.append(str(value))
    if unit:
        parts.append(unit)
    if tolerance:
        parts.append(f"(tol: {tolerance})")
    return " ".join(parts).strip()

def format_dim_reason(dim):
    """Format a dimension entry into a readable string."""
    if not dim:
        return ""
    raw = dim.get("raw_text")
    if raw:
        return f"Dimension '{raw}'"
    parts = []
    if dim.get("value") is not None:
        parts.append(str(dim.get("value")))
    if dim.get("symbol"):
        parts.append(dim.get("symbol"))
    if dim.get("unit"):
        parts.append(dim.get("unit"))
    if dim.get("tolerance"):
        parts.append(f"(tol: {dim.get('tolerance')})")
    return " ".join(parts).strip()

def format_feature_reason(feature):
    """Format feature into readable string."""
    if not feature:
        return ""
    fid = feature.get("id", "")
    ftype = feature.get("type", "")
    role = feature.get("role", "")
    links = feature.get("table_links", [])
    parts = [f"Feature {fid} ({ftype})"]
    if role:
        parts.append(f"role='{role}'")
    if links:
        parts.append(f"table_links={links}")
    return " ".join(parts)

def collect_table_cells_by_keyword(data, keywords):
    """
    Search all tables' cells for label or value containing any of the keywords (case-insensitive).
    Returns list of matching formatted cell reasons.
    """
    matches = []
    tables = data.get("extracted_data", {}).get("tables", [])
    for t in tables:
        for c in t.get("cells", []) or []:
            text_to_search = " ".join([
                str(c.get("label", "") or ""),
                str(c.get("value", "") or "")
            ]).lower()
            for k in keywords:
                if k.lower() in text_to_search:
                    matches.append({"table_id": t.get("id"), "cell": c})
                    break
    return matches

def collect_dimensions_by_keyword(data, keywords):
    """Search dimensions raw_text/values for keywords."""
    matches = []
    dims = data.get("extracted_data", {}).get("dimensions", [])
    for d in dims:
        text = " ".join([
            str(d.get("raw_text", "") or ""),
            str(d.get("symbol", "") or ""),
            str(d.get("leaders", "") or "")
        ]).lower()
        for k in keywords:
            if k.lower() in text:
                matches.append(d)
                break
    return matches

def collect_features_by_keyword(data, keywords):
    """Search features' type/role for keywords."""
    matches = []
    feats = data.get("extracted_data", {}).get("features", [])
    for f in feats:
        text = " ".join([
            str(f.get("type", "") or ""),
            str(f.get("role", "") or ""),
            str(f.get("id", "") or "")
        ]).lower()
        for k in keywords:
            if k.lower() in text:
                matches.append(f)
                break
    return matches

def collect_notes_and_metadata_by_keyword(data, keywords):
    """Search notes, title block, metadata fields for keywords."""
    matches = []
    # Search tables labelled as notes too
    notes_table = find_table_by_id(data, "tbl_notes")
    if notes_table:
        for c in notes_table.get("cells", []) or []:
            text_to_search = " ".join([str(c.get("label","") or ""), str(c.get("value","") or "")]).lower()
            for k in keywords:
                if k.lower() in text_to_search:
                    matches.append({"source": "tbl_notes", "cell": c})
                    break
    # Search general tables for free text matches as well (already covered in table search)
    # Search metadata/title_block
    metadata = data.get("extracted_data", {}).get("metadata", {}) or {}
    title_block = metadata.get("title_block", {}) or {}
    tb_text = " ".join([str(v or "") for v in title_block.values()]).lower()
    for k in keywords:
        if k.lower() in tb_text:
            matches.append({"source": "title_block", "value": title_block})
            break
    return matches

def dedupe_preserve_order(seq, key=lambda x: x):
    seen = set()
    out = []
    for item in seq:
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out

# -------------------- EVIDENCE-DRIVEN RULES --------------------

def identify_manufacturing_processes(data):
    results = []
    added = set()

    def add(process, evidences):
        """Add process with joined evidence only if evidence non-empty and not already added."""
        if not evidences:
            return
        # flatten evidences to strings
        ev_texts = []
        for e in evidences:
            if isinstance(e, dict) and "cell" in e and "table_id" in e:
                ev_texts.append(f"[{e['table_id']}] {format_cell_reason(e['cell'])}")
            elif isinstance(e, dict) and e.get("source") == "title_block":
                tb = e.get("value", {})
                tb_str = "; ".join([f"{k}: {v}" for k,v in tb.items() if v])
                ev_texts.append(f"[title_block] {tb_str}")
            elif isinstance(e, dict) and "cell" in e:  # general notes schema
                ev_texts.append(format_cell_reason(e['cell']))
            elif isinstance(e, dict) and e.get("id") and e.get("type"):
                ev_texts.append(format_feature_reason(e))
            elif isinstance(e, dict) and e.get("raw_text"):
                ev_texts.append(format_dim_reason(e))
            else:
                ev_texts.append(str(e))
        # dedupe evidence lines and join
        ev_texts = dedupe_preserve_order(ev_texts, key=lambda x: x)
        reason = "; ".join(ev_texts)
        if process not in added:
            results.append({"process": process, "reason": reason})
            added.add(process)

    # shortcut handles
    all_tables = {t.get("id"): t for t in data.get("extracted_data", {}).get("tables", [])}

    # ------------------ Forging & related ------------------
    forging_table = find_table_by_id(data, "tbl_forging_details")
    if forging_table:
        add("Forging", [format_cell_reason(c) for c in forging_table.get("cells", []) if c])

        # Normalising evidence present in forging table
        norm_matches = [c for c in forging_table.get("cells", []) if "NORMAL" in str(c.get("label","")).upper() or "NORMALI" in str(c.get("label","")).upper()]
        if norm_matches:
            add("Normalising", [norm_matches[0]])

        # Isothermal Annealing / Annealing references
        iso_matches = [c for c in forging_table.get("cells", []) if "ISOTHERMAL" in str(c.get("label","")).upper() or "ANNEAL" in str(c.get("label","")).upper()]
        if iso_matches:
            add("Isothermal Annealing", iso_matches)

        # Cold Forging / Swaging cues in forging table
        if any("COLD" in str(c.get("label","")).upper() or "SWAGE" in str(c.get("label","")).upper() for c in forging_table.get("cells", [])):
            add("Cold Forging (Fasteners)", [c for c in forging_table.get("cells", []) if "COLD" in str(c.get("label","")).upper() or "SWAGE" in str(c.get("label","")).upper()])

        # Straightening if forging mentions distortion/tolerance adjustments
        if any("STRAIGHTEN" in str(c.get("label","")).upper() or "STRAIGHT" in str(c.get("value","")).upper() for c in forging_table.get("cells", [])):
            add("Straightening", forging_table.get("cells", []))

    # ------------------ Heat treatment family ------------------
    heat_table = find_table_by_id(data, "tbl_heat_treatment")
    is_hardened = False
    if heat_table:
        # Carburising
        carburized = [c for c in heat_table.get("cells", []) if "CARBUR" in str(c.get("label","")).upper() or "CARBUR" in str(c.get("value","")).upper()]
        if carburized:
            add("Carburising", carburized)

        # Carbonitriding
        carbonitriding = [c for c in heat_table.get("cells", []) if "CARBONITRID" in str(c.get("label","")).upper() or "CARBONITRID" in str(c.get("value","")).upper()]
        if carbonitriding:
            add("Carbonitriding", carbonitriding)

        # Hardening & Tempering & Induction Hardening & Tempering
        harden = [c for c in heat_table.get("cells", []) if "HARDEN" in str(c.get("label","")).upper() or "HARDEN" in str(c.get("value","")).upper()]
        if harden:
            add("Hardening & Tempering", harden)
            is_hardened = True
        induction = [c for c in heat_table.get("cells", []) if "INDUCT" in str(c.get("label","")).upper() or "INDUCT" in str(c.get("value","")).upper()]
        if induction:
            add("Induction Hardening", induction)
        # Tempering explicit
        temp = [c for c in heat_table.get("cells", []) if "TEMPER" in str(c.get("label","")).upper() or "TEMPER" in str(c.get("value","")).upper()]
        if temp:
            add("Tempering", temp)
        # Annealing
        anneal = [c for c in heat_table.get("cells", []) if "ANNEAL" in str(c.get("label","")).upper() or "ANNEAL" in str(c.get("value","")).upper()]
        if anneal:
            add("Annealing", anneal)

    # ------------------ Surface treatments, plating, coating ------------------
    surface_table = find_table_by_id(data, "tbl_surface_treatment")
    if surface_table:
        surface_cells = surface_table.get("cells", []) or []
        # Shot Blasting / Shot Peening / Shot Peen
        if any("SHOT BLAST" in str(c.get("label","")).upper() or "SHOT BLAST" in str(c.get("value","")).upper() for c in surface_cells):
            add("Shot Blasting", [c for c in surface_cells if "SHOT BLAST" in str(c.get("label","")).upper() or "SHOT BLAST" in str(c.get("value","")).upper()])
        if any("SHOT PEEN" in str(c.get("label","")).upper() or "SHOT PEEN" in str(c.get("value","")).upper() or "PEEN" in str(c.get("label","")).upper() for c in surface_cells):
            add("Shot Peening", [c for c in surface_cells if "PEEN" in str(c.get("label","")).upper() or "PEEN" in str(c.get("value","")).upper()])

        # Chrome plating / Zinc passivation / Phosphating / Primer / Powder coating
        if any("CHROME" in str(c.get("label","")).upper() or "CHROME" in str(c.get("value","")).upper() for c in surface_cells):
            add("Chrome Plating", [c for c in surface_cells if "CHROME" in str(c.get("label","")).upper() or "CHROME" in str(c.get("value","")).upper()])
        if any("ZINC" in str(c.get("label","")).upper() or "ZINC" in str(c.get("value","")).upper() or "PASSIVAT" in str(c.get("label","")).upper() for c in surface_cells):
            add("Zinc Passivation / Plating", [c for c in surface_cells if "ZINC" in str(c.get("label","")).upper() or "PASSIVAT" in str(c.get("label","")).upper() or "ZINC" in str(c.get("value","")).upper()])
        if any("PHOSPHAT" in str(c.get("label","")).upper() or "PHOSPHAT" in str(c.get("value","")).upper() for c in surface_cells):
            add("Phosphating", [c for c in surface_cells if "PHOSPHAT" in str(c.get("label","")).upper() or "PHOSPHAT" in str(c.get("value","")).upper()])
        if any("PRIM" in str(c.get("label","")).upper() or "PRIM" in str(c.get("value","")).upper() for c in surface_cells):
            add("Priming (3 tank / 7 tank)", [c for c in surface_cells if "PRIM" in str(c.get("label","")).upper() or "PRIM" in str(c.get("value","")).upper()])
        if any("POWDER" in str(c.get("label","")).upper() or "POWDER" in str(c.get("value","")).upper() for c in surface_cells):
            add("Powder Coating", [c for c in surface_cells if "POWDER" in str(c.get("label","")).upper() or "POWDER" in str(c.get("value","")).upper()])

    # ------------------ General notes, deburring, chamfering, inspection ------------------
    general_notes = find_table_by_id(data, "tbl_general_notes")
    if general_notes:
        # Deburring and chamfering
        burr_match = [c for c in general_notes.get("cells", []) if "BURR" in str(c.get("value","")).upper() or "BURR" in str(c.get("label","")).upper()]
        if burr_match:
            add("Deburring", burr_match)
            add("Gear Tooth Chamfering", burr_match)
    # Chamfer dimension evidence
    chamfer_dims = [d for d in data.get("extracted_data", {}).get("dimensions", []) if d.get("raw_text") and ("X 45" in str(d.get("raw_text","")).upper() or "X45" in str(d.get("raw_text","")).upper() or "CHAMFER" in str(d.get("raw_text","")).upper())]
    if chamfer_dims:
        add("Gear Tooth Chamfering", chamfer_dims)

    # Inspection from permissible deviations
    deviations_table = find_table_by_id(data, "tbl_permissible_deviations")
    if deviations_table:
        add("Inspection", [format_cell_reason(c) for c in deviations_table.get("cells", []) if c])

    # Magnaflux / NDT
    # Search all tables for "MAGNA", "MAGNAFLUX", "MAGNETIC", "NDT", "ROTOR CRACK"
    mag_matches = collect_table_cells_by_keyword(data, ["MAGNA", "MAGNAFLUX", "NDT", "MAGNETIC", "MPI"])
    if mag_matches:
        add("Magnaflux", mag_matches)

    # ------------------ Gear specific family ------------------
    gear_table = find_table_by_id(data, "tbl_gear_data")
    if gear_table:
        add("Gear Hobbing", [format_cell_reason(c) for c in gear_table.get("cells", []) if c])
        # gear grinding (hard finishing) if gear quality/tolerance specified and heat treat hardened
        qual = next((c for c in gear_table.get("cells", []) if "QUALITY" in str(c.get("label","")).upper() or "TOLERANCE ZONE" in str(c.get("label","")).upper()), None)
        if qual:
            add("Gear Grinding", [qual])
        # hobbing vs shaping/shaving/rolling: look for explicit keywords in gear or notes
        # Gear Shaving / Gear Shaping / Gear Rolling / Gear Shaving hints
        g_keywords = collect_table_cells_by_keyword(data, ["SHAV", "SHAPE", "ROLL", "SHAVING", "SHAPING", "ROLLING"])
        if g_keywords:
            # assign processes based on exact keywords found
            if any("SHAV" in str(c["cell"].get("label","")).upper() or "SHAV" in str(c["cell"].get("value","")).upper() for c in g_keywords):
                add("Gear Shaving", g_keywords)
            if any("SHAPE" in str(c["cell"].get("label","")).upper() or "SHAPE" in str(c["cell"].get("value","")).upper() for c in g_keywords):
                add("Gear Shaping", g_keywords)
            if any("ROLL" in str(c["cell"].get("label","")).upper() or "ROLL" in str(c["cell"].get("value","")).upper() for c in g_keywords):
                add("Gear Rolling", g_keywords)

    # If gear table exists and module/teeth exist, it's strong evidence for hobbing already added.
    # For Gear Rolling/Shaping/Shaving also check tbl_notes
    notes_keywords = collect_notes_and_metadata_by_keyword(data, ["SHAV", "SHAPE", "ROLL", "GRIND", "CAM", "GTR"])
    if notes_keywords:
        # map to processes
        for nk in notes_keywords:
            # simple heuristic map
            txt = json.dumps(nk).upper()
            if "GTR" in txt:
                add("GTR", [nk])
            if "CAM" in txt:
                add("Cam Grinding", [nk])
            if "SHAV" in txt:
                add("Gear Shaving", [nk])
            if "SHAPE" in txt:
                add("Gear Shaping", [nk])
            if "ROLL" in txt:
                add("Gear Rolling", [nk])

    # ------------------ Machining family: turning, milling, slotting, sawing, drilling ------------------
    # Turning (based on cylindrical features / ⌀ dims)
    cyl_feats = [f for f in data.get("extracted_data", {}).get("features", []) if str(f.get("type","")).lower().startswith("cylindrical")]
    cyl_dims = [d for d in data.get("extracted_data", {}).get("dimensions", []) if d.get("symbol") == "⌀"]
    if cyl_feats or cyl_dims:
        add("Facing & Centering", cyl_feats + cyl_dims)
        add("Rough Turning", cyl_feats + cyl_dims)
        add("Finish Turning", cyl_feats + cyl_dims)
        add("Vertical Turning Centre (VTC)", cyl_feats + cyl_dims)

    # Milling family (VMC, HMC, VMC/HMC)
    # Search for "VMC", "HMC", "MILL", "VERTICAL MACHINING CENTRE", "HORIZONTAL MACHINING CENTRE"
    mill_matches = collect_table_cells_by_keyword(data, ["VMC", "HMC", "VERTICAL MACHINING CENTRE", "HORIZONTAL MACHINING CENTRE", "MILL", "MACHINING CENTRE"])
    if mill_matches:
        add("VMC (Vertical Machining Centre)", mill_matches)
        add("HMC (Horizontal Machining Centre)", mill_matches)

    # Slotting, Sawing, Blanking/Piercing
    slot_saw_matches = collect_table_cells_by_keyword(data, ["SLOT", "SLOTTING", "SAW", "BLANK", "PIERC", "PIERCING", "PUNCH"])
    if slot_saw_matches:
        if any("SLOT" in str(m["cell"].get("label","")).upper() or "SLOT" in str(m["cell"].get("value","")).upper() for m in slot_saw_matches):
            add("Slotting", slot_saw_matches)
        if any("SAW" in str(m["cell"].get("label","")).upper() or "SAW" in str(m["cell"].get("value","")).upper() for m in slot_saw_matches):
            add("Sawing", slot_saw_matches)
        if any("BLANK" in str(m["cell"].get("label","")).upper() or "PIERC" in str(m["cell"].get("value","")).upper() for m in slot_saw_matches):
            add("Blanking / Piercing", slot_saw_matches)

    # Drilling family: gun drilling (deep bore), gun drill, gun-drill keywords
    drill_matches = collect_table_cells_by_keyword(data, ["DRILL", "GUN DRILL", "GUN-DRILL", "BORE", "BORING", "REAM", "TAP", "TAPPING", "THREAD"])
    if drill_matches:
        # assign processes based on keywords
        if any("GUN" in str(m["cell"].get("label","")).upper() or "GUN" in str(m["cell"].get("value","")).upper() for m in drill_matches):
            add("Gun Drilling", drill_matches)
        if any("TAP" in str(m["cell"].get("label","")).upper() or "TAP" in str(m["cell"].get("value","")).upper() for m in drill_matches):
            add("Drilling / Tapping / Reaming", drill_matches)
        if any("REAM" in str(m["cell"].get("label","")).upper() or "REAM" in str(m["cell"].get("value","")).upper() for m in drill_matches):
            add("Drilling / Tapping / Reaming", drill_matches)
        # generic drilling
        add("Drilling / Tapping / Reaming", drill_matches)

    # Gun drilling/bore depth inference from dimensions: if diameter small and leaders mention long length, we'll add Gun Drilling evidence:
    for d in data.get("extracted_data", {}).get("dimensions", []):
        if d.get("symbol") == "⌀" and d.get("value") and d.get("value") <= 10:
            # shallow heuristic: small diameter bores may be gun drilled if note/feature mentions through-bore
            if any("THROUGH BORE" in str(f.get("role","")).upper() or "BOTH SIDE" in str(d.get("raw_text","")).upper() for f in data.get("extracted_data", {}).get("features", [])):
                add("Gun Drilling", [d])

    # Thread rolling / Traub / Thread related (look for "THREAD", "ROLL", "TRAUB")
    thread_matches = collect_table_cells_by_keyword(data, ["THREAD", "TRAUB", "ROLL"])
    if thread_matches:
        if any("TRAUB" in str(m["cell"].get("label","")).upper() or "TRAUB" in str(m["cell"].get("value","")).upper() for m in thread_matches):
            add("Traub", thread_matches)
        if any("THREAD" in str(m["cell"].get("label","")).upper() or "THREAD" in str(m["cell"].get("value","")).upper() for m in thread_matches):
            add("Thread Rolling", thread_matches)
        # Thread rolling could also be inferred from title_block part name (fasteners) etc.
        tb_hits = collect_notes_and_metadata_by_keyword(data, ["FASTENER", "THREAD"])
        if tb_hits:
            add("Thread Rolling", tb_hits)

    # Milling / VMC / HMC above - Gun drilling & other drilling covered.
    # Milling general
    milling_matches = collect_table_cells_by_keyword(data, ["MILL", "MILLING", "VMC", "HMC"])
    if milling_matches:
        add("Milling", milling_matches)

    # Traub already attempted; Traub is lathe brand - proceed if evidence
    # Traub process covered above.

    # ------------------ Grinding family ------------------
    # Grinding, Gear Grinding, Cam Grinding
    grind_matches = collect_table_cells_by_keyword(data, ["GRIND", "GRINDING", "CAM"])
    if grind_matches:
        # Cam Grinding
        if any("CAM" in str(m["cell"].get("label","")).upper() or "CAM" in str(m["cell"].get("value","")).upper() for m in grind_matches):
            add("Cam Grinding", grind_matches)
        # Gear Grinding
        if any("QUALITY" in str(m["cell"].get("label","")).upper() or "TOLERANCE" in str(m["cell"].get("label","")).upper() for m in (gear_table.get("cells", []) if gear_table else [])):
            add("Gear Grinding", grind_matches)
        add("Grinding", grind_matches)

    # GTR ambiguous: look for GTR in notes/tables
    gtr_matches = collect_table_cells_by_keyword(data, ["GTR"])
    if gtr_matches:
        add("GTR", gtr_matches)

    # ------------------ Welding ------------------
    weld_matches = collect_table_cells_by_keyword(data, ["WELD", "MIG"])
    if weld_matches:
        if any("MIG" in str(m["cell"].get("label","")).upper() or "MIG" in str(m["cell"].get("value","")).upper() for m in weld_matches):
            add("MIG Welding", weld_matches)
            add("MIG Tack Welding", weld_matches)
        else:
            add("MIG Welding", weld_matches)

    # ------------------ Surface prep / washing ------------------
    if is_hardened:
        # Washing / RPO Application always inferred when heat treat hardened present
        add("Washing / RPO Application", [c for c in (heat_table.get("cells", []) if heat_table else [])])

    # ------------------ Vendor / administrative processes ------------------
    # Vendor Code Punching evidence in notes/table
    vendor_matches = collect_table_cells_by_keyword(data, ["VENDOR CODE", "VENDOR", "CODE PUNCH", "VENDOR CODE PUNCH"])
    if vendor_matches:
        add("Vendor Code Punching", vendor_matches)

    # Primer Coating / Painting already attempted above under surface_table; also look for "PAINT"
    paint_matches = collect_table_cells_by_keyword(data, ["PAINT", "PRIMER", "PRIMING", "PRIMER COATING"])
    if paint_matches:
        add("Primer Coating / Painting", paint_matches)

    # Phosphating done above.

    # ------------------ Special forming operations ------------------
    # Swaging evidence
    swage_matches = collect_table_cells_by_keyword(data, ["SWAGE", "SWAGING"])
    if swage_matches:
        add("Swaging", swage_matches)

    # Cold Forging covered earlier

    # ------------------ Finishing and coating family ------------------
    blackodize_matches = collect_table_cells_by_keyword(data, ["BLACKODIZ", "BLACK OXIDE", "BLACKODIZING", "BLACK OXIDE"])
    if blackodize_matches:
        add("Blackodizing", blackodize_matches)

    # Zinc / Phosphating / Chrome done earlier. Primer / Powder Coating done earlier.

    # ------------------ Misc heuristics ------------------
    # If any explicit 'S PILOT' or 'S Pilot' mention then add S Pilot.
    s_pilot_matches = collect_table_cells_by_keyword(data, ["S PILOT", "S PILOT"])
    if s_pilot_matches:
        add("S Pilot", s_pilot_matches)

    # Trailing fallback: if part name contains words suggesting a gear process, we already added gear processes.
    # Additional processes that may be present as keywords in any cell or notes:
    additional_process_keywords = {
        "Slotting": ["SLOT", "SLOTTING"],
        "Sawing": ["SAW"],
        "Shot Peening": ["PEEN", "SHOT PEEN"],
        "Thread Rolling": ["THREAD", "ROLL"],
        "Swaging": ["SWAGE"],
        "Blanking / Piercing": ["BLANK", "PIERC"],
        "Brazing": ["BRAZE"]
    }
    for proc, keys in additional_process_keywords.items():
        matches = collect_table_cells_by_keyword(data, keys)
        if matches:
            add(proc, matches)

    # ------------------ Final dedupe & return ------------------
    return results