
"""
Forging weight calculator — geometry path + reverse-from-finished path.

Usage examples:
  python forging_gross_both.py part.json --finished-kg 1.48
  python forging_gross_both.py part.json --finished-kg 1.48 --allowance-mm 4 --rho 7.85 \
      --loss flash=0.22 scale=0.05 shear=0.03 trim=0.05

Outputs both:
  A) Geometry-based blank (+allowance), then +losses -> gross
  B) Reverse-from-finished per paper: gross = finished / (1 - total_loss)
"""

import argparse, json, math, re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ------------------ defaults (tune to plant data) ------------------
DEFAULT_RHO_G_CM3 = 7.85         # steel-like density (e.g., 20MnCr5 / EN353)
DEFAULT_ALLOWANCE_MM = 4.0       # "each side" => OD+8, H+8
# Process losses AFTER forging blank to get gross billet mass
DEFAULT_LOSSES = {
    "flash": 0.22,    # 22% (closed-die with gutter; tune)
    "scale": 0.05,    # 5% oxidation
    "shear": 0.03,    # 3% billet cut loss
    "trim":  0.05     # 5% trimming/runners/misc
}
# Total default ≈ 35% (0.35). Adjust to match your route.

# ------------------ utilities ------------------
_num = re.compile(r"[-+]?\d+(?:\.\d+)?")
def n(x: Any) -> Optional[float]:
    if x is None: return None
    if isinstance(x, (int,float)): return float(x)
    m = _num.search(str(x)); return float(m.group()) if m else None

def cyl_vol_mm3(d_mm: Optional[float], h_mm: Optional[float]) -> Optional[float]:
    if d_mm is None or h_mm is None: return None
    r = d_mm/2.0
    return math.pi * r * r * h_mm

def mass_kg_from_mm3(v_mm3: Optional[float], rho_g_cm3: float) -> Optional[float]:
    if v_mm3 is None: return None
    return (v_mm3 / 1000.0 * rho_g_cm3) / 1000.0  # mm³→cm³→g→kg

def jget(d: Dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur: return default
        cur = cur[k]
    return cur

# ------------------ read finished geometry from your JSON ------------------
def get_overall_OD_H(j: Dict) -> Tuple[Optional[float], Optional[float]]:
    OD = n(jget(j,"extracted_data","overall_dimensions","diameter","value"))
    H  = n(jget(j,"extracted_data","overall_dimensions","length","value"))
    if OD is None or H is None:
        dims = jget(j,"extracted_data","geometric_decomposition","base_shapes", default=[]) or []
        if dims:
            d = dims[0].get("dimensions", {})
            OD = OD or n(jget(d,"main_outer_diameter","value") or d.get("main_outer_diameter"))
            H  = H  or n(jget(d,"total_height","value") or d.get("total_height"))
    return OD, H

def get_step_band_dims(j: Dict) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    dims = jget(j,"extracted_data","geometric_decomposition","base_shapes", default=[]) or []
    if not dims: return (None,None,None,None)
    d = dims[0].get("dimensions", {})
    rim_OD = n(jget(d,"main_outer_diameter","value") or d.get("main_outer_diameter"))
    hub_OD = n(jget(d,"hub_outer_diameter","value")  or d.get("hub_outer_diameter"))
    hub_H  = n(jget(d,"hub_height","value")          or d.get("hub_height"))
    rim_H  = n(jget(d,"main_height","value")         or d.get("main_height"))
    if rim_H is None:
        mhs = n(jget(d,"main_height_each_side","value") or d.get("main_height_each_side"))
        if mhs is not None: rim_H = 2.0 * mhs
    if rim_H is None and hub_H is not None:
        tot = n(jget(d,"total_height","value") or d.get("total_height"))
        if tot is not None: rim_H = max(tot - hub_H, 0.0)
    return rim_OD, rim_H, hub_OD, hub_H

def get_bore_d_and_depth(j: Dict) -> Tuple[Optional[float], Optional[float]]:
    subs = jget(j,"extracted_data","geometric_decomposition","subtracted_features", default=[]) or []
    bore_d=None; depth=None
    for s in subs:
        if (s.get("feature_type") or "").lower() in ("bore","hole"):
            dims = s.get("dimensions", {})
            candidates = [
                n(jget(dims,"main_diameter","value") or dims.get("main_diameter")),
                n(jget(dims,"entry_diameter","value") or dims.get("entry_diameter")),
                n(dims.get("diameter")), n(dims.get("outer_diameter"))
            ]
            candidates = [x for x in candidates if x is not None]
            if candidates:
                d_sel = min(candidates)                     # core diameter
                bore_d = d_sel if (bore_d is None or d_sel < bore_d) else bore_d
            depth = depth or n(jget(dims,"depth","value") or dims.get("depth") or
                               jget(dims,"height","value") or dims.get("height"))
    if depth is None:
        # fall back to overall length if nothing else
        depth = n(jget(j,"extracted_data","overall_dimensions","length","value"))
    return bore_d, depth

# ------------------ finished volume/mass ------------------
def finished_volume_mm3(j: Dict) -> Optional[float]:
    rim_OD, rim_H, hub_OD, hub_H = get_step_band_dims(j)
    total=0.0; ok=False
    if rim_OD and rim_H and rim_H>0:
        v = cyl_vol_mm3(rim_OD, rim_H)
        if v: total += v; ok=True
    if hub_OD and hub_H and hub_H>0:
        v = cyl_vol_mm3(hub_OD, hub_H)
        if v: total += v; ok=True
    if not ok:
        OD,H = get_overall_OD_H(j)
        total = cyl_vol_mm3(OD,H) or 0.0
    # subtract core bore
    bore_d, depth = get_bore_d_and_depth(j)
    if bore_d and depth:
        total -= cyl_vol_mm3(bore_d, depth) or 0.0
    return max(total, 0.0)

# ------------------ geometry-based forging blank ------------------
def forge_blank_volume_mm3(j: Dict, allowance_mm: float) -> Optional[float]:
    """Axisymmetric envelope: OD+2*allowance, H+2*allowance; bores suppressed."""
    OD, H = get_overall_OD_H(j)
    if OD is None or H is None: return None
    return cyl_vol_mm3(OD + 2*allowance_mm, H + 2*allowance_mm)

# ------------------ reverse-from-finished (paper method) ------------------
def gross_from_finished(finished_kg: float, losses: Dict[str,float]) -> float:
    """
    Gross = Finished / (1 - Σloss)
    'losses' are fractions (e.g., 0.22 for 22%).
    """
    total_loss = sum(losses.values())
    if total_loss >= 1.0:
        raise ValueError("Total loss fraction must be < 1.0")
    return finished_kg / (1.0 - total_loss)

# ------------------ helpers for CLI ------------------
def parse_losses(loss_args: Optional[list]) -> Dict[str,float]:
    if not loss_args: return dict(DEFAULT_LOSSES)
    d = {}
    for item in loss_args:
        # format: key=0.12
        if "=" not in item: continue
        k, v = item.split("=", 1)
        d[k.strip()] = float(v)
    return d

# ------------------ main ------------------
def main():
    ap = argparse.ArgumentParser(description="Forging weight — geometry path + reverse-from-finished path.")
    ap.add_argument("json_file", help="extraction JSON")
    ap.add_argument("--finished-kg", type=float, default=None, help="known finished mass in kg (preferred if available)")
    ap.add_argument("--rho", type=float, default=DEFAULT_RHO_G_CM3, help="density g/cm^3")
    ap.add_argument("--allowance-mm", type=float, default=DEFAULT_ALLOWANCE_MM, help="stock per side (mm)")
    ap.add_argument("--loss", action="append", help="loss items like flash=0.22 scale=0.05 shear=0.03 trim=0.05")
    args = ap.parse_args()

    j = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    losses = parse_losses(args.loss)  # dict of fractions

    # Finished mass (given or computed from volume)
    finished_v = finished_volume_mm3(j)
    finished_m = args.finished_kg if args.finished_kg is not None else mass_kg_from_mm3(finished_v, args.rho)

    # A) Geometry path → blank → gross
    blank_v = forge_blank_volume_mm3(j, args.allowance_mm)
    blank_m = mass_kg_from_mm3(blank_v, args.rho) if blank_v is not None else None
    gross_geom = (blank_m * (1.0 + sum(losses.values()))) if blank_m is not None else None

    # B) Reverse-from-finished (paper)
    gross_rev = gross_from_finished(finished_m, losses) if finished_m is not None else None

    # Report
    print("\n=== Inputs ===")
    print(f"Density (g/cm^3): {args.rho}")
    print(f"Allowance per side (mm): {args.allowance_mm}")
    print(f"Losses: {', '.join([f'{k}={v:.3f}' for k,v in losses.items()])} | total={sum(losses.values()):.3f}")

    print("\n=== Finished (from JSON unless overridden) ===")
    print(f"Finished volume (mm^3): {finished_v if finished_v is not None else 'NA'}")
    print(f"Finished mass (kg):     {finished_m if finished_m is not None else 'NA'}")

    print("\n=== Path A: Geometry → Blank (+stock) → Gross (+losses) ===")
    print(f"Blank volume (mm^3):    {blank_v if blank_v is not None else 'NA'}")
    print(f"Blank mass (kg):        {blank_m if blank_m is not None else 'NA'}")
    print(f"Gross mass (kg):        {gross_geom if gross_geom is not None else 'NA'}")

    print("\n=== Path B: Reverse-from-Finished (paper method) ===")
    print(f"Gross mass (kg):        {gross_rev if gross_rev is not None else 'NA'}")

    # Quick reconciliation to your sample target (e.g., 2.86 kg)
    if finished_m is not None and gross_rev is not None:
        ratio = gross_rev / finished_m
        print(f"\nGross/Finished ratio:   {ratio:.3f} (target ~1.90–2.00 typical for closed-die gears)")
    print()

if __name__ == "__main__":
    main()
