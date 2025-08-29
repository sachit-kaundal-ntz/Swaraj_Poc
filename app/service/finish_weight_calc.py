#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, json, math, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

DEFAULT_DENSITY_G_CM3 = 7.85
DENSITY_MAP = {"EN353":7.85, "20MnCr5":7.85, "IS:9175":7.85, "IS-1570":7.85}

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
def first_number(x: Any) -> Optional[float]:
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    m = _NUM_RE.search(str(x)); return float(m.group()) if m else None

def cyl_vol_mm3(d_mm: Optional[float], h_mm: Optional[float]) -> Optional[float]:
    if d_mm is None or h_mm is None: return None
    r = d_mm/2.0; return math.pi * r * r * h_mm

def mass_kg_from_volume_mm3(v_mm3: Optional[float], rho_g_cm3: Optional[float]) -> Optional[float]:
    if v_mm3 is None or rho_g_cm3 is None: return None
    return (v_mm3/1000.0 * rho_g_cm3) / 1000.0

def get_density(material_text: Optional[str]) -> float:
    if not material_text: return DEFAULT_DENSITY_G_CM3
    mt = material_text.lower()
    for k, rho in DENSITY_MAP.items():
        if k.lower() in mt: return rho
    return DEFAULT_DENSITY_G_CM3

def _get(j: Dict, *keys, default=None):
    cur = j
    for k in keys:
        if not isinstance(cur, dict) or k not in cur: return default
        cur = cur[k]
    return cur

# ---------- INPUT PARSERS (updated to match your JSON) ----------

def finished_dims_simple(j: Dict) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Returns OD, overall H, bore_D, hub_OD, hub_H from:
      extracted_data.overall_dimensions + other_critical_dimensions
    """
    OD  = first_number(_get(j, "extracted_data","overall_dimensions","diameter","value"))
    H   = first_number(_get(j, "extracted_data","overall_dimensions","length","value"))
    bore = None; hub_OD=None; hub_H=None

    for item in _get(j,"extracted_data","overall_dimensions","other_critical_dimensions", default=[]) or []:
        name = (item.get("feature") or "").lower()
        val  = first_number(item.get("value"))
        if val is None: continue
        if "hub diameter" in name: hub_OD = val
        elif "hub length" in name:  hub_H  = val
        elif "bore" in name:        bore   = val  # matches "Bore Diameter (main)" etc.

    return OD, H, bore, hub_OD, hub_H

def additive_height_sum_from_geo(j: Dict) -> Optional[float]:
    geo = _get(j,"extracted_data","geometric_decomposition", default={})
    bases = geo.get("base_shapes") or []
    found=False; total=0.0
    for b in bases:
        dims = b.get("dimensions") or {}
        st = (b.get("shape_type") or "").lower()
        if st == "cylinder":
            h = first_number(dims.get("height")); 
            if h: total+=h; found=True
        elif st == "stepped_cylinder":
            # Handle both styles: (main_height + hub_height) OR total_height or main_height_each_side*2 + hub_height
            mh  = first_number(dims.get("main_height"))
            mhs = first_number(dims.get("main_height_each_side"))
            hh  = first_number(dims.get("hub_height"))
            th  = first_number(dims.get("total_height"))
            if mhs and hh:
                total += (2*mhs + hh); found=True
            elif mh and hh:
                total += (mh + hh); found=True
            elif th:
                total += th; found=True
    return total if found else None

def finished_volume_from_geo(j: Dict) -> Optional[float]:
    """
    Reads stepped cylinder per your JSON:
      - base_shapes[0].dimensions.main_outer_diameter.value
      - base_shapes[0].dimensions.main_height_each_side.value  (rim band, each side)
      - base_shapes[0].dimensions.hub_outer_diameter.value
      - base_shapes[0].dimensions.hub_height.value
      - total_height.value  as fallback
    Subtractive bores may use keys: diameter, outer_diameter, main_diameter, entry_diameter, depth/height.
    """
    geo = _get(j,"extracted_data","geometric_decomposition", default={})
    bases = geo.get("base_shapes") or []
    subs  = geo.get("subtracted_features") or []

    total_add = 0.0
    # Additive bands
    for b in bases:
        st = (b.get("shape_type") or "").lower()
        dims = b.get("dimensions") or {}
        if st == "cylinder":
            d = first_number(_get(dims,"outer_diameter"))
            h = first_number(_get(dims,"height"))
            v = cyl_vol_mm3(d,h); 
            if v: total_add += v
        elif st == "stepped_cylinder":
            d_main = first_number(_get(dims,"main_outer_diameter","value") or _get(dims,"main_outer_diameter"))
            d_hub  = first_number(_get(dims,"hub_outer_diameter","value") or _get(dims,"hub_outer_diameter"))
            h_main = first_number(_get(dims,"main_height","value") or _get(dims,"main_height"))
            h_main_each_side = first_number(_get(dims,"main_height_each_side","value") or _get(dims,"main_height_each_side"))
            h_hub  = first_number(_get(dims,"hub_height","value") or _get(dims,"hub_height"))
            h_tot  = first_number(_get(dims,"total_height","value") or _get(dims,"total_height"))

            # Prefer explicit band heights; else derive rim height from 2*each_side; else single cylinder fallback
            rim_h = None
            if h_main is not None:
                rim_h = h_main
            elif h_main_each_side is not None:
                rim_h = 2.0 * h_main_each_side
            elif (h_tot is not None) and (h_hub is not None):
                rim_h = max(h_tot - h_hub, 0.0)

            if d_main and rim_h and rim_h > 0:
                v = cyl_vol_mm3(d_main, rim_h); 
                if v: total_add += v
            if d_hub and h_hub:
                v = cyl_vol_mm3(d_hub, h_hub); 
                if v: total_add += v
            if total_add == 0.0 and d_main and h_tot:
                # worst-case fallback
                v = cyl_vol_mm3(d_main, h_tot); 
                if v: total_add += v

    if total_add == 0.0: 
        return None

    # Subtractive bores (tolerant to your key names)
    depth_default = additive_height_sum_from_geo(j) or first_number(_get(j,"extracted_data","overall_dimensions","length","value"))
    total_sub = 0.0
    for s in subs:
        if (s.get("feature_type") or "").lower() in ("bore","hole"):
            dims = s.get("dimensions") or {}
            d = (first_number(_get(dims,"diameter")) or
                 first_number(_get(dims,"outer_diameter")) or
                 first_number(_get(dims,"main_diameter","value") or _get(dims,"main_diameter")) or
                 first_number(_get(dims,"entry_diameter","value") or _get(dims,"entry_diameter")))
            # Prefer the *smaller* cylindrical core if both main/entry exist
            md = first_number(_get(dims,"main_diameter","value") or _get(dims,"main_diameter"))
            ed = first_number(_get(dims,"entry_diameter","value") or _get(dims,"entry_diameter"))
            if md and ed: d = min(md, ed)

            h = (first_number(_get(dims,"depth","value") or _get(dims,"depth")) or
                 first_number(_get(dims,"height","value") or _get(dims,"height")) or
                 depth_default)
            v = cyl_vol_mm3(d,h)
            if v: total_sub += v

    return max(total_add - total_sub, 0.0)

def finished_volume_fallback(j: Dict) -> Optional[float]:
    OD, H, bore, hub_OD, hub_H = finished_dims_simple(j)
    if OD is None or H is None: return None
    # Split into rim + hub if possible
    v = 0.0
    if hub_OD and hub_H and hub_H <= H:
        rim_h = max(H - hub_H, 0.0)
        if rim_h > 0: v += cyl_vol_mm3(OD, rim_h) or 0.0
        v += cyl_vol_mm3(hub_OD, hub_H) or 0.0
    else:
        v += cyl_vol_mm3(OD, H) or 0.0
    if bore: v -= cyl_vol_mm3(bore, H) or 0.0
    return max(v, 0.0)

def finished_volume_mm3(j: Dict) -> Optional[float]:
    return finished_volume_from_geo(j) or finished_volume_fallback(j)

def forging_envelope_volume_mm3(j: Dict, allowance_mm: float) -> Optional[float]:
    OD, H, *_ = finished_dims_simple(j)
    if OD is None or H is None:
        # infer from geo if needed
        geo = _get(j,"extracted_data","geometric_decomposition", default={})
        bases = geo.get("base_shapes") or []
        maxD=None; sumH=0.0
        for b in bases:
            dims=b.get("dimensions") or {}; st=(b.get("shape_type") or "").lower()
            if st=="cylinder":
                d=first_number(_get(dims,"outer_diameter")); h=first_number(_get(dims,"height"))
                if d: maxD = d if maxD is None else max(maxD,d)
                if h: sumH += h
            elif st=="stepped_cylinder":
                d1 = first_number(_get(dims,"main_outer_diameter","value") or _get(dims,"main_outer_diameter"))
                d2 = first_number(_get(dims,"hub_outer_diameter","value") or _get(dims,"hub_outer_diameter"))
                for d in [d1,d2]:
                    if d: maxD = d if maxD is None else max(maxD,d)
                mh  = first_number(_get(dims,"main_height","value") or _get(dims,"main_height"))
                mhs = first_number(_get(dims,"main_height_each_side","value") or _get(dims,"main_height_each_side"))
                hh  = first_number(_get(dims,"hub_height","value") or _get(dims,"hub_height"))
                th  = first_number(_get(dims,"total_height","value") or _get(dims,"total_height"))
                if mh and hh: sumH += mh + hh
                elif mhs and hh: sumH += 2*mhs + hh
                elif th: sumH += th
        OD = OD or maxD
        H  = H or (sumH if sumH>0 else None)
    if OD is None or H is None: return None
    return cyl_vol_mm3(OD + 2*allowance_mm, H + 2*allowance_mm)

# ---------- PIPELINE ----------

def analyze_file(path: Path, allowance_mm: float) -> Dict[str, Any]:
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = _get(j,"extracted_data","drawing_metadata", default={})
    mat  = (meta.get("material_specification") or
            _get(j,"extracted_data","material_and_treatment","base_material"))
    rho  = get_density(mat)

    v_fin   = finished_volume_mm3(j)
    v_forge = forging_envelope_volume_mm3(j, allowance_mm)
    m_fin   = mass_kg_from_volume_mm3(v_fin, rho) if v_fin is not None else None
    m_forge = mass_kg_from_volume_mm3(v_forge, rho) if v_forge is not None else None

    return {
        "file": path.name,
        "drawing_number": meta.get("drawing_number"),
        "part_name": meta.get("part_name"),
        "material": mat,
        "density_g_cm3": rho,
        "finished_volume_mm3": v_fin,
        "finished_mass_kg": m_fin,
        "forge_envelope_volume_mm3": v_forge,
        "forge_envelope_mass_kg": m_forge,
        "scrap_mass_kg_(forge-fin)": ((m_forge - m_fin) if (m_forge is not None and m_fin is not None) else None),
        "scrap_%_of_forge": (((m_forge - m_fin)/m_forge*100.0) if (m_forge and m_fin) else None),
    }

def main():
    ap = argparse.ArgumentParser(description="Compute forging envelope mass from extracted drawing JSONs.")
    ap.add_argument("json_files", nargs="+", help="One or more extraction JSON files")
    ap.add_argument("--allowance-mm", type=float, default=4.0,
                    help="Allowance per side (mm). Envelope uses OD+2*allowance, H+2*allowance.")
    ap.add_argument("--out", type=str, default="forging_weight_report.csv")
    args = ap.parse_args()

    rows: List[Dict[str, Any]] = []
    for p in args.json_files:
        try: rows.append(analyze_file(Path(p), args.allowance_mm))
        except Exception as e: print(f"[ERROR] {p}: {e}")

    if not rows: 
        print("No rows produced."); return
    df = pd.DataFrame(rows)
    cols = ["file","drawing_number","part_name","material","density_g_cm3",
            "finished_volume_mm3","finished_mass_kg",
            "forge_envelope_volume_mm3","forge_envelope_mass_kg",
            "scrap_mass_kg_(forge-fin)","scrap_%_of_forge"]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(args.out, index=False)
    print(f"Saved: {Path(args.out).resolve()}")
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
