"""
volume_calculation_service.py
Step 2 — Volume Calculation (CSG)
Location: app/service/volume_calculation_service.py

Walks assembly_order[] using CSG → net volume in mm³ and cm³.
Entry point: compute_volume(extracted_data)
"""

import math

# ──────────────────────────────────────────────────────────────────────────────
# Feature → Process mapping  (Source B for Step 4 operations)
# Imported by cost_service via: from .volume_calculation_service import FEATURE_PROCESS_MAP
# ──────────────────────────────────────────────────────────────────────────────
FEATURE_PROCESS_MAP: dict[tuple, list] = {
    ("cylindrical_rim",  "gear_tip"):     ["Gear Hobbing", "Gear Tooth Chamfering"],
    ("cylindrical_step", "hub_outer"):    ["Rough Turning", "Finish Turning"],
    ("cylindrical_bore", "through_bore"): ["Drilling / Boring"],
    # H7/H8 fit adds Internal Grinding — checked dynamically in cost_service
    ("internal_spline",  "spline_bore"):  ["Gear Shaping", "Broaching"],
    ("keyway",           "*"):            ["Broaching"],
    ("chamfer",          "*"):            ["Gear Tooth Chamfering"],
    ("thread",           "*"):            ["Threading"],
    ("groove",           "*"):            ["Turning"],
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lookup_dim(dim_id_list: list, dims_index: dict):
    for d_id in (dim_id_list or []):
        val = dims_index.get(d_id)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _get_table_cell_value(tables: list, table_id: str, cell_label: str):
    for tbl in tables:
        if tbl.get("id", "").lower() == table_id.lower():
            for cell in tbl.get("cells", []):
                if cell.get("label", "").strip().upper() == cell_label.strip().upper():
                    try:
                        return float(cell.get("value", 0))
                    except (TypeError, ValueError):
                        return None
    return None


def _compute_feature_volume(feat: dict, dims_index: dict, tables: list) -> tuple:
    """
    Compute volume for a single feature.
    Returns (volume_mm3: float, breakdown: dict).
    """
    feat_type   = feat.get("type", "").lower()
    axial_stack = dims_index.get("dim_hub_height") or dims_index.get("dim_face_width") or 0.0

    if feat_type == "cylindrical_rim":
        od = (_lookup_dim(feat.get("outer_diameter_dim_ids") or feat.get("diameter_dim_ids", []), dims_index)
              or dims_index.get("dim_outer_dia", 0.0))
        fw = (_lookup_dim(feat.get("face_width_dim_ids", []), dims_index)
              or dims_index.get("dim_face_width", 0.0))
        volume = math.pi * (od / 2) ** 2 * fw
        return volume, {"OD_mm": od, "face_width_mm": fw, "formula": "π×(OD/2)²×face_width"}

    elif feat_type == "cylindrical_step":
        hub_dia    = (_lookup_dim(feat.get("diameter_dim_ids", []), dims_index)
                      or dims_index.get("dim_hub_dia", 0.0))
        hub_height = dims_index.get("dim_hub_height", 0.0)
        face_width = dims_index.get("dim_face_width", 0.0)
        length     = _lookup_dim(feat.get("length_dim_ids", []), dims_index)
        if length is None:
            length = max(hub_height - face_width, 0.0)
        volume = math.pi * (hub_dia / 2) ** 2 * length
        return volume, {"hub_dia_mm": hub_dia, "extension_mm": length, "formula": "π×(hub_dia/2)²×extension"}

    elif feat_type == "cylindrical_bore":
        bore_dia = (_lookup_dim(feat.get("diameter_dim_ids", []), dims_index)
                    or dims_index.get("dim_bore", 0.0))
        volume = math.pi * (bore_dia / 2) ** 2 * axial_stack
        return volume, {"bore_dia_mm": bore_dia, "axial_stack_mm": axial_stack, "formula": "π×(bore/2)²×axial_stack"}

    elif feat_type == "internal_spline":
        major_dia = (_get_table_cell_value(tables, "tbl_spline_data", "MAJOR DIAMETER")
                     or _lookup_dim(feat.get("diameter_dim_ids", []), dims_index) or 0.0)
        volume = math.pi * (major_dia / 2) ** 2 * axial_stack
        return volume, {"major_dia_mm": major_dia, "axial_stack_mm": axial_stack, "formula": "π×(major_dia/2)²×axial_stack"}

    elif feat_type == "keyway":
        w = _lookup_dim(feat.get("width_dim_ids",  []), dims_index)
        h = _lookup_dim(feat.get("depth_dim_ids",  []), dims_index)
        l = _lookup_dim(feat.get("length_dim_ids", []), dims_index)
        if w and h and l:
            return w * h * l, {"width_mm": w, "depth_mm": h, "length_mm": l, "formula": "width×depth×length"}
        return 0.0, {"note": "keyway dims incomplete — volume set to 0"}

    elif feat_type == "chamfer":
        return 0.0, {"note": "chamfer volume correction not applied (negligible)"}

    return 0.0, {"note": f"Unknown feature type '{feat_type}' — volume set to 0"}


def _get_feature_processes(feat: dict, dims_index: dict) -> list:
    feat_type = feat.get("type", "").lower()
    role      = feat.get("role", "").lower()

    processes = list(
        FEATURE_PROCESS_MAP.get((feat_type, role))
        or FEATURE_PROCESS_MAP.get((feat_type, "*"))
        or []
    )

    # H7/H8 → Internal Grinding
    if feat_type == "cylindrical_bore":
        fit = feat.get("fit", "")
        if fit and ("H7" in fit.upper() or "H8" in fit.upper()):
            if "Internal Grinding" not in processes:
                processes.append("Internal Grinding")

    return processes


# ──────────────────────────────────────────────────────────────────────────────
# CSG method (preferred)
# ──────────────────────────────────────────────────────────────────────────────

def _csg_method(extracted_data: dict) -> dict:
    dims_index    = {d["id"]: float(d.get("value", 0) or 0)
                     for d in extracted_data.get("dimensions", [])
                     if d.get("value") is not None}
    tables        = extracted_data.get("tables", [])
    features_map  = {f["id"]: f for f in extracted_data.get("features", [])}
    assembly_order = extracted_data.get("assembly_order", [])

    net_volume_mm3  = 0.0
    feature_breakdown = []

    for step in assembly_order:
        feat_id = step.get("feature_id")
        csg_op  = step.get("op", "revolve").lower()
        feat    = features_map.get(feat_id)
        if feat is None:
            continue

        vol, breakdown = _compute_feature_volume(feat, dims_index, tables)
        processes      = _get_feature_processes(feat, dims_index)

        if csg_op == "revolve":
            net_volume_mm3 += vol
            sign = "+"
        elif csg_op == "subtract":
            net_volume_mm3 -= vol
            sign = "−"
        else:
            sign = "?"

        feature_breakdown.append({
            "feature_id":       feat_id,
            "type":             feat.get("type"),
            "role":             feat.get("role"),
            "csg_op":           csg_op,
            "volume_mm3":       round(vol, 3),
            "sign":             sign,
            "breakdown":        breakdown,
            "processes_implied": processes,
        })

    return {"net_volume_mm3": net_volume_mm3, "feature_breakdown": feature_breakdown, "method": "csg_assembly_order"}


# ──────────────────────────────────────────────────────────────────────────────
# Fallback (dim-ID lookup when no assembly_order)
# ──────────────────────────────────────────────────────────────────────────────

def _fallback_dim_method(extracted_data: dict) -> dict:
    dims_index = {d["id"]: float(d.get("value", 0) or 0)
                  for d in extracted_data.get("dimensions", [])
                  if d.get("value") is not None}
    tables = extracted_data.get("tables", [])

    od      = dims_index.get("dim_outer_dia", 0.0)
    fw      = dims_index.get("dim_face_width", 0.0)
    hub_dia = dims_index.get("dim_hub_dia", 0.0)
    hub_h   = dims_index.get("dim_hub_height", fw)
    bore    = dims_index.get("dim_bore", 0.0)

    extension = max(hub_h - fw, 0.0)

    rim_vol   = math.pi * (od / 2) ** 2 * fw       if od and fw       else 0.0
    hub_vol   = math.pi * (hub_dia / 2) ** 2 * extension if hub_dia and extension else 0.0
    bore_vol  = math.pi * (bore / 2) ** 2 * hub_h  if bore and hub_h  else 0.0

    major_dia = _get_table_cell_value(tables, "tbl_spline_data", "MAJOR DIAMETER")
    spline_vol = math.pi * (major_dia / 2) ** 2 * hub_h if major_dia and hub_h else 0.0

    net = rim_vol + hub_vol - bore_vol - spline_vol

    breakdown = [
        {"feature": "rim",          "csg_op": "revolve",  "volume_mm3": round(rim_vol,  3)},
        {"feature": "hub_extension","csg_op": "revolve",  "volume_mm3": round(hub_vol,  3)},
        {"feature": "bore",         "csg_op": "subtract", "volume_mm3": round(bore_vol, 3)},
    ]
    if spline_vol:
        breakdown.append({"feature": "spline", "csg_op": "subtract", "volume_mm3": round(spline_vol, 3)})

    return {"net_volume_mm3": net, "feature_breakdown": breakdown, "method": "dim_id_fallback"}


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def compute_volume(extracted_data: dict) -> dict:
    """
    Step 2 public entry point.
    Uses CSG when assembly_order[] is present, otherwise fallback.

    Returns:
    {
        net_volume_mm3: float,
        net_volume_cm3: float,
        method: str,
        feature_breakdown: list,
    }
    """
    result  = _csg_method(extracted_data) if extracted_data.get("assembly_order") else _fallback_dim_method(extracted_data)
    raw_mm3 = result["net_volume_mm3"]

    # 1 cm³ floor (= 1000 mm³)
    net_cm3 = max(raw_mm3, 1000.0) / 1000.0

    return {
        "net_volume_mm3":   round(raw_mm3, 3),
        "net_volume_cm3":   round(net_cm3, 4),
        "method":           result["method"],
        "feature_breakdown": result["feature_breakdown"],
    }