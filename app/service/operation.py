# import json

# with open(r"F:\pocSwaraj\test6.json", "r") as f:

#     data = json.load(f)
 
# extracted_data = data["extracted_data"]

# operation_machine_map = {

#     "Forging": ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"],

#     "Normalising": ["Normalising Furnace"],

#     "Isothermal Annealing": ["Isothermal Annealing Furnace"],

#     "Annealing": ["Annealing Furnace"],

#     "Carburising": ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"],

#     "Carbonitriding": ["Carbonitriding Furnace"],

#     "Tempering": ["Tempering Furnace"],

#     "Hardening & Tempering": ["Hardening & Tempering Furnace"],

#     "Induction Hardening": ["Induction Hardening M/c"],

#     "Gear Hobbing": ["Gear Hobbing CNC", "Gear Hobbing Conventional"],

#     "Gear Shaping": ["Gear Shaping Conventional"],

#     "Gear Shaving": ["Gear Shaving CNC", "Gear Shaving Conventional"],

#     "Gear Grinding": ["Gear Grinding", "CNC Grinding"],

#     "Chamfering": ["Gear Tooth Chamfering"],

#     "Grinding": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"],

#     "Broaching": ["Horizontal Broaching", "Vertical Broaching"],

#     "Drilling": ["Drilling - Pillar Type", "Drilling - Radial"],

#     "Gun Drilling": ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"],

#     "Turning": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"],

#     "Inspection": ["Magnaflux", "Manual"],

#     "Shot Blasting": ["Shot Blasting"],

#     "Shot Peening": ["Shot Peening"],

#     "Plating": ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"],

#     "Phosphating": ["Phosphating Tank"],

#     "Powder Coating": ["Powder Coating"],

#     "Primer Coating / Painting": ["Primer Coating", "Painting cum primer"],

#     "Blackodizing": ["Blackodizing Furnace"],

# }


# keywords_to_operations = {

#     "forging": "Forging",

#     "normalized": "Normalising",

#     "anneal": "Annealing",

#     "isothermal": "Isothermal Annealing",

#     "carburized": "Carburising",

#     "carbonitriding": "Carbonitriding",

#     "tempering": "Tempering",

#     "hardness": "Hardening & Tempering",

#     "induction": "Induction Hardening",

#     "gear": "Gear Hobbing",

#     "spline": "Broaching",

#     "grinding": "Gear Grinding",

#     "chamfer": "Chamfering",

#     "drill": "Drilling",

#     "blast": "Shot Blasting",

#     "peen": "Shot Peening",

#     "plate": "Plating",

#     "phosphate": "Phosphating",

#     "powder": "Powder Coating",

#     "paint": "Primer Coating / Painting",

#     "blackodizing": "Blackodizing",

#     "inspect": "Inspection",

# }

# found_operations = {}
 
# def scan_json(obj):

#     if isinstance(obj, dict):

#         for k, v in obj.items():

#             scan_json(v)

#     elif isinstance(obj, list):

#         for v in obj:

#             scan_json(v)

#     elif isinstance(obj, str):

#         lower_val = obj.lower()

#         for key, operation in keywords_to_operations.items():

#             if key in lower_val:

#                 found_operations[operation] = {

#                     "machines": operation_machine_map.get(operation, []),

#                     "reason": f"Found keyword '{key}' in JSON value: '{obj}'"

#                 }
 
# scan_json(extracted_data)

# import pprint

# pprint.pprint(found_operations)

 
"""
operation.py
Location: app/service/operation.py

Implements:
  - OPERATION_MACHINE_MAP    : all operations → available machines
  - KEYWORDS_TO_OPERATIONS   : keyword → operation name
  - OPERATION_COST_TEMPLATES : per-operation time + rate  ← ALL RATES IN INR
  - FEATURE_PROCESS_MAP      : feature type + role → operations implied
  - scan_and_find_operations()
  - get_feature_operations()
  - get_operation_cost()
  - build_operations_with_costs()

All USD rates from spec converted at USD_TO_INR = 84.
"""

from typing import Any

USD_TO_INR: float = 84.0


def _inr(usd: float) -> float:
    return round(usd * USD_TO_INR, 2)


# ─────────────────────────────────────────────────────────────────────────────
# OPERATION → MACHINE MAP
# ─────────────────────────────────────────────────────────────────────────────
OPERATION_MACHINE_MAP: dict[str, list[str]] = {
    "Forging":                   ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"],
    "Normalising":               ["Normalising Furnace"],
    "Isothermal Annealing":      ["Isothermal Annealing Furnace"],
    "Annealing":                 ["Annealing Furnace"],
    "Carburising":               ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"],
    "Carbonitriding":            ["Carbonitriding Furnace"],
    "Tempering":                 ["Tempering Furnace"],
    "Hardening & Tempering":     ["Hardening & Tempering Furnace"],
    "Induction Hardening":       ["Induction Hardening M/c"],
    "Gear Hobbing":              ["Gear Hobbing CNC", "Gear Hobbing Conventional"],
    "Helical Hobbing":           ["Gear Hobbing CNC", "Gear Hobbing Conventional"],
    "Gear Shaping":              ["Gear Shaping Conventional"],
    "Gear Shaving":              ["Gear Shaving CNC", "Gear Shaving Conventional"],
    "Gear Grinding":             ["Gear Grinding", "CNC Grinding"],
    "Grinding - Gear":           ["Gear Grinding", "CNC Grinding"],
    "Grinding - CNC":            ["Gear Grinding", "CNC Grinding"],
    "Gear Tooth Chamfering":     ["Gear Tooth Chamfering"],
    "Chamfering":                ["Gear Tooth Chamfering"],
    "Grinding":                  ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"],
    "Internal Grinding":         ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"],
    "Broaching":                 ["Horizontal Broaching", "Vertical Broaching"],
    "Drilling / Boring":         ["Drilling - Pillar Type", "Drilling - Radial"],
    "Drilling":                  ["Drilling - Pillar Type", "Drilling - Radial"],
    "Gun Drilling":              ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"],
    "Rough Turning":             ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"],
    "Finish Turning":            ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"],
    "Turning":                   ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"],
    "Final Inspection":          ["Magnaflux", "Manual"],
    "Inspection":                ["Magnaflux", "Manual"],
    "Shot Blasting":             ["Shot Blasting"],
    "Shot Peening":              ["Shot Peening"],
    "Deburring":                 ["Manual Deburring"],
    "Plating":                   ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"],
    "Phosphating":               ["Phosphating Tank"],
    "Powder Coating":            ["Powder Coating"],
    "Primer Coating / Painting": ["Primer Coating", "Painting cum primer"],
    "Blackodizing":              ["Blackodizing Furnace"],
    "Threading":                 ["CNC Turning Centre /twin chuck", "Lathe CNC"],
    "Nitriding":                 ["Nitriding Furnace"],
    "Quenching":                 ["Carburising GCF", "Carburising SQF"],
}

# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD → OPERATION  (Source A — context-aware keyword scan)
# ─────────────────────────────────────────────────────────────────────────────
KEYWORDS_TO_OPERATIONS: dict[str, str] = {
    # geometry / family
    "forging":        "Forging",
    "helical":        "Helical Hobbing",
    "gear":           "Gear Hobbing",
    "spline":         "Broaching",
    "keyway":         "Broaching",
    "chamfer":        "Gear Tooth Chamfering",
    "thread":         "Threading",
    "groove":         "Turning",
    # heat treatment
    "carburiz":       "Carburising",
    "carburis":       "Carburising",
    "carbonitriding": "Carbonitriding",
    "nitrid":         "Nitriding",
    "induction":      "Induction Hardening",
    "tempering":      "Tempering",
    "hardening":      "Hardening & Tempering",
    "quench":         "Quenching",
    "normalized":     "Normalising",
    "normalised":     "Normalising",
    "anneal":         "Annealing",
    "isothermal":     "Isothermal Annealing",
    # surface / finish
    "phosphat":       "Phosphating",
    "zinc":           "Plating",
    "plat":           "Plating",
    "blackod":        "Blackodizing",
    "blackodizing":   "Blackodizing",
    "powder coat":    "Powder Coating",
    "paint":          "Primer Coating / Painting",
    # quality / process
    "grinding":       "Gear Grinding",
    "grind":          "Gear Grinding",
    "peen":           "Shot Peening",
    "blast":          "Shot Blasting",
    "deburr":         "Deburring",
    "drill":          "Drilling / Boring",
    "inspect":        "Final Inspection",
    "cmm":            "Final Inspection",
    "din":            "Gear Grinding",   # DIN quality class → grinding confirmed
}

# ─────────────────────────────────────────────────────────────────────────────
# OPERATION COST TEMPLATES  ← ALL RATES IN INR/hr  (spec rates × 84)
# cost = (time_min / 60) × rate_INR_per_hr
# ─────────────────────────────────────────────────────────────────────────────
OPERATION_COST_TEMPLATES: dict[str, dict] = {
    "Forging":                   {"time_min": 15,  "rate": _inr(60.00)},   # ₹5040/hr
    "Gear Hobbing":              {"time_min": 25,  "rate": _inr(95.00)},   # ₹7980/hr
    "Helical Hobbing":           {"time_min": 35,  "rate": _inr(105.00)},  # ₹8820/hr
    "Gear Tooth Chamfering":     {"time_min": 8,   "rate": _inr(45.00)},   # ₹3780/hr
    "Chamfering":                {"time_min": 8,   "rate": _inr(45.00)},
    "Carburising":               {"time_min": 90,  "rate": _inr(55.00)},   # ₹4620/hr
    "Carbonitriding":            {"time_min": 90,  "rate": _inr(55.00)},
    "Quenching":                 {"time_min": 30,  "rate": _inr(55.00)},
    "Tempering":                 {"time_min": 60,  "rate": _inr(55.00)},
    "Hardening & Tempering":     {"time_min": 90,  "rate": _inr(55.00)},
    "Nitriding":                 {"time_min": 120, "rate": _inr(55.00)},
    "Induction Hardening":       {"time_min": 20,  "rate": _inr(75.00)},   # ₹6300/hr  (spec: $90 in gear_rule; $75 in op.py — using op.py)
    "Normalising":               {"time_min": 60,  "rate": _inr(45.00)},
    "Annealing":                 {"time_min": 60,  "rate": _inr(45.00)},
    "Isothermal Annealing":      {"time_min": 90,  "rate": _inr(45.00)},
    "Gear Grinding":             {"time_min": 30,  "rate": _inr(120.00)},  # ₹10080/hr
    "Grinding - Gear":           {"time_min": 30,  "rate": _inr(120.00)},
    "Grinding - CNC":            {"time_min": 30,  "rate": _inr(120.00)},
    "Internal Grinding":         {"time_min": 30,  "rate": _inr(120.00)},
    "Grinding":                  {"time_min": 25,  "rate": _inr(100.00)},  # ₹8400/hr
    "Gear Shaping":              {"time_min": 55,  "rate": _inr(110.00)},  # ₹9240/hr
    "Gear Shaving":              {"time_min": 20,  "rate": _inr(95.00)},
    "Broaching":                 {"time_min": 10,  "rate": _inr(70.00)},   # ₹5880/hr
    "Rough Turning":             {"time_min": 18,  "rate": _inr(75.00)},   # ₹6300/hr
    "Finish Turning":            {"time_min": 12,  "rate": _inr(80.00)},   # ₹6720/hr
    "Turning":                   {"time_min": 15,  "rate": _inr(75.00)},
    "Drilling / Boring":         {"time_min": 10,  "rate": _inr(70.00)},
    "Drilling":                  {"time_min": 10,  "rate": _inr(70.00)},
    "Gun Drilling":              {"time_min": 20,  "rate": _inr(85.00)},   # ₹7140/hr
    "Threading":                 {"time_min": 10,  "rate": _inr(70.00)},
    "Shot Peening":              {"time_min": 15,  "rate": _inr(50.00)},   # ₹4200/hr
    "Shot Blasting":             {"time_min": 10,  "rate": _inr(40.00)},   # ₹3360/hr
    "Deburring":                 {"time_min": 6,   "rate": _inr(40.00)},
    "Final Inspection":          {"time_min": 15,  "rate": _inr(85.00)},   # ₹7140/hr
    "Inspection":                {"time_min": 15,  "rate": _inr(85.00)},
    "Phosphating":               {"time_min": 20,  "rate": _inr(35.00)},   # ₹2940/hr
    "Plating":                   {"time_min": 30,  "rate": _inr(40.00)},
    "Blackodizing":              {"time_min": 20,  "rate": _inr(35.00)},
    "Powder Coating":            {"time_min": 25,  "rate": _inr(40.00)},
    "Primer Coating / Painting": {"time_min": 20,  "rate": _inr(35.00)},
}

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE → PROCESS MAP  (Source B — structural/geometry inference)
# key: (feature_type, role)  — use "*" as wildcard for role
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_PROCESS_MAP: dict[tuple[str, str], list[str]] = {
    ("cylindrical_rim",  "gear_tip"):     ["Gear Hobbing", "Gear Tooth Chamfering"],
    ("cylindrical_step", "hub_outer"):    ["Rough Turning", "Finish Turning"],
    ("cylindrical_bore", "through_bore"): ["Drilling / Boring"],
    ("internal_spline",  "spline_bore"):  ["Gear Shaping", "Broaching"],
    ("keyway",           "*"):            ["Broaching"],
    ("chamfer",          "*"):            ["Gear Tooth Chamfering"],
    ("thread",           "*"):            ["Threading"],
    ("groove",           "*"):            ["Turning"],
}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def scan_and_find_operations(extracted_data: dict) -> dict[str, dict]:
    """
    Source A — context-aware keyword scan across all string values in
    extracted_data. Returns:
        { "Gear Hobbing": {"machines": [...], "reason": "..."}, ... }
    """
    found: dict[str, dict] = {}

    def _scan(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                _scan(v)
        elif isinstance(obj, list):
            for v in obj:
                _scan(v)
        elif isinstance(obj, str):
            lower_val = obj.lower()
            for keyword, operation in KEYWORDS_TO_OPERATIONS.items():
                if keyword in lower_val and operation not in found:
                    found[operation] = {
                        "machines": OPERATION_MACHINE_MAP.get(operation, []),
                        "reason":   f"Keyword '{keyword}' found in: '{obj[:80]}'"
                    }

    _scan(extracted_data)
    return found


def get_feature_operations(features: list[dict]) -> dict[str, dict]:
    """
    Source B — structural inference from features[].
    Also handles H7/H8 bore fit → Internal Grinding.
    """
    found: dict[str, dict] = {}

    for feat in features:
        feat_type = feat.get("type", "").lower()
        role      = feat.get("role", "").lower()
        fit       = feat.get("fit", "")

        ops = (
            FEATURE_PROCESS_MAP.get((feat_type, role))
            or FEATURE_PROCESS_MAP.get((feat_type, "*"))
            or []
        )

        for op in ops:
            if op not in found:
                found[op] = {
                    "machines": OPERATION_MACHINE_MAP.get(op, []),
                    "reason":   f"Feature type='{feat_type}' role='{role}'"
                }

        if feat_type == "cylindrical_bore" and fit.upper() in ("H7", "H8"):
            op = "Internal Grinding"
            if op not in found:
                found[op] = {
                    "machines": OPERATION_MACHINE_MAP.get(op, []),
                    "reason":   f"Bore fit='{fit}' requires Internal Grinding"
                }

    return found


def get_operation_cost(operation_name: str) -> dict:
    """
    Returns cost dict for a single operation name.
    { "time_min": int, "rate": float [INR/hr], "cost": float [INR] }
    Falls back to time=15, rate=₹5040/hr if not in templates.
    """
    template = OPERATION_COST_TEMPLATES.get(
        operation_name, {"time_min": 15, "rate": _inr(60.00)}
    )
    time_min = template["time_min"]
    rate     = template["rate"]
    cost     = round((time_min / 60.0) * rate, 2)
    return {"time_min": time_min, "rate_per_hour": rate, "cost": cost}


def build_operations_with_costs(
    source_a_ops: dict[str, dict],   # from scan_and_find_operations()
    source_b_ops: dict[str, dict],   # from get_feature_operations()
) -> list[dict]:
    """
    Spec Step 4: Merges Source A (keyword) + Source B (feature_map).
    Source A takes priority on duplicates.
    All costs in INR.

    Returns:
    [
      {
        "step", "operation", "time_min",
        "rate_per_hour" [INR/hr], "cost" [INR],
        "machine_options", "source", "reason"
      },
      ...
    ]
    """
    merged: dict[str, dict] = {}

    for op_name, info in source_b_ops.items():
        merged[op_name] = {"source": "feature_map", **info}

    for op_name, info in source_a_ops.items():
        if op_name in merged:
            merged[op_name]["source"] = "both"
            merged[op_name]["reason"] = info["reason"]
        else:
            merged[op_name] = {"source": "keyword_scan", **info}

    result = []
    for step_num, (op_name, info) in enumerate(merged.items(), start=1):
        cost_info = get_operation_cost(op_name)
        result.append({
            "step":            step_num,
            "operation":       op_name,
            "time_min":        cost_info["time_min"],
            "rate_per_hour":   cost_info["rate_per_hour"],   # INR/hr
            "cost":            cost_info["cost"],            # INR
            "machine_options": info.get("machines", []),
            "source":          info.get("source", "unknown"),
            "reason":          info.get("reason", ""),
        })

    return result