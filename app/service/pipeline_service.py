"""
pipeline_service.py
Pipeline Orchestrator — calls all 6 steps in order.
Location: app/service/pipeline_service.py

Fixes vs original:
  - compute_volue() typo → VolumeCalculationService().calculate_from_extracted_data()
  - volume_result["net_volume_cm3"] → volume_result["volume_summary"]["total_volume_cm3"]
  - Added graceful fallback when volume calculation fails
  - All costs now in INR (propagated from cost_service + materials)
"""

from .gear_rule                import classify_and_plan
from .VolumeCalculationService import VolumeCalculationService
from .cost_service             import compute_full_cost
from .validation_service       import validate_all

_vol_service = VolumeCalculationService()


def run_full_pipeline(
    extracted_data: dict,
    overhead_pct:   float = 15.0,
    margin_pct:     float = 20.0,
    currency:       str   = "INR",
) -> dict:
    """
    Run the full 6-step cost estimation pipeline.

    Step 1 — Gear Classification      (gear_rule.classify_and_plan)
    Step 2 — Volume Calculation        (VolumeCalculationService.calculate_from_extracted_data)
    Step 3 — Material Cost             (cost_service.compute_material_cost)
    Step 4 — Operations Cost           (cost_service.build_operations_with_costs)
    Step 5 — Cost Breakdown            (cost_service.compute_full_cost)
    Step 6 — Validation                (validation_service.validate_all)

    All monetary values returned in INR.

    Returns
    -------
    dict  Full pipeline_result (matches /api/google/analyze-direct response schema)
    """
    # ── Step 1: Gear Classification ──────────────────────────────────────────
    classification = classify_and_plan(extracted_data)
    gear_family    = classification["gear_family"]
    gear_rule_ops  = classification["operations_sequence"]

    # ── Step 2: Volume Calculation ───────────────────────────────────────────
    volume_result = _vol_service.calculate_from_extracted_data(extracted_data)

    if volume_result.get("status") == "success":
        net_volume_cm3 = volume_result["volume_summary"]["total_volume_cm3"]
    else:
        # Fallback: 1 cm³ floor so cost calculation still runs
        net_volume_cm3 = 1.0

    # ── Steps 3, 4, 5: Material + Operations + Full Breakdown ───────────────
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

    # ── Assemble final result ────────────────────────────────────────────────
    return {
        "gear_family":            gear_family,
        "classification_evidence": classification["evidence"],
        "volume": {
            "status":              volume_result.get("status"),
            "dimensions_used":     volume_result.get("dimensions_used", {}),
            "volume_breakdown_mm3": volume_result.get("volume_breakdown_mm3", {}),
            "volume_summary":      volume_result.get("volume_summary", {}),
            "mass_calculation":    volume_result.get("mass_calculation", {}),
            "calculation_notes":   volume_result.get("calculation_notes", []),
            "error":               volume_result.get("error"),       # None on success
        },
        "material_info":    cost_result["material_info"],
        "operations_detail": cost_result["operations_detail"],
        "cost_breakdown":   cost_result["cost_breakdown"],
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