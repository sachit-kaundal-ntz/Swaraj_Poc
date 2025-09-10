# gear_rule_engine.py

import re
from typing import Any, Dict, List, Tuple, Optional

def _lower(x: Optional[str]) -> str:
    return (x or "").lower()

def _num(s: Any) -> Optional[float]:
    if s is None: return None
    try:
        return float(re.findall(r"[-+]?\d+(?:\.\d+)?", str(s))[0])
    except Exception:
        return None

def _walk_texts(j: Dict) -> List[str]:
    texts = []
    xd = j.get("extracted_data", {})

    md = xd.get("drawing_metadata", {}) or {}
    if isinstance(md, dict):
        texts += [md.get("part_name",""), md.get("drawing_number",""), md.get("component_type","")]
    elif isinstance(md, str):
        texts.append(md)

    for n in xd.get("manufacturing_notes", []) or []:
        if isinstance(n, dict):
            texts.append(n.get("note_text",""))
        elif isinstance(n, str):
            texts.append(n)

    for s in xd.get("surface_specifications", []) or []:
        if isinstance(s, dict):
            texts += [s.get("surface_symbol",""), s.get("machining_requirement","")]
        elif isinstance(s, str):
            texts.append(s)

    mat = xd.get("material_and_treatment", {})
    if isinstance(mat, dict):
        texts += [mat.get("base_material",""), mat.get("heat_treatment",""), mat.get("finish","")]
    elif isinstance(mat, str):
        texts.append(mat)

    for f in xd.get("feature_dimensions", []) or []:
        if isinstance(f, dict):
            texts += [f.get("feature_type",""), f.get("feature_description",""), f.get("specification","")]
        elif isinstance(f, str):
            texts.append(f)

    for v in xd.get("section_views", []) or []:
        if isinstance(v, dict):
            texts.append(v.get("section_identifier",""))
        elif isinstance(v, str):
            texts.append(v)

    return [t for t in texts if t]

def _get_overall_OD_H(j: Dict) -> Tuple[Optional[float], Optional[float]]:
    xd = j.get("extracted_data", {}) or {}
    od = _num(xd.get("overall_dimensions", {}).get("diameter", {}).get("value"))
    ln = _num(xd.get("overall_dimensions", {}).get("length", {}).get("value"))
    # fallbacks from geometric_decomposition
    if od is None or ln is None:
        bases = xd.get("geometric_decomposition", {}).get("base_shapes", []) or []
        if bases:
            dims = bases[0].get("dimensions", {}) or {}
            if od is None:
                od = _num(dims.get("main_outer_diameter","") or (dims.get("main_outer_diameter",{}) or {}).get("value"))
            if ln is None:
                ln = _num(dims.get("total_height","") or (dims.get("total_height",{}) or {}).get("value"))
    return od, ln

def _get_helix_angle(j: Dict) -> Optional[float]:
    # Try to find an explicit helix angle in feature specs or tables
    xd = j.get("extracted_data", {}) or {}
    for f in xd.get("feature_dimensions", []) or []:
        for k in ("feature_description","specification"):
            txt = _lower(f.get(k))
            if "helix" in txt or "β" in txt or "spiral angle" in txt:
                vals = re.findall(r"[-+]?\d+(?:\.\d+)?", txt)
                if vals: return float(vals[0])
    # Some drawings place helix in tables_and_data
    for t in xd.get("tables_and_data", []) or []:
        for row in t.get("table_data", []) or []:
            for cell in row.values():
                ct = _lower(str(cell))
                if any(w in ct for w in ["helix","spiral angle","β"]):
                    vals = re.findall(r"[-+]?\d+(?:\.\d+)?", ct)
                    if vals: return float(vals[0])
    return None

def _has_internal_teeth(j: Dict) -> bool:
    """Detect internal gear: inward-facing teeth / internal ring."""
    texts = " ".join(_walk_texts(j)).lower()
    if any(w in texts for w in ["internal gear","ring gear","annular gear","inner teeth","inward-facing teeth"]):
        return True
    # Geometry hint: a ring-like blank with subtracted inner tooth form
    xd = j.get("extracted_data", {}) or {}
    # Internal tooth processes (shaping/skiving/broaching) frequently appear in notes/specs
    if any(w in texts for w in ["gear shaping","power skiving","internal broach"]):
        return True
    return False

def _looks_bevel(j: Dict) -> Tuple[bool, Optional[str]]:
    """Detect straight vs spiral bevel by text & hints (conical body, intersecting shafts)."""
    texts = " ".join(_walk_texts(j)).lower()
    if "bevel" in texts:
        if any(w in texts for w in ["straight bevel","straight tooth"]):
            return True, "straight bevel"
        if any(w in texts for w in ["spiral bevel","zerol","hypoid"]):
            return True, "spiral bevel"
        # If unspecified, default to 'bevel'
        return True, "bevel"
    # Conical cues (rarely explicit in extraction without the word 'bevel')
    return False, None

def _looks_cluster(j: Dict) -> bool:
    """Detect multiple gear sections on one shaft/hub."""
    texts = " ".join(_walk_texts(j)).lower()
    if "cluster gear" in texts:
        return True
    # Heuristic: multiple gear segments present in features
    gears = 0
    for f in j.get("extracted_data", {}).get("feature_dimensions", []) or []:
        desc = _lower(f.get("feature_description"))
        if "gear" in desc or "tooth" in desc:
            gears += 1
    return gears >= 2

def _looks_bull(j: Dict) -> bool:
    """Detect bull gear (very large driven gear)."""
    texts = " ".join(_walk_texts(j)).lower()
    if "bull gear" in texts:
        return True
    # Heuristic size threshold
    od, _ = _get_overall_OD_H(j)
    return bool(od and od >= 600.0)  # adjust threshold to your domain

def classify_gear_family(j: Dict) -> Tuple[str, Dict[str,str]]:
    """
    Returns (gear_family, evidence_map).
    gear_family in {"spur","helical","straight bevel","spiral bevel","bevel","internal","cluster","bull","unknown"}
    """
    ev = {}
    # Priority: internal & bevel & cluster/bull (mutually distinctive) before spur/helical
    if _has_internal_teeth(j):
        ev["family"] = "Detected internal-gear cues (ring/inner teeth/shaping/skiving)"
        return "internal", ev
    looks_bev, bev_type = _looks_bevel(j)
    if looks_bev:
        ev["family"] = f"Detected {bev_type or 'bevel'} by text cues"
        return bev_type or "bevel", ev
    if _looks_cluster(j):
        ev["family"] = "Multiple gear segments / 'cluster gear' text"
        return "cluster", ev
    if _looks_bull(j):
        ev["family"] = "Large OD or 'bull gear' text"
        return "bull", ev

    # Spur vs Helical (external): helix angle or keywords
    texts = " ".join(_walk_texts(j)).lower()
    helix = _get_helix_angle(j)
    if helix is not None and helix > 0.2:
        ev["family"] = f"Helix angle {helix}°"
        return "helical", ev
    if "helical" in texts:
        ev["family"] = "Keyword 'helical'"
        return "helical", ev
    # default to spur if gear hints exist and no helix cues
    if any(w in texts for w in ["gear","tooth","module","involute","hob"]):
        ev["family"] = "Gear terms present; no helix cues → spur"
        return "spur", ev

    ev["family"] = "No clear gear cues"
    return "unknown", ev

# ---------- Operation inference ----------

def infer_operations(j: Dict, gear_family: str) -> Tuple[List[str], Dict[str,str]]:
    ops: List[str] = []
    why: Dict[str,str] = {}
    texts = " ".join(_walk_texts(j)).lower()
    xd = j.get("extracted_data", {}) or {}

    def add(op: str, reason: str):
        if op not in ops:
            ops.append(op); why[op] = reason

    # 0) Universal prep
    if "forge" in texts or "forging" in texts:
        add("Forging", "Notes/material mention forging")
    # If no explicit forging but it's a gear blank: allow heuristic
    elif gear_family in {"spur","helical","straight bevel","spiral bevel","bevel","bull","cluster"}:
        add("Forging", "Default blank preparation for steel gears")

    # 1) Turning (rough/finish) if cylindrical bands exist
    od, ln = _get_overall_OD_H(j)
    if od and ln:
        add("Rough Turning", "Cylindrical blank with overall OD/Length present")
        # Surface roughness heuristic for finish turning
        rough_vals = []
        for s in xd.get("surface_specifications", []) or []:
            rv = _lower(s.get("roughness_value"))
            if rv:
                try:
                    rough_vals += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", rv)]
                except: pass
        if any(v <= 3.2 for v in rough_vals):
            add("Finish Turning", "Surface roughness ≤ 3.2 µm on turned surfaces")

    # 2) Tooth cutting per family
    if gear_family in {"spur","helical","bull","cluster"}:
        add("Gear Hobbing", f"{gear_family.title()} external teeth")
    if gear_family == "internal":
        # internal: shaping/skiving/broaching (rule per guide)
        if any(k in texts for k in ["skiving","power skiving"]):
            add("Power Skiving", "Internal gear note mentions skiving")
        elif "broach" in texts:
            add("Broaching", "Internal gear note mentions broach")
        else:
            add("Gear Shaping", "Internal teeth require shaping/skiving/broaching")
    if "keyway" in texts or any((f.get("feature_type") or "").lower()=="keyway" for f in xd.get("feature_dimensions",[]) or []):
        add("Broaching", "Keyway feature implies broach")

    # 3) Chamfering on teeth/edges
    if "chamfer" in texts:
        add("Gear Tooth Chamfering", "Chamfer noted")
    else:
        # often implicit; add for external gears
        if gear_family in {"spur","helical","bull","cluster"}:
            add("Gear Tooth Chamfering", "Standard edge break for external teeth")

    # 4) Heat treatment
    ht = _lower(xd.get("material_and_treatment", {}).get("heat_treatment"))
    if any(k in ht for k in ["carbur", "case hard"]):
        add("Carburising", "Heat treatment notes")
        add("Quenching", "Post-carburising hardening")
        if "temper" in ht:
            add("Tempering", "Heat treatment notes")
        else:
            add("Tempering", "Standard post-quench temper")
    else:
        if "harden" in ht: add("Hardening", "Heat treatment notes")
        if "temper" in ht: add("Tempering", "Heat treatment notes")

    # 5) Grinding based on roughness / GD&T / notes
    tight = False
    for g in xd.get("geometric_tolerances", []) or []:
        t = _lower(g.get("tolerance_type"))
        val = _lower(g.get("tolerance_value"))
        if any(k in t for k in ["runout","circularity","cylindricity","profile","parallel","perpendicular"]):
            tight = True
    if tight or "grind" in texts:
        if gear_family in {"internal","spur","helical","bull","cluster"}:
            add("Grinding - Gear", "Tight tooth/geometry tolerance or notes")
        add("Grinding - CNC", "Tight datum/OD/ID tolerance or notes")

    # 6) Deburring post-cut
    add("Deburring", "Standard post-cut operation")

    # 7) Family-specific extras
    if gear_family in {"straight bevel","spiral bevel","bevel"}:
        # manufacturing per guide: forging → bevel cutting → heat treat → grinding/lapping
        add("Bevel Gear Cutting", "Bevel gear family (milling/shaping)")
        add("Lapping", "Bevel finishing (noise/surface)")

    return ops, why

def classify_and_plan(j: Dict) -> Dict[str, Any]:
    family, family_ev = classify_gear_family(j)
    ops, why_ops = infer_operations(j, family)
    return {
        "gear_family": family,
        "evidence": family_ev,
        "operations_sequence": ops,
        "operations_evidence": why_ops
    }