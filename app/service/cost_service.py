# """
# cost_service.py
# Steps 3, 4 & 5 — Material Cost, Operations Cost, Full Cost Breakdown
# Location: app/service/cost_service.py

# Public API:
#     match_material(text)                                                  → dict
#     compute_material_cost(extracted_data, net_volume_cm3)                 → dict
#     build_operations_with_costs(extracted_data, gear_family, gear_rule_ops) → list
#     compute_full_cost(extracted_data, ...)                                → dict
# """

# from .materials import MATERIAL_PROPERTIES
# from .gear_rule import OPERATIONS_TEMPLATES
# from .volume_calculation_service import FEATURE_PROCESS_MAP


# # ──────────────────────────────────────────────────────────────────────────────
# # Step 3 — Material Matching & Cost
# # ──────────────────────────────────────────────────────────────────────────────

# def match_material(text: str) -> dict:
#     """
#     Fuzzy-match material text → MATERIAL_PROPERTIES entry.
#     Lookup order: all keys in order → default-steel (fallback).
#     Returns: {matched_key, density, rate, matched_pattern}
#     """
#     if not text:
#         return _default_material()

#     text_lower = str(text).lower().strip()

#     for mat_key, props in MATERIAL_PROPERTIES.items():
#         if mat_key == "default-steel":
#             continue  # reserved as fallback
#         for pattern in props.get("patterns", []):
#             if pattern in text_lower:
#                 return {
#                     "matched_key":     mat_key,
#                     "density":         props["density"],
#                     "rate":            props["rate"],
#                     "matched_pattern": pattern,
#                 }

#     return _default_material()


# def _default_material() -> dict:
#     props = MATERIAL_PROPERTIES["default-steel"]
#     return {
#         "matched_key":     "default-steel",
#         "density":         props["density"],
#         "rate":            props["rate"],
#         "matched_pattern": None,
#     }


# def compute_material_cost(extracted_data: dict, net_volume_cm3: float) -> dict:
#     """
#     Step 3 — Material Cost.

#     Material text lookup order:
#       1. metadata.title_block.material
#       2. material_and_treatment.base_material
#       3. Fallback → default-steel

#     Returns:
#     {
#         matched_material, matched_pattern, density_g_cm3, rate_per_kg,
#         net_volume_cm3, mass_kg, cost, currency, source
#     }
#     """
#     tb_material  = (extracted_data.get("metadata", {})
#                                   .get("title_block", {})
#                                   .get("material"))
#     mat_treat    = extracted_data.get("material_and_treatment", {})
#     base_material = mat_treat.get("base_material")

#     mat_text = tb_material or base_material or ""
#     source   = (
#         "title_block.material"              if tb_material  else
#         "material_and_treatment.base_material" if base_material else
#         "fallback-default-steel"
#     )

#     mat_info = match_material(mat_text)

#     mass_kg = net_volume_cm3 * mat_info["density"] / 1000.0
#     cost    = mass_kg * mat_info["rate"]

#     return {
#         "matched_material":  mat_info["matched_key"],
#         "matched_pattern":   mat_info["matched_pattern"],
#         "density_g_cm3":     mat_info["density"],
#         "rate_per_kg":       mat_info["rate"],
#         "net_volume_cm3":    round(net_volume_cm3, 4),
#         "mass_kg":           round(mass_kg, 4),
#         "cost":              round(cost, 2),
#         "currency":          "USD",
#         "source":            source,
#     }


# # ──────────────────────────────────────────────────────────────────────────────
# # Step 4 — Operations Cost
# # ──────────────────────────────────────────────────────────────────────────────

# def _op_cost(estimated_time_min: float, rate_per_hour: float) -> float:
#     """Per-op cost formula: (time_min / 60) × rate_per_hr"""
#     return (estimated_time_min / 60.0) * rate_per_hour


# def _get_template(gear_family: str, op_name: str) -> dict:
#     """Look up operation template dict. Falls back to spur family, then bare defaults."""
#     for tmpl in OPERATIONS_TEMPLATES.get(gear_family, []):
#         if tmpl["operation"].lower() == op_name.lower():
#             return tmpl
#     for tmpl in OPERATIONS_TEMPLATES.get("spur", []):
#         if tmpl["operation"].lower() == op_name.lower():
#             return tmpl
#     return {
#         "operation":          op_name,
#         "description":        "",
#         "estimated_time_min": 15,
#         "rate_per_hour":      60,
#         "machine_options":    [],
#     }


# def _feature_ops(extracted_data: dict) -> list:
#     """
#     Source B — infer operations from features[].
#     Returns list of operation name strings (de-duped by caller).
#     """
#     ops = []
#     for feat in extracted_data.get("features", []):
#         feat_type = feat.get("type", "").lower()
#         role      = feat.get("role", "").lower()

#         key = (feat_type, role)
#         if key in FEATURE_PROCESS_MAP:
#             ops.extend(FEATURE_PROCESS_MAP[key])
#         else:
#             key_wild = (feat_type, "*")
#             if key_wild in FEATURE_PROCESS_MAP:
#                 ops.extend(FEATURE_PROCESS_MAP[key_wild])

#         # H7/H8 bore fit → Internal Grinding
#         if feat_type == "cylindrical_bore":
#             fit = feat.get("fit", "")
#             if fit and ("H7" in fit.upper() or "H8" in fit.upper()):
#                 ops.append("Internal Grinding")

#     # Also check bore dim tolerance
#     for dim in extracted_data.get("dimensions", []):
#         if dim.get("id") == "dim_bore":
#             tol = str(dim.get("tolerance", "")).upper()
#             if "H7" in tol or "H8" in tol:
#                 ops.append("Internal Grinding")

#     return ops


# def build_operations_with_costs(
#     extracted_data: dict,
#     gear_family: str,
#     gear_rule_ops: list,
# ) -> list:
#     """
#     Step 4 — Build merged operations list with per-op costs.

#     Merges:
#       Source A — gear_rule_ops  (context-aware, WHY — higher priority)
#       Source B — feature_map ops (geometry-driven, HOW)

#     Duplicates removed by operation name (first occurrence wins).

#     Returns:
#     [
#       {
#         step, operation, description,
#         estimated_time_min, rate_per_hour, cost,
#         machine_options, source
#       },
#       ...
#     ]
#     """
#     seen    = {}   # op_name → source label
#     ordered = []   # (op_name, source)

#     # Source A — gear_rule (higher priority)
#     for op_name in gear_rule_ops:
#         if op_name not in seen:
#             seen[op_name] = "gear_rule"
#             ordered.append((op_name, "gear_rule"))

#     # Source B — feature map
#     for op_name in _feature_ops(extracted_data):
#         if op_name not in seen:
#             seen[op_name] = "feature_map"
#             ordered.append((op_name, "feature_map"))

#     result = []
#     for step_no, (op_name, source) in enumerate(ordered, start=1):
#         tmpl = _get_template(gear_family, op_name)
#         cost = _op_cost(tmpl["estimated_time_min"], tmpl["rate_per_hour"])
#         result.append({
#             "step":               step_no,
#             "operation":          op_name,
#             "description":        tmpl.get("description", ""),
#             "estimated_time_min": tmpl["estimated_time_min"],
#             "rate_per_hour":      tmpl["rate_per_hour"],
#             "cost":               round(cost, 2),
#             "machine_options":    tmpl.get("machine_options", []),
#             "source":             source,
#         })

#     return result


# # ──────────────────────────────────────────────────────────────────────────────
# # Step 5 — Full Cost Breakdown
# # ──────────────────────────────────────────────────────────────────────────────

# def compute_full_cost(
#     extracted_data: dict,
#     net_volume_cm3: float,
#     gear_family: str,
#     gear_rule_ops: list,
#     overhead_pct: float = 15.0,
#     margin_pct: float   = 20.0,
#     currency: str       = "USD",
# ) -> dict:
#     """
#     Orchestrates Steps 3 + 4 + 5 and returns the full cost result dict.

#     Returns:
#     {
#         material_info:    {...},
#         operations_detail: [...],
#         cost_breakdown:   {
#             material_cost, operations_cost,
#             overhead_pct, overhead_cost,
#             subtotal, margin_pct, margin_cost,
#             total_cost, currency
#         }
#     }
#     """
#     # Step 3 — material
#     mat_info      = compute_material_cost(extracted_data, net_volume_cm3)
#     material_cost = mat_info["cost"]

#     # Step 4 — operations
#     ops_detail      = build_operations_with_costs(extracted_data, gear_family, gear_rule_ops)
#     operations_cost = sum(op["cost"] for op in ops_detail)

#     # Step 5 — breakdown
#     overhead = (material_cost + operations_cost) * overhead_pct / 100.0
#     subtotal = material_cost + operations_cost + overhead
#     margin   = subtotal * margin_pct / 100.0
#     total    = subtotal + margin

#     cost_breakdown = {
#         "material_cost":   round(material_cost, 2),
#         "operations_cost": round(operations_cost, 2),
#         "overhead_pct":    overhead_pct,
#         "overhead_cost":   round(overhead, 2),
#         "subtotal":        round(subtotal, 2),
#         "margin_pct":      margin_pct,
#         "margin_cost":     round(margin, 2),
#         "total_cost":      round(total, 2),
#         "currency":        currency,
#     }

#     return {
#         "material_info":    mat_info,
#         "operations_detail": ops_detail,
#         "cost_breakdown":   cost_breakdown,
#     }

"""
cost_service.py
Steps 3, 4 & 5 — Material Cost, Operations Cost, Full Cost Breakdown
Location: app/service/cost_service.py

Public API:
    match_material(text)                          → dict
    compute_material_cost(extracted_data, vol)    → dict
    build_operations_with_costs(extracted_data, gear_family, gear_rule_ops) → list
    compute_full_cost(extracted_data, ...)        → dict
"""

import sys
import os

# Works both as app.service.cost_service (uvicorn) and standalone (python cost_service.py)
try:
    from app.service.materials import MATERIAL_PROPERTIES
    from app.service.gear_rule import OPERATIONS_TEMPLATES, classify_and_plan
    from app.service.volume_calculation_service import FEATURE_PROCESS_MAP
except ImportError:
    try:
        from .materials import MATERIAL_PROPERTIES
        from .gear_rule import OPERATIONS_TEMPLATES, classify_and_plan
        from .volume_calculation_service import FEATURE_PROCESS_MAP
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from materials import MATERIAL_PROPERTIES
        from gear_rule import OPERATIONS_TEMPLATES, classify_and_plan
        from volume_calculation_service import FEATURE_PROCESS_MAP


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 — Material Matching & Cost
# ──────────────────────────────────────────────────────────────────────────────

def match_material(text: str) -> dict:
    """
    Fuzzy-match material text → MATERIAL_PROPERTIES entry.
    Lookup order: alloy-steel … → default-steel (fallback).
    Returns: {matched_key, density, rate, matched_pattern}
    """
    if not text:
        return _default_material()

    text_lower = str(text).lower().strip()

    for mat_key, props in MATERIAL_PROPERTIES.items():
        if mat_key == "default-steel":
            continue  # reserved as fallback
        for pattern in props.get("patterns", []):
            if pattern in text_lower:
                return {
                    "matched_key": mat_key,
                    "density": props["density"],
                    "rate": props["rate"],
                    "matched_pattern": pattern,
                }

    return _default_material()


def _default_material() -> dict:
    props = MATERIAL_PROPERTIES["default-steel"]
    return {
        "matched_key": "default-steel",
        "density": props["density"],
        "rate": props["rate"],
        "matched_pattern": None,
    }


def compute_material_cost(extracted_data: dict, net_volume_cm3: float) -> dict:
    """
    Step 3 — Material Cost.

    Material text lookup order:
      1. metadata.title_block.material
      2. material_and_treatment.base_material
      3. Fallback → default-steel

    Returns:
    {
        matched_material, density, rate,
        mass_kg, cost, currency,
        source (which field was used)
    }
    """
    # 1st priority
    tb_material = (
        extracted_data.get("metadata", {})
        .get("title_block", {})
        .get("material")
    )
    # 2nd priority
    mat_treat = extracted_data.get("material_and_treatment", {})
    base_material = mat_treat.get("base_material")

    mat_text = tb_material or base_material or ""
    source = "title_block.material" if tb_material else (
        "material_and_treatment.base_material" if base_material else "fallback-default-steel"
    )

    mat_info = match_material(mat_text)

    mass_kg = net_volume_cm3 * mat_info["density"] / 1000.0
    cost = mass_kg * mat_info["rate"]

    return {
        "matched_material": mat_info["matched_key"],
        "matched_pattern": mat_info["matched_pattern"],
        "density_g_cm3": mat_info["density"],
        "rate_per_kg": mat_info["rate"],
        "net_volume_cm3": round(net_volume_cm3, 4),
        "mass_kg": round(mass_kg, 4),
        "cost": round(cost, 2),
        "currency": "USD",
        "source": source,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Step 4 — Operations Cost
# ──────────────────────────────────────────────────────────────────────────────

def _op_cost(estimated_time_min: float, rate_per_hour: float) -> float:
    """Per-op cost formula: (time_min / 60) × rate_per_hr"""
    return (estimated_time_min / 60.0) * rate_per_hour


def _get_template(gear_family: str, op_name: str) -> dict:
    """Look up operation template. Falls back to spur family."""
    for tmpl in OPERATIONS_TEMPLATES.get(gear_family, []):
        if tmpl["operation"].lower() == op_name.lower():
            return tmpl
    for tmpl in OPERATIONS_TEMPLATES.get("spur", []):
        if tmpl["operation"].lower() == op_name.lower():
            return tmpl
    # Unknown op — use defaults
    return {
        "operation": op_name,
        "description": "",
        "estimated_time_min": 15,
        "rate_per_hour": 60,
        "machine_options": [],
    }


def _feature_ops(extracted_data: dict) -> list[str]:
    """
    Source B — infer operations from features[].
    Returns list of operation name strings (may have duplicates — de-duped later).
    """
    ops = []
    for feat in extracted_data.get("features", []):
        feat_type = feat.get("type", "").lower()
        role = feat.get("role", "").lower()

        # Exact role match
        key = (feat_type, role)
        if key in FEATURE_PROCESS_MAP:
            ops.extend(FEATURE_PROCESS_MAP[key])
        else:
            # Wildcard
            key_wild = (feat_type, "*")
            if key_wild in FEATURE_PROCESS_MAP:
                ops.extend(FEATURE_PROCESS_MAP[key_wild])

        # H7/H8 bore → add Internal Grinding
        if feat_type == "cylindrical_bore":
            fit = feat.get("fit", "")
            if fit and ("H7" in fit.upper() or "H8" in fit.upper()):
                ops.append("Internal Grinding")

    # Also check bore dim tolerance in dimensions[]
    for dim in extracted_data.get("dimensions", []):
        if dim.get("id") == "dim_bore":
            tol = str(dim.get("tolerance", "")).upper()
            if "H7" in tol or "H8" in tol:
                ops.append("Internal Grinding")

    return ops


def build_operations_with_costs(
    extracted_data: dict,
    gear_family: str,
    gear_rule_ops: list[str],
) -> list[dict]:
    """
    Step 4 — Build merged operations list with per-op costs.

    Merges:
      Source A — gear_rule_ops (context-aware, WHY)
      Source B — feature_map ops (geometry-driven, HOW)

    Duplicates removed by operation name (first occurrence wins).

    Returns list of dicts:
    {
        step, operation, description, estimated_time_min,
        rate_per_hour, cost, machine_options, source
    }
    """
    seen = {}  # op_name → source
    ordered = []  # (op_name, source)

    # Source A — gear_rule (higher priority)
    for op_name in gear_rule_ops:
        if op_name not in seen:
            seen[op_name] = "gear_rule"
            ordered.append((op_name, "gear_rule"))

    # Source B — feature map
    for op_name in _feature_ops(extracted_data):
        if op_name not in seen:
            seen[op_name] = "feature_map"
            ordered.append((op_name, "feature_map"))

    # Build result list
    result = []
    for step_no, (op_name, source) in enumerate(ordered, start=1):
        tmpl = _get_template(gear_family, op_name)
        cost = _op_cost(tmpl["estimated_time_min"], tmpl["rate_per_hour"])
        result.append(
            {
                "step": step_no,
                "operation": op_name,
                "description": tmpl.get("description", ""),
                "estimated_time_min": tmpl["estimated_time_min"],
                "rate_per_hour": tmpl["rate_per_hour"],
                "cost": round(cost, 2),
                "machine_options": tmpl.get("machine_options", []),
                "source": source,
            }
        )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Step 5 — Full Cost Breakdown
# ──────────────────────────────────────────────────────────────────────────────

def compute_full_cost(
    extracted_data: dict,
    net_volume_cm3: float,
    gear_family: str,
    gear_rule_ops: list[str],
    overhead_pct: float = 15.0,
    margin_pct: float = 20.0,
    currency: str = "USD",
) -> dict:
    """
    Orchestrates Steps 3+4+5 and returns the full cost result dict.

    Returns:
    {
        material_info: {...},       # from compute_material_cost
        operations_detail: [...],   # from build_operations_with_costs
        cost_breakdown: {
            material_cost, operations_cost,
            overhead_pct, overhead_cost,
            subtotal, margin_pct, margin_cost,
            total_cost, currency
        }
    }
    """
    # Step 3
    mat_info = compute_material_cost(extracted_data, net_volume_cm3)
    material_cost = mat_info["cost"]

    # Step 4
    ops_detail = build_operations_with_costs(extracted_data, gear_family, gear_rule_ops)
    operations_cost = sum(op["cost"] for op in ops_detail)

    # Step 5
    overhead = (material_cost + operations_cost) * overhead_pct / 100.0
    subtotal = material_cost + operations_cost + overhead
    margin = subtotal * margin_pct / 100.0
    total = subtotal + margin

    cost_breakdown = {
        "material_cost": round(material_cost, 2),
        "operations_cost": round(operations_cost, 2),
        "overhead_pct": overhead_pct,
        "overhead_cost": round(overhead, 2),
        "subtotal": round(subtotal, 2),
        "margin_pct": margin_pct,
        "margin_cost": round(margin, 2),
        "total_cost": round(total, 2),
        "currency": currency,
    }

    return {
        "material_info": mat_info,
        "operations_detail": ops_detail,
        "cost_breakdown": cost_breakdown,
    }