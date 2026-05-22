"""
pipeline_service.py
Pipeline Orchestrator — calls all 6 steps in order.
Location: app/service/pipeline_service.py
"""

from .gear_rule import classify_and_plan
from .volume_calculation_service import compute_volume
from .cost_service import compute_full_cost
from .validation_service import validate_all


def run_full_pipeline(
    extracted_data: dict,
    overhead_pct: float = 15.0,
    margin_pct: float = 20.0,
    currency: str = "USD",
) -> dict:
    """
    Run the full 6-step cost estimation pipeline.

    Step 1 — Gear Classification      (gear_rule.classify_and_plan)
    Step 2 — Volume Calculation        (volume_calculation_service.compute_volume)
    Step 3 — Material Cost             (cost_service.compute_material_cost)
    Step 4 — Operations Cost           (cost_service.build_operations_with_costs)
    Step 5 — Cost Breakdown            (cost_service.compute_full_cost)
    Step 6 — Validation                (validation_service.validate_all)

    Returns the full pipeline_result dict.
    """
    # ── Step 1: Gear Classification ──────────────────────────────────────────
    classification = classify_and_plan(extracted_data)
    gear_family    = classification["gear_family"]
    gear_rule_ops  = classification["operations_sequence"]

    # ── Step 2: Volume Calculation ───────────────────────────────────────────
    volume_result  = compute_volume(extracted_data)
    net_volume_cm3 = volume_result["net_volume_cm3"]

    # ── Steps 3, 4, 5: Material + Operations + Breakdown ────────────────────
    cost_result = compute_full_cost(
        extracted_data=extracted_data,
        net_volume_cm3=net_volume_cm3,
        gear_family=gear_family,
        gear_rule_ops=gear_rule_ops,
        overhead_pct=overhead_pct,
        margin_pct=margin_pct,
        currency=currency,
    )

    # ── Step 6: Validation ───────────────────────────────────────────────────
    validation_report = validate_all(
        extracted_data=extracted_data,
        volume_result=volume_result,
        cost_result=cost_result,
    )

    # ── Assemble final result (matches /api/google/analyze-direct response) ──
    return {
        "gear_family": gear_family,
        "classification_evidence": classification["evidence"],
        "volume": {
            "net_volume_mm3": volume_result["net_volume_mm3"],
            "net_volume_cm3": volume_result["net_volume_cm3"],
            "method": volume_result["method"],
            "feature_breakdown": volume_result["feature_breakdown"],
        },
        "material_info": cost_result["material_info"],
        "operations_detail": cost_result["operations_detail"],
        "cost_breakdown": cost_result["cost_breakdown"],
        "validation_report": {
            "validation_passed": validation_report["validation_passed"],
            "confidence_score":  validation_report["confidence_score"],
            "confidence_level":  validation_report["confidence_level"],
            "ready_for_quote":   validation_report["ready_for_quote"],
            "error_count":       validation_report["error_count"],
            "warn_count":        validation_report["warn_count"],
            "rules":             validation_report["rules"],
        },
    }


# backward-compat alias (drwaingRouter previously called run_pipeline)
run_pipeline = run_full_pipeline