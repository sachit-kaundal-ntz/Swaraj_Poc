# # gear_rule_engine.py

# import re
# from typing import Any, Dict, List, Tuple, Optional

# def _lower(x: Optional[str]) -> str:
#     return (x or "").lower()

# def _num(s: Any) -> Optional[float]:
#     if s is None: return None
#     try:
#         return float(re.findall(r"[-+]?\d+(?:\.\d+)?", str(s))[0])
#     except Exception:
#         return None

# def _walk_texts(j: Dict) -> List[str]:
#     texts = []
#     xd = j.get("extracted_data", {})

#     md = xd.get("drawing_metadata", {}) or {}
#     if isinstance(md, dict):
#         texts += [md.get("part_name",""), md.get("drawing_number",""), md.get("component_type","")]
#     elif isinstance(md, str):
#         texts.append(md)

#     for n in xd.get("manufacturing_notes", []) or []:
#         if isinstance(n, dict):
#             texts.append(n.get("note_text",""))
#         elif isinstance(n, str):
#             texts.append(n)

#     for s in xd.get("surface_specifications", []) or []:
#         if isinstance(s, dict):
#             texts += [s.get("surface_symbol",""), s.get("machining_requirement","")]
#         elif isinstance(s, str):
#             texts.append(s)

#     mat = xd.get("material_and_treatment", {})
#     if isinstance(mat, dict):
#         texts += [mat.get("base_material",""), mat.get("heat_treatment",""), mat.get("finish","")]
#     elif isinstance(mat, str):
#         texts.append(mat)

#     for f in xd.get("feature_dimensions", []) or []:
#         if isinstance(f, dict):
#             texts += [f.get("feature_type",""), f.get("feature_description",""), f.get("specification","")]
#         elif isinstance(f, str):
#             texts.append(f)

#     for v in xd.get("section_views", []) or []:
#         if isinstance(v, dict):
#             texts.append(v.get("section_identifier",""))
#         elif isinstance(v, str):
#             texts.append(v)

#     return [t for t in texts if t]

# def _get_overall_OD_H(j: Dict) -> Tuple[Optional[float], Optional[float]]:
#     xd = j.get("extracted_data", {}) or {}
#     od = _num(xd.get("overall_dimensions", {}).get("diameter", {}).get("value"))
#     ln = _num(xd.get("overall_dimensions", {}).get("length", {}).get("value"))
#     # fallbacks from geometric_decomposition
#     if od is None or ln is None:
#         bases = xd.get("geometric_decomposition", {}).get("base_shapes", []) or []
#         if bases:
#             dims = bases[0].get("dimensions", {}) or {}
#             if od is None:
#                 od = _num(dims.get("main_outer_diameter","") or (dims.get("main_outer_diameter",{}) or {}).get("value"))
#             if ln is None:
#                 ln = _num(dims.get("total_height","") or (dims.get("total_height",{}) or {}).get("value"))
#     return od, ln

# def _get_helix_angle(j: Dict) -> Optional[float]:
#     # Try to find an explicit helix angle in feature specs or tables
#     xd = j.get("extracted_data", {}) or {}
#     for f in xd.get("feature_dimensions", []) or []:
#         for k in ("feature_description","specification"):
#             txt = _lower(f.get(k))
#             if "helix" in txt or "β" in txt or "spiral angle" in txt:
#                 vals = re.findall(r"[-+]?\d+(?:\.\d+)?", txt)
#                 if vals: return float(vals[0])
#     # Some drawings place helix in tables_and_data
#     for t in xd.get("tables_and_data", []) or []:
#         for row in t.get("table_data", []) or []:
#             for cell in row.values():
#                 ct = _lower(str(cell))
#                 if any(w in ct for w in ["helix","spiral angle","β"]):
#                     vals = re.findall(r"[-+]?\d+(?:\.\d+)?", ct)
#                     if vals: return float(vals[0])
#     return None

# def _has_internal_teeth(j: Dict) -> bool:
#     """Detect internal gear: inward-facing teeth / internal ring."""
#     texts = " ".join(_walk_texts(j)).lower()
#     if any(w in texts for w in ["internal gear","ring gear","annular gear","inner teeth","inward-facing teeth"]):
#         return True
#     # Geometry hint: a ring-like blank with subtracted inner tooth form
#     xd = j.get("extracted_data", {}) or {}
#     # Internal tooth processes (shaping/skiving/broaching) frequently appear in notes/specs
#     if any(w in texts for w in ["gear shaping","power skiving","internal broach"]):
#         return True
#     return False

# def _looks_bevel(j: Dict) -> Tuple[bool, Optional[str]]:
#     """Detect straight vs spiral bevel by text & hints (conical body, intersecting shafts)."""
#     texts = " ".join(_walk_texts(j)).lower()
#     if "bevel" in texts:
#         if any(w in texts for w in ["straight bevel","straight tooth"]):
#             return True, "straight bevel"
#         if any(w in texts for w in ["spiral bevel","zerol","hypoid"]):
#             return True, "spiral bevel"
#         # If unspecified, default to 'bevel'
#         return True, "bevel"
#     # Conical cues (rarely explicit in extraction without the word 'bevel')
#     return False, None

# def _looks_cluster(j: Dict) -> bool:
#     """Detect multiple gear sections on one shaft/hub."""
#     texts = " ".join(_walk_texts(j)).lower()
#     if "cluster gear" in texts:
#         return True
#     # Heuristic: multiple gear segments present in features
#     gears = 0
#     for f in j.get("extracted_data", {}).get("feature_dimensions", []) or []:
#         desc = _lower(f.get("feature_description"))
#         if "gear" in desc or "tooth" in desc:
#             gears += 1
#     return gears >= 2

# def _looks_bull(j: Dict) -> bool:
#     """Detect bull gear (very large driven gear)."""
#     texts = " ".join(_walk_texts(j)).lower()
#     if "bull gear" in texts:
#         return True
#     # Heuristic size threshold
#     od, _ = _get_overall_OD_H(j)
#     return bool(od and od >= 600.0)  # adjust threshold to your domain

# def classify_gear_family(j: Dict) -> Tuple[str, Dict[str,str]]:
#     """
#     Returns (gear_family, evidence_map).
#     gear_family in {"spur","helical","straight bevel","spiral bevel","bevel","internal","cluster","bull","unknown"}
#     """
#     ev = {}
#     # Priority: internal & bevel & cluster/bull (mutually distinctive) before spur/helical
#     if _has_internal_teeth(j):
#         ev["family"] = "Detected internal-gear cues (ring/inner teeth/shaping/skiving)"
#         return "internal", ev
#     looks_bev, bev_type = _looks_bevel(j)
#     if looks_bev:
#         ev["family"] = f"Detected {bev_type or 'bevel'} by text cues"
#         return bev_type or "bevel", ev
#     if _looks_cluster(j):
#         ev["family"] = "Multiple gear segments / 'cluster gear' text"
#         return "cluster", ev
#     if _looks_bull(j):
#         ev["family"] = "Large OD or 'bull gear' text"
#         return "bull", ev

#     # Spur vs Helical (external): helix angle or keywords
#     texts = " ".join(_walk_texts(j)).lower()
#     helix = _get_helix_angle(j)
#     if helix is not None and helix > 0.2:
#         ev["family"] = f"Helix angle {helix}°"
#         return "helical", ev
#     if "helical" in texts:
#         ev["family"] = "Keyword 'helical'"
#         return "helical", ev
#     # default to spur if gear hints exist and no helix cues
#     if any(w in texts for w in ["gear","tooth","module","involute","hob"]):
#         ev["family"] = "Gear terms present; no helix cues → spur"
#         return "spur", ev

#     ev["family"] = "No clear gear cues"
#     return "unknown", ev

# # ---------- Operation inference ----------

# def infer_operations(j: Dict, gear_family: str) -> Tuple[List[str], Dict[str,str]]:
#     ops: List[str] = []
#     why: Dict[str,str] = {}
#     texts = " ".join(_walk_texts(j)).lower()
#     xd = j.get("extracted_data", {}) or {}

#     def add(op: str, reason: str):
#         if op not in ops:
#             ops.append(op); why[op] = reason

#     # 0) Universal prep
#     if "forge" in texts or "forging" in texts:
#         add("Forging", "Notes/material mention forging")
#     # If no explicit forging but it's a gear blank: allow heuristic
#     elif gear_family in {"spur","helical","straight bevel","spiral bevel","bevel","bull","cluster"}:
#         add("Forging", "Default blank preparation for steel gears")

#     # 1) Turning (rough/finish) if cylindrical bands exist
#     od, ln = _get_overall_OD_H(j)
#     if od and ln:
#         add("Rough Turning", "Cylindrical blank with overall OD/Length present")
#         # Surface roughness heuristic for finish turning
#         rough_vals = []
#         for s in xd.get("surface_specifications", []) or []:
#             rv = _lower(s.get("roughness_value"))
#             if rv:
#                 try:
#                     rough_vals += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", rv)]
#                 except: pass
#         if any(v <= 3.2 for v in rough_vals):
#             add("Finish Turning", "Surface roughness ≤ 3.2 µm on turned surfaces")

#     # 2) Tooth cutting per family
#     if gear_family in {"spur","helical","bull","cluster"}:
#         add("Gear Hobbing", f"{gear_family.title()} external teeth")
#     if gear_family == "internal":
#         # internal: shaping/skiving/broaching (rule per guide)
#         if any(k in texts for k in ["skiving","power skiving"]):
#             add("Power Skiving", "Internal gear note mentions skiving")
#         elif "broach" in texts:
#             add("Broaching", "Internal gear note mentions broach")
#         else:
#             add("Gear Shaping", "Internal teeth require shaping/skiving/broaching")
#     if "keyway" in texts or any((f.get("feature_type") or "").lower()=="keyway" for f in xd.get("feature_dimensions",[]) or []):
#         add("Broaching", "Keyway feature implies broach")

#     # 3) Chamfering on teeth/edges
#     if "chamfer" in texts:
#         add("Gear Tooth Chamfering", "Chamfer noted")
#     else:
#         # often implicit; add for external gears
#         if gear_family in {"spur","helical","bull","cluster"}:
#             add("Gear Tooth Chamfering", "Standard edge break for external teeth")

#     # 4) Heat treatment
#     ht = _lower(xd.get("material_and_treatment", {}).get("heat_treatment"))
#     if any(k in ht for k in ["carbur", "case hard"]):
#         add("Carburising", "Heat treatment notes")
#         add("Quenching", "Post-carburising hardening")
#         if "temper" in ht:
#             add("Tempering", "Heat treatment notes")
#         else:
#             add("Tempering", "Standard post-quench temper")
#     else:
#         if "harden" in ht: add("Hardening", "Heat treatment notes")
#         if "temper" in ht: add("Tempering", "Heat treatment notes")

#     # 5) Grinding based on roughness / GD&T / notes
#     tight = False
#     for g in xd.get("geometric_tolerances", []) or []:
#         t = _lower(g.get("tolerance_type"))
#         val = _lower(g.get("tolerance_value"))
#         if any(k in t for k in ["runout","circularity","cylindricity","profile","parallel","perpendicular"]):
#             tight = True
#     if tight or "grind" in texts:
#         if gear_family in {"internal","spur","helical","bull","cluster"}:
#             add("Grinding - Gear", "Tight tooth/geometry tolerance or notes")
#         add("Grinding - CNC", "Tight datum/OD/ID tolerance or notes")

#     # 6) Deburring post-cut
#     add("Deburring", "Standard post-cut operation")

#     # 7) Family-specific extras
#     if gear_family in {"straight bevel","spiral bevel","bevel"}:
#         # manufacturing per guide: forging → bevel cutting → heat treat → grinding/lapping
#         add("Bevel Gear Cutting", "Bevel gear family (milling/shaping)")
#         add("Lapping", "Bevel finishing (noise/surface)")

#     return ops, why

# def classify_and_plan(j: Dict) -> Dict[str, Any]:
#     family, family_ev = classify_gear_family(j)
#     ops, why_ops = infer_operations(j, family)
#     return {
#         "gear_family": family,
#         "evidence": family_ev,
#         "operations_sequence": ops,
#         "operations_evidence": why_ops
#     }

# """
# gear_rule.py
# Step 1 — Gear Classification
# Location: app/service/gear_rule.py

# Reads drawing text → gear family (spur/helical/bevel) + operations list.
# Entry point: classify_and_plan(extracted_data)
# """

# import math

# # ──────────────────────────────────────────────────────────────────────────────
# # Operation templates per gear family
# # Also used by cost_service for per-op cost lookup via _get_template()
# # ──────────────────────────────────────────────────────────────────────────────
# OPERATIONS_TEMPLATES = {
#     "spur": [
#         {"operation": "Forging",              "description": "Blank forging",                       "estimated_time_min": 15,  "rate_per_hour": 60,  "machine_options": ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"]},
#         {"operation": "Gear Hobbing",         "description": "Spur gear tooth cutting by hobbing",  "estimated_time_min": 25,  "rate_per_hour": 95,  "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
#         {"operation": "Helical Hobbing",      "description": "Helical gear tooth cutting",          "estimated_time_min": 35,  "rate_per_hour": 105, "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
#         {"operation": "Gear Tooth Chamfering","description": "Chamfer tooth edges",                 "estimated_time_min": 8,   "rate_per_hour": 45,  "machine_options": ["Gear Tooth Chamfering"]},
#         {"operation": "Chamfering",           "description": "General chamfering",                  "estimated_time_min": 8,   "rate_per_hour": 45,  "machine_options": ["Gear Tooth Chamfering"]},
#         {"operation": "Carburising",          "description": "Case carburising",                    "estimated_time_min": 90,  "rate_per_hour": 55,  "machine_options": ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"]},
#         {"operation": "Carbonitriding",       "description": "Carbonitriding",                      "estimated_time_min": 90,  "rate_per_hour": 55,  "machine_options": ["Carbonitriding Furnace"]},
#         {"operation": "Quenching",            "description": "Oil/water quench after carburising",  "estimated_time_min": 30,  "rate_per_hour": 55,  "machine_options": ["Carburising SQF", "Carburising Salt bath"]},
#         {"operation": "Tempering",            "description": "Stress relieve temper",               "estimated_time_min": 60,  "rate_per_hour": 55,  "machine_options": ["Tempering Furnace"]},
#         {"operation": "Hardening & Tempering","description": "Through hardening + temper",          "estimated_time_min": 90,  "rate_per_hour": 55,  "machine_options": ["Hardening & Tempering Furnace"]},
#         {"operation": "Nitriding",            "description": "Gas / plasma nitriding",              "estimated_time_min": 480, "rate_per_hour": 55,  "machine_options": ["Nitriding Furnace"]},
#         {"operation": "Induction Hardening",  "description": "Induction surface hardening",         "estimated_time_min": 20,  "rate_per_hour": 90,  "machine_options": ["Induction Hardening M/c"]},
#         {"operation": "Normalising",          "description": "Normalising",                         "estimated_time_min": 60,  "rate_per_hour": 45,  "machine_options": ["Normalising Furnace"]},
#         {"operation": "Annealing",            "description": "Annealing",                           "estimated_time_min": 60,  "rate_per_hour": 45,  "machine_options": ["Annealing Furnace"]},
#         {"operation": "Isothermal Annealing", "description": "Isothermal annealing",                "estimated_time_min": 90,  "rate_per_hour": 45,  "machine_options": ["Isothermal Annealing Furnace"]},
#         {"operation": "Gear Grinding",        "description": "Tooth flank profile grinding",        "estimated_time_min": 30,  "rate_per_hour": 120, "machine_options": ["Gear Grinding", "CNC Grinding"]},
#         {"operation": "Grinding - Gear",      "description": "Gear profile CNC grinding",           "estimated_time_min": 30,  "rate_per_hour": 120, "machine_options": ["Gear Grinding", "CNC Grinding"]},
#         {"operation": "Grinding - CNC",       "description": "CNC cylindrical / surface grinding",  "estimated_time_min": 30,  "rate_per_hour": 120, "machine_options": ["Gear Grinding", "CNC Grinding"]},
#         {"operation": "Internal Grinding",    "description": "Bore internal grinding for H7/H8 fit","estimated_time_min": 30,  "rate_per_hour": 120, "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
#         {"operation": "Grinding",             "description": "General grinding",                    "estimated_time_min": 25,  "rate_per_hour": 100, "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
#         {"operation": "Rough Turning",        "description": "OD rough turning",                    "estimated_time_min": 18,  "rate_per_hour": 75,  "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
#         {"operation": "Finish Turning",       "description": "OD finish turning",                   "estimated_time_min": 12,  "rate_per_hour": 80,  "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
#         {"operation": "Turning",              "description": "General turning / groove",            "estimated_time_min": 15,  "rate_per_hour": 75,  "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
#         {"operation": "Drilling / Boring",    "description": "Bore drilling or boring",             "estimated_time_min": 10,  "rate_per_hour": 70,  "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
#         {"operation": "Drilling",             "description": "Drilling",                            "estimated_time_min": 10,  "rate_per_hour": 70,  "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
#         {"operation": "Gun Drilling",         "description": "Deep-hole gun drilling",              "estimated_time_min": 20,  "rate_per_hour": 85,  "machine_options": ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"]},
#         {"operation": "Gear Shaping",         "description": "Internal/external gear shaping",      "estimated_time_min": 55,  "rate_per_hour": 110, "machine_options": ["Gear Shaping Conventional"]},
#         {"operation": "Gear Shaving",         "description": "Gear tooth shaving",                  "estimated_time_min": 20,  "rate_per_hour": 95,  "machine_options": ["Gear Shaving CNC", "Gear Shaving Conventional"]},
#         {"operation": "Broaching",            "description": "Keyway / spline broaching",           "estimated_time_min": 10,  "rate_per_hour": 70,  "machine_options": ["Horizontal Broaching", "Vertical Broaching"]},
#         {"operation": "Threading",            "description": "Thread cutting",                      "estimated_time_min": 10,  "rate_per_hour": 70,  "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC"]},
#         {"operation": "Shot Peening",         "description": "Shot peen tooth roots",               "estimated_time_min": 20,  "rate_per_hour": 60,  "machine_options": ["Shot Peening"]},
#         {"operation": "Shot Blasting",        "description": "Shot blasting",                       "estimated_time_min": 10,  "rate_per_hour": 40,  "machine_options": ["Shot Blasting"]},
#         {"operation": "Phosphating",          "description": "Black phosphate coating",             "estimated_time_min": 30,  "rate_per_hour": 45,  "machine_options": ["Phosphating Tank"]},
#         {"operation": "Plating",              "description": "Zinc / electroplating",              "estimated_time_min": 45,  "rate_per_hour": 50,  "machine_options": ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"]},
#         {"operation": "Blackodizing",         "description": "Black oxide coating",                 "estimated_time_min": 30,  "rate_per_hour": 40,  "machine_options": ["Blackodizing Furnace"]},
#         {"operation": "Powder Coating",       "description": "Powder coating",                     "estimated_time_min": 25,  "rate_per_hour": 40,  "machine_options": ["Powder Coating"]},
#         {"operation": "Primer Coating / Painting", "description": "Primer / painting",             "estimated_time_min": 20,  "rate_per_hour": 35,  "machine_options": ["Primer Coating", "Painting cum primer"]},
#         {"operation": "Final Inspection",     "description": "CMM / Magnaflux inspection",          "estimated_time_min": 15,  "rate_per_hour": 85,  "machine_options": ["Magnaflux", "Manual"]},
#         {"operation": "Inspection",           "description": "General inspection",                  "estimated_time_min": 15,  "rate_per_hour": 85,  "machine_options": ["Magnaflux", "Manual"]},
#         {"operation": "Deburring",            "description": "Remove all burrs",                    "estimated_time_min": 6,   "rate_per_hour": 40,  "machine_options": ["Manual Deburring"]},
#     ],
#     "helical": [],
#     "bevel":   [],
# }

# # Helical: copy spur but swap "Gear Hobbing" → "Helical Hobbing"
# _helical = []
# for _op in OPERATIONS_TEMPLATES["spur"]:
#     if _op["operation"] == "Gear Hobbing":
#         _helical.append({
#             "operation": "Helical Hobbing",
#             "description": "Helical gear tooth cutting",
#             "estimated_time_min": 35,
#             "rate_per_hour": 105,
#             "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"],
#         })
#     else:
#         _helical.append(_op.copy())
# OPERATIONS_TEMPLATES["helical"] = _helical
# OPERATIONS_TEMPLATES["bevel"]   = [op.copy() for op in OPERATIONS_TEMPLATES["spur"]]


# # ──────────────────────────────────────────────────────────────────────────────
# # Internal helpers
# # ──────────────────────────────────────────────────────────────────────────────

# def _get_all_text(extracted_data: dict) -> str:
#     parts = []
#     def _walk(obj):
#         if isinstance(obj, str):
#             parts.append(obj.lower())
#         elif isinstance(obj, dict):
#             for v in obj.values():
#                 _walk(v)
#         elif isinstance(obj, list):
#             for item in obj:
#                 _walk(item)
#     _walk(extracted_data)
#     return " ".join(parts)


# def _get_table_cell(extracted_data: dict, table_id: str, cell_label: str):
#     for tbl in extracted_data.get("tables", []):
#         if tbl.get("id", "").lower() == table_id.lower():
#             for cell in tbl.get("cells", []):
#                 if cell.get("label", "").strip().upper() == cell_label.strip().upper():
#                     return cell.get("value")
#     return None


# def _get_surface_ra(extracted_data: dict):
#     min_ra = None
#     for spec in extracted_data.get("surface_specifications", []):
#         rv = spec.get("roughness_value", "")
#         if isinstance(rv, str) and "ra" in rv.lower():
#             try:
#                 val = float("".join(
#                     c for c in rv.lower().replace("ra", "").strip().split()[0]
#                     if c in "0123456789."
#                 ))
#                 if min_ra is None or val < min_ra:
#                     min_ra = val
#             except (ValueError, IndexError):
#                 pass
#         elif isinstance(rv, (int, float)):
#             if min_ra is None or rv < min_ra:
#                 min_ra = rv
#     return min_ra


# def _get_tolerance_types(extracted_data: dict) -> list:
#     return [
#         t.get("tolerance_type", "").lower()
#         for t in extracted_data.get("geometric_tolerances", [])
#         if t.get("tolerance_type")
#     ]


# def _has_feature_type(extracted_data: dict, feat_type: str) -> bool:
#     return any(
#         f.get("type", "").lower() == feat_type.lower()
#         for f in extracted_data.get("features", [])
#     )


# def _op_template(family: str, op_name: str) -> dict:
#     for op in OPERATIONS_TEMPLATES.get(family, OPERATIONS_TEMPLATES["spur"]):
#         if op["operation"].lower() == op_name.lower():
#             return op
#     for op in OPERATIONS_TEMPLATES["spur"]:
#         if op["operation"].lower() == op_name.lower():
#             return op
#     return {"operation": op_name, "estimated_time_min": 15, "rate_per_hour": 60, "machine_options": []}


# # ──────────────────────────────────────────────────────────────────────────────
# # Public API
# # ──────────────────────────────────────────────────────────────────────────────

# def classify_and_plan(extracted_data: dict) -> dict:
#     """
#     Step 1 — Gear Classification & Operation Planning.

#     Input:  extracted_data dict  (or {"extracted_data": ...} wrapper)
#     Output: {
#         gear_family, evidence,
#         operations_sequence, operations_evidence
#     }
#     """
#     if "extracted_data" in extracted_data:
#         extracted_data = extracted_data["extracted_data"]

#     all_text  = _get_all_text(extracted_data)
#     evidence  = []
#     ops_planned: list[tuple[str, str]] = []   # (op_name, reason)

#     # ── Gear family ──────────────────────────────────────────────────────────
#     helix_angle = _get_table_cell(extracted_data, "tbl_gear_data", "HELIX ANGLE")
#     gear_family = "spur"

#     try:
#         helix_val = float(str(helix_angle).replace("°", "").strip()) if helix_angle else 0.0
#     except ValueError:
#         helix_val = 0.0

#     if helix_val > 0.2:
#         gear_family = "helical"
#         evidence.append(f"Helix angle = {helix_val}° > 0.2° → helical gear family")
#     elif "helical" in all_text:
#         gear_family = "helical"
#         evidence.append("Keyword 'helical' found in drawing text → helical gear family")
#     elif "bevel" in all_text:
#         gear_family = "bevel"
#         evidence.append("Keyword 'bevel' found in drawing text → bevel gear family")
#     else:
#         evidence.append("No helix angle or helical keyword → default spur gear family")

#     # ── Default ops (always present) ─────────────────────────────────────────
#     if gear_family == "helical":
#         ops_planned += [
#             ("Forging",              "Default: all gears require forging blank"),
#             ("Helical Hobbing",      "Default: helical gear tooth cutting"),
#             ("Gear Tooth Chamfering","Default: chamfer after hobbing"),
#             ("Deburring",            "Default: deburring always required"),
#         ]
#     else:
#         ops_planned += [
#             ("Forging",              "Default: all gears require forging blank"),
#             ("Gear Hobbing",         "Default: spur/bevel gear tooth cutting"),
#             ("Gear Tooth Chamfering","Default: chamfer after hobbing"),
#             ("Deburring",            "Default: deburring always required"),
#         ]

#     # ── Heat treatment ───────────────────────────────────────────────────────
#     mat_treat  = extracted_data.get("material_and_treatment", {})
#     title_block = extracted_data.get("metadata", {}).get("title_block", {})
#     ht_text = (
#         str(mat_treat.get("heat_treatment", "")).lower() + " " +
#         str(title_block.get("heat_treatment", "")).lower()
#     )

#     if "carbur" in ht_text:
#         ops_planned += [
#             ("Carburising", "heat_treatment contains 'carbur'"),
#             ("Quenching",   "Carburising requires quench"),
#             ("Tempering",   "Carburising requires temper"),
#         ]
#     if "carbonitriding" in ht_text:
#         ops_planned.append(("Carbonitriding", "heat_treatment contains 'carbonitriding'"))
#     if "nitrid" in ht_text:
#         ops_planned.append(("Nitriding", "heat_treatment contains 'nitrid'"))
#     if "induction" in ht_text:
#         ops_planned.append(("Induction Hardening", "heat_treatment contains 'induction'"))
#     if "normaliz" in ht_text or "normalised" in ht_text or "normalized" in ht_text:
#         ops_planned.append(("Normalising", "heat_treatment contains 'normaliz'"))
#     if "anneal" in ht_text and "isothermal" not in ht_text:
#         ops_planned.append(("Annealing", "heat_treatment contains 'anneal'"))
#     if "isothermal" in ht_text:
#         ops_planned.append(("Isothermal Annealing", "heat_treatment contains 'isothermal'"))

#     # ── Surface / finish ─────────────────────────────────────────────────────
#     finish_text = (
#         str(mat_treat.get("finish", "")).lower() + " " +
#         str(title_block.get("finish", "")).lower()
#     )
#     if "phosphat" in finish_text:
#         ops_planned.append(("Phosphating", "finish contains 'phosphat'"))
#     if "zinc" in finish_text or "plat" in finish_text:
#         ops_planned.append(("Plating", "finish contains 'zinc' or 'plat'"))
#     if "blackod" in finish_text:
#         ops_planned.append(("Blackodizing", "finish contains 'blackod'"))
#     if "powder" in finish_text:
#         ops_planned.append(("Powder Coating", "finish contains 'powder'"))
#     if "paint" in finish_text:
#         ops_planned.append(("Primer Coating / Painting", "finish contains 'paint'"))

#     # ── Surface roughness (Ra) ───────────────────────────────────────────────
#     min_ra = _get_surface_ra(extracted_data)
#     if min_ra is not None:
#         if min_ra <= 0.8:
#             ops_planned.append(("Grinding - Gear", f"Ra ≤ 0.8 µm ({min_ra}) → Gear grinding required"))
#             ops_planned.append(("Grinding - CNC",  f"Ra ≤ 0.8 µm ({min_ra}) → CNC grinding required"))
#         elif min_ra <= 3.2:
#             ops_planned.append(("Finish Turning", f"Ra ≤ 3.2 µm ({min_ra}) → Finish Turning required"))

#     # ── GD&T tolerances ──────────────────────────────────────────────────────
#     for tt in _get_tolerance_types(extracted_data):
#         if "runout" in tt or "cylindricity" in tt:
#             ops_planned.append(("Grinding - Gear", f"Tolerance '{tt}' → Grinding - Gear"))
#             ops_planned.append(("Grinding - CNC",  f"Tolerance '{tt}' → Grinding - CNC"))

#     # ── Bore fit ─────────────────────────────────────────────────────────────
#     for dim in extracted_data.get("dimensions", []):
#         if dim.get("id") == "dim_bore":
#             tol = str(dim.get("tolerance", "")).upper()
#             if "H7" in tol or "H8" in tol:
#                 ops_planned.append(("Drilling / Boring", "Bore dim present → Drilling/Boring"))
#                 ops_planned.append(("Internal Grinding", f"Bore tolerance {tol} → Internal Grinding"))

#     # ── Feature-based ops ────────────────────────────────────────────────────
#     if _has_feature_type(extracted_data, "keyway"):
#         ops_planned.append(("Broaching", "feature type 'keyway' → Broaching"))
#     if _has_feature_type(extracted_data, "internal_spline"):
#         ops_planned.append(("Gear Shaping", "feature type 'internal_spline' → Gear Shaping"))
#         ops_planned.append(("Broaching",    "feature type 'internal_spline' → Broaching"))

#     # ── Manufacturing notes ──────────────────────────────────────────────────
#     for note in extracted_data.get("manufacturing_notes", []):
#         nt = note.get("note_text", "").lower()
#         raw = note.get("note_text", "")
#         if "peen" in nt:
#             ops_planned.append(("Shot Peening",   f"Note: '{raw}'"))
#         if "blast" in nt:
#             ops_planned.append(("Shot Blasting",  f"Note: '{raw}'"))
#         if "deburr" in nt:
#             ops_planned.append(("Deburring",      "Note confirms deburring"))
#         if "grind" in nt:
#             ops_planned.append(("Grinding - Gear",f"Note: '{raw}'"))
#         if "inspect" in nt or "cmm" in nt:
#             ops_planned.append(("Final Inspection",f"Note: '{raw}'"))
#         if "din" in nt and "grind" in nt:
#             ops_planned.append(("Grinding - Gear","DIN + grind in notes → confirm grinding ops"))

#     # ── Quality class ────────────────────────────────────────────────────────
#     quality = str(_get_table_cell(extracted_data, "tbl_gear_data", "QUALITY CLASS") or "").upper()
#     if "DIN 6" in quality or "DIN6" in quality:
#         ops_planned.append(("Grinding - Gear", "DIN 6 quality class → fine grinding required"))
#     elif "DIN 8" in quality or "DIN8" in quality:
#         evidence.append("DIN 8 quality class → hobbing only, no additional grinding")

#     # ── Rough turning (always for hub blank) ─────────────────────────────────
#     ops_planned.append(("Rough Turning", "Hub/blank OD requires rough turning"))

#     # ── De-duplicate preserving insertion order ───────────────────────────────
#     seen: set[str] = set()
#     operations_sequence: list[str]  = []
#     operations_evidence: list[dict] = []

#     for op_name, reason in ops_planned:
#         if op_name not in seen:
#             seen.add(op_name)
#             operations_sequence.append(op_name)
#             tmpl = _op_template(gear_family, op_name)
#             operations_evidence.append({
#                 "operation":          op_name,
#                 "reason":             reason,
#                 "estimated_time_min": tmpl.get("estimated_time_min", 15),
#                 "rate_per_hour":      tmpl.get("rate_per_hour", 60),
#                 "machine_options":    tmpl.get("machine_options", []),
#             })

#     return {
#         "gear_family":         gear_family,
#         "evidence":            evidence,
#         "operations_sequence": operations_sequence,
#         "operations_evidence": operations_evidence,
#     }


# def compute_cost_breakdown(
#     material_cost: float,
#     operations_cost: float,
#     overhead_pct: float = 15.0,
#     margin_pct: float   = 20.0,
#     currency: str       = "USD",
# ) -> dict:
#     """Step 5 convenience wrapper (also callable standalone)."""
#     overhead = (material_cost + operations_cost) * overhead_pct / 100.0
#     subtotal = material_cost + operations_cost + overhead
#     margin   = subtotal * margin_pct / 100.0
#     total    = subtotal + margin
#     return {
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


"""
gear_rule.py
Step 1 — Gear Classification & Operation Planning
Location: app/service/gear_rule.py

All machine rates are in INR/hr (converted from USD at 84 INR/USD).
"""

import math

USD_TO_INR: float = 84.0   # ← single constant — keep in sync with materials.py


def _inr(usd: float) -> float:
    return round(usd * USD_TO_INR, 2)


OPERATIONS_TEMPLATES: dict = {
    "spur": [
        # ── Forging ────────────────────────────────────────────────────────
        {"operation": "Forging",                   "description": "Blank forging",                        "estimated_time_min": 15,  "rate_per_hour": _inr(60),   "machine_options": ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"]},
        # ── Tooth cutting ──────────────────────────────────────────────────
        {"operation": "Gear Hobbing",              "description": "Spur gear tooth cutting by hobbing",   "estimated_time_min": 25,  "rate_per_hour": _inr(95),   "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
        {"operation": "Helical Hobbing",           "description": "Helical gear tooth cutting",           "estimated_time_min": 35,  "rate_per_hour": _inr(105),  "machine_options": ["Gear Hobbing CNC", "Gear Hobbing Conventional"]},
        {"operation": "Gear Tooth Chamfering",     "description": "Chamfer tooth edges",                  "estimated_time_min": 8,   "rate_per_hour": _inr(45),   "machine_options": ["Gear Tooth Chamfering"]},
        {"operation": "Chamfering",                "description": "General chamfering",                   "estimated_time_min": 8,   "rate_per_hour": _inr(45),   "machine_options": ["Gear Tooth Chamfering"]},
        # ── Heat treatment ─────────────────────────────────────────────────
        {"operation": "Carburising",               "description": "Case carburising",                     "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"]},
        {"operation": "Carbonitriding",            "description": "Carbonitriding",                       "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Carbonitriding Furnace"]},
        {"operation": "Quenching",                 "description": "Oil/water quench after carburising",   "estimated_time_min": 30,  "rate_per_hour": _inr(55),   "machine_options": ["Carburising SQF", "Carburising Salt bath"]},
        {"operation": "Tempering",                 "description": "Stress relieve temper",                "estimated_time_min": 60,  "rate_per_hour": _inr(55),   "machine_options": ["Tempering Furnace"]},
        {"operation": "Hardening & Tempering",     "description": "Through hardening + temper",           "estimated_time_min": 90,  "rate_per_hour": _inr(55),   "machine_options": ["Hardening & Tempering Furnace"]},
        {"operation": "Nitriding",                 "description": "Gas / plasma nitriding",               "estimated_time_min": 480, "rate_per_hour": _inr(55),   "machine_options": ["Nitriding Furnace"]},
        {"operation": "Induction Hardening",       "description": "Induction surface hardening",          "estimated_time_min": 20,  "rate_per_hour": _inr(90),   "machine_options": ["Induction Hardening M/c"]},
        {"operation": "Normalising",               "description": "Normalising",                          "estimated_time_min": 60,  "rate_per_hour": _inr(45),   "machine_options": ["Normalising Furnace"]},
        {"operation": "Annealing",                 "description": "Annealing",                            "estimated_time_min": 60,  "rate_per_hour": _inr(45),   "machine_options": ["Annealing Furnace"]},
        {"operation": "Isothermal Annealing",      "description": "Isothermal annealing",                 "estimated_time_min": 90,  "rate_per_hour": _inr(45),   "machine_options": ["Isothermal Annealing Furnace"]},
        # ── Grinding ───────────────────────────────────────────────────────
        {"operation": "Gear Grinding",             "description": "Tooth flank profile grinding",         "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Grinding - Gear",           "description": "Gear profile CNC grinding",            "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Grinding - CNC",            "description": "CNC cylindrical / surface grinding",   "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Gear Grinding", "CNC Grinding"]},
        {"operation": "Internal Grinding",         "description": "Bore internal grinding for H7/H8 fit", "estimated_time_min": 30,  "rate_per_hour": _inr(120),  "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
        {"operation": "Grinding",                  "description": "General grinding",                     "estimated_time_min": 25,  "rate_per_hour": _inr(100),  "machine_options": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"]},
        # ── Turning ────────────────────────────────────────────────────────
        {"operation": "Rough Turning",             "description": "OD rough turning",                     "estimated_time_min": 18,  "rate_per_hour": _inr(75),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        {"operation": "Finish Turning",            "description": "OD finish turning",                    "estimated_time_min": 12,  "rate_per_hour": _inr(80),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        {"operation": "Turning",                   "description": "General turning / groove",             "estimated_time_min": 15,  "rate_per_hour": _inr(75),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"]},
        # ── Drilling / boring ──────────────────────────────────────────────
        {"operation": "Drilling / Boring",         "description": "Bore drilling or boring",              "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
        {"operation": "Drilling",                  "description": "Drilling",                             "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Drilling - Pillar Type", "Drilling - Radial"]},
        {"operation": "Gun Drilling",              "description": "Deep-hole gun drilling",               "estimated_time_min": 20,  "rate_per_hour": _inr(85),   "machine_options": ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"]},
        # ── Gear secondary ops ─────────────────────────────────────────────
        {"operation": "Gear Shaping",              "description": "Internal/external gear shaping",       "estimated_time_min": 55,  "rate_per_hour": _inr(110),  "machine_options": ["Gear Shaping Conventional"]},
        {"operation": "Gear Shaving",              "description": "Gear tooth shaving",                   "estimated_time_min": 20,  "rate_per_hour": _inr(95),   "machine_options": ["Gear Shaving CNC", "Gear Shaving Conventional"]},
        {"operation": "Broaching",                 "description": "Keyway / spline broaching",            "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["Horizontal Broaching", "Vertical Broaching"]},
        {"operation": "Threading",                 "description": "Thread cutting",                       "estimated_time_min": 10,  "rate_per_hour": _inr(70),   "machine_options": ["CNC Turning Centre /twin chuck", "Lathe CNC"]},
        # ── Surface treatment ──────────────────────────────────────────────
        {"operation": "Shot Peening",              "description": "Shot peen tooth roots",                "estimated_time_min": 20,  "rate_per_hour": _inr(60),   "machine_options": ["Shot Peening"]},
        {"operation": "Shot Blasting",             "description": "Shot blasting",                        "estimated_time_min": 10,  "rate_per_hour": _inr(40),   "machine_options": ["Shot Blasting"]},
        {"operation": "Phosphating",               "description": "Black phosphate coating",              "estimated_time_min": 30,  "rate_per_hour": _inr(45),   "machine_options": ["Phosphating Tank"]},
        {"operation": "Plating",                   "description": "Zinc / electroplating",               "estimated_time_min": 45,  "rate_per_hour": _inr(50),   "machine_options": ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"]},
        {"operation": "Blackodizing",              "description": "Black oxide coating",                  "estimated_time_min": 30,  "rate_per_hour": _inr(40),   "machine_options": ["Blackodizing Furnace"]},
        {"operation": "Powder Coating",            "description": "Powder coating",                       "estimated_time_min": 25,  "rate_per_hour": _inr(40),   "machine_options": ["Powder Coating"]},
        {"operation": "Primer Coating / Painting", "description": "Primer / painting",                   "estimated_time_min": 20,  "rate_per_hour": _inr(35),   "machine_options": ["Primer Coating", "Painting cum primer"]},
        # ── Inspection / finishing ─────────────────────────────────────────
        {"operation": "Final Inspection",          "description": "CMM / Magnaflux inspection",           "estimated_time_min": 15,  "rate_per_hour": _inr(85),   "machine_options": ["Magnaflux", "Manual"]},
        {"operation": "Inspection",                "description": "General inspection",                   "estimated_time_min": 15,  "rate_per_hour": _inr(85),   "machine_options": ["Magnaflux", "Manual"]},
        {"operation": "Deburring",                 "description": "Remove all burrs",                     "estimated_time_min": 6,   "rate_per_hour": _inr(40),   "machine_options": ["Manual Deburring"]},
    ],
    "helical": [],
    "bevel":   [],
}

# Helical: copy spur but swap "Gear Hobbing" → "Helical Hobbing"
_helical = []
for _op in OPERATIONS_TEMPLATES["spur"]:
    if _op["operation"] == "Gear Hobbing":
        _helical.append({
            "operation":          "Helical Hobbing",
            "description":        "Helical gear tooth cutting",
            "estimated_time_min": 35,
            "rate_per_hour":      _inr(105),
            "machine_options":    ["Gear Hobbing CNC", "Gear Hobbing Conventional"],
        })
    else:
        _helical.append(_op.copy())
OPERATIONS_TEMPLATES["helical"] = _helical
OPERATIONS_TEMPLATES["bevel"]   = [op.copy() for op in OPERATIONS_TEMPLATES["spur"]]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_all_text(extracted_data: dict) -> str:
    parts = []
    def _walk(obj):
        if isinstance(obj, str):    parts.append(obj.lower())
        elif isinstance(obj, dict): [_walk(v) for v in obj.values()]
        elif isinstance(obj, list): [_walk(i) for i in obj]
    _walk(extracted_data)
    return " ".join(parts)


def _get_table_cell(extracted_data: dict, table_id: str, cell_label: str):
    for tbl in extracted_data.get("tables", []):
        if tbl.get("id", "").lower() == table_id.lower():
            for cell in tbl.get("cells", []):
                if cell.get("label", "").strip().upper() == cell_label.strip().upper():
                    return cell.get("value")
    return None


def _get_surface_ra(extracted_data: dict):
    min_ra = None
    for spec in extracted_data.get("surface_specifications", []):
        rv = spec.get("roughness_value", "")
        if isinstance(rv, str) and "ra" in rv.lower():
            try:
                val = float("".join(
                    c for c in rv.lower().replace("ra", "").strip().split()[0]
                    if c in "0123456789."
                ))
                if min_ra is None or val < min_ra:
                    min_ra = val
            except (ValueError, IndexError):
                pass
        elif isinstance(rv, (int, float)):
            if min_ra is None or rv < min_ra:
                min_ra = rv
    return min_ra


def _get_tolerance_types(extracted_data: dict) -> list:
    return [t.get("tolerance_type", "").lower()
            for t in extracted_data.get("geometric_tolerances", [])
            if t.get("tolerance_type")]


def _has_feature_type(extracted_data: dict, feat_type: str) -> bool:
    return any(f.get("type", "").lower() == feat_type.lower()
               for f in extracted_data.get("features", []))


def _op_template(family: str, op_name: str) -> dict:
    for op in OPERATIONS_TEMPLATES.get(family, OPERATIONS_TEMPLATES["spur"]):
        if op["operation"].lower() == op_name.lower():
            return op
    for op in OPERATIONS_TEMPLATES["spur"]:
        if op["operation"].lower() == op_name.lower():
            return op
    return {
        "operation":          op_name,
        "estimated_time_min": 15,
        "rate_per_hour":      _inr(60),
        "machine_options":    [],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def classify_and_plan(extracted_data: dict) -> dict:
    """Step 1 — Gear Classification & Operation Planning."""
    if "extracted_data" in extracted_data:
        extracted_data = extracted_data["extracted_data"]

    all_text = _get_all_text(extracted_data)
    evidence: list[str]               = []
    ops_planned: list[tuple[str,str]] = []

    # ── Gear family ──────────────────────────────────────────────────────────
    helix_angle = _get_table_cell(extracted_data, "tbl_gear_data", "HELIX ANGLE")
    gear_family = "spur"
    try:
        helix_val = float(str(helix_angle).replace("°", "").strip()) if helix_angle else 0.0
    except ValueError:
        helix_val = 0.0

    if helix_val > 0.2:
        gear_family = "helical"
        evidence.append(f"Helix angle = {helix_val}° > 0.2° → helical gear family")
    elif "helical" in all_text:
        gear_family = "helical"
        evidence.append("Keyword 'helical' found → helical gear family")
    elif "bevel" in all_text:
        gear_family = "bevel"
        evidence.append("Keyword 'bevel' found → bevel gear family")
    else:
        evidence.append("No helix angle → default spur gear family")

    # ── Default ops ──────────────────────────────────────────────────────────
    if gear_family == "helical":
        ops_planned += [
            ("Forging",               "Default: all gears require forging blank"),
            ("Helical Hobbing",       "Default: helical gear tooth cutting"),
            ("Gear Tooth Chamfering", "Default: chamfer after hobbing"),
            ("Deburring",             "Default: deburring always required"),
        ]
    else:
        ops_planned += [
            ("Forging",               "Default: all gears require forging blank"),
            ("Gear Hobbing",          "Default: spur/bevel gear tooth cutting"),
            ("Gear Tooth Chamfering", "Default: chamfer after hobbing"),
            ("Deburring",             "Default: deburring always required"),
        ]

    # ── Heat treatment ───────────────────────────────────────────────────────
    mat_treat   = extracted_data.get("material_and_treatment", {})
    title_block = extracted_data.get("metadata", {}).get("title_block", {})
    ht_text = (str(mat_treat.get("heat_treatment",  "")).lower() + " " +
               str(title_block.get("heat_treatment", "")).lower())

    if "carbur"         in ht_text: ops_planned += [("Carburising", "heat_treatment: carbur"), ("Quenching", "Carburising→quench"), ("Tempering", "Carburising→temper")]
    if "carbonitriding" in ht_text: ops_planned.append(("Carbonitriding",    "heat_treatment: carbonitriding"))
    if "nitrid"         in ht_text: ops_planned.append(("Nitriding",          "heat_treatment: nitrid"))
    if "induction"      in ht_text: ops_planned.append(("Induction Hardening","heat_treatment: induction"))
    if "normaliz" in ht_text or "normalised" in ht_text or "normalized" in ht_text:
        ops_planned.append(("Normalising", "heat_treatment: normaliz"))
    if "anneal" in ht_text and "isothermal" not in ht_text:
        ops_planned.append(("Annealing",           "heat_treatment: anneal"))
    if "isothermal" in ht_text:
        ops_planned.append(("Isothermal Annealing", "heat_treatment: isothermal"))

    # ── Surface / finish ─────────────────────────────────────────────────────
    finish_text = (str(mat_treat.get("finish",   "")).lower() + " " +
                   str(title_block.get("finish", "")).lower())
    if "phosphat" in finish_text: ops_planned.append(("Phosphating",               "finish: phosphat"))
    if "zinc"     in finish_text or "plat" in finish_text: ops_planned.append(("Plating", "finish: zinc/plat"))
    if "blackod"  in finish_text: ops_planned.append(("Blackodizing",              "finish: blackod"))
    if "powder"   in finish_text: ops_planned.append(("Powder Coating",            "finish: powder"))
    if "paint"    in finish_text: ops_planned.append(("Primer Coating / Painting", "finish: paint"))

    # ── Ra ───────────────────────────────────────────────────────────────────
    min_ra = _get_surface_ra(extracted_data)
    if min_ra is not None:
        if min_ra <= 0.8:
            ops_planned += [
                ("Grinding - Gear", f"Ra≤0.8 µm ({min_ra})"),
                ("Grinding - CNC",  f"Ra≤0.8 µm ({min_ra})"),
            ]
        elif min_ra <= 3.2:
            ops_planned.append(("Finish Turning", f"Ra≤3.2 µm ({min_ra})"))

    # ── GD&T ─────────────────────────────────────────────────────────────────
    for tt in _get_tolerance_types(extracted_data):
        if "runout" in tt or "cylindricity" in tt:
            ops_planned += [
                ("Grinding - Gear", f"Tolerance '{tt}'"),
                ("Grinding - CNC",  f"Tolerance '{tt}'"),
            ]

    # ── Bore fit ─────────────────────────────────────────────────────────────
    for dim in extracted_data.get("dimensions", []):
        if dim.get("id") == "dim_bore":
            tol = str(dim.get("tolerance", "")).upper()
            if "H7" in tol or "H8" in tol:
                ops_planned += [
                    ("Drilling / Boring",  "Bore dim present"),
                    ("Internal Grinding",  f"Bore tol {tol}"),
                ]

    # ── Features ─────────────────────────────────────────────────────────────
    if _has_feature_type(extracted_data, "keyway"):
        ops_planned.append(("Broaching", "feature: keyway"))
    if _has_feature_type(extracted_data, "internal_spline"):
        ops_planned += [
            ("Gear Shaping", "feature: internal_spline"),
            ("Broaching",    "feature: internal_spline"),
        ]

    # ── Manufacturing notes ──────────────────────────────────────────────────
    for note in extracted_data.get("manufacturing_notes", []):
        nt  = note.get("note_text", "").lower()
        raw = note.get("note_text", "")
        if "peen"    in nt: ops_planned.append(("Shot Peening",             f"Note: '{raw}'"))
        if "blast"   in nt: ops_planned.append(("Shot Blasting",            f"Note: '{raw}'"))
        if "deburr"  in nt: ops_planned.append(("Deburring",                "Note: deburring"))
        if "grind"   in nt: ops_planned.append(("Grinding - Gear",          f"Note: '{raw}'"))
        if "inspect" in nt or "cmm" in nt: ops_planned.append(("Final Inspection", f"Note: '{raw}'"))
        if "din"     in nt and "grind" in nt: ops_planned.append(("Grinding - Gear", "DIN+grind in notes"))

    # ── Quality class ────────────────────────────────────────────────────────
    quality = str(_get_table_cell(extracted_data, "tbl_gear_data", "QUALITY CLASS") or "").upper()
    if "DIN 6" in quality or "DIN6" in quality:
        ops_planned.append(("Grinding - Gear", "DIN 6 → fine grinding"))
    elif "DIN 8" in quality or "DIN8" in quality:
        evidence.append("DIN 8 → hobbing only, no extra grinding")

    # ── Rough turning always ─────────────────────────────────────────────────
    ops_planned.append(("Rough Turning", "Hub/blank OD rough turning"))

    # ── De-duplicate ─────────────────────────────────────────────────────────
    seen: set[str]              = set()
    operations_sequence: list   = []
    operations_evidence: list   = []

    for op_name, reason in ops_planned:
        if op_name not in seen:
            seen.add(op_name)
            operations_sequence.append(op_name)
            tmpl = _op_template(gear_family, op_name)
            operations_evidence.append({
                "operation":          op_name,
                "reason":             reason,
                "estimated_time_min": tmpl.get("estimated_time_min", 15),
                "rate_per_hour":      tmpl.get("rate_per_hour", _inr(60)),
                "machine_options":    tmpl.get("machine_options", []),
            })

    return {
        "gear_family":         gear_family,
        "evidence":            evidence,
        "operations_sequence": operations_sequence,
        "operations_evidence": operations_evidence,
    }


def compute_cost_breakdown(
    material_cost:   float,
    operations_cost: float,
    overhead_pct:    float = 15.0,
    margin_pct:      float = 20.0,
    currency:        str   = "INR",   # ← INR default
) -> dict:
    overhead = (material_cost + operations_cost) * overhead_pct / 100.0
    subtotal = material_cost + operations_cost + overhead
    margin   = subtotal * margin_pct / 100.0
    total    = subtotal + margin
    return {
        "material_cost":   round(material_cost,   2),
        "operations_cost": round(operations_cost, 2),
        "overhead_pct":    overhead_pct,
        "overhead_cost":   round(overhead, 2),
        "subtotal":        round(subtotal, 2),
        "margin_pct":      margin_pct,
        "margin_cost":     round(margin,   2),
        "total_cost":      round(total,    2),
        "currency":        currency,
    }