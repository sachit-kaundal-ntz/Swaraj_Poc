
import math

USD_TO_INR: float = 84.0   # ← single constant — keep in sync with materials.py


def _inr(usd: float) -> float:
    return round(usd * USD_TO_INR, 2)


OPERATIONS_TEMPLATES: dict = {
    "spur": [
        # ── Forging ────────────────────────────────────────────────────────
        {"operation": "Forging",                   "description": "Blank forging",                        "estimated_time_min": 15,  "rate_per_hour": _inr(60),   "machine_options": ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"]},
        # ── Tooth cutting ──────────────────────────────────────────────────
        {"operation": "Gear Hobbing",              "description": "Spur gear tooth cutting by hobbing",   "estimated_time_min": 25,  "rate_per_hour": _inr(95),   "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
        {"operation": "Helical Hobbing",           "description": "Helical gear tooth cutting",           "estimated_time_min": 35,  "rate_per_hour": _inr(105),  "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
        {"operation": "Gear Tooth Chamfering",     "description": "Chamfer tooth edges",                  "estimated_time_min": 8,   "rate_per_hour": _inr(45),   "machine_options": ["Gear Tooth Chamfering"]},
        {"operation": "Chamfering",                "description": "General chamfering",                   "estimated_time_min": 8,   "rate_per_hour": _inr(45),   "machine_options": ["Gear Tooth Chamfering"]},
        # ── Heat treatment ─────────────────────────────────────────────────
        {"operation": "Carburising",               "description": "Case carburising",                     "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"]},
        {"operation": "Carbonitriding",            "description": "Carbonitriding",                       "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Carbonitriding Furnace"]},
        {"operation": "Quenching",                 "description": "Oil/water quench after carburising",   "estimated_time_min": 30,  "rate_per_hour": _inr(55),   "machine_options": ["Carburising SQF", "Carburising Salt bath"]},
        {"operation": "Tempering",                 "description": "Stress relieve temper",                "estimated_time_min": 60,  "rate_per_hour": _inr(55),   "machine_options": ["Tempering Furnace"]},
        {"operation": "Hardening & Tempering",     "description": "Through hardening + temper",           "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Hardening & Tempering Furnace"]},
        {"operation": "Nitriding",                 "description": "Gas / plasma nitriding",               "estimated_time_min": 480, "rate_per_hour": _inr(55),   "machine_options": ["Nitriding Furnace"]},
        {"operation": "Induction Hardening",       "description": "Induction surface hardening",          "estimated_time_min": 20,  "rate_per_hour": _inr(90),   "machine_options": ["Induction Hardening M/c"]},
        {"operation": "Normalising",               "description": "Normalising",                          "estimated_time_min": 60,  "rate_per_hour": _inr(45),   "machine_options": ["Normalising Furnace"]},
        {"operation": "Annealing",                 "description": "Annealing",                            "estimated_time_min": 60,  "rate_per_hour": _inr(45),   "machine_options": ["Annealing Furnace"]},
        {"operation": "Isothermal Annealing",      "description": "Isothermal annealing",                 "estimated_time_min": 90,  "rate_per_hour": _inr(45),   "machine_options": ["Isothermal Annealing Furnace"]},
        # ── Grinding ───────────────────────────────────────────────────────
        {"operation": "Gear Grinding",             "description": "Tooth flank profile grinding",         "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Grinding - Gear",           "description": "Gear profile CNC grinding",            "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Grinding - CNC",            "description": "CNC cylindrical / surface grinding",   "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Internal Grinding",         "description": "Bore internal grinding for H7/H8 fit", "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
        {"operation": "Grinding",                  "description": "General grinding",                     "estimated_time_min": 25,  "rate_per_hour": _inr(100),  "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
        # ── Turning ────────────────────────────────────────────────────────
        {"operation": "Rough Turning",             "description": "OD rough turning",                     "estimated_time_min": 18,  "rate_per_hour": _inr(75),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        {"operation": "Finish Turning",            "description": "OD finish turning",                    "estimated_time_min": 12,  "rate_per_hour": _inr(80),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        {"operation": "Turning",                   "description": "General turning / groove",             "estimated_time_min": 15,  "rate_per_hour": _inr(75),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        # ── Drilling / boring ──────────────────────────────────────────────
        {"operation": "Drilling / Boring",         "description": "Bore drilling or boring",              "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
        {"operation": "Drilling",                  "description": "Drilling",                             "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
        {"operation": "Gun Drilling",              "description": "Deep-hole gun drilling",               "estimated_time_min": 20,  "rate_per_hour": _inr(85),   "machine_options": ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"]},
        # ── Gear secondary ops ─────────────────────────────────────────────
        {"operation": "Gear Shaping",              "description": "Internal/external gear shaping",       "estimated_time_min": 55,  "rate_per_hour": _inr(110),  "machine_options": ["Gear Shaping Conventional"]},
        {"operation": "Gear Shaving",              "description": "Gear tooth shaving",                   "estimated_time_min": 20,  "rate_per_hour": _inr(95),   "machine_options": ["Gear Shaving CNC", "Gear Shaving Conventional"]},
        {"operation": "Broaching",                 "description": "Keyway / spline broaching",            "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Horizontal Broaching", "Vertical Broaching"]},
        {"operation": "Threading",                 "description": "Thread cutting",                       "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC"]},
        # ── Surface treatment ──────────────────────────────────────────────
        {"operation": "Shot Peening",              "description": "Shot peen tooth roots",                "estimated_time_min": 20,  "rate_per_hour": _inr(60),   "machine_options": ["Shot Peening"]},
        {"operation": "Shot Blasting",             "description": "Shot blasting",                        "estimated_time_min": 10,  "rate_per_hour": _inr(40),   "machine_options": ["Shot Blasting"]},
        {"operation": "Phosphating",               "description": "Black phosphate coating",              "estimated_time_min": 30,  "rate_per_hour": _inr(45),   "machine_options": ["Phosphating Tank"]},
        {"operation": "Plating",                   "description": "Zinc / electroplating",               "estimated_time_min": 45,  "rate_per_hour": _inr(50),   "machine_options": ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"]},
        {"operation": "Blackodizing",              "description": "Black oxide coating",                  "estimated_time_min": 30,  "rate_per_hour": _inr(40),   "machine_options": ["Blackodizing Furnace"]},
        {"operation": "Powder Coating",            "description": "Powder coating",                       "estimated_time_min": 25,  "rate_per_hour": _inr(40),   "machine_options": ["Powder Coating"]},
        {"operation": "Primer Coating / Painting", "description": "Primer / painting",                   "estimated_time_min": 20,  "rate_per_hour": _inr(35),   "machine_options": ["Primer Coating", "Painting cum primer"]},
        # ── Inspection / finishing ─────────────────────────────────────────
        {"operation": "Final Inspection",          "description": "CMM / Magnaflux inspection",           "estimated_time_min": 15,  "rate_per_hour": _inr(85),   "machine_options": ["Magnaflux", "Manual"]},
        {"operation": "Inspection",                "description": "General inspection",                   "estimated_time_min": 15,  "rate_per_hour": _inr(85),   "machine_options": ["Magnaflux", "Manual"]},
        {"operation": "Deburring",                 "description": "Remove all burrs",                     "estimated_time_min": 6,   "rate_per_hour": _inr(40),   "machine_options": ["Manual Deburring"]},
    ],
    "helical": [],
    "bevel":   [],
}

# Helical: copy spur but swap "Gear Hobbing" → "Helical Hobbing"
_helical = []
for _op in OPERATIONS_TEMPLATES["spur"]:
    if _op["operation"] == "Gear Hobbing":
        _helical.append({
            "operation":          "Helical Hobbing",
            "description":        "Helical gear tooth cutting",
            "estimated_time_min": 35,
            "rate_per_hour":      _inr(105),
            "machine_options":    ["Gear Hobbing CNC", "Gear Hobbing Conventional"],
        })
    else:
        _helical.append(_op.copy())
OPERATIONS_TEMPLATES["helical"] = _helical
OPERATIONS_TEMPLATES["bevel"]   = [op.copy() for op in OPERATIONS_TEMPLATES["spur"]]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_all_text(extracted_data: dict) -> str:
    parts = []
    def _walk(obj):
        if isinstance(obj, str):    parts.append(obj.lower())
        elif isinstance(obj, dict): [_walk(v) for v in obj.values()]
        elif isinstance(obj, list): [_walk(i) for i in obj]
    _walk(extracted_data)
    return " ".join(parts)


def _get_table_cell(extracted_data: dict, table_id: str, cell_label: str):
    for tbl in extracted_data.get("tables", []):
        if tbl.get("id", "").lower() == table_id.lower():
            for cell in tbl.get("cells", []):
                if cell.get("label", "").strip().upper() == cell_label.strip().upper():
                    return cell.get("value")
    return None


def _get_surface_ra(extracted_data: dict):
    min_ra = None
    for spec in extracted_data.get("surface_specifications", []):
        rv = spec.get("roughness_value", "")
        if isinstance(rv, str) and "ra" in rv.lower():
            try:
                val = float("".join(
                    c for c in rv.lower().replace("ra", "").strip().split()[0]
                    if c in "0123456789."
                ))
                if min_ra is None or val < min_ra:
                    min_ra = val
            except (ValueError, IndexError):
                pass
        elif isinstance(rv, (int, float)):
            if min_ra is None or rv < min_ra:
                min_ra = rv
    return min_ra


def _get_tolerance_types(extracted_data: dict) -> list:
    return [t.get("tolerance_type", "").lower()
            for t in extracted_data.get("geometric_tolerances", [])
            if t.get("tolerance_type")]


def _has_feature_type(extracted_data: dict, feat_type: str) -> bool:
    return any(f.get("type", "").lower() == feat_type.lower()
               for f in extracted_data.get("features", []))


def _op_template(family: str, op_name: str) -> dict:
    for op in OPERATIONS_TEMPLATES.get(family, OPERATIONS_TEMPLATES["spur"]):
        if op["operation"].lower() == op_name.lower():
            return op
    for op in OPERATIONS_TEMPLATES["spur"]:
        if op["operation"].lower() == op_name.lower():
            return op
    return {
        "operation":          op_name,
        "estimated_time_min": 15,
        "rate_per_hour":      _inr(60),
        "machine_options":    [],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def classify_and_plan(extracted_data: dict) -> dict:
    """Step 1 — Gear Classification & Operation Planning."""
    if "extracted_data" in extracted_data:
        extracted_data = extracted_data["extracted_data"]

    all_text = _get_all_text(extracted_data)
    evidence: list[str]               = []
    ops_planned: list[tuple[str,str]] = []

    # ── Gear family ──────────────────────────────────────────────────────────
    helix_angle = _get_table_cell(extracted_data, "tbl_gear_data", "HELIX ANGLE")
    gear_family = "spur"
    try:
        helix_val = float(str(helix_angle).replace("°", "").strip()) if helix_angle else 0.0
    except ValueError:
        helix_val = 0.0

    if helix_val > 0.2:
        gear_family = "helical"
        evidence.append(f"Helix angle = {helix_val}° > 0.2° → helical gear family")
    elif "helical" in all_text:
        gear_family = "helical"
        evidence.append("Keyword 'helical' found → helical gear family")
    elif "bevel" in all_text:
        gear_family = "bevel"
        evidence.append("Keyword 'bevel' found → bevel gear family")
    else:
        evidence.append("No helix angle → default spur gear family")

    # ── Default ops ──────────────────────────────────────────────────────────
    if gear_family == "helical":
        ops_planned += [
            ("Forging",               "Default: all gears require forging blank"),
            ("Helical Hobbing",       "Default: helical gear tooth cutting"),
            ("Gear Tooth Chamfering", "Default: chamfer after hobbing"),
            ("Deburring",             "Default: deburring always required"),
        ]
    else:
        ops_planned += [
            ("Forging",               "Default: all gears require forging blank"),
            ("Gear Hobbing",          "Default: spur/bevel gear tooth cutting"),
            ("Gear Tooth Chamfering", "Default: chamfer after hobbing"),
            ("Deburring",             "Default: deburring always required"),
        ]

    # ── Heat treatment ───────────────────────────────────────────────────────
    mat_treat   = extracted_data.get("material_and_treatment", {})
    title_block = extracted_data.get("metadata", {}).get("title_block", {})
    ht_text = (str(mat_treat.get("heat_treatment",  "")).lower() + " " +
               str(title_block.get("heat_treatment", "")).lower())

    if "carbur"         in ht_text: ops_planned += [("Carburising", "heat_treatment: carbur"), ("Quenching", "Carburising→quench"), ("Tempering", "Carburising→temper")]
    if "carbonitriding" in ht_text: ops_planned.append(("Carbonitriding",    "heat_treatment: carbonitriding"))
    if "nitrid"         in ht_text: ops_planned.append(("Nitriding",          "heat_treatment: nitrid"))
    if "induction"      in ht_text: ops_planned.append(("Induction Hardening","heat_treatment: induction"))
    if "normaliz" in ht_text or "normalised" in ht_text or "normalized" in ht_text:
        ops_planned.append(("Normalising", "heat_treatment: normaliz"))
    if "anneal" in ht_text and "isothermal" not in ht_text:
        ops_planned.append(("Annealing",           "heat_treatment: anneal"))
    if "isothermal" in ht_text:
        ops_planned.append(("Isothermal Annealing", "heat_treatment: isothermal"))

    # ── Surface / finish ─────────────────────────────────────────────────────
    finish_text = (str(mat_treat.get("finish",   "")).lower() + " " +
                   str(title_block.get("finish", "")).lower())
    if "phosphat" in finish_text: ops_planned.append(("Phosphating",               "finish: phosphat"))
    if "zinc"     in finish_text or "plat" in finish_text: ops_planned.append(("Plating", "finish: zinc/plat"))
    if "blackod"  in finish_text: ops_planned.append(("Blackodizing",              "finish: blackod"))
    if "powder"   in finish_text: ops_planned.append(("Powder Coating",            "finish: powder"))
    if "paint"    in finish_text: ops_planned.append(("Primer Coating / Painting", "finish: paint"))

    # ── Ra ───────────────────────────────────────────────────────────────────
    min_ra = _get_surface_ra(extracted_data)
    if min_ra is not None:
        if min_ra <= 0.8:
            ops_planned += [
                ("Grinding - Gear", f"Ra≤0.8 µm ({min_ra})"),
                ("Grinding - CNC",  f"Ra≤0.8 µm ({min_ra})"),
            ]
        elif min_ra <= 3.2:
            ops_planned.append(("Finish Turning", f"Ra≤3.2 µm ({min_ra})"))

    # ── GD&T ─────────────────────────────────────────────────────────────────
    for tt in _get_tolerance_types(extracted_data):
        if "runout" in tt or "cylindricity" in tt:
            ops_planned += [
                ("Grinding - Gear", f"Tolerance '{tt}'"),
                ("Grinding - CNC",  f"Tolerance '{tt}'"),
            ]

    # ── Bore fit ─────────────────────────────────────────────────────────────
    for dim in extracted_data.get("dimensions", []):
        if dim.get("id") == "dim_bore":
            tol = str(dim.get("tolerance", "")).upper()
            if "H7" in tol or "H8" in tol:
                ops_planned += [
                    ("Drilling / Boring",  "Bore dim present"),
                    ("Internal Grinding",  f"Bore tol {tol}"),
                ]

    # ── Features ─────────────────────────────────────────────────────────────
    if _has_feature_type(extracted_data, "keyway"):
        ops_planned.append(("Broaching", "feature: keyway"))
    if _has_feature_type(extracted_data, "internal_spline"):
        ops_planned += [
            ("Gear Shaping", "feature: internal_spline"),
            ("Broaching",    "feature: internal_spline"),
        ]

    # ── Manufacturing notes ──────────────────────────────────────────────────
    for note in extracted_data.get("manufacturing_notes", []):
        nt  = note.get("note_text", "").lower()
        raw = note.get("note_text", "")
        if "peen"    in nt: ops_planned.append(("Shot Peening",             f"Note: '{raw}'"))
        if "blast"   in nt: ops_planned.append(("Shot Blasting",            f"Note: '{raw}'"))
        if "deburr"  in nt: ops_planned.append(("Deburring",                "Note: deburring"))
        if "grind"   in nt: ops_planned.append(("Grinding - Gear",          f"Note: '{raw}'"))
        if "inspect" in nt or "cmm" in nt: ops_planned.append(("Final Inspection", f"Note: '{raw}'"))
        if "din"     in nt and "grind" in nt: ops_planned.append(("Grinding - Gear", "DIN+grind in notes"))

    # ── Quality class ────────────────────────────────────────────────────────
    quality = str(_get_table_cell(extracted_data, "tbl_gear_data", "QUALITY CLASS") or "").upper()
    if "DIN 6" in quality or "DIN6" in quality:
        ops_planned.append(("Grinding - Gear", "DIN 6 → fine grinding"))
    elif "DIN 8" in quality or "DIN8" in quality:
        evidence.append("DIN 8 → hobbing only, no extra grinding")

    # ── Rough turning always ─────────────────────────────────────────────────
    ops_planned.append(("Rough Turning", "Hub/blank OD rough turning"))

    # ── De-duplicate ─────────────────────────────────────────────────────────
    seen: set[str]              = set()
    operations_sequence: list   = []
    operations_evidence: list   = []

    for op_name, reason in ops_planned:
        if op_name not in seen:
            seen.add(op_name)
            operations_sequence.append(op_name)
            tmpl = _op_template(gear_family, op_name)
            operations_evidence.append({
                "operation":          op_name,
                "reason":             reason,
                "estimated_time_min": tmpl.get("estimated_time_min", 15),
                "rate_per_hour":      tmpl.get("rate_per_hour", _inr(60)),
                "machine_options":    tmpl.get("machine_options", []),
            })

    return {
        "gear_family":         gear_family,
        "evidence":            evidence,
        "operations_sequence": operations_sequence,
        "operations_evidence": operations_evidence,
    }


def compute_cost_breakdown(
    material_cost:   float,
    operations_cost: float,
    overhead_pct:    float = 15.0,
    margin_pct:      float = 20.0,
    currency:        str   = "INR",   # ← INR default
) -> dict:
    overhead = (material_cost + operations_cost) * overhead_pct / 100.0
    subtotal = material_cost + operations_cost + overhead
    margin   = subtotal * margin_pct / 100.0
    total    = subtotal + margin
    return {
        "material_cost":   round(material_cost,   2),
        "operations_cost": round(operations_cost, 2),
        "overhead_pct":    overhead_pct,
        "overhead_cost":   round(overhead, 2),
        "subtotal":        round(subtotal, 2),
        "margin_pct":      margin_pct,
        "margin_cost":     round(margin,   2),
        "total_cost":      round(total,    2),
        "currency":        currency,
    }