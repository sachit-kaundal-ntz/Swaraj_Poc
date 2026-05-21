import math
import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.log.logger import get_logger

logger = get_logger(__name__)

# Material densities in g/mm³
MATERIAL_DENSITIES = {
    "20MnCr5":  0.00785,
    "16MnCr5":  0.00785,
    "18CrNiMo7-6": 0.00785,
    "42CrMo4":  0.00785,
    "steel":    0.00785,
    "default":  0.00785,
}


def _cylinder_volume(d_outer_mm: float, height_mm: float, d_inner_mm: float = 0.0) -> float:
    """Volume of a hollow (or solid) cylinder in mm³."""
    r_o = d_outer_mm / 2.0
    r_i = d_inner_mm / 2.0 if d_inner_mm else 0.0
    return math.pi * height_mm * (r_o ** 2 - r_i ** 2)


def _find_dim_value(dimensions: List[Dict], dim_id: str) -> Optional[float]:
    """Return numeric value for a dimension by id, or None."""
    for d in dimensions:
        if d.get("id") == dim_id:
            val = d.get("value")
            if isinstance(val, (int, float)):
                return float(val)
            try:
                if isinstance(val, str) and val.strip():
                    return float(val)
            except (ValueError, TypeError):
                pass
    return None


def _find_table_cell_value(tables: List[Dict], table_id: str, label_keywords: List[str]) -> Optional[float]:
    """Search a specific table for a cell whose label contains any of the keywords."""
    for t in tables:
        if t.get("id") != table_id:
            continue
        for cell in t.get("cells", []):
            label = (cell.get("label") or "").upper()
            if any(kw.upper() in label for kw in label_keywords):
                try:
                    return float(cell.get("value"))
                except (TypeError, ValueError):
                    pass
    return None


def _get_density(material: Optional[str]) -> float:
    """Resolve material string to density in g/mm³."""
    if not material:
        return MATERIAL_DENSITIES["default"]
    for key in MATERIAL_DENSITIES:
        if key.lower() in material.lower():
            return MATERIAL_DENSITIES[key]
    return MATERIAL_DENSITIES["default"]


class VolumeCalculationService:

    # ------------------------------------------------------------------ #
    #  PUBLIC ENTRY POINT                                                  #
    # ------------------------------------------------------------------ #

    def calculate_from_extracted_data(
        self,
        extracted: Dict[str, Any],
        include_bore_subtraction: bool = True,
    ) -> Dict[str, Any]:
        """
        Main calculation method.

        Parameters
        ----------
        extracted : dict
            The `extracted_data` object from the drawing JSON (after Gemini extraction).
        include_bore_subtraction : bool
            If True, subtract bore cylinder from hub volume (more accurate).
            If False, return gross solid volumes only.

        Returns
        -------
        dict  Volume/mass result with full breakdown.
        """
        dims = extracted.get("dimensions", [])
        tables = extracted.get("tables", [])
        title_block = (extracted.get("metadata") or {}).get("title_block") or {}
        material = title_block.get("material")
        density = _get_density(material)

        # ── 1. Collect key dimensions ─────────────────────────────────── #
        gear_outer  = _find_dim_value(dims, "dim_outer_dia")
        face_width  = _find_dim_value(dims, "dim_face_width")
        hub_height  = _find_dim_value(dims, "dim_hub_height")
        hub_outer   = self._resolve_hub_outer(dims, tables)
        bore_dia    = _find_dim_value(dims, "dim_bore")

        # ── 2. Validate required dimensions ──────────────────────────── #
        missing = []
        if gear_outer is None:
            missing.append("dim_outer_dia (gear outer diameter)")
        if face_width is None:
            missing.append("dim_face_width (gear face width)")
        if missing:
            return self._error_result(f"Missing required dimensions: {missing}")

        # ── 3. Compute volumes ────────────────────────────────────────── #
        # Gear rim: solid cylinder of outer diameter × face width
        rim_vol = _cylinder_volume(gear_outer, face_width)

        # Hub body: cylinder of hub_outer × hub_height (whole axial stack)
        hub_gross_vol = 0.0
        if hub_outer and hub_height:
            hub_gross_vol = _cylinder_volume(hub_outer, hub_height)

        # Bore subtraction: passes through the full hub_height (or face_width if no hub)
        bore_vol = 0.0
        axial_bore_length = hub_height if hub_height else face_width
        if include_bore_subtraction and bore_dia and axial_bore_length:
            bore_vol = _cylinder_volume(bore_dia, axial_bore_length)

        # Net volumes
        rim_net  = max(rim_vol - bore_vol, 0.0)          # bore removed from rim section
        hub_net  = max(hub_gross_vol - bore_vol, 0.0)    # bore removed from hub section

        # Total net (avoid double-subtracting bore)
        if hub_gross_vol > 0:
            total_net = (rim_vol + hub_gross_vol) - bore_vol
        else:
            total_net = rim_vol - bore_vol
        total_net = max(total_net, 0.0)

        # ── 4. Mass ───────────────────────────────────────────────────── #
        mass_g  = total_net * density
        mass_kg = mass_g / 1000.0

        # Drawing-specified weight for comparison
        drawing_weight_kg = self._drawing_weight(title_block)
        diff_pct = None
        if drawing_weight_kg:
            try:
                diff_pct = round((mass_kg - drawing_weight_kg) / drawing_weight_kg * 100.0, 2)
            except ZeroDivisionError:
                pass

        # ── 5. Build result ───────────────────────────────────────────── #
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "dimensions_used": {
                "gear_outer_diameter_mm":  gear_outer,
                "gear_face_width_mm":      face_width,
                "hub_outer_diameter_mm":   hub_outer,
                "hub_height_mm":           hub_height,
                "bore_diameter_mm":        bore_dia,
                "bore_subtraction_applied": include_bore_subtraction and bore_dia is not None,
            },
            "volume_breakdown_mm3": {
                "gear_rim_gross_mm3":   round(rim_vol, 2),
                "hub_gross_mm3":        round(hub_gross_vol, 2),
                "bore_cylinder_mm3":    round(bore_vol, 2),
                "total_net_mm3":        round(total_net, 2),
            },
            "volume_summary": {
                "total_volume_mm3":    round(total_net, 2),
                "total_volume_cm3":    round(total_net / 1_000.0, 4),
                "total_volume_liters": round(total_net / 1_000_000.0, 6),
            },
            "mass_calculation": {
                "material":                    material or "unknown (assumed steel)",
                "density_g_per_mm3":           density,
                "calculated_mass_g":           round(mass_g, 2),
                "calculated_mass_kg":          round(mass_kg, 4),
                "drawing_specified_weight_kg": drawing_weight_kg,
                "weight_difference_percent":   diff_pct,
            },
            "calculation_notes": [
                "Gear rim modelled as solid cylinder: OD × face_width.",
                "Hub modelled as solid cylinder: hub_OD × hub_height.",
                f"Bore subtraction {'applied' if bore_vol > 0 else 'skipped (no bore dim found)'}.",
                "Spline, keyway, chamfer volumes not subtracted (minor contributors).",
                "Hub diameter resolved from: dim_hub_step_dia → dim_hub_dia → spline major dia.",
            ],
        }

    # ------------------------------------------------------------------ #
    #  CALCULATE FROM JSON FILE PATH                                       #
    # ------------------------------------------------------------------ #

    def calculate_from_json_file(
        self,
        json_path: str,
        include_bore_subtraction: bool = True,
    ) -> Dict[str, Any]:
        """Load a saved drawing JSON file and compute volumes."""
        if not os.path.exists(json_path):
            return self._error_result(f"JSON file not found: {json_path}")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return self._error_result(f"Invalid JSON: {e}")

        # Handle both raw extracted_data and wrapped formats
        extracted = data.get("extracted_data", data)
        return self.calculate_from_extracted_data(extracted, include_bore_subtraction)

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #

    def _resolve_hub_outer(self, dims: List[Dict], tables: List[Dict]) -> Optional[float]:
        """
        Try candidates in priority order and return the smallest valid hub diameter.
        Priority: dim_hub_step_dia → dim_hub_dia → dim_hub_dia_small → spline major dia
        """
        candidates = []
        for did in ("dim_hub_step_dia", "dim_hub_dia", "dim_hub_dia_small"):
            v = _find_dim_value(dims, did)
            if v:
                candidates.append(v)

        if not candidates:
            v = _find_table_cell_value(tables, "tbl_spline_data", ["MAJOR DIAMETER"])
            if v:
                candidates.append(v)

        return min(candidates) if candidates else None

    @staticmethod
    def _drawing_weight(title_block: Dict) -> Optional[float]:
        for k in ("weight_kg", "weight", "mass_kg", "mass"):
            if k in title_block:
                try:
                    return float(title_block[k])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _error_result(message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "error": message,
            "timestamp": datetime.now().isoformat(),
        }