"""
run_cost.py
-----------
Standalone cost estimation runner.
Place this file in your project ROOT (same level as app/, venv/, .env).

Run:
    python run_cost.py
    python run_cost.py --image uploads/drawings/your_drawing.jpg
    python run_cost.py --json manufacturing_operations_selection.json
"""

import sys
import os
import json
import math
import argparse

# ── Make sure app/ is importable ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app", "service"))
sys.path.insert(0, os.path.join(ROOT, "app"))


# ══════════════════════════════════════════════════════════════════════════════
# MATERIAL CATALOGUE  (mirrors materials.py)
# ══════════════════════════════════════════════════════════════════════════════
MATERIAL_PROPERTIES = {
    "alloy-steel":     {"density": 7.85, "rate": 4.50,  "patterns": ["20mncr","16mncr","4140","4340","en36","scm","8620","alloy steel","en353","18crnimo"]},
    "carbon-steel":    {"density": 7.85, "rate": 3.00,  "patterns": ["c45","c35","en8","1045","s45c","mild steel","carbon steel","en9","c60","ck45"]},
    "stainless-steel": {"density": 8.00, "rate": 8.50,  "patterns": ["stainless","ss304","ss316","aisi 316","aisi 304","304l","316l","17-4"]},
    "cast-iron":       {"density": 7.20, "rate": 2.50,  "patterns": ["cast iron","gg25","ggg40","fc25","sg iron","grey iron","ductile iron"]},
    "aluminium":       {"density": 2.70, "rate": 6.50,  "patterns": ["aluminium","aluminum","6061","7075","al6061","al7075","2024","5052"]},
    "bronze":          {"density": 8.80, "rate": 14.00, "patterns": ["bronze","phos bronze","phosphor bronze","cusn","c93200"]},
    "brass":           {"density": 8.50, "rate": 11.00, "patterns": ["brass","cuzn","c36000"]},
    "nylon":           {"density": 1.14, "rate": 6.00,  "patterns": ["nylon","pa6","pa66","polyamide"]},
    "peek":            {"density": 1.31, "rate": 110.0, "patterns": ["peek","polyetheretherketone"]},
    "sintered-steel":  {"density": 6.80, "rate": 5.50,  "patterns": ["sintered steel","powder metal","pm steel"]},
    "tool-steel":      {"density": 7.85, "rate": 12.00, "patterns": ["d2","h13","m2","tool steel","hss","high speed steel"]},
    "titanium":        {"density": 4.51, "rate": 35.00, "patterns": ["titanium","ti-6al-4v","grade 5","ti64"]},
    "default-steel":   {"density": 7.85, "rate": 4.00,  "patterns": []},
}

# ══════════════════════════════════════════════════════════════════════════════
# OPERATION TEMPLATES  (mirrors gear_ops.py / gear_rule.py)
# ══════════════════════════════════════════════════════════════════════════════
OPERATIONS_TEMPLATES = {
    "spur": [
        {"operation":"Forging",             "time":15,  "rate":60,  "machines":["Forging Complex","Forging Symmetrical"]},
        {"operation":"Gear Hobbing",         "time":25,  "rate":95,  "machines":["Gear Hobbing CNC","Gear Hobbing Conventional"]},
        {"operation":"Helical Hobbing",      "time":35,  "rate":105, "machines":["Gear Hobbing CNC","Gear Hobbing Conventional"]},
        {"operation":"Gear Tooth Chamfering","time":8,   "rate":45,  "machines":["Gear Tooth Chamfering"]},
        {"operation":"Heat Treatment",       "time":90,  "rate":55,  "machines":["Carburising GCF","SQF","Salt bath"]},
        {"operation":"Gear Grinding",        "time":30,  "rate":120, "machines":["Gear Grinding","CNC Grinding"]},
        {"operation":"Grinding - Gear",      "time":30,  "rate":120, "machines":["Gear Grinding","CNC Grinding"]},
        {"operation":"Grinding - CNC",       "time":30,  "rate":120, "machines":["CNC Grinding","Cylindrical Grinding"]},
        {"operation":"Rough Turning",        "time":18,  "rate":75,  "machines":["CNC Turning Centre","Lathe CNC","VTC"]},
        {"operation":"Finish Turning",       "time":12,  "rate":80,  "machines":["CNC Turning Centre","Lathe CNC","VTC"]},
        {"operation":"Drilling / Boring",    "time":10,  "rate":70,  "machines":["Drilling Pillar Type","Drilling Radial"]},
        {"operation":"Internal Grinding",    "time":30,  "rate":120, "machines":["Grinding Cylindrical","Surface","Centreless"]},
        {"operation":"Gear Shaping",         "time":55,  "rate":110, "machines":["Gear Shaping Conventional"]},
        {"operation":"Broaching",            "time":10,  "rate":70,  "machines":["Horizontal Broaching","Vertical Broaching"]},
        {"operation":"Final Inspection",     "time":15,  "rate":85,  "machines":["Magnaflux","Manual"]},
        {"operation":"Deburring",            "time":6,   "rate":40,  "machines":["(manual)"]},
        {"operation":"Carburising",          "time":90,  "rate":55,  "machines":["Carburising GCF","SQF"]},
        {"operation":"Quenching",            "time":30,  "rate":55,  "machines":["Salt bath","SQF"]},
        {"operation":"Tempering",            "time":60,  "rate":55,  "machines":["Salt bath"]},
        {"operation":"Nitriding",            "time":480, "rate":55,  "machines":["Gas Nitriding Furnace"]},
        {"operation":"Induction Hardening",  "time":20,  "rate":90,  "machines":["Induction Hardening Machine"]},
        {"operation":"Shot Peening",         "time":20,  "rate":60,  "machines":["Shot Peening Machine"]},
        {"operation":"Phosphating",          "time":30,  "rate":45,  "machines":["Phosphating Tank"]},
        {"operation":"Plating",              "time":45,  "rate":50,  "machines":["Plating Line"]},
        {"operation":"Blackodizing",         "time":30,  "rate":40,  "machines":["Blackodizing Tank"]},
    ]
}

FEATURE_PROCESS_MAP = {
    ("cylindrical_rim",  "gear_tip"):    ["Gear Hobbing","Gear Tooth Chamfering"],
    ("cylindrical_step", "hub_outer"):   ["Rough Turning","Finish Turning"],
    ("cylindrical_bore", "through_bore"):["Drilling / Boring"],
    ("internal_spline",  "spline_bore"): ["Gear Shaping","Broaching"],
    ("keyway",           "*"):           ["Broaching"],
    ("chamfer",          "*"):           ["Gear Tooth Chamfering"],
    ("thread",           "*"):           ["Threading"],
    ("groove",           "*"):           ["Turning"],
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — GEAR CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════
def _all_text(data):
    parts = []
    def walk(o):
        if isinstance(o, str): parts.append(o.lower())
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for i in o: walk(i)
    walk(data)
    return " ".join(parts)

def _tbl(data, tbl_id, label):
    for t in data.get("tables", []):
        if t.get("id","").lower() == tbl_id.lower():
            for c in t.get("cells", []):
                if c.get("label","").strip().upper() == label.strip().upper():
                    try: return float(c.get("value", 0))
                    except: return c.get("value")
    return None

def _min_ra(data):
    ra = None
    for s in data.get("surface_specifications", []):
        rv = s.get("roughness_value","")
        if isinstance(rv, str) and "ra" in rv.lower():
            try:
                v = float("".join(c for c in rv.lower().replace("ra","").strip().split()[0] if c in "0123456789."))
                if ra is None or v < ra: ra = v
            except: pass
        elif isinstance(rv, (int,float)):
            if ra is None or rv < ra: ra = rv
    return ra

def _op_tmpl(op_name):
    for t in OPERATIONS_TEMPLATES["spur"]:
        if t["operation"].lower() == op_name.lower():
            return t
    return {"operation":op_name,"time":15,"rate":60,"machines":[]}

def step1_classify(data):
    """Step 1 — Gear Classification & Operation Planning"""
    txt = _all_text(data)
    helix = _tbl(data, "tbl_gear_data", "HELIX ANGLE")
    try:    helix_val = float(str(helix).replace("°","").strip()) if helix else 0.0
    except: helix_val = 0.0

    gear_family = "helical" if (helix_val > 0.2 or "helical" in txt) else \
                  "bevel"   if "bevel" in txt else "spur"

    ops = []  # list of (name, reason)

    # Default ops
    hobbing = "Helical Hobbing" if gear_family == "helical" else "Gear Hobbing"
    ops += [
        ("Forging",              "Default: blank forging"),
        (hobbing,                f"Default: {gear_family} tooth cutting"),
        ("Gear Tooth Chamfering","Default: chamfer after hobbing"),
        ("Deburring",            "Default: always required"),
        ("Rough Turning",        "Default: blank OD turning"),
    ]

    # Heat treatment
    mat_treat = data.get("material_and_treatment", {})
    tb        = data.get("metadata", {}).get("title_block", {})
    ht = (str(mat_treat.get("heat_treatment","")) + " " + str(tb.get("heat_treatment",""))).lower()
    if "carbur" in ht:
        ops += [("Carburising","HT: carburising"),("Quenching","HT: quench"),("Tempering","HT: temper")]
    if "nitrid"    in ht: ops.append(("Nitriding",           "HT: nitriding"))
    if "induction" in ht: ops.append(("Induction Hardening", "HT: induction"))

    # Finish / surface treatment
    fin = (str(mat_treat.get("finish","")) + " " + str(tb.get("finish",""))).lower()
    if "phosphat" in fin:           ops.append(("Phosphating", "Finish: phosphating"))
    if "zinc" in fin or "plat" in fin: ops.append(("Plating",  "Finish: zinc/plating"))
    if "blackod" in fin:            ops.append(("Blackodizing","Finish: blackodizing"))

    # Surface Ra
    ra = _min_ra(data)
    if ra is not None:
        if ra <= 0.8:
            ops += [("Grinding - Gear", f"Ra≤0.8µm ({ra})"),("Grinding - CNC", f"Ra≤0.8µm ({ra})")]
        elif ra <= 3.2:
            ops.append(("Finish Turning", f"Ra≤3.2µm ({ra})"))

    # GD&T tolerances
    for t in data.get("geometric_tolerances", []):
        tt = t.get("tolerance_type","").lower()
        if "runout" in tt or "cylindricity" in tt:
            ops += [("Grinding - Gear","GD&T runout/cylindricity"),("Grinding - CNC","GD&T runout/cylindricity")]

    # Bore fit H7/H8
    for d in data.get("dimensions", []):
        if d.get("id") == "dim_bore":
            tol = str(d.get("tolerance","")).upper()
            if "H7" in tol or "H8" in tol:
                ops += [("Drilling / Boring","Bore dim"),("Internal Grinding",f"Bore fit {tol}")]

    # Features
    for feat in data.get("features", []):
        if feat.get("type","").lower() == "keyway":        ops.append(("Broaching","Feature: keyway"))
        if feat.get("type","").lower() == "internal_spline":
            ops += [("Gear Shaping","Feature: internal_spline"),("Broaching","Feature: internal_spline")]

    # Manufacturing notes
    for note in data.get("manufacturing_notes", []):
        nt = note.get("note_text","").lower()
        if "peen"    in nt: ops.append(("Shot Peening",   f"Note: {note.get('note_text')}"))
        if "deburr"  in nt: ops.append(("Deburring",      "Note: deburring"))
        if "grind"   in nt: ops.append(("Grinding - Gear","Note: grinding"))
        if "inspect" in nt: ops.append(("Final Inspection","Note: inspect"))

    # Quality class
    qc = str(_tbl(data,"tbl_gear_data","QUALITY CLASS") or "").upper()
    if "DIN 6" in qc or "DIN6" in qc:
        ops.append(("Grinding - Gear","DIN 6 → fine grinding"))

    # De-duplicate
    seen, seq, evidence = set(), [], []
    for name, reason in ops:
        if name not in seen:
            seen.add(name)
            seq.append(name)
            t = _op_tmpl(name)
            evidence.append({"operation":name,"reason":reason,
                              "time_min":t["time"],"rate":t["rate"],"machines":t["machines"]})

    return {"gear_family": gear_family, "operations_sequence": seq, "operations_evidence": evidence}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — VOLUME CALCULATION
# ══════════════════════════════════════════════════════════════════════════════
def step2_volume(data):
    """Step 2 — CSG Volume or fallback dim-ID method"""
    dims = {d["id"]: float(d.get("value",0) or 0) for d in data.get("dimensions",[]) if d.get("value") is not None}
    tables = data.get("tables", [])
    feats  = {f["id"]: f for f in data.get("features", [])}
    asm    = data.get("assembly_order", [])

    axial_stack = dims.get("dim_hub_height") or dims.get("dim_face_width") or 0.0

    def feat_vol(feat):
        ft = feat.get("type","").lower()
        od   = dims.get("dim_outer_dia",0)
        fw   = dims.get("dim_face_width",0)
        hd   = dims.get("dim_hub_dia",0)
        hh   = dims.get("dim_hub_height", fw)
        bore = dims.get("dim_bore",0)

        if ft == "cylindrical_rim":
            return math.pi * (od/2)**2 * fw
        if ft == "cylindrical_step":
            ext = max(hh - fw, 0)
            return math.pi * (hd/2)**2 * ext
        if ft == "cylindrical_bore":
            return math.pi * (bore/2)**2 * axial_stack
        if ft == "internal_spline":
            major = None
            for tbl in tables:
                if tbl.get("id","").lower() == "tbl_spline_data":
                    for c in tbl.get("cells",[]):
                        if c.get("label","").strip().upper() == "MAJOR DIAMETER":
                            try: major = float(c.get("value",0))
                            except: pass
            major = major or bore
            return math.pi * (major/2)**2 * axial_stack
        if ft == "keyway":
            ids = feat.get
            # keyway volume is small — skip for now
            return 0.0
        return 0.0

    breakdown = []

    if asm:
        net = 0.0
        for step in asm:
            fid = step.get("feature_id")
            op  = step.get("op","revolve").lower()
            f   = feats.get(fid)
            if not f: continue
            v = feat_vol(f)
            net += v if op == "revolve" else -v
            # processes from feature
            key = (f.get("type","").lower(), f.get("role","").lower())
            procs = FEATURE_PROCESS_MAP.get(key, FEATURE_PROCESS_MAP.get((f.get("type","").lower(),"*"), []))
            breakdown.append({"feature_id":fid,"type":f.get("type"),"role":f.get("role"),
                               "csg_op":op,"volume_mm3":round(v,2),"processes":procs})
        method = "csg_assembly_order"
    else:
        # Fallback
        od   = dims.get("dim_outer_dia",0)
        fw   = dims.get("dim_face_width",0)
        hd   = dims.get("dim_hub_dia",0)
        hh   = dims.get("dim_hub_height", fw)
        bore = dims.get("dim_bore",0)
        ext  = max(hh - fw, 0)

        rim_v  = math.pi * (od/2)**2 * fw   if od and fw   else 0
        hub_v  = math.pi * (hd/2)**2 * ext  if hd and ext  else 0
        bore_v = math.pi * (bore/2)**2 * hh if bore and hh else 0

        major = None
        for tbl in tables:
            if tbl.get("id","").lower() == "tbl_spline_data":
                for c in tbl.get("cells",[]):
                    if c.get("label","").strip().upper() == "MAJOR DIAMETER":
                        try: major = float(c.get("value",0))
                        except: pass
        spline_v = math.pi * (major/2)**2 * hh if major and hh else 0

        net = rim_v + hub_v - bore_v - spline_v
        breakdown = [
            {"feature":"rim",    "csg_op":"revolve",  "volume_mm3":round(rim_v,2)},
            {"feature":"hub",    "csg_op":"revolve",  "volume_mm3":round(hub_v,2)},
            {"feature":"bore",   "csg_op":"subtract", "volume_mm3":round(bore_v,2)},
        ]
        if spline_v: breakdown.append({"feature":"spline","csg_op":"subtract","volume_mm3":round(spline_v,2)})
        method = "dim_id_fallback"

    net_cm3 = max(net, 1000.0) / 1000.0
    return {"net_volume_mm3": round(net,2), "net_volume_cm3": round(net_cm3,4),
            "method": method, "feature_breakdown": breakdown}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — MATERIAL COST
# ══════════════════════════════════════════════════════════════════════════════
def step3_material(data, net_volume_cm3):
    """Step 3 — Fuzzy material match → mass → cost"""
    tb  = data.get("metadata",{}).get("title_block",{})
    mt  = data.get("material_and_treatment",{})
    txt = (tb.get("material") or mt.get("base_material") or "").lower()

    matched_key, density, rate, pattern = "default-steel", 7.85, 4.00, None
    for key, props in MATERIAL_PROPERTIES.items():
        if key == "default-steel": continue
        for p in props["patterns"]:
            if p in txt:
                matched_key, density, rate, pattern = key, props["density"], props["rate"], p
                break
        if pattern: break

    mass_kg  = net_volume_cm3 * density / 1000.0
    cost     = round(mass_kg * rate, 2)
    return {"matched_material":matched_key, "matched_pattern":pattern,
            "density_g_cm3":density, "rate_per_kg":rate,
            "net_volume_cm3":net_volume_cm3, "mass_kg":round(mass_kg,4), "cost":cost}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — OPERATIONS COST
# ══════════════════════════════════════════════════════════════════════════════
def step4_operations(data, gear_family, gear_rule_ops):
    """Step 4 — Merge gear_rule ops + feature_map ops → per-op cost"""
    seen, ordered = set(), []

    # Source A — gear_rule (WHY)
    for op in gear_rule_ops:
        if op not in seen:
            seen.add(op); ordered.append((op,"gear_rule"))

    # Source B — feature map (HOW)
    for feat in data.get("features",[]):
        ft   = feat.get("type","").lower()
        role = feat.get("role","").lower()
        key  = (ft, role)
        procs = FEATURE_PROCESS_MAP.get(key, FEATURE_PROCESS_MAP.get((ft,"*"), []))
        # H7/H8 bore
        if ft == "cylindrical_bore":
            fit = feat.get("fit","")
            if "H7" in fit.upper() or "H8" in fit.upper():
                procs = procs + ["Internal Grinding"]
        for op in procs:
            if op not in seen:
                seen.add(op); ordered.append((op,"feature_map"))

    # Bore dim tolerance check
    for d in data.get("dimensions",[]):
        if d.get("id") == "dim_bore":
            tol = str(d.get("tolerance","")).upper()
            if ("H7" in tol or "H8" in tol) and "Internal Grinding" not in seen:
                seen.add("Internal Grinding"); ordered.append(("Internal Grinding","dim_tolerance"))

    result = []
    for i, (op_name, src) in enumerate(ordered, 1):
        tmpl = _op_tmpl(op_name)
        cost = round((tmpl["time"] / 60.0) * tmpl["rate"], 2)
        result.append({"step":i, "operation":op_name,
                        "estimated_time_min":tmpl["time"],
                        "rate_per_hour":tmpl["rate"],
                        "cost":cost,
                        "machine_options":tmpl["machines"],
                        "source":src})
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — COST BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════
def step5_breakdown(mat_cost, ops_detail, overhead_pct=15.0, margin_pct=20.0, currency="USD"):
    """Step 5 — material + ops + overhead% + margin% = TOTAL"""
    ops_cost = sum(o["cost"] for o in ops_detail)
    overhead = (mat_cost + ops_cost) * overhead_pct / 100.0
    subtotal = mat_cost + ops_cost + overhead
    margin   = subtotal * margin_pct / 100.0
    total    = subtotal + margin
    return {
        "material_cost":   round(mat_cost, 2),
        "operations_cost": round(ops_cost, 2),
        "overhead_pct":    overhead_pct,
        "overhead_cost":   round(overhead, 2),
        "subtotal":        round(subtotal, 2),
        "margin_pct":      margin_pct,
        "margin_cost":     round(margin, 2),
        "total_cost":      round(total, 2),
        "currency":        currency,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — VALIDATION  (key rules only — confidence score)
# ══════════════════════════════════════════════════════════════════════════════
def step6_validate(data, volume_result, mat_info, cost_breakdown, ops_detail):
    """Step 6 — Validation rules → confidence score"""
    rules  = []
    score  = 100

    def rule(rid, layer, sev, passed, msg):
        nonlocal score
        rules.append({"rule_id":rid,"layer":layer,"severity":sev,"passed":passed,"message":msg})
        if not passed:
            if sev == "ERROR": score -= 20
            elif sev == "WARN": score -= 5

    dims   = {d["id"]: float(d.get("value",0) or 0) for d in data.get("dimensions",[]) if d.get("value") is not None}
    od     = dims.get("dim_outer_dia")
    fw     = dims.get("dim_face_width")
    hd     = dims.get("dim_hub_dia")
    hh     = dims.get("dim_hub_height")
    bore   = dims.get("dim_bore")
    mod    = _tbl(data,"tbl_gear_data","MODULE")
    teeth  = _tbl(data,"tbl_gear_data","NO OF TEETH")
    helix  = _tbl(data,"tbl_gear_data","HELIX ANGLE")
    press  = _tbl(data,"tbl_gear_data","PRESSURE ANGLE")
    mass   = mat_info.get("mass_kg",0)
    total  = cost_breakdown.get("total_cost",0)
    method = volume_result.get("method","")

    # ── Layer 1: Geometric Physics ───────────────────────────────────────────
    if mod and teeth and od:
        pd = float(mod)*float(teeth)
        rule("G1",1,"ERROR", od > pd, f"OD({od}) {'>' if od>pd else '≤'} pitch_dia({pd:.1f})")
    if hh is not None and fw is not None:
        rule("G2",1,"ERROR", hh >= fw, f"hub_height({hh}) {'≥' if hh>=fw else '<'} face_width({fw})")
    if bore and hd and od:
        rule("G3",1,"ERROR", bore < hd < od, f"bore({bore}) < hub_dia({hd}) < OD({od}): {'OK' if bore<hd<od else 'FAIL'}")
    if fw and od and od > 0:
        r = fw/od
        rule("G4",1,"WARN", 0.05<=r<=0.8, f"face_width/OD={r:.3f} (expected 0.05–0.8)")
    if mod and teeth and od:
        exp_od = (float(teeth)+2)*float(mod)
        diff   = abs(od-exp_od)/exp_od*100 if exp_od else 0
        rule("G6",1,"WARN", diff<=8, f"OD({od}) vs expected({exp_od:.1f}): {diff:.1f}% (limit 8%)")
    if hd and bore:
        rule("G7",1,"ERROR", hd > bore, f"hub_dia({hd}) {'>' if hd>bore else '≤'} bore({bore})")

    # ── Layer 2: Material Science ────────────────────────────────────────────
    rule("M2",2,"WARN", mass > 0, f"mass={mass:.3f} kg")
    dw = data.get("metadata",{}).get("title_block",{}).get("weight_kg")
    if dw:
        try:
            diff = abs(mass-float(dw))/float(dw)*100 if float(dw) else 0
            rule("M4",2,"WARN", diff<=25, f"calc={mass:.2f}kg vs drawing={dw}kg ({diff:.1f}%)")
        except: pass

    # ── Layer 3: Manufacturing Feasibility ───────────────────────────────────
    if mod is not None:
        rule("MF1",3,"WARN", 0.3<=float(mod)<=50, f"module={mod} (0.3–50)")
    if teeth is not None:
        rule("MF2",3,"WARN", int(teeth)>=8, f"teeth={int(teeth)} (min 8, undercut risk)")
    if press is not None:
        try:
            pa = float(str(press).replace("°",""))
            rule("MF5",3,"WARN", pa in (14.5,20.0,25.0), f"pressure angle={pa}° (must be 14.5/20/25)")
        except: pass

    # ── Layer 4: Data Completeness ───────────────────────────────────────────
    rule("C1",4,"ERROR", od is not None,  "dim_outer_dia " + ("present" if od else "MISSING"))
    rule("C2",4,"ERROR", fw is not None,  "dim_face_width " + ("present" if fw else "MISSING"))
    rule("C3",4,"WARN",  mat_info.get("matched_material","default-steel") != "default-steel",
         f"material={mat_info.get('matched_material')}")
    rule("C4",4,"WARN",  mod is not None, "MODULE " + ("found" if mod else "MISSING in tbl_gear_data"))
    rule("C7",4,"WARN",  method=="csg_assembly_order",
         "assembly_order: " + ("CSG used" if method=="csg_assembly_order" else "MISSING — fallback dim method"))

    # ── Layer 5: Cross-Consistency ───────────────────────────────────────────
    if hh is not None and fw is not None:
        rule("X2",5,"WARN", hh>=fw, f"hub_height({hh}) ≥ face_width({fw})")
    rule("X4",5,"INFO",  method=="csg_assembly_order",
         "Volume method: " + method)

    # ── Layer 6: Cost Plausibility ───────────────────────────────────────────
    rule("CP1",6,"WARN", total>0, f"total={total}")
    if total>0:
        mp = cost_breakdown.get("material_cost",0)/total*100
        rule("CP2",6,"WARN", 10<=mp<=75, f"material%={mp:.1f}% (10–75%)")
    bad = [o for o in ops_detail if not (15<=o.get("rate_per_hour",0)<=800)]
    rule("CP3",6,"WARN", len(bad)==0, f"{len(bad)} ops with out-of-range rates")
    if mass>0:
        cpk = total/mass
        rule("CP4",6,"WARN", 1<=cpk<=5000, f"cost/kg=${cpk:.2f} (1–5000)")
    rule("CP5",6,"WARN", 5<=cost_breakdown.get("overhead_pct",15)<=50,
         f"overhead={cost_breakdown.get('overhead_pct')}%")
    rule("CP6",6,"WARN", len(ops_detail)>0, f"{len(ops_detail)} operations")

    # Confidence score adjustments
    if od is None:  score -= 15
    if fw is None:  score -= 10
    if mat_info.get("matched_material","default-steel") == "default-steel": score -= 10
    if method != "csg_assembly_order": score -= 10
    score = max(0, score)

    errors = sum(1 for r in rules if not r["passed"] and r["severity"]=="ERROR")
    warns  = sum(1 for r in rules if not r["passed"] and r["severity"]=="WARN")
    level  = "HIGH" if score>=85 else "MEDIUM" if score>=65 else "LOW"
    quote  = score >= 65

    return {"validation_passed": errors==0, "confidence_score": score,
            "confidence_level": level, "ready_for_quote": quote,
            "error_count": errors, "warn_count": warns, "rules": rules}


# ══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(data, overhead_pct=15.0, margin_pct=20.0, currency="USD"):
    s1  = step1_classify(data)
    s2  = step2_volume(data)
    s3  = step3_material(data, s2["net_volume_cm3"])
    s4  = step4_operations(data, s1["gear_family"], s1["operations_sequence"])
    s5  = step5_breakdown(s3["cost"], s4, overhead_pct, margin_pct, currency)
    s6  = step6_validate(data, s2, s3, s5, s4)
    return {"gear_family":s1["gear_family"], "volume":s2, "material_info":s3,
            "operations_detail":s4, "cost_breakdown":s5, "validation_report":s6}


# ══════════════════════════════════════════════════════════════════════════════
# PRETTY PRINT
# ══════════════════════════════════════════════════════════════════════════════
def print_report(r):
    cb  = r["cost_breakdown"]
    val = r["validation_report"]
    mat = r["material_info"]
    vol = r["volume"]

    print("\n" + "="*62)
    print("  GEAR COST ESTIMATION REPORT")
    print("="*62)

    print(f"\n{'STEP 1 — GEAR CLASSIFICATION':}")
    print(f"  Gear Family   : {r['gear_family'].upper()}")

    print(f"\nSTEP 2 — VOLUME")
    print(f"  Method        : {vol['method']}")
    print(f"  Net Volume    : {vol['net_volume_mm3']:,.2f} mm³  =  {vol['net_volume_cm3']:.4f} cm³")
    for fb in vol.get("feature_breakdown", []):
        name = fb.get("feature_id") or fb.get("feature","?")
        sign = "+" if fb["csg_op"]=="revolve" else "−"
        print(f"    {sign} {name:<25} {fb['volume_mm3']:>12,.2f} mm³")

    print(f"\nSTEP 3 — MATERIAL")
    print(f"  Material      : {mat['matched_material']}  (matched: '{mat['matched_pattern']}')")
    print(f"  Density       : {mat['density_g_cm3']} g/cm³")
    print(f"  Rate          : ${mat['rate_per_kg']}/kg")
    print(f"  Mass          : {mat['mass_kg']:.4f} kg")
    print(f"  Material Cost : ${mat['cost']:.2f}")

    print(f"\nSTEP 4 — OPERATIONS")
    print(f"  {'#':<3} {'Operation':<26} {'Min':>4} {'$/hr':>6} {'Cost':>8}  Source")
    print(f"  {'-'*3} {'-'*26} {'-'*4} {'-'*6} {'-'*8}  {'-'*12}")
    for op in r["operations_detail"]:
        print(f"  {op['step']:<3} {op['operation']:<26} {op['estimated_time_min']:>4} "
              f"${op['rate_per_hour']:>5} ${op['cost']:>7.2f}  {op['source']}")

    print(f"\nSTEP 5 — COST BREAKDOWN")
    print(f"  Material Cost    : ${cb['material_cost']:>9.2f}")
    print(f"  Operations Cost  : ${cb['operations_cost']:>9.2f}")
    print(f"  Overhead ({cb['overhead_pct']}%)   : ${cb['overhead_cost']:>9.2f}")
    print(f"  Subtotal         : ${cb['subtotal']:>9.2f}")
    print(f"  Margin ({cb['margin_pct']}%)      : ${cb['margin_cost']:>9.2f}")
    print(f"  {'─'*32}")
    print(f"  TOTAL            : ${cb['total_cost']:>9.2f} {cb['currency']}")

    print(f"\nSTEP 6 — VALIDATION")
    icon = "✅" if val["confidence_level"]=="HIGH" else "⚠️ " if val["confidence_level"]=="MEDIUM" else "❌"
    print(f"  Confidence Score : {val['confidence_score']}/100  →  {icon} {val['confidence_level']}")
    print(f"  Ready for Quote  : {'YES' if val['ready_for_quote'] else 'NO'}")
    print(f"  Errors : {val['error_count']}   Warnings : {val['warn_count']}")
    failed = [r for r in val["rules"] if not r["passed"]]
    if failed:
        print(f"\n  Failed Rules:")
        for ru in failed:
            icon2 = "🔴" if ru["severity"]=="ERROR" else "🟡" if ru["severity"]=="WARN" else "🔵"
            print(f"    {icon2} [{ru['rule_id']}] {ru['message']}")
    print("="*62 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA  (matches spec example: OD=168, face_w=45, hub=90, hub_h=54, bore=58)
# ══════════════════════════════════════════════════════════════════════════════
SAMPLE_DATA = {
    "dimensions": [
        {"id": "dim_outer_dia",   "value": 168.0, "unit": "mm", "tolerance": "±0.05"},
        {"id": "dim_face_width",  "value": 45.0,  "unit": "mm"},
        {"id": "dim_hub_dia",     "value": 90.0,  "unit": "mm"},
        {"id": "dim_hub_height",  "value": 54.0,  "unit": "mm"},
        {"id": "dim_bore",        "value": 58.0,  "unit": "mm", "tolerance": "H7"},
    ],
    "features": [
        {"id":"feat_rim",    "type":"cylindrical_rim",  "role":"gear_tip",    "outer_diameter_dim_ids":["dim_outer_dia"], "face_width_dim_ids":["dim_face_width"]},
        {"id":"feat_hub",    "type":"cylindrical_step", "role":"hub_outer",   "diameter_dim_ids":["dim_hub_dia"]},
        {"id":"feat_bore",   "type":"cylindrical_bore", "role":"through_bore","diameter_dim_ids":["dim_bore"], "fit":"H7"},
    ],
    "assembly_order": [
        {"op":"revolve",  "feature_id":"feat_rim"},
        {"op":"revolve",  "feature_id":"feat_hub"},
        {"op":"subtract", "feature_id":"feat_bore"},
    ],
    "tables": [
        {"id":"tbl_gear_data","cells":[
            {"label":"MODULE",         "value": 3},
            {"label":"NO OF TEETH",    "value": 52},
            {"label":"HELIX ANGLE",    "value": 0},
            {"label":"PRESSURE ANGLE", "value": 20},
            {"label":"ADDENDUM",       "value": 3},
            {"label":"QUALITY CLASS",  "value": "DIN 6"},
        ]}
    ],
    "metadata": {"title_block": {
        "material":        "20MnCr5",
        "weight_kg":       3.2,
        "heat_treatment":  "Case Carburized",
        "drawing_no":      "GF-2024-001",
        "part_name":       "Spur Gear",
    }},
    "material_and_treatment": {
        "base_material":        "20MnCr5",
        "heat_treatment":       "Case Carburized 58-62 HRC",
        "case_depth_mm":        0.8,
        "hardness_requirement": "58-62 HRC",
        "finish":               "Black phosphate",
    },
    "manufacturing_notes": [
        {"note_text": "Gear to be ground to DIN Quality Class 6"},
        {"note_text": "All burrs to be deburred"},
        {"note_text": "Inspect with CMM after grinding"},
    ],
    "geometric_tolerances": [
        {"tolerance_type":"runout","tolerance_value":"0.02 mm","datum":"A"},
    ],
    "surface_specifications": [
        {"roughness_value":"Ra 0.8 µm","location":"Tooth flanks"},
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Gear Cost Estimator — standalone runner")
    parser.add_argument("--json",  help="Path to extracted_data JSON file")
    parser.add_argument("--image", help="Path to drawing image (requires GOOGLE_API_KEY in .env)")
    parser.add_argument("--overhead", type=float, default=15.0, help="Overhead %% (default 15)")
    parser.add_argument("--margin",   type=float, default=20.0, help="Margin %% (default 20)")
    args = parser.parse_args()

    if args.json:
        print(f"\nLoading extracted data from: {args.json}")
        with open(args.json) as f:
            raw = json.load(f)
        # Support both {"extracted_data": {...}} wrapper and raw dict
        data = raw.get("extracted_data", raw)

    elif args.image:
        print(f"\nUploading image to Gemini: {args.image}")
        try:
            # Load .env
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass

            # Try importing Gemini service from existing codebase
            try:
                from app.service.techinalDrawingService import extract_drawing_data
                data = extract_drawing_data(args.image)
                print("Gemini extraction complete.")
            except ImportError:
                print("ERROR: Could not import techinalDrawingService.")
                print("Make sure GOOGLE_API_KEY is set in .env and the server dependencies are installed.")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR during Gemini extraction: {e}")
            sys.exit(1)

    else:
        print("\nNo --json or --image provided. Running with built-in sample data.")
        print("(Spec example: OD=168mm, 20MnCr5, Case Carburized, DIN 6)")
        data = SAMPLE_DATA

    result = run_pipeline(data, overhead_pct=args.overhead, margin_pct=args.margin)
    print_report(result)

    # Also save JSON output
    out_path = "cost_result.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Full JSON result saved to: {out_path}\n")


if __name__ == "__main__":
    main()