"""
validation_service.py
Step 6 — Validation (30 rules across 6 layers)
Location: app/service/validation_service.py

Entry point: validate_all(extracted_data, volume_result, cost_result)
Returns: {validation_passed, confidence_score, confidence_level,
          ready_for_quote, error_count, warn_count, rules}
"""


def _get_dim(extracted_data: dict, dim_id: str):
    for d in extracted_data.get("dimensions", []):
        if d.get("id") == dim_id:
            try:
                return float(d.get("value", 0) or 0)
            except (TypeError, ValueError):
                return None
    return None


def _get_table_cell(extracted_data: dict, table_id: str, label: str):
    for tbl in extracted_data.get("tables", []):
        if tbl.get("id", "").lower() == table_id.lower():
            for cell in tbl.get("cells", []):
                if cell.get("label", "").strip().upper() == label.strip().upper():
                    try:
                        return float(cell.get("value", 0) or 0)
                    except (TypeError, ValueError):
                        return cell.get("value")
    return None


def _rule(rule_id, layer, severity, passed, message):
    return {
        "rule_id": rule_id,
        "layer": layer,
        "severity": severity,
        "passed": passed,
        "message": message,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1 — Geometric Physics (G1–G8)
# ──────────────────────────────────────────────────────────────────────────────

def _layer1_geometric(extracted_data: dict) -> list:
    results = []

    od = _get_dim(extracted_data, "dim_outer_dia")
    fw = _get_dim(extracted_data, "dim_face_width")
    hub_dia = _get_dim(extracted_data, "dim_hub_dia")
    hub_h = _get_dim(extracted_data, "dim_hub_height")
    bore = _get_dim(extracted_data, "dim_bore")

    module = _get_table_cell(extracted_data, "tbl_gear_data", "MODULE")
    no_teeth = _get_table_cell(extracted_data, "tbl_gear_data", "NO OF TEETH")

    # G1: OD > pitch_dia (= module × teeth)
    if module and no_teeth and od:
        pitch_dia = float(module) * float(no_teeth)
        passed = od > pitch_dia
        results.append(_rule("G1", 1, "ERROR",
            passed,
            f"OD ({od}) must be > pitch_dia ({pitch_dia:.1f})" if not passed else
            f"OK: OD {od} > pitch_dia {pitch_dia:.1f}"
        ))
    else:
        results.append(_rule("G1", 1, "WARN", True, "G1 skipped: module, teeth, or OD missing"))

    # G2: hub_height ≥ face_width
    if hub_h is not None and fw is not None:
        passed = hub_h >= fw
        results.append(_rule("G2", 1, "ERROR",
            passed,
            f"hub_height ({hub_h}) must be ≥ face_width ({fw})" if not passed else
            f"OK: hub_height {hub_h} ≥ face_width {fw}"
        ))
    else:
        results.append(_rule("G2", 1, "WARN", True, "G2 skipped: hub_height or face_width missing"))

    # G3: bore < hub_dia < OD
    if bore and hub_dia and od:
        passed = bore < hub_dia < od
        results.append(_rule("G3", 1, "ERROR",
            passed,
            f"bore ({bore}) < hub_dia ({hub_dia}) < OD ({od}) violated" if not passed else
            f"OK: bore {bore} < hub_dia {hub_dia} < OD {od}"
        ))
    else:
        results.append(_rule("G3", 1, "WARN", True, "G3 skipped: bore, hub_dia, or OD missing"))

    # G4: face_width / OD ratio 0.05–0.8
    if fw and od and od > 0:
        ratio = fw / od
        passed = 0.05 <= ratio <= 0.8
        results.append(_rule("G4", 1, "WARN",
            passed,
            f"face_width/OD = {ratio:.3f}; expected 0.05–0.8" if not passed else
            f"OK: face_width/OD = {ratio:.3f}"
        ))
    else:
        results.append(_rule("G4", 1, "WARN", True, "G4 skipped: face_width or OD missing"))

    # G5: pitch_dia = module × teeth (±5%)
    if module and no_teeth:
        calc_pd = float(module) * float(no_teeth)
        addendum = _get_table_cell(extracted_data, "tbl_gear_data", "ADDENDUM")
        if od and addendum:
            implied_pd = od - 2 * float(addendum)
            diff_pct = abs(calc_pd - implied_pd) / calc_pd * 100 if calc_pd else 0
            passed = diff_pct <= 5
            results.append(_rule("G5", 1, "WARN",
                passed,
                f"G5: pitch_dia mismatch: calc={calc_pd:.2f} vs implied={implied_pd:.2f} ({diff_pct:.1f}%)" if not passed else
                f"OK G5: pitch_dia cross-check within 5%"
            ))
        else:
            results.append(_rule("G5", 1, "WARN", True, "G5 skipped: addendum or OD missing"))
    else:
        results.append(_rule("G5", 1, "WARN", True, "G5 skipped: module or teeth missing"))

    # G6: OD ≈ (num_teeth + 2) × module (±8%)
    if module and no_teeth and od:
        expected_od = (float(no_teeth) + 2) * float(module)
        diff_pct = abs(od - expected_od) / expected_od * 100 if expected_od else 0
        passed = diff_pct <= 8
        results.append(_rule("G6", 1, "WARN",
            passed,
            f"OD ({od}) vs expected ({expected_od:.2f}) diff={diff_pct:.1f}% (limit 8%)" if not passed else
            f"OK G6: OD ≈ (teeth+2)×module within 8%"
        ))
    else:
        results.append(_rule("G6", 1, "WARN", True, "G6 skipped: module, teeth, or OD missing"))

    # G7: hub_dia > bore (basic sanity)
    if hub_dia and bore:
        passed = hub_dia > bore
        results.append(_rule("G7", 1, "ERROR",
            passed,
            f"hub_dia ({hub_dia}) must be > bore ({bore})" if not passed else
            f"OK G7: hub_dia {hub_dia} > bore {bore}"
        ))
    else:
        results.append(_rule("G7", 1, "WARN", True, "G7 skipped: hub_dia or bore missing"))

    # G8: spline minor < spline major
    spline_major = _get_table_cell(extracted_data, "tbl_spline_data", "MAJOR DIAMETER")
    spline_minor = _get_table_cell(extracted_data, "tbl_spline_data", "MINOR DIAMETER")
    if spline_major and spline_minor:
        passed = float(spline_minor) < float(spline_major)
        results.append(_rule("G8", 1, "WARN",
            passed,
            f"Spline minor ({spline_minor}) must be < major ({spline_major})" if not passed else
            f"OK G8: spline minor {spline_minor} < major {spline_major}"
        ))
    else:
        results.append(_rule("G8", 1, "INFO", True, "G8 skipped: spline data absent"))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 2 — Material Science (M1–M4)
# ──────────────────────────────────────────────────────────────────────────────

MATERIAL_DENSITY_RANGES = {
    "alloy-steel": (7.7, 8.0),
    "carbon-steel": (7.7, 8.0),
    "stainless-steel": (7.9, 8.1),
    "cast-iron": (6.8, 7.4),
    "aluminium": (2.6, 2.9),
    "bronze": (8.5, 9.0),
    "brass": (8.3, 8.7),
    "nylon": (1.0, 1.2),
    "peek": (1.25, 1.40),
    "sintered-steel": (6.5, 7.0),
    "default-steel": (7.7, 8.0),
}

# Heat treatment compatibility: material key → allowed HT keywords
HT_COMPATIBILITY = {
    "alloy-steel": ["carbur", "nitrid", "induction", "temper", "quench", "case"],
    "carbon-steel": ["induction", "temper", "quench", "normaliz"],
    "stainless-steel": ["nitrid", "solution", "age"],
    "cast-iron": ["normaliz", "stress reliev"],
    "aluminium": ["age", "anneal", "temper"],
    "nylon": [],
    "peek": [],
}


def _layer2_material(extracted_data: dict, mat_info: dict) -> list:
    results = []
    mat_key = mat_info.get("matched_material", "default-steel")
    density = mat_info.get("density_g_cm3", 7.85)
    mass_kg = mat_info.get("mass_kg", 0)

    # M1: Density in valid range
    lo, hi = MATERIAL_DENSITY_RANGES.get(mat_key, (6.0, 10.0))
    passed = lo <= density <= hi
    results.append(_rule("M1", 2, "WARN",
        passed,
        f"Density {density} g/cm³ out of expected range [{lo}, {hi}] for {mat_key}" if not passed else
        f"OK M1: density {density} in range for {mat_key}"
    ))

    # M2: mass sanity > 0
    passed = mass_kg > 0
    results.append(_rule("M2", 2, "WARN",
        passed,
        f"Calculated mass {mass_kg} kg ≤ 0 — check volume" if not passed else
        f"OK M2: mass {mass_kg:.3f} kg > 0"
    ))

    # M3: Heat treatment vs material compatibility
    mat_treat = extracted_data.get("material_and_treatment", {})
    ht_text = str(mat_treat.get("heat_treatment", "")).lower()
    tb_ht = str(
        extracted_data.get("metadata", {}).get("title_block", {}).get("heat_treatment", "")
    ).lower()
    combined_ht = ht_text + " " + tb_ht

    if combined_ht.strip():
        allowed = HT_COMPATIBILITY.get(mat_key, ["carbur", "nitrid", "induction", "temper"])
        if not allowed:
            passed = False
            results.append(_rule("M3", 2, "WARN", passed,
                f"Material {mat_key} typically not heat treatable — HT specified: '{combined_ht.strip()}'"))
        else:
            matched_ht = any(kw in combined_ht for kw in allowed)
            results.append(_rule("M3", 2, "WARN", True,
                f"M3: HT compatibility OK for {mat_key}" if matched_ht else
                f"M3 INFO: HT text '{combined_ht.strip()}' not explicitly matched for {mat_key}"))
    else:
        results.append(_rule("M3", 2, "INFO", True, "M3: No heat treatment specified"))

    # M4: Weight vs drawing spec (X3/M4 — calc mass vs title_block.weight_kg)
    drawing_weight = extracted_data.get("metadata", {}).get("title_block", {}).get("weight_kg")
    if drawing_weight:
        try:
            dw = float(drawing_weight)
            diff_pct = abs(mass_kg - dw) / dw * 100 if dw else 0
            passed = diff_pct <= 25
            results.append(_rule("M4", 2, "WARN",
                passed,
                f"Calc mass {mass_kg:.2f} kg vs drawing {dw} kg — diff={diff_pct:.1f}% (limit 25%)" if not passed else
                f"OK M4: calc mass {mass_kg:.2f} kg within 25% of drawing weight {dw} kg"
            ))
        except (TypeError, ValueError):
            results.append(_rule("M4", 2, "INFO", True, "M4 skipped: weight_kg not numeric"))
    else:
        results.append(_rule("M4", 2, "INFO", True, "M4 skipped: no drawing weight_kg specified"))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 3 — Manufacturing Feasibility (MF1–MF5)
# ──────────────────────────────────────────────────────────────────────────────

def _layer3_manufacturing(extracted_data: dict) -> list:
    results = []

    module = _get_table_cell(extracted_data, "tbl_gear_data", "MODULE")
    no_teeth = _get_table_cell(extracted_data, "tbl_gear_data", "NO OF TEETH")
    helix = _get_table_cell(extracted_data, "tbl_gear_data", "HELIX ANGLE")
    pressure = _get_table_cell(extracted_data, "tbl_gear_data", "PRESSURE ANGLE")

    # MF1: Module 0.3–50 mm
    if module is not None:
        passed = 0.3 <= float(module) <= 50
        results.append(_rule("MF1", 3, "WARN",
            passed,
            f"Module {module} outside standard range 0.3–50 mm" if not passed else
            f"OK MF1: module {module} in range [0.3, 50]"
        ))
    else:
        results.append(_rule("MF1", 3, "WARN", True, "MF1 skipped: module not found"))

    # MF2: teeth ≥ 8 (undercut risk)
    if no_teeth is not None:
        passed = int(no_teeth) >= 8
        results.append(_rule("MF2", 3, "WARN",
            passed,
            f"Teeth count {int(no_teeth)} < 8 — undercut risk WARNING" if not passed else
            f"OK MF2: teeth {int(no_teeth)} ≥ 8"
        ))
    else:
        results.append(_rule("MF2", 3, "WARN", True, "MF2 skipped: no_of_teeth not found"))

    # MF3: helix angle 0–45°
    if helix is not None:
        try:
            h = float(str(helix).replace("°", "").strip())
            passed = 0.0 <= h <= 45.0
            results.append(_rule("MF3", 3, "WARN",
                passed,
                f"Helix angle {h}° outside range [0, 45]°" if not passed else
                f"OK MF3: helix angle {h}° in range"
            ))
        except ValueError:
            results.append(_rule("MF3", 3, "INFO", True, "MF3 skipped: helix angle not numeric"))
    else:
        results.append(_rule("MF3", 3, "INFO", True, "MF3: no helix angle (spur gear)"))

    # MF4: Reserved / placeholder
    results.append(_rule("MF4", 3, "INFO", True, "MF4: no additional feasibility check defined"))

    # MF5: Pressure angle must be 14.5°, 20°, or 25°
    if pressure is not None:
        try:
            pa = float(str(pressure).replace("°", "").strip())
            passed = pa in (14.5, 20.0, 25.0)
            results.append(_rule("MF5", 3, "WARN",
                passed,
                f"Pressure angle {pa}° is non-standard (must be 14.5, 20, or 25)" if not passed else
                f"OK MF5: pressure angle {pa}° is standard"
            ))
        except ValueError:
            results.append(_rule("MF5", 3, "WARN", True, "MF5 skipped: pressure angle not numeric"))
    else:
        results.append(_rule("MF5", 3, "WARN", True, "MF5 skipped: pressure angle not found"))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 4 — Data Completeness (C1–C7)
# ──────────────────────────────────────────────────────────────────────────────

def _layer4_completeness(extracted_data: dict, mat_info: dict) -> list:
    results = []

    od = _get_dim(extracted_data, "dim_outer_dia")
    fw = _get_dim(extracted_data, "dim_face_width")
    module = _get_table_cell(extracted_data, "tbl_gear_data", "MODULE")
    mat = extracted_data.get("metadata", {}).get("title_block", {}).get("material") or \
          extracted_data.get("material_and_treatment", {}).get("base_material")

    # C1: outer_dia present (ERROR)
    passed = od is not None
    results.append(_rule("C1", 4, "ERROR",
        passed,
        "dim_outer_dia missing — required for volume and validation" if not passed else
        f"OK C1: dim_outer_dia = {od}"
    ))

    # C2: face_width present (ERROR)
    passed = fw is not None
    results.append(_rule("C2", 4, "ERROR",
        passed,
        "dim_face_width missing — required for volume" if not passed else
        f"OK C2: dim_face_width = {fw}"
    ))

    # C3: material identified (WARN)
    passed = mat_info.get("matched_material", "default-steel") != "default-steel"
    results.append(_rule("C3", 4, "WARN",
        passed,
        f"Material not matched — using default-steel fallback (material text: '{mat}')" if not passed else
        f"OK C3: material matched → {mat_info['matched_material']}"
    ))

    # C4: module in table (WARN)
    passed = module is not None
    results.append(_rule("C4", 4, "WARN",
        passed,
        "MODULE not found in tbl_gear_data — gear calculations may be inaccurate" if not passed else
        f"OK C4: module = {module}"
    ))

    # C5: no_of_teeth present
    teeth = _get_table_cell(extracted_data, "tbl_gear_data", "NO OF TEETH")
    passed = teeth is not None
    results.append(_rule("C5", 4, "WARN",
        passed,
        "NO OF TEETH missing from tbl_gear_data" if not passed else
        f"OK C5: no_of_teeth = {teeth}"
    ))

    # C6: features[] not empty
    passed = len(extracted_data.get("features", [])) > 0
    results.append(_rule("C6", 4, "WARN",
        passed,
        "features[] is empty — no geometry to process" if not passed else
        f"OK C6: {len(extracted_data.get('features', []))} feature(s) found"
    ))

    # C7: assembly_order[] present
    passed = len(extracted_data.get("assembly_order", [])) > 0
    results.append(_rule("C7", 4, "WARN",
        passed,
        "assembly_order[] missing — volume calculation used fallback dim method" if not passed else
        "OK C7: assembly_order present — CSG method used"
    ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 5 — Cross-Consistency (X1–X4)
# ──────────────────────────────────────────────────────────────────────────────

def _layer5_cross(extracted_data: dict, volume_result: dict, mat_info: dict) -> list:
    results = []

    module = _get_table_cell(extracted_data, "tbl_gear_data", "MODULE")
    no_teeth = _get_table_cell(extracted_data, "tbl_gear_data", "NO OF TEETH")
    od = _get_dim(extracted_data, "dim_outer_dia")
    fw = _get_dim(extracted_data, "dim_face_width")
    hub_h = _get_dim(extracted_data, "dim_hub_height")
    addendum = _get_table_cell(extracted_data, "tbl_gear_data", "ADDENDUM")

    # X1: pitch_dia = module × teeth (±5%)
    if module and no_teeth and od and addendum:
        calc_pd = float(module) * float(no_teeth)
        implied_pd = od - 2 * float(addendum)
        diff_pct = abs(calc_pd - implied_pd) / calc_pd * 100 if calc_pd else 0
        passed = diff_pct <= 5
        results.append(_rule("X1", 5, "WARN",
            passed,
            f"X1: pitch_dia mismatch: module×teeth={calc_pd:.2f} vs OD-2×addendum={implied_pd:.2f} ({diff_pct:.1f}% > 5%)" if not passed else
            f"OK X1: pitch_dia cross-check ±{diff_pct:.1f}%"
        ))
    else:
        results.append(_rule("X1", 5, "INFO", True, "X1 skipped: insufficient data"))

    # X2: hub_height ≥ face_width
    if hub_h is not None and fw is not None:
        passed = hub_h >= fw
        results.append(_rule("X2", 5, "WARN",
            passed,
            f"X2: hub_height ({hub_h}) < face_width ({fw})" if not passed else
            f"OK X2: hub_height {hub_h} ≥ face_width {fw}"
        ))
    else:
        results.append(_rule("X2", 5, "INFO", True, "X2 skipped: hub_height or face_width missing"))

    # X3: calc mass vs drawing weight < 25%
    drawing_weight = extracted_data.get("metadata", {}).get("title_block", {}).get("weight_kg")
    mass_kg = mat_info.get("mass_kg", 0)
    if drawing_weight:
        try:
            dw = float(drawing_weight)
            diff_pct = abs(mass_kg - dw) / dw * 100 if dw else 0
            passed = diff_pct <= 25
            results.append(_rule("X3", 5, "WARN",
                passed,
                f"X3: Mass mismatch: calc {mass_kg:.2f} kg vs drawing {dw} kg ({diff_pct:.1f}%)" if not passed else
                f"OK X3: mass within 25% of drawing weight"
            ))
        except (TypeError, ValueError):
            results.append(_rule("X3", 5, "INFO", True, "X3 skipped: weight_kg not numeric"))
    else:
        results.append(_rule("X3", 5, "INFO", True, "X3 skipped: no drawing weight_kg"))

    # X4: CSG volume method used (not fallback)
    method = volume_result.get("method", "")
    passed = method == "csg_assembly_order"
    results.append(_rule("X4", 5, "INFO",
        passed,
        f"Volume method: '{method}' (fallback used — confidence penalty applies)" if not passed else
        "OK X4: CSG assembly_order method used"
    ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Layer 6 — Cost Plausibility (CP1–CP6)
# ──────────────────────────────────────────────────────────────────────────────

def _layer6_cost(cost_result: dict, mat_info: dict) -> list:
    results = []

    cb = cost_result.get("cost_breakdown", {})
    ops_detail = cost_result.get("operations_detail", [])

    total = cb.get("total_cost", 0)
    mat_cost = cb.get("material_cost", 0)
    overhead_pct = cb.get("overhead_pct", 15)
    mass_kg = mat_info.get("mass_kg", 0)

    # CP1: total > 0
    passed = total > 0
    results.append(_rule("CP1", 6, "WARN",
        passed,
        f"Total cost {total} ≤ 0 — pipeline error" if not passed else
        f"OK CP1: total cost = ${total}"
    ))

    # CP2: material% 10–75% of total
    if total > 0:
        mat_pct = (mat_cost / total) * 100
        passed = 10 <= mat_pct <= 75
        results.append(_rule("CP2", 6, "WARN",
            passed,
            f"Material% = {mat_pct:.1f}% of total (expected 10–75%)" if not passed else
            f"OK CP2: material% = {mat_pct:.1f}%"
        ))
    else:
        results.append(_rule("CP2", 6, "INFO", True, "CP2 skipped: total = 0"))

    # CP3: all op rates 15–800 $/hr
    bad_ops = [op for op in ops_detail if not (15 <= op.get("rate_per_hour", 0) <= 800)]
    passed = len(bad_ops) == 0
    results.append(_rule("CP3", 6, "WARN",
        passed,
        f"Ops with out-of-range rate: {[o['operation'] for o in bad_ops]}" if not passed else
        "OK CP3: all op rates in range [15, 800] $/hr"
    ))

    # CP4: total/kg 1–5000 $/kg
    if mass_kg > 0:
        cost_per_kg = total / mass_kg
        passed = 1 <= cost_per_kg <= 5000
        results.append(_rule("CP4", 6, "WARN",
            passed,
            f"Cost/kg = ${cost_per_kg:.2f}/kg — out of expected range [1, 5000]" if not passed else
            f"OK CP4: cost/kg = ${cost_per_kg:.2f}/kg"
        ))
    else:
        results.append(_rule("CP4", 6, "WARN", False, "CP4: mass_kg = 0 — cannot check cost/kg"))

    # CP5: overhead% in 5–50%
    passed = 5 <= overhead_pct <= 50
    results.append(_rule("CP5", 6, "WARN",
        passed,
        f"Overhead {overhead_pct}% out of expected range [5, 50]%" if not passed else
        f"OK CP5: overhead {overhead_pct}% in range"
    ))

    # CP6: at least 1 operation
    passed = len(ops_detail) > 0
    results.append(_rule("CP6", 6, "WARN",
        passed,
        "No operations generated — cost may be incomplete" if not passed else
        f"OK CP6: {len(ops_detail)} operations in cost"
    ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Confidence Score
# ──────────────────────────────────────────────────────────────────────────────

def _compute_confidence(
    all_rules: list,
    extracted_data: dict,
    volume_result: dict,
    mat_info: dict,
) -> int:
    score = 100

    for r in all_rules:
        if not r["passed"]:
            if r["severity"] == "ERROR":
                score -= 20
            elif r["severity"] == "WARN":
                score -= 5

    # Additional confidence penalties
    od = _get_dim(extracted_data, "dim_outer_dia")
    fw = _get_dim(extracted_data, "dim_face_width")
    mat_key = mat_info.get("matched_material", "default-steel")
    drawing_weight = extracted_data.get("metadata", {}).get("title_block", {}).get("weight_kg")
    mass_kg = mat_info.get("mass_kg", 0)
    method = volume_result.get("method", "")

    if od is None:
        score -= 15
    if fw is None:
        score -= 10
    if mat_key == "default-steel":
        score -= 10
    if method != "csg_assembly_order":
        score -= 10
    if drawing_weight:
        try:
            dw = float(drawing_weight)
            diff_pct = abs(mass_kg - dw) / dw * 100 if dw else 0
            if diff_pct > 25:
                score -= 8
        except (TypeError, ValueError):
            pass

    return max(0, score)


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def validate_all(
    extracted_data: dict,
    volume_result: dict,
    cost_result: dict,
) -> dict:
    """
    Step 6 — Run all 30 validation rules across 6 layers.

    Returns:
    {
        validation_passed: bool,
        confidence_score: int,
        confidence_level: "HIGH" | "MEDIUM" | "LOW",
        ready_for_quote: bool,
        error_count: int,
        warn_count: int,
        rules: list[dict],
    }
    """
    mat_info = cost_result.get("material_info", {})

    layer1 = _layer1_geometric(extracted_data)
    layer2 = _layer2_material(extracted_data, mat_info)
    layer3 = _layer3_manufacturing(extracted_data)
    layer4 = _layer4_completeness(extracted_data, mat_info)
    layer5 = _layer5_cross(extracted_data, volume_result, mat_info)
    layer6 = _layer6_cost(cost_result, mat_info)

    all_rules = layer1 + layer2 + layer3 + layer4 + layer5 + layer6

    error_count = sum(1 for r in all_rules if not r["passed"] and r["severity"] == "ERROR")
    warn_count = sum(1 for r in all_rules if not r["passed"] and r["severity"] == "WARN")

    validation_passed = error_count == 0

    score = _compute_confidence(all_rules, extracted_data, volume_result, mat_info)

    if score >= 85:
        confidence_level = "HIGH"
        ready_for_quote = True
    elif score >= 65:
        confidence_level = "MEDIUM"
        ready_for_quote = True
    else:
        confidence_level = "LOW"
        ready_for_quote = False

    return {
        "validation_passed": validation_passed,
        "confidence_score": score,
        "confidence_level": confidence_level,
        "ready_for_quote": ready_for_quote,
        "error_count": error_count,
        "warn_count": warn_count,
        "rules": all_rules,
    }