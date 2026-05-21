"""
compute_gear_volume_mass.py

Reads an extracted drawing JSON (structure like the JSON you provided),
computes the solid volume approximating parts as cylinders (no bore/spline removal),
and prints a structured JSON summary (volumes in mm³ / cm³ and mass in g / kg).

Usage:
    python compute_gear_volume_mass.py /path/to/extracted_json.json

If no path is provided, the script will try "./extracted.json".
"""

import json
import math
import sys
from typing import Any, Dict, Optional

# Material density in g/mm³ (20MnCr5 ≈ 7.85 g/cm³ = 0.00785 g/mm³)
DENSITY_G_PER_MM3 = 0.00785


def cylinder_volume(d_outer_mm: float, height_mm: float, d_inner_mm: float = 0.0) -> float:
    """Return volume of hollow (or solid if d_inner_mm==0) cylinder in mm³."""
    r_o = d_outer_mm / 2.0
    r_i = d_inner_mm / 2.0 if d_inner_mm else 0.0
    return math.pi * height_mm * (r_o * r_o - r_i * r_i)


def find_dimension_value(dimensions: list, dim_id: str) -> Optional[float]:
    """Search dimensions array for a dimension with given id and return numeric value or None."""
    for d in dimensions:
        if d.get("id") == dim_id:
            val = d.get("value")
            if isinstance(val, (int, float)):
                return float(val)
            # sometimes value may be string numeric - try convert
            try:
                if isinstance(val, str) and val.strip() != "":
                    return float(val)
            except Exception:
                return None
    return None


def choose_smallest_hub(dims: list, possible_hub_ids: list) -> Optional[float]:
    """Given a list of candidate dimension ids, return the smallest numeric diameter found."""
    candidates = []
    for pid in possible_hub_ids:
        v = find_dimension_value(dims, pid)
        if v:
            candidates.append(float(v))
    return min(candidates) if candidates else None


def extract_relevant_dimensions(extracted: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Extract the dimensions we will use:
      - gear_outer_diameter_mm (from dim_outer_dia)
      - gear_face_width_mm (from dim_face_width)
      - hub_outer_diameter_mm (prefer smallest hub step like ⌀58)
      - hub_height_mm (from dim_hub_height)
    """
    dims = extracted.get("dimensions", [])

    # Primary picks (these match the ids from your JSON)
    gear_outer = find_dimension_value(dims, "dim_outer_dia")
    face_width = find_dimension_value(dims, "dim_face_width")
    hub_height = find_dimension_value(dims, "dim_hub_height")

    # Choose smallest hub diameter among candidates:
    # the JSON contains dim_hub_dia (⌀90) and dim_hub_step_dia (⌀58)
    hub_outer = choose_smallest_hub(dims, ["dim_hub_step_dia", "dim_hub_dia", "dim_hub_dia_small"])

    # fallback logic: if hub not found, check tables for "MAJOR DIAMETER" or other hints
    if hub_outer is None:
        # try reading from spline table major diameter if present in tables
        tables = extracted.get("tables", [])
        for t in tables:
            cells = t.get("cells", [])
            for c in cells:
                label = (c.get("label") or "").strip().upper()
                if label in ("MAJOR DIAMETER", "MAJOR DIAMETER (MM)"):
                    try:
                        hub_outer = float(c.get("value"))
                    except Exception:
                        pass
                    if hub_outer:
                        break
            if hub_outer:
                break

    return {
        "gear_outer_diameter_mm": gear_outer,
        "gear_face_width_mm": face_width,
        "hub_outer_diameter_mm": hub_outer,
        "hub_height_mm": hub_height,
    }


def compute_volumes_and_mass(extracted: Dict[str, Any]) -> Dict[str, Any]:
    dims_used = extract_relevant_dimensions(extracted)

    gear_outer = dims_used["gear_outer_diameter_mm"]
    face_width = dims_used["gear_face_width_mm"]
    hub_outer = dims_used["hub_outer_diameter_mm"]
    hub_height = dims_used["hub_height_mm"]

    # validate required dims
    missing = []
    if gear_outer is None:
        missing.append("gear_outer_diameter_mm (dim_outer_dia)")
    if face_width is None:
        missing.append("gear_face_width_mm (dim_face_width)")
    if missing:
        raise ValueError(f"Missing required dimensions: {missing}")

    # Gear rim approximated as solid cylinder of diameter = gear_outer, height = face_width
    gear_rim_vol_mm3 = cylinder_volume(gear_outer, face_width)

    # Hub volume (if both hub diameter and hub height available). If hub height is missing,
    # we may assume hub height 0 (no hub) — but better to compute only when both present.
    hub_vol_mm3 = 0.0
    if hub_outer is not None and hub_height is not None:
        hub_vol_mm3 = cylinder_volume(hub_outer, hub_height)

    total_volume_mm3 = gear_rim_vol_mm3 + hub_vol_mm3

    mass_g = total_volume_mm3 * DENSITY_G_PER_MM3
    mass_kg = mass_g / 1000.0

    # drawing-specified weight if present (optional)
    drawing_weight_kg = None
    title_block = extracted.get("metadata", {}).get("title_block", {}) or {}
    # try common keys: weight, weight_kg or mass
    for k in ("weight_kg", "weight", "mass_kg", "mass"):
        if k in title_block:
            try:
                drawing_weight_kg = float(title_block[k])
                break
            except Exception:
                drawing_weight_kg = None

    weight_diff_percent = None
    if drawing_weight_kg:
        try:
            weight_diff_percent = (mass_kg - drawing_weight_kg) / drawing_weight_kg * 100.0
        except Exception:
            weight_diff_percent = None

    result = {
        "dimensions_used": {
            "gear_outer_diameter_mm": gear_outer,
            "gear_face_width_mm": face_width,
            "hub_outer_diameter_mm": hub_outer,
            "hub_height_mm": hub_height,
        },
        "volume_breakdown_mm3": {
            "gear_rim_volume_mm3": round(gear_rim_vol_mm3, 2),
            "hub_volume_mm3": round(hub_vol_mm3, 2),
            "total_solid_volume_mm3": round(total_volume_mm3, 2),
        },
        "volume_summary": {
            "total_volume_mm3": round(total_volume_mm3, 2),
            "total_volume_cm3": round(total_volume_mm3 / 1000.0, 4),
            "total_volume_liters": round(total_volume_mm3 / 1_000_000.0, 6),
        },
        "mass_calculation": {
            "material": title_block.get("material", "20MnCr5"),
            "density_g_per_mm3": DENSITY_G_PER_MM3,
            "calculated_mass_g": round(mass_g, 2),
            "calculated_mass_kg": round(mass_kg, 4),
            "drawing_specified_weight_kg": drawing_weight_kg,
            "weight_difference_percent": None
            if weight_diff_percent is None
            else round(weight_diff_percent, 2),
        },
        "calculation_notes": [
            "Cylindrical approximations used for gear rim and hub.",
            "No bore or internal spline subtractions applied (solid volumes only).",
            "Hub chosen as the smallest hub diameter found (prefers dim_hub_step_dia).",
        ],
    }

    return result


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    if len(argv) >= 2:
        json_path = argv[1]
    else:
        json_path = r"D:\swaraj\Gear-Cost\Swaraj_Poc\outputs\drawings\f3febbf9-10fc-438b-bf88-4843d2bee9a0\test.json"  # default fallback

    try:
        data = load_json_file(json_path)
    except FileNotFoundError:
        print(json.dumps({"error": f"JSON file not found: {json_path}"}))
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON file: {e}"}))
        sys.exit(2)

    # Your extracted data might be nested under a key like "extracted_data"
    extracted = data.get("extracted_data") if isinstance(data, dict) and "extracted_data" in data else data

    try:
        result = compute_volumes_and_mass(extracted)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(3)

    # Pretty-print output JSON
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main(sys.argv)
