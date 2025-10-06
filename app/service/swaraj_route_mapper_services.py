from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import math
import re
from app.utils.swaraj_route_mapper_utils import MACHINES, OPS

def _lower(s: Optional[str]) -> str:
    """Safe lowercase conversion."""
    return (s or "").lower()

def has_external_gears(d: Dict[str, Any]) -> bool:
    """Detect presence of external gear features in extracted JSON."""
    tokens = str(d).lower()
    return any(k in tokens for k in [
        "external_gear_teeth", "gear teeth", "gear_data", "module", "pitch circle diameter", "pcd"
    ])

def gear_teeth_count(d: Dict[str, Any]) -> Optional[int]:
    """Attempt to extract gear tooth count from feature dimensions or tables."""
    for key in ("feature_dimensions", "tables_and_data", "geometric_decomposition"):
        if key in d:
            tokens = str(d[key]).lower()
            m = re.search(r"(no\.?\s*of\s*teeth|number_of_teeth)\"?\D+(\d+)", tokens)
            if m:
                try:
                    return int(m.group(2))
                except ValueError:
                    pass
    return None

def gear_module(d: Dict[str, Any]) -> Optional[float]:
    """Extract gear module if mentioned in JSON."""
    tokens = str(d).lower()
    m = re.search(r"(module)\"?\D+([0-9]+(\.[0-9]+)?)", tokens)
    if m:
        try:
            return float(m.group(2))
        except ValueError:
            return None
    return None

def has_internal_spline(d: Dict[str, Any]) -> bool:
    """Detect internal spline features (e.g., DIN 5480)."""
    tokens = str(d).lower()
    return "spline" in tokens or "din 5480" in tokens

def bore_diameter_mm(d: Dict[str, Any]) -> Optional[float]:
    """Detect bore diameter in mm from common drawing keywords."""
    tokens = str(d)
    m = re.search(r"(?i)(bore[^0-9]*|main_diameter[^0-9]*|diameter[^0-9]*)\b([0-9]{2,3}(\.[0-9]+)?)\s*mm", tokens)
    if m:
        return float(m.group(2))
    return None

def od_mm(d: Dict[str, Any]) -> Optional[float]:
    """Detect outer diameter (OD) from JSON."""
    tokens = str(d)
    m = re.search(r"(?i)(outer diameter|tip_diameter|diameter\"\s*:\s*\"?)(\d{2,4}(\.\d+)?)\s*mm", tokens)
    if m:
        try:
            return float(m.group(2))
        except ValueError:
            return None
    # Fallback for structured JSON keys
    try:
        val = d.get("overall_dimensions", {}).get("diameter", {}).get("value")
        unit = d.get("overall_dimensions", {}).get("diameter", {}).get("unit")
        if val is not None and (unit or "").lower().startswith("mm"):
            return float(val)
    except Exception:
        pass
    return None

def material_string(d: Dict[str, Any]) -> str:
    """Identify material string from JSON."""
    tokens = str(d).lower()
    if "20mncr5" in tokens:
        return "20MnCr5"
    return ""

def needs_case_hardening(d: Dict[str, Any]) -> bool:
    """Detect if part requires case hardening."""
    mat = material_string(d)
    return mat == "20MnCr5"

def has_chamfers_or_edge_relief(d: Dict[str, Any]) -> bool:
    """Detect chamfers or edge relief."""
    return "chamfer" in str(d).lower()

def has_heat_treat_table(d: Dict[str, Any]) -> bool:
    """Detect heat treatment instructions."""
    text = str(d).lower()
    return any(x in text for x in ["hardness", "hrc", "carbur", "carbon nitrid", "induction harden"])

def has_grinding_callouts(d: Dict[str, Any]) -> bool:
    """Detect grinding operations required."""
    return "grind" in str(d).lower()

def has_bevel_gear(d: Dict[str, Any]) -> bool:
    """Detect bevel gear features."""
    text = str(d).lower()
    return "bevel" in text

def has_gun_drill(d: Dict[str, Any]) -> bool:
    """Detect deep hole / gun drilling requirement."""
    text = str(d).lower()
    return "gun drill" in text or "deep hole" in text

# -------------------------------
# 3) Rulebook construction
# -------------------------------

def build_rulebook() -> List[Dict[str, Any]]:
    """
    Build the list of routing rules.
    Each rule specifies a condition, operations to add, suggested machines, confidence, and reason.
    """
    return [
        dict(
            name="stock_prep",
            if_any=["*"],
            add=[(OPS["SAWING"], [MACHINES["SAW_BAND"], MACHINES["SAW_HACK"]], 0.85, "Cut raw stock to length")],
        ),
        dict(
            name="forging_blank",
            if_fn=lambda d: has_external_gears(d) and (od_mm(d) or 0) >= 80,
            add=[(OPS["FORGING"], [MACHINES["FORGING_SYMMETRICAL"]], 0.75, "Gear OD + teeth → forged blank likely")],
        ),
        dict(
            name="rough_turn",
            if_fn=lambda d: True,
            add=[
                (OPS["FACING_CENTERING"], [MACHINES["LATHE_CENTRE"]], 0.8, "Create datums (faces/centers)"),
                (OPS["ROUGH_TURN"], [MACHINES["LATHE_HEAVY"], MACHINES["LATHE_CNC"]], 0.85, "Rough to near-net OD/ID"),
            ],
        ),
        dict(
            name="bore_ops",
            if_fn=lambda d: bore_diameter_mm(d) is not None,
            add=[
                (OPS["DRILL_TAP_REAM"], [MACHINES["DRILL_PILLAR"], MACHINES["DRILL_RADIAL"]], 0.8, "Through/step bores from drawing"),
            ] + ([(OPS["GUN_DRILL"], [MACHINES["GUN_DRILL_CONV"], MACHINES["GUN_DRILL_SPM"]], 0.6, "Deep hole/gun drilling hint")]
                 if has_gun_drill else []),
        ),
        dict(
            name="internal_spline",
            if_fn=lambda d: has_internal_spline(d),
            add=[(OPS["BROACH"], [MACHINES["BROACH_VERT"], MACHINES["BROACH_HORZ"]], 0.9, "DIN 5480 / internal spline")],
        ),
        dict(
            name="gear_cutting",
            if_fn=lambda d: has_external_gears(d),
            add=[
                (OPS["GEAR_HOB"], [MACHINES["HOB_CNC"], MACHINES["HOB_CONV"]], 0.9, "External gear cutting (hob)"),
                (OPS["GEAR_SHAPE"], [MACHINES["SHAPER_CONV"], MACHINES["CNC_SHAPER"]], 0.5, "Fallback where hobbing not feasible"),
                (OPS["GEAR_TOOTH_CHAMFER"], [MACHINES["GEAR_TOOTH_CHAMFER"]], 0.8, "Tooth entry relief/chamfer"),
            ],
        ),
        dict(
            name="gear_finishing",
            if_fn=lambda d: has_external_gears(d),
            add=[
                (OPS["GEAR_SHAVE"], [MACHINES["SHAVE_CNC"], MACHINES["SHAVE_CONV"]], 0.7, "Improve flank surface & noise"),
            ] + ([(OPS["GEAR_GRIND"], [MACHINES["GEAR_GRINDING"]], 0.8, "Tight involute/runout tolerances → grinding")]
                 if has_grinding_callouts else []),
        ),
        dict(
            name="heat_treat_case_harden",
            if_fn=lambda d: needs_case_hardening(d) or has_heat_treat_table(d),
            add=[
                (OPS["CARBURIZE"], [MACHINES["CARB_GCF"], MACHINES["CARB_SQF"], MACHINES["CARB_SALT"]], 0.9, "Case harden (20MnCr5)"),
                (OPS["HARDEN_TEMPER"], [MACHINES["HARD_TEMPER_FURNACE"], MACHINES["TEMPERING_FURNACE"]], 0.9, "Harden+temper to spec"),
                (OPS["SHOT_BLAST"], [MACHINES["SHOT_BLAST"]], 0.6, "Descale after HT"),
                (OPS["SHOT_PEEN"], [MACHINES["SHOT_PEEN"]], 0.5, "Optional compressive stress on teeth"),
            ],
        ),
        dict(
            name="post_ht_grind",
            if_fn=lambda d: has_grinding_callouts(d) or "runout" in str(d).lower(),
            add=[
                (OPS["GRIND"], [MACHINES["GRIND_CYL"], MACHINES["GRIND_SURF"], MACHINES["GRIND_CENTERLESS"]], 0.75, "Tight runout/size after HT"),
            ],
        ),
        dict(
            name="surface_treat",
            if_fn=lambda d: True,
            add=[
                (OPS["DEBURR"], [MACHINES["DEBURR_MACHINE"]], 0.85, "Remove burrs edges & teeth"),
                (OPS["PHOSPHATE"], [MACHINES["PHOS_TANK"]], 0.4, "Phosphating (if corrosion/oil-retention)"),
                (OPS["BLACKODIZE"], [MACHINES["BLACKDIZING_FURNACE"]], 0.3, "Blackodizing if specified"),
            ],
        ),
        dict(
            name="inspection",
            if_fn=lambda d: True,
            add=[
                (OPS["MAGNAFLUX"], [MACHINES["MAGNAFLUX"]], 0.5, "Crack detection (critical parts)"),
                (OPS["INSPECTION"], [], 1.0, "Dimensional & functional inspection"),
            ],
        ),
    ]

# -------------------------------
# 4) Routing logic
# -------------------------------

def map_operations(part_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a part JSON to a sequence of operations and suggested machines.
    
    Returns:
        dict: {
            "route_operations": List of operations with confidence & reasons,
            "sequence": Ordered operation names,
            "machine_pool": Unique machine list across operations,
            "notes": Part summary (material, OD, module, teeth, internal spline)
        }
    """
    rules = build_rulebook()
    planned: List[Dict[str, Any]] = []

    # Evaluate each rule
    for rule in rules:
        cond_ok = False
        if "if_any" in rule:
            cond_ok = True  # unconditional
        elif "if_fn" in rule and callable(rule["if_fn"]):
            try:
                cond_ok = bool(rule["if_fn"](part_json))
            except Exception:
                cond_ok = False

        if not cond_ok:
            continue

        for (op, machines, conf, reason) in rule["add"]:
            planned.append({
                "operation": op,
                "suggested_machines": machines,
                "confidence": round(float(conf), 2),
                "reason": reason,
            })

    # Heuristic ordering
    order = [
        OPS["SAWING"], OPS["FORGING"], OPS["FACING_CENTERING"], OPS["ROUGH_TURN"],
        OPS["DRILL_TAP_REAM"], OPS["GUN_DRILL"], OPS["BROACH"],
        OPS["GEAR_HOB"], OPS["GEAR_SHAPE"], OPS["GEAR_TOOTH_CHAMFER"],
        OPS["GEAR_SHAVE"], OPS["GEAR_GRIND"],
        OPS["CARBURIZE"], OPS["HARDEN_TEMPER"], OPS["INDUCTION_HARDEN"], OPS["TEMPER"],
        OPS["SHOT_BLAST"], OPS["SHOT_PEEN"],
        OPS["GRIND"], OPS["FINISH_TURN"],
        OPS["DEBURR"], OPS["PHOSPHATE"], OPS["BLACKODIZE"], OPS["POWDER_COAT"], OPS["PRIMER_COAT"], OPS["PRIMER_PAINT"], OPS["WASH_RPO"],
        OPS["MAGNAFLUX"], OPS["INSPECTION"],
    ]
    order_index = {name: i for i, name in enumerate(order)}
    planned.sort(key=lambda x: order_index.get(x["operation"], 999))

    # Flatten machine list
    ops_seq = [p["operation"] for p in planned]
    machines_flat = []
    for p in planned:
        for m in p["suggested_machines"]:
            if m not in machines_flat:
                machines_flat.append(m)

    return {
        "route_operations": planned,
        "sequence": ops_seq,
        "machine_pool": machines_flat,
        "notes": {
            "material": material_string(part_json) or "unspecified",
            "od_mm": od_mm(part_json),
            "module": gear_module(part_json),
            "teeth": gear_teeth_count(part_json),
            "has_internal_spline": has_internal_spline(part_json),
        }
    }