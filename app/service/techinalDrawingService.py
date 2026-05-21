
# ###########################################ratelimit###########################################



# import os
# import uuid
# import json
# import csv
# import traceback
# from datetime import datetime
# from dotenv import load_dotenv
# import google.generativeai as genai
# from typing import Dict, List, Optional, Any
# from PIL import Image
# import base64
# import io

# from app.log.logger import get_logger

# logger = get_logger(__name__)
# load_dotenv()
# # Ensure the Google API key is provided via environment variable and is not empty.
# GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# if not GOOGLE_API_KEY:
#     raise RuntimeError(
#         "GOOGLE_API_KEY is not set.\n"
#         "Steps to fix:\n"
#         "1) Rotate the leaked API key in Google Cloud Console (disable/delete the exposed key).\n"
#         "2) Create a new API key and restrict it (HTTP referrers, IPs, and enabled APIs).\n"
#         "3) Set the new key in environment variable GOOGLE_API_KEY (do NOT commit it).\n"
#         "4) For local dev, add it to your shell profile or a local .env (ensure .env is in .gitignore).\n"
#     )
# genai.configure(api_key=GOOGLE_API_KEY)
# model = genai.GenerativeModel('gemini-2.5-flash')

# class TechnicalDrawingExtractionService:
#     def __init__(self):
#         self.processed_files = {}  
    
#     def clean_text(self, text: str) -> str:
#         """Remove non-UTF-8 characters and null bytes from text"""
#         if not text:
#             return ""
        
#         text = text.replace('\x00', '')
        
#         try:
#             text = text.encode('utf-8', errors='ignore').decode('utf-8')
#         except (UnicodeEncodeError, UnicodeDecodeError):
#             text = text.encode('ascii', errors='ignore').decode('ascii')
        
#         return text.strip()

#     def count_tokens_accurate(self, text: str) -> int:
#         """
#         More accurate token counting using Gemini's count_tokens method.
#         Falls back to improved estimation if API call fails.
#         """
#         try:
#             if not text:
#                 return 0
            
#             token_count = model.count_tokens(text)
#             return token_count.total_tokens
            
#         except Exception as e:
#             logger.warning(f"Failed to get accurate token count, using estimation: {str(e)}")
#             return self.estimate_tokens(text)
    
#     def estimate_tokens(self, text: str) -> int:
#         """
#         Improved token estimation for Gemini models.
#         Based on analysis that Gemini tokenization is closer to:
#         - ~3.5-4 characters per token for English
#         - Technical terms and numbers may have different ratios
#         """
#         if not text:
#             return 0
        
#         words = text.split()
#         chars = len(text)
        
#         base_tokens = chars / 3.5
        
#         technical_chars = sum(1 for c in text if c in '()[]{}+-=<>≥≤±∅°')
#         if technical_chars > chars * 0.1: 
#             base_tokens = chars / 3.0  
        
#         return int(base_tokens)

#     def estimate_image_tokens(self, image_path: str) -> int:
#         """
#         Estimate tokens consumed by an image.
#         Gemini's image token consumption depends on image size and resolution.
#         """
#         try:
#             if not os.path.exists(image_path):
#                 return 0
            
#             with Image.open(image_path) as img:
#                 width, height = img.size
                
#             pixels = width * height
            
#             if pixels <= 512 * 512:
#                 return 258 
#             elif pixels <= 1024 * 1024:
#                 return 516  
#             else:
#                 return 774  
                
#         except Exception as e:
#             logger.warning(f"Could not estimate image tokens: {str(e)}")
#             return 500  
    
#     def count_total_tokens_for_request(self, prompt: str, image_path: str = None) -> Dict[str, int]:
#         """
#         Count total tokens for a complete request including prompt and image.
#         """
#         prompt_tokens = self.count_tokens_accurate(prompt)
#         image_tokens = self.estimate_image_tokens(image_path) if image_path else 0
        
#         return {
#             "prompt_tokens": prompt_tokens,
#             "image_tokens": image_tokens,
#             "total_input_tokens": prompt_tokens + image_tokens
#         }

#     async def upload_image_to_gemini(self, image_path: str) -> Any:
#         """Upload image file to Gemini"""
#         try:
#             logger.info(f"Uploading image file to Gemini: {image_path}")
            
#             if not os.path.exists(image_path):
#                 raise FileNotFoundError(f"Image file not found: {image_path}")
                
#             file_size = os.path.getsize(image_path)
#             if file_size == 0:
#                 raise ValueError("Image file is empty")
                
#             uploaded_file = genai.upload_file(image_path)
#             logger.info(f"Successfully uploaded image to Gemini")
#             return uploaded_file
            
#         except Exception as e:
#             logger.error(f"Failed to upload image to Gemini: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
#             raise Exception(f"Image upload failed: {str(e)}")

#     async def extract_technical_drawing_data(self, image_path: str) -> Dict:
#         """Extract technical drawing data from image using Gemini - Universal Version"""
#         try:
#             logger.info(f"Starting technical drawing extraction for: {image_path}")
            

#             PROMPT = """
#                     You are an expert mechanical drawing interpreter. Your role is to extract ONLY the
#                     explicitly printed information from a mechanical gear drawing and return a structured JSON.

#                     ════════════════════════════════════════════════════════
#                     SECTION 1 — ABSOLUTE RULES
#                     ════════════════════════════════════════════════════════
#                     1. Never invent values. If a value is not visible, set "value": null and
#                     "source": "missing_on_drawing".
#                     2. Root diameter is NOT a cavity. Do not treat root_diameter as hollow volume.
#                     3. Face width vs hub height — CRITICAL:
#                     - Face width  = axial dimension of ONLY the gear rim/toothed section (SMALLER value)
#                     - Hub height  = TOTAL axial dimension of the complete assembly (LARGER value)
#                     - Hub height is ALWAYS greater than face width. If not, SWAP assignments.
#                     4. Bore subtraction passes through the full axial stack (face_width + hub_extension).
#                     5. Preserve all units, tolerances, and symbols exactly (⌀, ±, H7, −0.1, etc.).
#                     6. Copy source text exactly into "raw_text".
#                     7. Always include "view_id" and leader arrow mapping where visible.
#                     8. All tables (gear data, spline data, permissible deviations, heat-treat, material,
#                     surface treatment, forging details) must appear in "tables" and be linked via
#                     features[*].table_links.

#                     ════════════════════════════════════════════════════════
#                     SECTION 2 — MANDATORY SCAN SEQUENCE (follow this ORDER)
#                     ════════════════════════════════════════════════════════
#                     Before writing any JSON, scan the drawing in this fixed order and take notes:

#                     STEP A — Inventory every named view:
#                     List every view label found on the drawing:
#                     e.g. "SECTION A-A", "SECTION B-B", "ISOMETRIC VIEW",
#                         "LEAD CROWNING DETAIL", "GEAR TOOTH EDGE CHAMFER", "GEAR TIP CHAMFER".
#                     Assign each a unique view_id (view_main, view_iso, view_lead_crown,
#                     view_tooth_edge_chamfer, view_tip_chamfer, etc.).
#                     Do not skip any labeled sub-view, no matter how small.

#                     STEP B — Inventory every dimension callout in EVERY view:
#                     For each dimension line found, record:
#                         - The raw text exactly as printed
#                         - Which view it belongs to
#                         - What geometry it points to (leader endpoint descriptions)
#                     Include dimensions in detail sub-views and callout boxes.

#                     STEP C — Inventory every data table:
#                     List every table found (gear data, spline data, permissible deviations,
#                     heat treatment, surface treatment, forging details, title block).

#                     STEP D — Inventory every note/general instruction block.

#                     Only after completing steps A–D, assemble the JSON output.

#                     ════════════════════════════════════════════════════════
#                     SECTION 3 — DETAIL SUB-VIEW EXTRACTION (NEW — CRITICAL)
#                     ════════════════════════════════════════════════════════
#                     Gear drawings typically contain 2–4 small detail views in the lower-left corner.
#                     Each MUST be extracted into its own dimension entries.

#                     ### LEAD CROWNING DETAIL
#                     - Look for a small sectional or profile view labeled "LEAD CROWNING DETAIL"
#                     or "CENTRE OF CROWN".
#                     - Extract: crowning radius (e.g. "R3.8×0.3 DEEP"), depth value, and any
#                     associated annotation text.
#                     - Assign view_id: "view_lead_crown"
#                     - Add entries: dim_crown_radius, dim_crown_depth

#                     ### GEAR TOOTH EDGE CHAMFER
#                     - Look for a small angled detail view labeled "GEAR TOOTH EDGE CHAMFER".
#                     - Extract: chamfer size (e.g. "0.5×1.0"), angle if shown, note "BOTH SIDES"
#                     if stated.
#                     - Assign view_id: "view_tooth_edge_chamfer"
#                     - Add entry: dim_tooth_edge_chamfer

#                     ### GEAR TIP CHAMFER
#                     - Look for a small view labeled "GEAR TIP CHAMFER".
#                     - Extract: chamfer dimensions (e.g. "0.35×0.1"), angle if shown.
#                     - Assign view_id: "view_tip_chamfer"
#                     - Add entry: dim_tip_chamfer

#                     ### ISOMETRIC VIEW
#                     - Assign view_id: "view_iso"
#                     - No dimensions typically here, but note if any annotation is present.

#                     For all detail sub-views:
#                     - If a dimension is present but illegible due to image quality, set
#                     "value": null, "source": "illegible_on_drawing".
#                     - Never omit the view or its dimension entries — create the entry with null
#                     if needed.

#                     ════════════════════════════════════════════════════════
#                     SECTION 4 — SECONDARY DIMENSIONS IN MAIN SECTION VIEW
#                     ════════════════════════════════════════════════════════
#                     In addition to the 5 primary dimensions, the main section view often contains
#                     secondary dimensions that MUST also be captured:

#                     - Top-level overall width dimension (e.g. "15.2±0.1") — often a small
#                     dimension at the top of the section view spanning a sub-feature.
#                     Add as: dim_overall_width or dim_sub_width with appropriate leader notes.
#                     - Relief groove / small bore diameter (e.g. "⌀3.58") — small internal
#                     annular groove visible in section.
#                     Add as: dim_relief_groove_dia.
#                     - Any shoulder, step, or undercut dimensions shown with leader lines.
#                     - Spline entry chamfer dimensions if called out separately from the spline table.

#                     Rule: Any printed dimension callout visible in ANY view must have a
#                     corresponding entry in "dimensions". No callout may be silently skipped.

#                     ════════════════════════════════════════════════════════
#                     SECTION 5 — COMPONENT DEFINITIONS & IDENTIFICATION
#                     ════════════════════════════════════════════════════════

#                     ### BORE
#                     - Central through-hole for shaft mounting.
#                     - Symbols: ⌀, H7, H8, or fit designation.
#                     - Spans full axial length unless otherwise noted.
#                     - May contain internal splines or keyways.

#                     ### RIM
#                     - Outer circular section carrying gear teeth.
#                     - Outer diameter = largest ⌀ on drawing (gear tip circle).
#                     - Face width = SMALLER axial dimension (toothed section only).

#                     ### HUB
#                     - Cylindrical extension beyond the gear rim.
#                     - Hub diameter = smaller ⌀ on hub section (not rim OD).
#                     - Hub height = LARGER axial dimension (total assembly length end to end).

#                     ### SPLINE
#                     - Internal tooth profile inside bore for torque transmission.
#                     - Has dedicated spline data table (DIN 5480 or similar standard).
#                     - Extract: major dia, minor dia, no. of teeth, module, pressure angle,
#                     pin measurement + tolerance, pin diameter.

#                     ════════════════════════════════════════════════════════
#                     SECTION 6 — DIMENSION ASSIGNMENT LOGIC CHECKS
#                     ════════════════════════════════════════════════════════
#                     1. Hub height > Face width — ALWAYS. If violated, SWAP.
#                     2. Outer diameter > Hub diameter > Bore diameter.
#                     3. Two axial dimensions exist → larger = hub_height, smaller = face_width.
#                     4. Diameter hierarchy: tip OD > hub OD > bore ID.
#                     5. All four chamfer/crowning detail views must yield at least one dim entry each
#                     (null-valued if illegible, but the entry must exist).

#                     ════════════════════════════════════════════════════════
#                     SECTION 7 — TABLE EXTRACTION RULES
#                     ════════════════════════════════════════════════════════
#                     Extract ALL of the following tables if present:
#                     tbl_gear_data          — module, teeth, pressure angle, helix angle,
#                                             direction, coeff. of correction, span measurement
#                                             (+ tolerance), quality/DIN, mating gear ref,
#                                             centre distance (+ tolerance), pitch circle dia,
#                                             base diameter, measurement over pins (+ tolerance),
#                                             pin diameter, SAP, EAP, max TIF dia, operating PCD.
#                     tbl_spline_data        — standard, fit type, no. of teeth, module,
#                                             pressure angle, measurement between pins
#                                             (+ tolerance), pin diameter, major dia
#                                             (+ tolerance), minor dia (+ tolerance).
#                     tbl_permissible_dev    — runout of faces, runout of gear pitch crown,
#                                             double flank total Fi″, double flank tooth-to-tooth
#                                             fi″, tooth trace form fβr, tooth alignment fHB,
#                                             tooth trace total Fβ, profile form fα,
#                                             profile angle fHα, total profile Fα.
#                     tbl_heat_treatment     — carburize depth, surface hardness (HRC),
#                                             core hardness (HRC).
#                     tbl_surface_treatment  — shot blast shot size.
#                     tbl_forging_details    — normalized BHN, grain size (ASTM),
#                                             microstructure description, max bainite %.

#                     For every cell: preserve exact label text, numeric value, unit, and
#                     tolerance string as separate fields.

#                     ════════════════════════════════════════════════════════
#                     SECTION 8 — METADATA / TITLE BLOCK
#                     ════════════════════════════════════════════════════════
#                     Extract:
#                     drawing_no, part_name, material, scale, company_name, division,
#                     first_angle / third_angle projection indicator (if shown),
#                     revision level (if shown).

#                     ════════════════════════════════════════════════════════
#                     SECTION 9 — OUTPUT JSON SCHEMA
#                     ════════════════════════════════════════════════════════
#                     Return ONLY valid JSON — no commentary, no markdown fences.

#                     {
#                     "units": "mm",
#                     "views": [
#                         {"id": "view_main",               "name": "SECTION B-B",            "bbox": null},
#                         {"id": "view_iso",                "name": "ISOMETRIC VIEW",         "bbox": null},
#                         {"id": "view_lead_crown",         "name": "LEAD CROWNING DETAIL",   "bbox": null},
#                         {"id": "view_tooth_edge_chamfer", "name": "GEAR TOOTH EDGE CHAMFER","bbox": null},
#                         {"id": "view_tip_chamfer",        "name": "GEAR TIP CHAMFER",       "bbox": null}
#                     ],
#                     "tables": [
#                         {
#                         "id": "tbl_gear_data",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "MODULE",                  "value": null, "unit": "mm"},
#                             {"label": "NO. OF TEETH",            "value": null, "unit": null},
#                             {"label": "PRESSURE ANGLE",          "value": null, "unit": "°"},
#                             {"label": "HELIX ANGLE",             "value": null, "unit": "°"},
#                             {"label": "DIRECTION OF HELIX",      "value": null, "unit": null},
#                             {"label": "COEFFICIENT OF CORRECTION","value": null,"unit": null},
#                             {"label": "SPAN MEASUREMENT OVER TEETH","value": null,"unit": null},
#                             {"label": "SPAN MEASUREMENT",        "value": null, "unit": "mm",
#                             "tolerance": null},
#                             {"label": "QUALITY (DIN 3962-63)",   "value": null, "unit": null},
#                             {"label": "MESHES WITH GEAR",        "value": null, "unit": null},
#                             {"label": "CENTER DISTANCE",         "value": null, "unit": "mm",
#                             "tolerance": null},
#                             {"label": "PITCH CIRCLE DIAMETER",   "value": null, "unit": "mm"},
#                             {"label": "BASE DIAMETER",           "value": null, "unit": "mm"},
#                             {"label": "MEASUREMENT OVER PINS",   "value": null, "unit": "mm",
#                             "tolerance": null},
#                             {"label": "PIN DIAMETER",            "value": null, "unit": "mm"},
#                             {"label": "SAP",                     "value": null, "unit": "mm"},
#                             {"label": "EAP",                     "value": null, "unit": "mm"},
#                             {"label": "MAX TRUE INVOLUTE FORM DIA (TIF)","value": null,"unit": "mm"},
#                             {"label": "OPERATING PCD",           "value": null, "unit": "mm"}
#                         ]
#                         },
#                         {
#                         "id": "tbl_spline_data",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "STANDARD",               "value": null, "unit": null},
#                             {"label": "FIT",                    "value": null, "unit": null},
#                             {"label": "NO. OF TEETH",           "value": null, "unit": null},
#                             {"label": "MODULE",                 "value": null, "unit": "mm"},
#                             {"label": "PRESSURE ANGLE",         "value": null, "unit": "°"},
#                             {"label": "MEASUREMENT BETWEEN PINS","value": null,"unit": "mm",
#                             "tolerance": null},
#                             {"label": "PIN DIAMETER",           "value": null, "unit": "mm"},
#                             {"label": "MAJOR DIAMETER",         "value": null, "unit": "mm",
#                             "tolerance": null},
#                             {"label": "MINOR DIAMETER",         "value": null, "unit": "mm",
#                             "tolerance": null}
#                         ]
#                         },
#                         {
#                         "id": "tbl_permissible_dev",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "REFERENCE: SPLINE PITCH CYLINDER","value": null,"unit": null},
#                             {"label": "RUNOUT OF FACE A & B",            "value": null,"unit": null},
#                             {"label": "RUNOUT OF GEAR PITCH CROWN",      "value": null,"unit": null},
#                             {"label": "DOUBLE FLANK TOTAL ERROR (Fi\")", "value": null,"unit": null},
#                             {"label": "DOUBLE FLANK TOOTH-TO-TOOTH (fi\")","value": null,"unit": null},
#                             {"label": "TOOTH TRACE FORM DEVIATION (fβr)","value": null,"unit": null},
#                             {"label": "TOOTH ALIGNMENT ERROR (fHB)",     "value": null,"unit": null},
#                             {"label": "TOOTH TRACE TOTAL DEVIATION (Fβ)","value": null,"unit": null},
#                             {"label": "PROFILE FORM DEVIATION (fα)",     "value": null,"unit": null},
#                             {"label": "PROFILE ANGLE DEVIATION (fHα)",   "value": null,"unit": null},
#                             {"label": "TOTAL PROFILE DEVIATION (Fα)",    "value": null,"unit": null}
#                         ]
#                         },
#                         {
#                         "id": "tbl_heat_treatment",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "CASE CARBURIZED DEPTH", "value": null, "unit": "mm"},
#                             {"label": "SURFACE HARDNESS",      "value": null, "unit": "HRC"},
#                             {"label": "CORE HARDNESS",         "value": null, "unit": "HRC"}
#                         ]
#                         },
#                         {
#                         "id": "tbl_surface_treatment",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "SHOT BLAST SHOT SIZE",  "value": null, "unit": "mm"}
#                         ]
#                         },
#                         {
#                         "id": "tbl_forging_details",
#                         "view_id": null,
#                         "cells": [
#                             {"label": "NORMALIZED TO",         "value": null, "unit": "BHN"},
#                             {"label": "GRAIN SIZE",            "value": null, "unit": "ASTM"},
#                             {"label": "MICROSTRUCTURE",        "value": null, "unit": null},
#                             {"label": "MAX BAINITE",           "value": null, "unit": "%"}
#                         ]
#                         }
#                     ],
#                     "dimensions": [
#                         {
#                         "id": "dim_outer_dia",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": "⌀",
#                         "tolerance": null,
#                         "leaders": ["gear tooth tip left", "gear tooth tip right"]
#                         },
#                         {
#                         "id": "dim_hub_dia",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": "⌀",
#                         "tolerance": null,
#                         "leaders": ["hub outer surface left", "hub outer surface right"]
#                         },
#                         {
#                         "id": "dim_face_width",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": ["left face of gear teeth", "right face of gear teeth"],
#                         "note": "SMALLER of the two axial dimensions — toothed section only"
#                         },
#                         {
#                         "id": "dim_hub_height",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": ["leftmost face of assembly", "rightmost face of assembly"],
#                         "note": "LARGER of the two axial dimensions — total assembly length"
#                         },
#                         {
#                         "id": "dim_bore",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": "⌀",
#                         "tolerance": null,
#                         "leaders": ["bore entry left", "bore entry right"]
#                         },
#                         {
#                         "id": "dim_overall_width",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": [],
#                         "note": "Secondary axial dimension callout if present (e.g. 15.2±0.1)"
#                         },
#                         {
#                         "id": "dim_relief_groove_dia",
#                         "view_id": "view_main",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": "⌀",
#                         "tolerance": null,
#                         "leaders": [],
#                         "note": "Small internal relief/undercut groove diameter if visible"
#                         },
#                         {
#                         "id": "dim_crown_radius",
#                         "view_id": "view_lead_crown",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": "R",
#                         "tolerance": null,
#                         "leaders": ["crowning radius callout"],
#                         "note": "From LEAD CROWNING DETAIL view — e.g. R3.8"
#                         },
#                         {
#                         "id": "dim_crown_depth",
#                         "view_id": "view_lead_crown",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": ["crown depth annotation"],
#                         "note": "From LEAD CROWNING DETAIL view — crowning depth e.g. 0.3 DEEP"
#                         },
#                         {
#                         "id": "dim_tooth_edge_chamfer",
#                         "view_id": "view_tooth_edge_chamfer",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": ["gear tooth edge"],
#                         "note": "From GEAR TOOTH EDGE CHAMFER view — e.g. 0.5×1.0 BOTH SIDES"
#                         },
#                         {
#                         "id": "dim_tip_chamfer",
#                         "view_id": "view_tip_chamfer",
#                         "raw_text": null,
#                         "value": null, "unit": "mm", "symbol": null,
#                         "tolerance": null,
#                         "leaders": ["gear tip edge"],
#                         "note": "From GEAR TIP CHAMFER view — e.g. 0.35×0.1"
#                         }
#                     ],
#                     "features": [
#                         {
#                         "id": "feat_rim",
#                         "type": "cylindrical_rim",
#                         "role": "gear_tip",
#                         "outer_diameter_dim_ids": ["dim_outer_dia"],
#                         "face_width_dim_ids": ["dim_face_width"],
#                         "table_links": ["tbl_gear_data"]
#                         },
#                         {
#                         "id": "feat_hub",
#                         "type": "cylindrical_step",
#                         "role": "hub_outer",
#                         "diameter_dim_ids": ["dim_hub_dia"],
#                         "length_dim_ids": ["dim_hub_height"]
#                         },
#                         {
#                         "id": "feat_bore_main",
#                         "type": "cylindrical_bore",
#                         "role": "through_bore",
#                         "diameter_dim_ids": ["dim_bore"],
#                         "length_dim_ids": ["dim_hub_height"],
#                         "fit_class": null
#                         },
#                         {
#                         "id": "feat_spline",
#                         "type": "internal_spline",
#                         "role": "spline_bore",
#                         "table_links": ["tbl_spline_data"]
#                         },
#                         {
#                         "id": "feat_lead_crown",
#                         "type": "tooth_modification",
#                         "role": "lead_crowning",
#                         "dim_ids": ["dim_crown_radius", "dim_crown_depth"],
#                         "view_id": "view_lead_crown"
#                         },
#                         {
#                         "id": "feat_tooth_edge_chamfer",
#                         "type": "chamfer",
#                         "role": "tooth_edge_chamfer",
#                         "dim_ids": ["dim_tooth_edge_chamfer"],
#                         "view_id": "view_tooth_edge_chamfer"
#                         },
#                         {
#                         "id": "feat_tip_chamfer",
#                         "type": "chamfer",
#                         "role": "gear_tip_chamfer",
#                         "dim_ids": ["dim_tip_chamfer"],
#                         "view_id": "view_tip_chamfer"
#                         }
#                     ],
#                     "assembly_order": [
#                         {"op": "revolve",   "feature_id": "feat_rim"},
#                         {"op": "revolve",   "feature_id": "feat_hub"},
#                         {"op": "subtract",  "feature_id": "feat_bore_main"},
#                         {"op": "subtract",  "feature_id": "feat_spline"},
#                         {"op": "modify",    "feature_id": "feat_lead_crown"},
#                         {"op": "chamfer",   "feature_id": "feat_tooth_edge_chamfer"},
#                         {"op": "chamfer",   "feature_id": "feat_tip_chamfer"}
#                     ],
#                     "metadata": {
#                         "title_block": {
#                         "drawing_no": null,
#                         "part_name": null,
#                         "material": null,
#                         "scale": null,
#                         "company_name": null,
#                         "division": null,
#                         "revision": null,
#                         "projection": null
#                         }
#                     }
#                     }

#                     ════════════════════════════════════════════════════════
#                     PATCH A — RANGE vs TOLERANCE DISTINCTION (fixes Heat / Surface / Forging)
#                     ════════════════════════════════════════════════════════

#                     CRITICAL: "value" vs "tolerance" field assignment rules — follow EXACTLY:

#                     ### RULE A1 — Process parameter ranges → always go in "value"
#                     Heat treatment, surface treatment, and forging cells contain PROCESS RANGES,
#                     not tolerances. A process range is the full acceptable specification for a
#                     manufacturing parameter. It ALWAYS goes in the "value" field as a string.
#                     The "tolerance" field for these cells is ALWAYS null.

#                     CORRECT examples:
#                     {"label": "CASE CARBURIZED DEPTH", "value": "0.9-1.2",  "unit": "mm",   "tolerance": null}
#                     {"label": "SURFACE HARDNESS",      "value": "58-62",    "unit": "HRC",  "tolerance": null}
#                     {"label": "CORE HARDNESS",         "value": "32-42",    "unit": "HRC",  "tolerance": null}
#                     {"label": "NORMALIZED TO",         "value": "155-185",  "unit": "BHN",  "tolerance": null}
#                     {"label": "GRAIN SIZE",            "value": "5 TO 8",   "unit": "ASTM", "tolerance": null}
#                     {"label": "MAX BAINITE",           "value": 5,          "unit": "%",    "tolerance": null}

#                     WRONG — never do this:
#                     {"label": "SURFACE HARDNESS", "value": null, "tolerance": "58-62"}  ← WRONG

#                     ### RULE A2 — Inequality operators (≤, <, >, ≥) are part of "value", not "tolerance"
#                     When a cell reads "≤ 1 MM" or "<= 1", store the ENTIRE expression
#                     (operator + number) as the value string. Never split the operator into
#                     the tolerance field.

#                     CORRECT:
#                     {"label": "SHOT BLAST SHOT SIZE", "value": "<= 1", "unit": "mm", "tolerance": null}

#                     WRONG:
#                     {"label": "SHOT BLAST SHOT SIZE", "value": 1.0, "tolerance": "≤"}  ← WRONG

#                     ### RULE A3 — Geometric dimension tolerances → go in "tolerance", numeric value in "value"
#                     Only dimensional callouts on the drawing (diameter, length, span measurement)
#                     use the "tolerance" field. These always have a plain numeric value in "value"
#                     and a deviation string in "tolerance".

#                     CORRECT:
#                     {"label": "SPAN MEASUREMENT", "value": 49.942, "unit": "mm", "tolerance": "-0.074/-0.118"}
#                     {"label": "CENTER DISTANCE",  "value": 103.0,  "unit": "mm", "tolerance": "± 0.05"}

#                     Quick test: If the cell is in a heat/surface/forging table → value gets the range,
#                     tolerance is null. If the cell is a dimension with ±/−/+ deviation → value gets
#                     the number, tolerance gets the deviation string.


#                     ════════════════════════════════════════════════════════
#                     PATCH B — LEAD CROWNING DETAIL PARSING (fixes detail sub-view accuracy)
#                     ════════════════════════════════════════════════════════

#                     ### RULE B1 — The lead crowning annotation encodes THREE distinct values in one line
#                     The LEAD CROWNING DETAIL view typically contains an annotation in this format:
#                         "Rx.x×y.y DEEP, CROWNED"
#                     or split across two lines. Parse it strictly as follows:

#                     Part 1 — Crown radius:     The number immediately after "R" prefix.
#                                                 Example: "R3.8×0.3 DEEP" → crown_radius = 3.8
#                                                 Store as: dim_crown_radius, value=3.8, symbol="R"

#                     Part 2 — Crown depth:      The number immediately before the word "DEEP".
#                                                 Example: "R3.8×0.3 DEEP" → crown_depth = 0.3
#                                                 Store as: dim_crown_depth, value=0.3, unit="mm"

#                     Part 3 — Crowning tolerance band: A small range annotation (e.g. 0.005–0.015)
#                                                 that appears separately from the Rx.x annotation.
#                                                 This is the crowning deviation band, NOT the depth.
#                                                 Store as: dim_crown_tolerance, value="0.005-0.015", unit="mm"

#                     NEVER merge these three into one field.
#                     NEVER assign the crowning tolerance band (0.005–0.015) to dim_crown_depth.
#                     If any of the three is not visible, set value=null, source="missing_on_drawing".

#                     JSON output for this view:
#                     {
#                         "id": "dim_crown_radius",
#                         "view_id": "view_lead_crown",
#                         "raw_text": "R3.8×0.3 DEEP, CROWNED",
#                         "value": 3.8, "unit": "mm", "symbol": "R", "tolerance": null
#                     },
#                     {
#                         "id": "dim_crown_depth",
#                         "view_id": "view_lead_crown",
#                         "raw_text": "0.3 DEEP",
#                         "value": 0.3, "unit": "mm", "symbol": null, "tolerance": null
#                     },
#                     {
#                         "id": "dim_crown_tolerance",
#                         "view_id": "view_lead_crown",
#                         "raw_text": "0.005-0.015",
#                         "value": "0.005-0.015", "unit": "mm", "tolerance": null,
#                         "note": "Crowning band tolerance — separate from crown depth"
#                     }


#                     ════════════════════════════════════════════════════════
#                     PATCH C — CHAMFER DIMENSION PARSING (fixes Gear Tooth Edge Chamfer)
#                     ════════════════════════════════════════════════════════

#                     ### RULE C1 — Chamfer format is ALWAYS "A×B", never a range "A–B"
#                     Chamfer dimensions on gear drawings use the format:
#                         A×B  (A times B, using the × multiplication symbol)
#                     where:
#                     A = first dimension (axial or lead-in distance)
#                     B = second dimension (radial or depth distance)

#                     The × separator looks visually similar to a dash (–) or hyphen (-) but
#                     means something completely different. NEVER read "A×B" as a range "A to B".

#                     ### RULE C2 — Extract both sub-dimensions separately
#                     For every chamfer dimension, extract:
#                     "dim_axial":  the A value (first number)
#                     "dim_radial": the B value (second number)
#                     "raw_text":   the exact annotation text including the × symbol

#                     CORRECT:
#                     {
#                         "id": "dim_tooth_edge_chamfer",
#                         "view_id": "view_tooth_edge_chamfer",
#                         "raw_text": "0.5×1.0 GEAR TOOTH EDGE CHAMFER BOTH SIDES",
#                         "dim_axial": 0.5,
#                         "dim_radial": 1.0,
#                         "unit": "mm",
#                         "note": "BOTH SIDES — applies to all gear tooth edges"
#                     }

#                     WRONG:
#                     {"raw_text": "0.3-1.0 ...", "tolerance": "0.3-1.0"}  ← reads × as range, WRONG

#                     ### RULE C3 — "BOTH SIDES" / "TYP" annotations are notes, not tolerances
#                     If the chamfer annotation includes "BOTH SIDES", "TYP.", or "ALL TEETH",
#                     capture these as a "note" string field, not as part of the tolerance.

#                     ### RULE C4 — Gear tip chamfer typically repeats the same value twice
#                     The GEAR TIP CHAMFER view often shows the same dimension on both the axial
#                     and radial sides (e.g. 0.35×0.35). If only one value is visible, assume
#                     it applies to both sides and record:
#                     dim_axial = dim_radial = that value.

#                     CORRECT:
#                     {
#                         "id": "dim_tip_chamfer",
#                         "view_id": "view_tip_chamfer",
#                         "raw_text": "0.35×0.35",
#                         "dim_axial": 0.35,
#                         "dim_radial": 0.35,
#                         "unit": "mm",
#                         "tolerance": "± 0.1"
#                     }


#                     ════════════════════════════════════════════════════════
#                     QUICK DECISION TABLE — use this before writing any cell value
#                     ════════════════════════════════════════════════════════

#                     | What you see on drawing          | "value" field          | "tolerance" field     |
#                     |----------------------------------|------------------------|-----------------------|
#                     | 58–62 HRC (heat treat)           | "58-62" (string)       | null                  |
#                     | 0.9–1.2 mm (case depth)          | "0.9-1.2" (string)     | null                  |
#                     | ≤ 1 mm (shot size)               | "<= 1" (string)        | null                  |
#                     | 49.942 −0.074/−0.118 (span)      | 49.942 (number)        | "-0.074/-0.118"       |
#                     | 103.0 ± 0.05 (centre dist)       | 103.0 (number)         | "± 0.05"              |
#                     | R3.8×0.3 DEEP (crown annotation) | 3.8 for radius entry   | null                  |
#                     |                                  | 0.3 for depth entry    | null                  |
#                     | 0.5×1.0 (chamfer)                | split: axial=0.5       | null                  |
#                     |                                  |        radial=1.0      |                       |
#                     | 0.005–0.015 (crown tolerance)    | "0.005-0.015" (string) | null                  |
#                     """
#             input_token_info = self.count_total_tokens_for_request(PROMPT, image_path)
#             logger.info(f"Input tokens - Prompt: {input_token_info['prompt_tokens']}, Image: {input_token_info['image_tokens']}, Total: {input_token_info['total_input_tokens']}")
            
#             uploaded_file = await self.upload_image_to_gemini(image_path)
            
#             response = model.generate_content(
#                 [PROMPT, uploaded_file],
#                 generation_config={"temperature": 0.0}
#             )
#             response_text = response.text.strip()
            
#             output_tokens = self.count_tokens_accurate(response_text)
#             total_tokens = input_token_info['total_input_tokens'] + output_tokens
            
#             logger.info(f"Token usage - Input: {input_token_info['total_input_tokens']}, Output: {output_tokens}, Total: {total_tokens}")
            
#             if response_text.startswith("```json"):
#                 response_text = response_text[7:-3].strip()
#             elif response_text.startswith("```"):
#                 response_text = response_text[3:-3].strip()
            
#             parsed_data = json.loads(response_text)
#             logger.info("Successfully parsed JSON response from Gemini")
            
#             parsed_data["token_usage"] = {
#                 "input_tokens": {
#                     "prompt_tokens": input_token_info['prompt_tokens'],
#                     "image_tokens": input_token_info['image_tokens'],
#                     "total_input_tokens": input_token_info['total_input_tokens']
#                 },
#                 "output_tokens": output_tokens,
#                 "total_tokens": total_tokens,
#                 "token_counting_method": "gemini_api_with_estimation_fallback",
#                 "image_dimensions": self._get_image_dimensions(image_path)
#             }
            
#             return parsed_data
            
#         except json.JSONDecodeError as e:
#             logger.error(f"JSON parsing error: {str(e)}")
#             logger.error(f"Response text: {response_text[:1000]}...")
            
#             input_token_info = self.count_total_tokens_for_request(PROMPT, image_path) if 'PROMPT' in locals() else {"prompt_tokens": 0, "image_tokens": 0, "total_input_tokens": 0}
#             output_tokens = self.count_tokens_accurate(response_text) if 'response_text' in locals() else 0
            
#             return {
#                 "error": f"Invalid JSON response from AI model: {str(e)}",
#                 "extracted_data": {},
#                 "token_usage": {
#                     "input_tokens": input_token_info,
#                     "output_tokens": output_tokens,
#                     "total_tokens": input_token_info.get('total_input_tokens', 0) + output_tokens,
#                     "token_counting_method": "gemini_api_with_estimation_fallback"
#                 }
#             }
#         except Exception as e:
#             logger.error(f"Technical drawing extraction failed: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
            
#             input_token_info = self.count_total_tokens_for_request(PROMPT, image_path) if 'PROMPT' in locals() else {"prompt_tokens": 0, "image_tokens": 0, "total_input_tokens": 0}
            
#             return {
#                 "error": str(e),
#                 "file": os.path.basename(image_path),
#                 "token_usage": {
#                     "input_tokens": input_token_info,
#                     "output_tokens": 0,
#                     "total_tokens": input_token_info.get('total_input_tokens', 0),
#                     "token_counting_method": "gemini_api_with_estimation_fallback"
#                 }
#             }
    
#     def _get_image_dimensions(self, image_path: str) -> Dict[str, Any]:
#         """Get image dimensions for token calculation reference"""
#         try:
#             with Image.open(image_path) as img:
#                 return {
#                     "width": img.width,
#                     "height": img.height,
#                     "total_pixels": img.width * img.height,
#                     "format": img.format
#                 }
#         except Exception:
#             return {"error": "Could not read image dimensions"}

#     async def process_all_data(self, data: Dict, filename: str) -> List[Dict]:
#         """Process all data into a flat structure for CSV output with universal organization"""
#         try:
#             logger.info(f"Processing data for CSV output: {filename}")
            
#             records = []
            
#             def create_universal_records(data, filename):
#                 universal_records = []
                
#                 if "drawing_metadata" in data:
#                     metadata_record = {
#                         "Filename": filename,
#                         "Record_Type": "Drawing_Metadata",
#                         **{f"Meta_{k}": v for k, v in data["drawing_metadata"].items()}
#                     }
#                     universal_records.append(metadata_record)
                
#                 if "overall_dimensions" in data:
#                     overall_record = {
#                         "Filename": filename,
#                         "Record_Type": "Overall_Dimensions",
#                         **{f"Overall_{k}": v for k, v in data["overall_dimensions"].items()}
#                     }
#                     universal_records.append(overall_record)
                
#                 if "feature_dimensions" in data and isinstance(data["feature_dimensions"], list):
#                     for i, feature in enumerate(data["feature_dimensions"]):
#                         feature_record = {
#                             "Filename": filename,
#                             "Record_Type": "Feature_Dimension",
#                             "Feature_Index": i + 1,
#                             **{f"Feature_{k}": v for k, v in feature.items()}
#                         }
#                         universal_records.append(feature_record)
                
#                 if "tolerances" in data:
#                     tol_record = {
#                         "Filename": filename,
#                         "Record_Type": "Tolerances",
#                         **{f"Tol_{k}": v for k, v in data["tolerances"].items()}
#                     }
#                     universal_records.append(tol_record)
                
#                 if "geometric_tolerances" in data and isinstance(data["geometric_tolerances"], list):
#                     for i, geo_tol in enumerate(data["geometric_tolerances"]):
#                         geo_record = {
#                             "Filename": filename,
#                             "Record_Type": "Geometric_Tolerance",
#                             "Tolerance_Index": i + 1,
#                             **{f"GeoTol_{k}": v for k, v in geo_tol.items()}
#                         }
#                         universal_records.append(geo_record)
                
#                 if "surface_specifications" in data and isinstance(data["surface_specifications"], list):
#                     for i, surface in enumerate(data["surface_specifications"]):
#                         surface_record = {
#                             "Filename": filename,
#                             "Record_Type": "Surface_Specification",
#                             "Surface_Index": i + 1,
#                             **{f"Surface_{k}": v for k, v in surface.items()}
#                         }
#                         universal_records.append(surface_record)
                
#                 if "threaded_features" in data and isinstance(data["threaded_features"], list):
#                     for i, thread in enumerate(data["threaded_features"]):
#                         thread_record = {
#                             "Filename": filename,
#                             "Record_Type": "Threaded_Feature",
#                             "Thread_Index": i + 1,
#                             **{f"Thread_{k}": v for k, v in thread.items()}
#                         }
#                         universal_records.append(thread_record)
                
#                 if "section_views" in data and isinstance(data["section_views"], list):
#                     for i, section in enumerate(data["section_views"]):
#                         section_record = {
#                             "Filename": filename,
#                             "Record_Type": "Section_View",
#                             "Section_Index": i + 1,
#                             **{f"Section_{k}": v for k, v in section.items()}
#                         }
#                         universal_records.append(section_record)
                
#                 if "manufacturing_notes" in data and isinstance(data["manufacturing_notes"], list):
#                     for i, note in enumerate(data["manufacturing_notes"]):
#                         note_record = {
#                             "Filename": filename,
#                             "Record_Type": "Manufacturing_Note",
#                             "Note_Index": i + 1,
#                             **{f"Note_{k}": v for k, v in note.items()}
#                         }
#                         universal_records.append(note_record)
                
#                 if "tables_and_data" in data and isinstance(data["tables_and_data"], list):
#                     for i, table in enumerate(data["tables_and_data"]):
#                         table_record = {
#                             "Filename": filename,
#                             "Record_Type": "Table_Data",
#                             "Table_Index": i + 1,
#                             **{f"Table_{k}": v for k, v in table.items()}
#                         }
#                         universal_records.append(table_record)
                
#                 if "material_and_treatment" in data:
#                     material_record = {
#                         "Filename": filename,
#                         "Record_Type": "Material_Treatment",
#                         **{f"Material_{k}": v for k, v in data["material_and_treatment"].items()}
#                     }
#                     universal_records.append(material_record)
                
#                 if "quality_requirements" in data:
#                     quality_record = {
#                         "Filename": filename,
#                         "Record_Type": "Quality_Requirements",
#                         **{f"Quality_{k}": v for k, v in data["quality_requirements"].items()}
#                     }
#                     universal_records.append(quality_record)
                
#                 return universal_records
            
#             records = create_universal_records(data, filename)
            
#             if not records:
#                 def flatten_dict(d, parent_key='', record=None):
#                     if record is None:
#                         record = {"Filename": filename, "Record_Type": "General"}
                    
#                     for k, v in d.items():
#                         new_key = f"{parent_key}_{k}" if parent_key else k
                        
#                         if isinstance(v, dict):
#                             flatten_dict(v, new_key, record)
#                         elif isinstance(v, list):
#                             if v and isinstance(v[0], dict):
#                                 for i, item in enumerate(v):
#                                     list_record = {"Filename": filename, "Record_Type": f"{new_key}_Item_{i+1}"}
#                                     flatten_dict(item, new_key, list_record)
#                                     records.append(list_record)
#                             else:
#                                 record[new_key] = "; ".join(str(x) for x in v)
#                         else:
#                             record[new_key] = str(v)
                    
#                     return record
                
#                 main_record = flatten_dict(data)
#                 records.append(main_record)
            
#             logger.info(f"Processed {len(records)} total records")
#             return records
            
#         except Exception as e:
#             logger.error(f"Data processing error: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
#             return [{
#                 "Filename": filename,
#                 "Error": f"Data processing error: {str(e)}",
#                 "Record_Type": "Error"
#             }]

#     async def process_image_file(
#         self,
#         task_id: str,
#         file_path: str,
#         output_dir: str
#     ) -> Dict:
#         """Process image file using Gemini extraction"""
#         try:
#             logger.info(f"Starting image processing for task: {task_id}")
            
#             if not os.path.exists(file_path):
#                 raise FileNotFoundError(f"Image file not found: {file_path}")
                
#             file_size = os.path.getsize(file_path)
#             logger.info(f"File size: {file_size} bytes")
            
#             if file_size == 0:
#                 raise ValueError("Image file is empty")
                
#             os.makedirs(output_dir, exist_ok=True)
#             base_filename = os.path.join(output_dir, task_id)
            
#             file_info = {
#                 "task_id": task_id,
#                 "original_filename": os.path.basename(file_path),
#                 "stored_filename": f"{task_id}_{os.path.basename(file_path)}",
#                 "file_path": file_path,
#                 "output_path": base_filename,
#                 "status": "processing",
#                 "file_size": file_size,
#                 "created_at": datetime.now().isoformat()
#             }
            
#             self.processed_files[task_id] = file_info
            
#             extracted_data = await self.extract_technical_drawing_data(file_path)
            
#             status = "completed" if "error" not in extracted_data else "completed_with_errors"
#             self.processed_files[task_id]["status"] = status
            
#             json_output = {
#                 "task_id": task_id,
#                 "filename": os.path.basename(file_path),
#                 "file_size": file_size,
#                 "extracted_data": extracted_data,
#                 "status": status,
#                 "timestamp": datetime.now().isoformat()
#             }
            
#             json_file_path = f"{base_filename}.json"
#             with open(json_file_path, "w", encoding='utf-8') as f:
#                 json.dump(json_output, f, indent=2, ensure_ascii=False)
#             logger.info(f"JSON output saved to: {json_file_path}")
            
#             csv_file_path = f"{base_filename}.csv"
#             processed_data = await self.process_all_data(extracted_data, os.path.basename(file_path))
            
#             if processed_data and len(processed_data) > 0:
#                 with open(csv_file_path, "w", newline="", encoding='utf-8') as csvfile:
#                     fieldnames = set()
#                     for record in processed_data:
#                         fieldnames.update(record.keys())
                    
#                     writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
#                     writer.writeheader()
#                     writer.writerows(processed_data)
#                 logger.info(f"CSV output saved to: {csv_file_path}")
            
#             return {
#                 "status": status,
#                 "output_path": base_filename,
#                 "file_size": file_size,
#                 "has_errors": "error" in extracted_data,
#                 "json_path": json_file_path,
#                 "csv_path": csv_file_path,
#                 "token_usage": extracted_data.get("token_usage", {})
#             }
            
#         except FileNotFoundError as e:
#             logger.error(f"File not found error: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
#             return {
#                 "status": "failed",
#                 "error": f"File not found: {str(e)}",
#                 "error_type": "file_not_found"
#             }
#         except ValueError as e:
#             logger.error(f"Value error: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
#             return {
#                 "status": "failed",
#                 "error": f"Invalid file or data: {str(e)}",
#                 "error_type": "invalid_data"
#             }
#         except Exception as e:
#             logger.error(f"Unexpected error in image processing: {str(e)}")
#             logger.error(f"Traceback: {traceback.format_exc()}")
#             return {
#                 "status": "failed",
#                 "error": f"Processing error: {str(e)}",
#                 "error_type": "processing_error"
#             }

#     def get_file_info(self, task_id: str) -> Optional[Dict]:
#         """Retrieve file information by task ID"""
#         return self.processed_files.get(task_id)

#     def get_all_processed_files(self) -> Dict:
#         """Get all processed files"""
#         return self.processed_files

#     def update_file_status(self, task_id: str, status: str) -> Optional[Dict]:
#         """Update file status"""
#         if task_id in self.processed_files:
#             self.processed_files[task_id]["status"] = status
#             self.processed_files[task_id]["updated_at"] = datetime.now().isoformat()
#             return self.processed_files[task_id]
#         return None

#     def delete_file_info(self, task_id: str) -> bool:
#         """Delete file information"""
#         if task_id in self.processed_files:
#             del self.processed_files[task_id]
#             return True
#         return False

    
#     def get_drawing_type_from_data(self, extracted_data: Dict) -> str:
#         """Determine drawing type from extracted data"""
#         try:
#             if "drawing_metadata" in extracted_data:
#                 drawing_type = extracted_data["drawing_metadata"].get("drawing_type", "unknown")
#                 component_type = extracted_data["drawing_metadata"].get("component_type", "")
#                 return f"{drawing_type}_{component_type}".replace(" ", "_").lower()
#             return "unknown"
#         except:
#             return "unknown"
    
#     def get_critical_dimensions(self, extracted_data: Dict) -> List[Dict]:
#         """Extract only critical dimensions for quick reference"""
#         critical_dims = []
        
#         try:
#             if "overall_dimensions" in extracted_data:
#                 for dim_name, dim_data in extracted_data["overall_dimensions"].items():
#                     if isinstance(dim_data, dict) and "value" in dim_data:
#                         critical_dims.append({
#                             "type": "overall",
#                             "feature": dim_name,
#                             "value": dim_data["value"],
#                             "unit": dim_data.get("unit", ""),
#                             "tolerance": dim_data.get("tolerance", "")
#                         })
            
#             if "feature_dimensions" in extracted_data:
#                 for feature in extracted_data["feature_dimensions"]:
#                     if isinstance(feature, dict) and "dimensions" in feature:
#                         feature_type = feature.get("feature_type", "unknown")
#                         dims = feature["dimensions"]
#                         if isinstance(dims, dict):
#                             for dim_key, dim_data in dims.items():
#                                 if isinstance(dim_data, dict) and "value" in dim_data:
#                                     critical_dims.append({
#                                         "type": "feature",
#                                         "feature": f"{feature_type}_{dim_key}",
#                                         "value": dim_data["value"],
#                                         "unit": dim_data.get("unit", ""),
#                                         "tolerance": dim_data.get("tolerance", "")
#                                     })
            
#             return critical_dims
            
#         except Exception as e:
#             logger.warning(f"Error extracting critical dimensions: {str(e)}")
#             return []
    
#     def generate_summary_report(self, extracted_data: Dict, filename: str) -> Dict:
#         """Generate a summary report of extracted data"""
#         try:
#             summary = {
#                 "filename": filename,
#                 "drawing_type": self.get_drawing_type_from_data(extracted_data),
#                 "extraction_timestamp": datetime.now().isoformat(),
#                 "has_errors": "error" in extracted_data,
#                 "data_completeness": {}
#             }
            
#             element_counts = {}
#             if "feature_dimensions" in extracted_data:
#                 element_counts["feature_dimensions"] = len(extracted_data["feature_dimensions"]) if isinstance(extracted_data["feature_dimensions"], list) else 0
            
#             if "geometric_tolerances" in extracted_data:
#                 element_counts["geometric_tolerances"] = len(extracted_data["geometric_tolerances"]) if isinstance(extracted_data["geometric_tolerances"], list) else 0
            
#             if "manufacturing_notes" in extracted_data:
#                 element_counts["manufacturing_notes"] = len(extracted_data["manufacturing_notes"]) if isinstance(extracted_data["manufacturing_notes"], list) else 0
            
#             if "threaded_features" in extracted_data:
#                 element_counts["threaded_features"] = len(extracted_data["threaded_features"]) if isinstance(extracted_data["threaded_features"], list) else 0
            
#             summary["element_counts"] = element_counts
#             summary["critical_dimensions"] = self.get_critical_dimensions(extracted_data)
#             summary["token_usage"] = extracted_data.get("token_usage", {})
            
#             return summary
            
#         except Exception as e:
#             logger.error(f"Error generating summary report: {str(e)}")
#             return {
#                 "filename": filename,
#                 "error": f"Summary generation failed: {str(e)}",
#                 "extraction_timestamp": datetime.now().isoformat()
#             }

#     def export_to_specific_format(self, extracted_data: Dict, format_type: str) -> str:
#         """Export data to specific formats (CAD import, inspection sheets, etc.)"""
#         try:
#             if format_type.lower() == "inspection_sheet":
#                 return self._create_inspection_sheet_format(extracted_data)
#             elif format_type.lower() == "cad_import":
#                 return self._create_cad_import_format(extracted_data)
#             elif format_type.lower() == "manufacturing_sheet":
#                 return self._create_manufacturing_sheet_format(extracted_data)
#             else:
#                 return "Unsupported format type"
                
#         except Exception as e:
#             logger.error(f"Export format error: {str(e)}")
#             return f"Export failed: {str(e)}"
    
#     def _create_inspection_sheet_format(self, data: Dict) -> str:
#         """Create inspection sheet format"""
#         lines = ["=== INSPECTION SHEET ===\n"]
        
#         if "drawing_metadata" in data:
#             meta = data["drawing_metadata"]
#             lines.append(f"Part Name: {meta.get('part_name', 'N/A')}")
#             lines.append(f"Drawing Number: {meta.get('drawing_number', 'N/A')}")
#             lines.append(f"Revision: {meta.get('revision', 'N/A')}")
#             lines.append(f"Material: {meta.get('material_specification', 'N/A')}\n")
        
#         critical_dims = self.get_critical_dimensions(data)
#         if critical_dims:
#             lines.append("=== CRITICAL DIMENSIONS FOR INSPECTION ===")
#             for dim in critical_dims:
#                 lines.append(f"• {dim['feature']}: {dim['value']} {dim['unit']} {dim.get('tolerance', '')}")
#             lines.append("")
        
#         if "geometric_tolerances" in data and data["geometric_tolerances"]:
#             lines.append("=== GEOMETRIC TOLERANCES ===")
#             for tol in data["geometric_tolerances"]:
#                 lines.append(f"• {tol.get('tolerance_type', 'Unknown')}: {tol.get('tolerance_value', 'N/A')} - {tol.get('feature', 'Unknown feature')}")
#             lines.append("")
        
#         return "\n".join(lines)
    
#     def _create_cad_import_format(self, data: Dict) -> str:
#         """Create CAD import compatible format"""
#         lines = ["# CAD Import Data"]
        
#         if "overall_dimensions" in data:
#             lines.append("## Overall Dimensions")
#             for dim_name, dim_data in data["overall_dimensions"].items():
#                 if isinstance(dim_data, dict) and "value" in dim_data:
#                     lines.append(f"{dim_name.upper()},{dim_data['value']},{dim_data.get('unit', 'mm')}")
        
#         return "\n".join(lines)
    
#     def _create_manufacturing_sheet_format(self, data: Dict) -> str:
#         """Create manufacturing instruction sheet"""
#         lines = ["=== MANUFACTURING INSTRUCTIONS ===\n"]
        
#         if "material_and_treatment" in data:
#             mat = data["material_and_treatment"]
#             lines.append("=== MATERIAL REQUIREMENTS ===")
#             lines.append(f"Base Material: {mat.get('base_material', 'N/A')}")
#             lines.append(f"Heat Treatment: {mat.get('heat_treatment', 'N/A')}")
#             lines.append(f"Hardness: {mat.get('hardness_requirement', 'N/A')}\n")
        
#         if "manufacturing_notes" in data and data["manufacturing_notes"]:
#             lines.append("=== MANUFACTURING NOTES ===")
#             for note in data["manufacturing_notes"]:
#                 lines.append(f"• {note.get('note_text', 'N/A')} ({note.get('note_type', 'General')})")
#             lines.append("")
        
#         return "\n".join(lines)




import os
import uuid
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional, Any
from PIL import Image
import base64
import io

from app.log.logger import get_logger

logger = get_logger(__name__)
load_dotenv()
# Ensure the Google API key is provided via environment variable and is not empty.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY is not set.\n"
        "Steps to fix:\n"
        "1) Rotate the leaked API key in Google Cloud Console (disable/delete the exposed key).\n"
        "2) Create a new API key and restrict it (HTTP referrers, IPs, and enabled APIs).\n"
        "3) Set the new key in environment variable GOOGLE_API_KEY (do NOT commit it).\n"
        "4) For local dev, add it to your shell profile or a local .env (ensure .env is in .gitignore).\n"
    )
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

class TechnicalDrawingExtractionService:
    def __init__(self):
        self.processed_files = {}  
    
    def clean_text(self, text: str) -> str:
        """Remove non-UTF-8 characters and null bytes from text"""
        if not text:
            return ""
        
        text = text.replace('\x00', '')
        
        try:
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            text = text.encode('ascii', errors='ignore').decode('ascii')
        
        return text.strip()

    def count_tokens_accurate(self, text: str) -> int:
        """
        More accurate token counting using Gemini's count_tokens method.
        Falls back to improved estimation if API call fails.
        """
        try:
            if not text:
                return 0
            
            token_count = model.count_tokens(text)
            return token_count.total_tokens
            
        except Exception as e:
            logger.warning(f"Failed to get accurate token count, using estimation: {str(e)}")
            return self.estimate_tokens(text)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Improved token estimation for Gemini models.
        Based on analysis that Gemini tokenization is closer to:
        - ~3.5-4 characters per token for English
        - Technical terms and numbers may have different ratios
        """
        if not text:
            return 0
        
        words = text.split()
        chars = len(text)
        
        base_tokens = chars / 3.5
        
        technical_chars = sum(1 for c in text if c in '()[]{}+-=<>≥≤±∅°')
        if technical_chars > chars * 0.1: 
            base_tokens = chars / 3.0  
        
        return int(base_tokens)

    def estimate_image_tokens(self, image_path: str) -> int:
        """
        Estimate tokens consumed by an image.
        Gemini's image token consumption depends on image size and resolution.
        """
        try:
            if not os.path.exists(image_path):
                return 0
            
            with Image.open(image_path) as img:
                width, height = img.size
                
            pixels = width * height
            
            if pixels <= 512 * 512:
                return 258 
            elif pixels <= 1024 * 1024:
                return 516  
            else:
                return 774  
                
        except Exception as e:
            logger.warning(f"Could not estimate image tokens: {str(e)}")
            return 500  
    
    def count_total_tokens_for_request(self, prompt: str, image_path: str = None) -> Dict[str, int]:
        """
        Count total tokens for a complete request including prompt and image.
        """
        prompt_tokens = self.count_tokens_accurate(prompt)
        image_tokens = self.estimate_image_tokens(image_path) if image_path else 0
        
        return {
            "prompt_tokens": prompt_tokens,
            "image_tokens": image_tokens,
            "total_input_tokens": prompt_tokens + image_tokens
        }

    async def upload_image_to_gemini(self, image_path: str) -> Any:
        """Upload image file to Gemini"""
        try:
            logger.info(f"Uploading image file to Gemini: {image_path}")
            
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
                
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                raise ValueError("Image file is empty")
                
            uploaded_file = genai.upload_file(image_path)
            logger.info(f"Successfully uploaded image to Gemini")
            return uploaded_file
            
        except Exception as e:
            logger.error(f"Failed to upload image to Gemini: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Image upload failed: {str(e)}")

    async def extract_technical_drawing_data(self, image_path: str) -> Dict:
        """Extract technical drawing data from image using Gemini - Universal Version"""
        try:
            logger.info(f"Starting technical drawing extraction for: {image_path}")
            

            PROMPT = """
                    You are an expert mechanical drawing interpreter. Your role is to extract ONLY the
                    explicitly printed information from a mechanical gear drawing and return a structured JSON.

                    ════════════════════════════════════════════════════════
                    SECTION 1 — ABSOLUTE RULES
                    ════════════════════════════════════════════════════════
                    1. Never invent values. If a value is not visible, set "value": null and
                    "source": "missing_on_drawing".
                    2. Root diameter is NOT a cavity. Do not treat root_diameter as hollow volume.
                    3. Face width vs hub height — CRITICAL:
                    - Face width  = axial dimension of ONLY the gear rim/toothed section (SMALLER value)
                    - Hub height  = TOTAL axial dimension of the complete assembly (LARGER value)
                    - Hub height is ALWAYS greater than face width. If not, SWAP assignments.
                    4. Bore subtraction passes through the full axial stack (face_width + hub_extension).
                    5. Preserve all units, tolerances, and symbols exactly (⌀, ±, H7, −0.1, etc.).
                    6. Copy source text exactly into "raw_text".
                    7. Always include "view_id" and leader arrow mapping where visible.
                    8. All tables (gear data, spline data, permissible deviations, heat-treat, material,
                    surface treatment, forging details) must appear in "tables" and be linked via
                    features[*].table_links.

                    ════════════════════════════════════════════════════════
                    SECTION 2 — MANDATORY SCAN SEQUENCE (follow this ORDER)
                    ════════════════════════════════════════════════════════
                    Before writing any JSON, scan the drawing in this fixed order and take notes:

                    STEP A — Inventory every named view:
                    List every view label found on the drawing:
                    e.g. "SECTION A-A", "SECTION B-B", "ISOMETRIC VIEW",
                        "LEAD CROWNING DETAIL", "GEAR TOOTH EDGE CHAMFER", "GEAR TIP CHAMFER".
                    Assign each a unique view_id (view_main, view_iso, view_lead_crown,
                    view_tooth_edge_chamfer, view_tip_chamfer, etc.).
                    Do not skip any labeled sub-view, no matter how small.

                    STEP B — Inventory every dimension callout in EVERY view:
                    For each dimension line found, record:
                        - The raw text exactly as printed
                        - Which view it belongs to
                        - What geometry it points to (leader endpoint descriptions)
                    Include dimensions in detail sub-views and callout boxes.

                    STEP C — Inventory every data table:
                    List every table found (gear data, spline data, permissible deviations,
                    heat treatment, surface treatment, forging details, title block).

                    STEP D — Inventory every note/general instruction block.

                    Only after completing steps A–D, assemble the JSON output.

                    ════════════════════════════════════════════════════════
                    SECTION 3 — DETAIL SUB-VIEW EXTRACTION (NEW — CRITICAL)
                    ════════════════════════════════════════════════════════
                    Gear drawings typically contain 2–4 small detail views in the lower-left corner.
                    Each MUST be extracted into its own dimension entries.

                    ### LEAD CROWNING DETAIL
                    - Look for a small sectional or profile view labeled "LEAD CROWNING DETAIL"
                    or "CENTRE OF CROWN".
                    - Extract: crowning radius (e.g. "R3.8×0.3 DEEP"), depth value, and any
                    associated annotation text.
                    - Assign view_id: "view_lead_crown"
                    - Add entries: dim_crown_radius, dim_crown_depth

                    ### GEAR TOOTH EDGE CHAMFER
                    - Look for a small angled detail view labeled "GEAR TOOTH EDGE CHAMFER".
                    - Extract: chamfer size (e.g. "0.5×1.0"), angle if shown, note "BOTH SIDES"
                    if stated.
                    - Assign view_id: "view_tooth_edge_chamfer"
                    - Add entry: dim_tooth_edge_chamfer

                    ### GEAR TIP CHAMFER
                    - Look for a small view labeled "GEAR TIP CHAMFER".
                    - Extract: chamfer dimensions (e.g. "0.35×0.1"), angle if shown.
                    - Assign view_id: "view_tip_chamfer"
                    - Add entry: dim_tip_chamfer

                    ### ISOMETRIC VIEW
                    - Assign view_id: "view_iso"
                    - No dimensions typically here, but note if any annotation is present.

                    For all detail sub-views:
                    - If a dimension is present but illegible due to image quality, set
                    "value": null, "source": "illegible_on_drawing".
                    - Never omit the view or its dimension entries — create the entry with null
                    if needed.

                    ════════════════════════════════════════════════════════
                    SECTION 4 — SECONDARY DIMENSIONS IN MAIN SECTION VIEW
                    ════════════════════════════════════════════════════════
                    In addition to the 5 primary dimensions, the main section view often contains
                    secondary dimensions that MUST also be captured:

                    - Top-level overall width dimension (e.g. "15.2±0.1") — often a small
                    dimension at the top of the section view spanning a sub-feature.
                    Add as: dim_overall_width or dim_sub_width with appropriate leader notes.
                    - Relief groove / small bore diameter (e.g. "⌀3.58") — small internal
                    annular groove visible in section.
                    Add as: dim_relief_groove_dia.
                    - Any shoulder, step, or undercut dimensions shown with leader lines.
                    - Spline entry chamfer dimensions if called out separately from the spline table.

                    Rule: Any printed dimension callout visible in ANY view must have a
                    corresponding entry in "dimensions". No callout may be silently skipped.

                    ════════════════════════════════════════════════════════
                    SECTION 5 — COMPONENT DEFINITIONS & IDENTIFICATION
                    ════════════════════════════════════════════════════════

                    ### BORE
                    - Central through-hole for shaft mounting.
                    - Symbols: ⌀, H7, H8, or fit designation.
                    - Spans full axial length unless otherwise noted.
                    - May contain internal splines or keyways.

                    ### RIM
                    - Outer circular section carrying gear teeth.
                    - Outer diameter = largest ⌀ on drawing (gear tip circle).
                    - Face width = SMALLER axial dimension (toothed section only).

                    ### HUB
                    - Cylindrical extension beyond the gear rim.
                    - Hub diameter = smaller ⌀ on hub section (not rim OD).
                    - Hub height = LARGER axial dimension (total assembly length end to end).

                    ### SPLINE
                    - Internal tooth profile inside bore for torque transmission.
                    - Has dedicated spline data table (DIN 5480 or similar standard).
                    - Extract: major dia, minor dia, no. of teeth, module, pressure angle,
                    pin measurement + tolerance, pin diameter.

                    ════════════════════════════════════════════════════════
                    SECTION 6 — DIMENSION ASSIGNMENT LOGIC CHECKS
                    ════════════════════════════════════════════════════════
                    1. Hub height > Face width — ALWAYS. If violated, SWAP.
                    2. Outer diameter > Hub diameter > Bore diameter.
                    3. Two axial dimensions exist → larger = hub_height, smaller = face_width.
                    4. Diameter hierarchy: tip OD > hub OD > bore ID.
                    5. All four chamfer/crowning detail views must yield at least one dim entry each
                    (null-valued if illegible, but the entry must exist).

                    ════════════════════════════════════════════════════════
                    SECTION 7 — TABLE EXTRACTION RULES
                    ════════════════════════════════════════════════════════
                    Extract ALL of the following tables if present:
                    tbl_gear_data          — module, teeth, pressure angle, helix angle,
                                            direction, coeff. of correction, span measurement
                                            (+ tolerance), quality/DIN, mating gear ref,
                                            centre distance (+ tolerance), pitch circle dia,
                                            base diameter, measurement over pins (+ tolerance),
                                            pin diameter, SAP, EAP, max TIF dia, operating PCD.
                    tbl_spline_data        — standard, fit type, no. of teeth, module,
                                            pressure angle, measurement between pins
                                            (+ tolerance), pin diameter, major dia
                                            (+ tolerance), minor dia (+ tolerance).
                    tbl_permissible_dev    — runout of faces, runout of gear pitch crown,
                                            double flank total Fi″, double flank tooth-to-tooth
                                            fi″, tooth trace form fβr, tooth alignment fHB,
                                            tooth trace total Fβ, profile form fα,
                                            profile angle fHα, total profile Fα.
                    tbl_heat_treatment     — carburize depth, surface hardness (HRC),
                                            core hardness (HRC).
                    tbl_surface_treatment  — shot blast shot size.
                    tbl_forging_details    — normalized BHN, grain size (ASTM),
                                            microstructure description, max bainite %.

                    For every cell: preserve exact label text, numeric value, unit, and
                    tolerance string as separate fields.

                    ════════════════════════════════════════════════════════
                    SECTION 8 — METADATA / TITLE BLOCK
                    ════════════════════════════════════════════════════════
                    Extract:
                    drawing_no, part_name, material, scale, company_name, division,
                    first_angle / third_angle projection indicator (if shown),
                    revision level (if shown).

                    ════════════════════════════════════════════════════════
                    SECTION 9 — OUTPUT JSON SCHEMA
                    ════════════════════════════════════════════════════════
                    Return ONLY valid JSON — no commentary, no markdown fences.

                    {
                    "units": "mm",
                    "views": [
                        {"id": "view_main",               "name": "SECTION B-B",            "bbox": null},
                        {"id": "view_iso",                "name": "ISOMETRIC VIEW",         "bbox": null},
                        {"id": "view_lead_crown",         "name": "LEAD CROWNING DETAIL",   "bbox": null},
                        {"id": "view_tooth_edge_chamfer", "name": "GEAR TOOTH EDGE CHAMFER","bbox": null},
                        {"id": "view_tip_chamfer",        "name": "GEAR TIP CHAMFER",       "bbox": null}
                    ],
                    "tables": [
                        {
                        "id": "tbl_gear_data",
                        "view_id": null,
                        "cells": [
                            {"label": "MODULE",                  "value": null, "unit": "mm"},
                            {"label": "NO. OF TEETH",            "value": null, "unit": null},
                            {"label": "PRESSURE ANGLE",          "value": null, "unit": "°"},
                            {"label": "HELIX ANGLE",             "value": null, "unit": "°"},
                            {"label": "DIRECTION OF HELIX",      "value": null, "unit": null},
                            {"label": "COEFFICIENT OF CORRECTION","value": null,"unit": null},
                            {"label": "SPAN MEASUREMENT OVER TEETH","value": null,"unit": null},
                            {"label": "SPAN MEASUREMENT",        "value": null, "unit": "mm",
                            "tolerance": null},
                            {"label": "QUALITY (DIN 3962-63)",   "value": null, "unit": null},
                            {"label": "MESHES WITH GEAR",        "value": null, "unit": null},
                            {"label": "CENTER DISTANCE",         "value": null, "unit": "mm",
                            "tolerance": null},
                            {"label": "PITCH CIRCLE DIAMETER",   "value": null, "unit": "mm"},
                            {"label": "BASE DIAMETER",           "value": null, "unit": "mm"},
                            {"label": "MEASUREMENT OVER PINS",   "value": null, "unit": "mm",
                            "tolerance": null},
                            {"label": "PIN DIAMETER",            "value": null, "unit": "mm"},
                            {"label": "SAP",                     "value": null, "unit": "mm"},
                            {"label": "EAP",                     "value": null, "unit": "mm"},
                            {"label": "MAX TRUE INVOLUTE FORM DIA (TIF)","value": null,"unit": "mm"},
                            {"label": "OPERATING PCD",           "value": null, "unit": "mm"}
                        ]
                        },
                        {
                        "id": "tbl_spline_data",
                        "view_id": null,
                        "cells": [
                            {"label": "STANDARD",               "value": null, "unit": null},
                            {"label": "FIT",                    "value": null, "unit": null},
                            {"label": "NO. OF TEETH",           "value": null, "unit": null},
                            {"label": "MODULE",                 "value": null, "unit": "mm"},
                            {"label": "PRESSURE ANGLE",         "value": null, "unit": "°"},
                            {"label": "MEASUREMENT BETWEEN PINS","value": null,"unit": "mm",
                            "tolerance": null},
                            {"label": "PIN DIAMETER",           "value": null, "unit": "mm"},
                            {"label": "MAJOR DIAMETER",         "value": null, "unit": "mm",
                            "tolerance": null},
                            {"label": "MINOR DIAMETER",         "value": null, "unit": "mm",
                            "tolerance": null}
                        ]
                        },
                        {
                        "id": "tbl_permissible_dev",
                        "view_id": null,
                        "cells": [
                            {"label": "REFERENCE: SPLINE PITCH CYLINDER","value": null,"unit": null},
                            {"label": "RUNOUT OF FACE A & B",            "value": null,"unit": null},
                            {"label": "RUNOUT OF GEAR PITCH CROWN",      "value": null,"unit": null},
                            {"label": "DOUBLE FLANK TOTAL ERROR (Fi\")", "value": null,"unit": null},
                            {"label": "DOUBLE FLANK TOOTH-TO-TOOTH (fi\")","value": null,"unit": null},
                            {"label": "TOOTH TRACE FORM DEVIATION (fβr)","value": null,"unit": null},
                            {"label": "TOOTH ALIGNMENT ERROR (fHB)",     "value": null,"unit": null},
                            {"label": "TOOTH TRACE TOTAL DEVIATION (Fβ)","value": null,"unit": null},
                            {"label": "PROFILE FORM DEVIATION (fα)",     "value": null,"unit": null},
                            {"label": "PROFILE ANGLE DEVIATION (fHα)",   "value": null,"unit": null},
                            {"label": "TOTAL PROFILE DEVIATION (Fα)",    "value": null,"unit": null}
                        ]
                        },
                        {
                        "id": "tbl_heat_treatment",
                        "view_id": null,
                        "cells": [
                            {"label": "CASE CARBURIZED DEPTH", "value": null, "unit": "mm"},
                            {"label": "SURFACE HARDNESS",      "value": null, "unit": "HRC"},
                            {"label": "CORE HARDNESS",         "value": null, "unit": "HRC"}
                        ]
                        },
                        {
                        "id": "tbl_surface_treatment",
                        "view_id": null,
                        "cells": [
                            {"label": "SHOT BLAST SHOT SIZE",  "value": null, "unit": "mm"}
                        ]
                        },
                        {
                        "id": "tbl_forging_details",
                        "view_id": null,
                        "cells": [
                            {"label": "NORMALIZED TO",         "value": null, "unit": "BHN"},
                            {"label": "GRAIN SIZE",            "value": null, "unit": "ASTM"},
                            {"label": "MICROSTRUCTURE",        "value": null, "unit": null},
                            {"label": "MAX BAINITE",           "value": null, "unit": "%"}
                        ]
                        }
                    ],
                    "dimensions": [
                        {
                        "id": "dim_outer_dia",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": "⌀",
                        "tolerance": null,
                        "leaders": ["gear tooth tip left", "gear tooth tip right"]
                        },
                        {
                        "id": "dim_hub_dia",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": "⌀",
                        "tolerance": null,
                        "leaders": ["hub outer surface left", "hub outer surface right"]
                        },
                        {
                        "id": "dim_face_width",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": ["left face of gear teeth", "right face of gear teeth"],
                        "note": "SMALLER of the two axial dimensions — toothed section only"
                        },
                        {
                        "id": "dim_hub_height",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": ["leftmost face of assembly", "rightmost face of assembly"],
                        "note": "LARGER of the two axial dimensions — total assembly length"
                        },
                        {
                        "id": "dim_bore",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": "⌀",
                        "tolerance": null,
                        "leaders": ["bore entry left", "bore entry right"]
                        },
                        {
                        "id": "dim_overall_width",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": [],
                        "note": "Secondary axial dimension callout if present (e.g. 15.2±0.1)"
                        },
                        {
                        "id": "dim_relief_groove_dia",
                        "view_id": "view_main",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": "⌀",
                        "tolerance": null,
                        "leaders": [],
                        "note": "Small internal relief/undercut groove diameter if visible"
                        },
                        {
                        "id": "dim_crown_radius",
                        "view_id": "view_lead_crown",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": "R",
                        "tolerance": null,
                        "leaders": ["crowning radius callout"],
                        "note": "From LEAD CROWNING DETAIL view — e.g. R3.8"
                        },
                        {
                        "id": "dim_crown_depth",
                        "view_id": "view_lead_crown",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": ["crown depth annotation"],
                        "note": "From LEAD CROWNING DETAIL view — crowning depth e.g. 0.3 DEEP"
                        },
                        {
                        "id": "dim_tooth_edge_chamfer",
                        "view_id": "view_tooth_edge_chamfer",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": ["gear tooth edge"],
                        "note": "From GEAR TOOTH EDGE CHAMFER view — e.g. 0.5×1.0 BOTH SIDES"
                        },
                        {
                        "id": "dim_tip_chamfer",
                        "view_id": "view_tip_chamfer",
                        "raw_text": null,
                        "value": null, "unit": "mm", "symbol": null,
                        "tolerance": null,
                        "leaders": ["gear tip edge"],
                        "note": "From GEAR TIP CHAMFER view — e.g. 0.35×0.1"
                        }
                    ],
                    "features": [
                        {
                        "id": "feat_rim",
                        "type": "cylindrical_rim",
                        "role": "gear_tip",
                        "outer_diameter_dim_ids": ["dim_outer_dia"],
                        "face_width_dim_ids": ["dim_face_width"],
                        "table_links": ["tbl_gear_data"]
                        },
                        {
                        "id": "feat_hub",
                        "type": "cylindrical_step",
                        "role": "hub_outer",
                        "diameter_dim_ids": ["dim_hub_dia"],
                        "length_dim_ids": ["dim_hub_height"]
                        },
                        {
                        "id": "feat_bore_main",
                        "type": "cylindrical_bore",
                        "role": "through_bore",
                        "diameter_dim_ids": ["dim_bore"],
                        "length_dim_ids": ["dim_hub_height"],
                        "fit_class": null
                        },
                        {
                        "id": "feat_spline",
                        "type": "internal_spline",
                        "role": "spline_bore",
                        "table_links": ["tbl_spline_data"]
                        },
                        {
                        "id": "feat_lead_crown",
                        "type": "tooth_modification",
                        "role": "lead_crowning",
                        "dim_ids": ["dim_crown_radius", "dim_crown_depth"],
                        "view_id": "view_lead_crown"
                        },
                        {
                        "id": "feat_tooth_edge_chamfer",
                        "type": "chamfer",
                        "role": "tooth_edge_chamfer",
                        "dim_ids": ["dim_tooth_edge_chamfer"],
                        "view_id": "view_tooth_edge_chamfer"
                        },
                        {
                        "id": "feat_tip_chamfer",
                        "type": "chamfer",
                        "role": "gear_tip_chamfer",
                        "dim_ids": ["dim_tip_chamfer"],
                        "view_id": "view_tip_chamfer"
                        }
                    ],
                    "assembly_order": [
                        {"op": "revolve",   "feature_id": "feat_rim"},
                        {"op": "revolve",   "feature_id": "feat_hub"},
                        {"op": "subtract",  "feature_id": "feat_bore_main"},
                        {"op": "subtract",  "feature_id": "feat_spline"},
                        {"op": "modify",    "feature_id": "feat_lead_crown"},
                        {"op": "chamfer",   "feature_id": "feat_tooth_edge_chamfer"},
                        {"op": "chamfer",   "feature_id": "feat_tip_chamfer"}
                    ],
                    "metadata": {
                        "title_block": {
                        "drawing_no": null,
                        "part_name": null,
                        "material": null,
                        "scale": null,
                        "company_name": null,
                        "division": null,
                        "revision": null,
                        "projection": null
                        }
                    }
                    }

                    ════════════════════════════════════════════════════════
                    PATCH A — RANGE vs TOLERANCE DISTINCTION (fixes Heat / Surface / Forging)
                    ════════════════════════════════════════════════════════

                    CRITICAL: "value" vs "tolerance" field assignment rules — follow EXACTLY:

                    ### RULE A1 — Process parameter ranges → always go in "value"
                    Heat treatment, surface treatment, and forging cells contain PROCESS RANGES,
                    not tolerances. A process range is the full acceptable specification for a
                    manufacturing parameter. It ALWAYS goes in the "value" field as a string.
                    The "tolerance" field for these cells is ALWAYS null.

                    CORRECT examples:
                    {"label": "CASE CARBURIZED DEPTH", "value": "0.9-1.2",  "unit": "mm",   "tolerance": null}
                    {"label": "SURFACE HARDNESS",      "value": "58-62",    "unit": "HRC",  "tolerance": null}
                    {"label": "CORE HARDNESS",         "value": "32-42",    "unit": "HRC",  "tolerance": null}
                    {"label": "NORMALIZED TO",         "value": "155-185",  "unit": "BHN",  "tolerance": null}
                    {"label": "GRAIN SIZE",            "value": "5 TO 8",   "unit": "ASTM", "tolerance": null}
                    {"label": "MAX BAINITE",           "value": 5,          "unit": "%",    "tolerance": null}

                    WRONG — never do this:
                    {"label": "SURFACE HARDNESS", "value": null, "tolerance": "58-62"}  ← WRONG

                    ### RULE A2 — Inequality operators (≤, <, >, ≥) are part of "value", not "tolerance"
                    When a cell reads "≤ 1 MM" or "<= 1", store the ENTIRE expression
                    (operator + number) as the value string. Never split the operator into
                    the tolerance field.

                    CORRECT:
                    {"label": "SHOT BLAST SHOT SIZE", "value": "<= 1", "unit": "mm", "tolerance": null}

                    WRONG:
                    {"label": "SHOT BLAST SHOT SIZE", "value": 1.0, "tolerance": "≤"}  ← WRONG

                    ### RULE A3 — Geometric dimension tolerances → go in "tolerance", numeric value in "value"
                    Only dimensional callouts on the drawing (diameter, length, span measurement)
                    use the "tolerance" field. These always have a plain numeric value in "value"
                    and a deviation string in "tolerance".

                    CORRECT:
                    {"label": "SPAN MEASUREMENT", "value": 49.942, "unit": "mm", "tolerance": "-0.074/-0.118"}
                    {"label": "CENTER DISTANCE",  "value": 103.0,  "unit": "mm", "tolerance": "± 0.05"}

                    Quick test: If the cell is in a heat/surface/forging table → value gets the range,
                    tolerance is null. If the cell is a dimension with ±/−/+ deviation → value gets
                    the number, tolerance gets the deviation string.


                    ════════════════════════════════════════════════════════
                    PATCH B — LEAD CROWNING DETAIL PARSING (fixes detail sub-view accuracy)
                    ════════════════════════════════════════════════════════

                    ### RULE B1 — The lead crowning annotation encodes THREE distinct values in one line
                    The LEAD CROWNING DETAIL view typically contains an annotation in this format:
                        "Rx.x×y.y DEEP, CROWNED"
                    or split across two lines. Parse it strictly as follows:

                    Part 1 — Crown radius:     The number immediately after "R" prefix.
                                                Example: "R3.8×0.3 DEEP" → crown_radius = 3.8
                                                Store as: dim_crown_radius, value=3.8, symbol="R"

                    Part 2 — Crown depth:      The number immediately before the word "DEEP".
                                                Example: "R3.8×0.3 DEEP" → crown_depth = 0.3
                                                Store as: dim_crown_depth, value=0.3, unit="mm"

                    Part 3 — Crowning tolerance band: A small range annotation (e.g. 0.005–0.015)
                                                that appears separately from the Rx.x annotation.
                                                This is the crowning deviation band, NOT the depth.
                                                Store as: dim_crown_tolerance, value="0.005-0.015", unit="mm"

                    NEVER merge these three into one field.
                    NEVER assign the crowning tolerance band (0.005–0.015) to dim_crown_depth.
                    If any of the three is not visible, set value=null, source="missing_on_drawing".

                    JSON output for this view:
                    {
                        "id": "dim_crown_radius",
                        "view_id": "view_lead_crown",
                        "raw_text": "R3.8×0.3 DEEP, CROWNED",
                        "value": 3.8, "unit": "mm", "symbol": "R", "tolerance": null
                    },
                    {
                        "id": "dim_crown_depth",
                        "view_id": "view_lead_crown",
                        "raw_text": "0.3 DEEP",
                        "value": 0.3, "unit": "mm", "symbol": null, "tolerance": null
                    },
                    {
                        "id": "dim_crown_tolerance",
                        "view_id": "view_lead_crown",
                        "raw_text": "0.005-0.015",
                        "value": "0.005-0.015", "unit": "mm", "tolerance": null,
                        "note": "Crowning band tolerance — separate from crown depth"
                    }


                    ════════════════════════════════════════════════════════
                    PATCH C — CHAMFER DIMENSION PARSING (fixes Gear Tooth Edge Chamfer)
                    ════════════════════════════════════════════════════════

                    ### RULE C1 — Chamfer format is ALWAYS "A×B", never a range "A–B"
                    Chamfer dimensions on gear drawings use the format:
                        A×B  (A times B, using the × multiplication symbol)
                    where:
                    A = first dimension (axial or lead-in distance)
                    B = second dimension (radial or depth distance)

                    The × separator looks visually similar to a dash (–) or hyphen (-) but
                    means something completely different. NEVER read "A×B" as a range "A to B".

                    ### RULE C2 — Extract both sub-dimensions separately
                    For every chamfer dimension, extract:
                    "dim_axial":  the A value (first number)
                    "dim_radial": the B value (second number)
                    "raw_text":   the exact annotation text including the × symbol

                    CORRECT:
                    {
                        "id": "dim_tooth_edge_chamfer",
                        "view_id": "view_tooth_edge_chamfer",
                        "raw_text": "0.5×1.0 GEAR TOOTH EDGE CHAMFER BOTH SIDES",
                        "dim_axial": 0.5,
                        "dim_radial": 1.0,
                        "unit": "mm",
                        "note": "BOTH SIDES — applies to all gear tooth edges"
                    }

                    WRONG:
                    {"raw_text": "0.3-1.0 ...", "tolerance": "0.3-1.0"}  ← reads × as range, WRONG

                    ### RULE C3 — "BOTH SIDES" / "TYP" annotations are notes, not tolerances
                    If the chamfer annotation includes "BOTH SIDES", "TYP.", or "ALL TEETH",
                    capture these as a "note" string field, not as part of the tolerance.

                    ### RULE C4 — Gear tip chamfer typically repeats the same value twice
                    The GEAR TIP CHAMFER view often shows the same dimension on both the axial
                    and radial sides (e.g. 0.35×0.35). If only one value is visible, assume
                    it applies to both sides and record:
                    dim_axial = dim_radial = that value.

                    CORRECT:
                    {
                        "id": "dim_tip_chamfer",
                        "view_id": "view_tip_chamfer",
                        "raw_text": "0.35×0.35",
                        "dim_axial": 0.35,
                        "dim_radial": 0.35,
                        "unit": "mm",
                        "tolerance": "± 0.1"
                    }


                    ════════════════════════════════════════════════════════
                    QUICK DECISION TABLE — use this before writing any cell value
                    ════════════════════════════════════════════════════════

                    | What you see on drawing          | "value" field          | "tolerance" field     |
                    |----------------------------------|------------------------|-----------------------|
                    | 58–62 HRC (heat treat)           | "58-62" (string)       | null                  |
                    | 0.9–1.2 mm (case depth)          | "0.9-1.2" (string)     | null                  |
                    | ≤ 1 mm (shot size)               | "<= 1" (string)        | null                  |
                    | 49.942 −0.074/−0.118 (span)      | 49.942 (number)        | "-0.074/-0.118"       |
                    | 103.0 ± 0.05 (centre dist)       | 103.0 (number)         | "± 0.05"              |
                    | R3.8×0.3 DEEP (crown annotation) | 3.8 for radius entry   | null                  |
                    |                                  | 0.3 for depth entry    | null                  |
                    | 0.5×1.0 (chamfer)                | split: axial=0.5       | null                  |
                    |                                  |        radial=1.0      |                       |
                    | 0.005–0.015 (crown tolerance)    | "0.005-0.015" (string) | null                  |
                    """
            input_token_info = self.count_total_tokens_for_request(PROMPT, image_path)
            logger.info(f"Input tokens - Prompt: {input_token_info['prompt_tokens']}, Image: {input_token_info['image_tokens']}, Total: {input_token_info['total_input_tokens']}")
            
            uploaded_file = await self.upload_image_to_gemini(image_path)
            
            response = model.generate_content(
                [PROMPT, uploaded_file],
                generation_config={"temperature": 0.0}
            )
            response_text = response.text.strip()
            
            output_tokens = self.count_tokens_accurate(response_text)
            total_tokens = input_token_info['total_input_tokens'] + output_tokens
            
            logger.info(f"Token usage - Input: {input_token_info['total_input_tokens']}, Output: {output_tokens}, Total: {total_tokens}")
            
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            parsed_data = json.loads(response_text)
            logger.info("Successfully parsed JSON response from Gemini")
            
            parsed_data["token_usage"] = {
                "input_tokens": {
                    "prompt_tokens": input_token_info['prompt_tokens'],
                    "image_tokens": input_token_info['image_tokens'],
                    "total_input_tokens": input_token_info['total_input_tokens']
                },
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "token_counting_method": "gemini_api_with_estimation_fallback",
                "image_dimensions": self._get_image_dimensions(image_path)
            }
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response text: {response_text[:1000]}...")
            
            input_token_info = self.count_total_tokens_for_request(PROMPT, image_path) if 'PROMPT' in locals() else {"prompt_tokens": 0, "image_tokens": 0, "total_input_tokens": 0}
            output_tokens = self.count_tokens_accurate(response_text) if 'response_text' in locals() else 0
            
            return {
                "error": f"Invalid JSON response from AI model: {str(e)}",
                "extracted_data": {},
                "token_usage": {
                    "input_tokens": input_token_info,
                    "output_tokens": output_tokens,
                    "total_tokens": input_token_info.get('total_input_tokens', 0) + output_tokens,
                    "token_counting_method": "gemini_api_with_estimation_fallback"
                }
            }
        except Exception as e:
            logger.error(f"Technical drawing extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            input_token_info = self.count_total_tokens_for_request(PROMPT, image_path) if 'PROMPT' in locals() else {"prompt_tokens": 0, "image_tokens": 0, "total_input_tokens": 0}
            
            return {
                "error": str(e),
                "file": os.path.basename(image_path),
                "token_usage": {
                    "input_tokens": input_token_info,
                    "output_tokens": 0,
                    "total_tokens": input_token_info.get('total_input_tokens', 0),
                    "token_counting_method": "gemini_api_with_estimation_fallback"
                }
            }
    
    def _get_image_dimensions(self, image_path: str) -> Dict[str, Any]:
        """Get image dimensions for token calculation reference"""
        try:
            with Image.open(image_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "total_pixels": img.width * img.height,
                    "format": img.format
                }
        except Exception:
            return {"error": "Could not read image dimensions"}

    async def process_image_file(
        self,
        task_id: str,
        file_path: str,
        output_dir: str
    ) -> Dict:
        """Process image file using Gemini extraction"""
        try:
            logger.info(f"Starting image processing for task: {task_id}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")
                
            file_size = os.path.getsize(file_path)
            logger.info(f"File size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError("Image file is empty")
                
            os.makedirs(output_dir, exist_ok=True)
            base_filename = os.path.join(output_dir, task_id)
            
            file_info = {
                "task_id": task_id,
                "original_filename": os.path.basename(file_path),
                "stored_filename": f"{task_id}_{os.path.basename(file_path)}",
                "file_path": file_path,
                "output_path": base_filename,
                "status": "processing",
                "file_size": file_size,
                "created_at": datetime.now().isoformat()
            }
            
            self.processed_files[task_id] = file_info
            
            extracted_data = await self.extract_technical_drawing_data(file_path)
            
            status = "completed" if "error" not in extracted_data else "completed_with_errors"
            self.processed_files[task_id]["status"] = status
            
            json_output = {
                "task_id": task_id,
                "filename": os.path.basename(file_path),
                "file_size": file_size,
                "extracted_data": extracted_data,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
            json_file_path = f"{base_filename}.json"
            with open(json_file_path, "w", encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON output saved to: {json_file_path}")
            
            return {
                "status": status,
                "output_path": base_filename,
                "file_size": file_size,
                "has_errors": "error" in extracted_data,
                "json_path": json_file_path,
                "token_usage": extracted_data.get("token_usage", {})
            }
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"File not found: {str(e)}",
                "error_type": "file_not_found"
            }
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"Invalid file or data: {str(e)}",
                "error_type": "invalid_data"
            }
        except Exception as e:
            logger.error(f"Unexpected error in image processing: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"Processing error: {str(e)}",
                "error_type": "processing_error"
            }

    def get_file_info(self, task_id: str) -> Optional[Dict]:
        """Retrieve file information by task ID"""
        return self.processed_files.get(task_id)

    def get_all_processed_files(self) -> Dict:
        """Get all processed files"""
        return self.processed_files

    def update_file_status(self, task_id: str, status: str) -> Optional[Dict]:
        """Update file status"""
        if task_id in self.processed_files:
            self.processed_files[task_id]["status"] = status
            self.processed_files[task_id]["updated_at"] = datetime.now().isoformat()
            return self.processed_files[task_id]
        return None

    def delete_file_info(self, task_id: str) -> bool:
        """Delete file information"""
        if task_id in self.processed_files:
            del self.processed_files[task_id]
            return True
        return False

    def get_drawing_type_from_data(self, extracted_data: Dict) -> str:
        """Determine drawing type from extracted data"""
        try:
            if "drawing_metadata" in extracted_data:
                drawing_type = extracted_data["drawing_metadata"].get("drawing_type", "unknown")
                component_type = extracted_data["drawing_metadata"].get("component_type", "")
                return f"{drawing_type}_{component_type}".replace(" ", "_").lower()
            return "unknown"
        except:
            return "unknown"
    
    def get_critical_dimensions(self, extracted_data: Dict) -> List[Dict]:
        """Extract only critical dimensions for quick reference"""
        critical_dims = []
        
        try:
            if "overall_dimensions" in extracted_data:
                for dim_name, dim_data in extracted_data["overall_dimensions"].items():
                    if isinstance(dim_data, dict) and "value" in dim_data:
                        critical_dims.append({
                            "type": "overall",
                            "feature": dim_name,
                            "value": dim_data["value"],
                            "unit": dim_data.get("unit", ""),
                            "tolerance": dim_data.get("tolerance", "")
                        })
            
            if "feature_dimensions" in extracted_data:
                for feature in extracted_data["feature_dimensions"]:
                    if isinstance(feature, dict) and "dimensions" in feature:
                        feature_type = feature.get("feature_type", "unknown")
                        dims = feature["dimensions"]
                        if isinstance(dims, dict):
                            for dim_key, dim_data in dims.items():
                                if isinstance(dim_data, dict) and "value" in dim_data:
                                    critical_dims.append({
                                        "type": "feature",
                                        "feature": f"{feature_type}_{dim_key}",
                                        "value": dim_data["value"],
                                        "unit": dim_data.get("unit", ""),
                                        "tolerance": dim_data.get("tolerance", "")
                                    })
            
            return critical_dims
            
        except Exception as e:
            logger.warning(f"Error extracting critical dimensions: {str(e)}")
            return []
    
    def generate_summary_report(self, extracted_data: Dict, filename: str) -> Dict:
        """Generate a summary report of extracted data"""
        try:
            summary = {
                "filename": filename,
                "drawing_type": self.get_drawing_type_from_data(extracted_data),
                "extraction_timestamp": datetime.now().isoformat(),
                "has_errors": "error" in extracted_data,
                "data_completeness": {}
            }
            
            element_counts = {}
            if "feature_dimensions" in extracted_data:
                element_counts["feature_dimensions"] = len(extracted_data["feature_dimensions"]) if isinstance(extracted_data["feature_dimensions"], list) else 0
            
            if "geometric_tolerances" in extracted_data:
                element_counts["geometric_tolerances"] = len(extracted_data["geometric_tolerances"]) if isinstance(extracted_data["geometric_tolerances"], list) else 0
            
            if "manufacturing_notes" in extracted_data:
                element_counts["manufacturing_notes"] = len(extracted_data["manufacturing_notes"]) if isinstance(extracted_data["manufacturing_notes"], list) else 0
            
            if "threaded_features" in extracted_data:
                element_counts["threaded_features"] = len(extracted_data["threaded_features"]) if isinstance(extracted_data["threaded_features"], list) else 0
            
            summary["element_counts"] = element_counts
            summary["critical_dimensions"] = self.get_critical_dimensions(extracted_data)
            summary["token_usage"] = extracted_data.get("token_usage", {})
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary report: {str(e)}")
            return {
                "filename": filename,
                "error": f"Summary generation failed: {str(e)}",
                "extraction_timestamp": datetime.now().isoformat()
            }

    def export_to_specific_format(self, extracted_data: Dict, format_type: str) -> str:
        """Export data to specific formats (CAD import, inspection sheets, etc.)"""
        try:
            if format_type.lower() == "inspection_sheet":
                return self._create_inspection_sheet_format(extracted_data)
            elif format_type.lower() == "cad_import":
                return self._create_cad_import_format(extracted_data)
            elif format_type.lower() == "manufacturing_sheet":
                return self._create_manufacturing_sheet_format(extracted_data)
            else:
                return "Unsupported format type"
                
        except Exception as e:
            logger.error(f"Export format error: {str(e)}")
            return f"Export failed: {str(e)}"
    
    def _create_inspection_sheet_format(self, data: Dict) -> str:
        """Create inspection sheet format"""
        lines = ["=== INSPECTION SHEET ===\n"]
        
        if "drawing_metadata" in data:
            meta = data["drawing_metadata"]
            lines.append(f"Part Name: {meta.get('part_name', 'N/A')}")
            lines.append(f"Drawing Number: {meta.get('drawing_number', 'N/A')}")
            lines.append(f"Revision: {meta.get('revision', 'N/A')}")
            lines.append(f"Material: {meta.get('material_specification', 'N/A')}\n")
        
        critical_dims = self.get_critical_dimensions(data)
        if critical_dims:
            lines.append("=== CRITICAL DIMENSIONS FOR INSPECTION ===")
            for dim in critical_dims:
                lines.append(f"• {dim['feature']}: {dim['value']} {dim['unit']} {dim.get('tolerance', '')}")
            lines.append("")
        
        if "geometric_tolerances" in data and data["geometric_tolerances"]:
            lines.append("=== GEOMETRIC TOLERANCES ===")
            for tol in data["geometric_tolerances"]:
                lines.append(f"• {tol.get('tolerance_type', 'Unknown')}: {tol.get('tolerance_value', 'N/A')} - {tol.get('feature', 'Unknown feature')}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _create_cad_import_format(self, data: Dict) -> str:
        """Create CAD import compatible format"""
        lines = ["# CAD Import Data"]
        
        if "overall_dimensions" in data:
            lines.append("## Overall Dimensions")
            for dim_name, dim_data in data["overall_dimensions"].items():
                if isinstance(dim_data, dict) and "value" in dim_data:
                    lines.append(f"{dim_name.upper()},{dim_data['value']},{dim_data.get('unit', 'mm')}")
        
        return "\n".join(lines)
    
    def _create_manufacturing_sheet_format(self, data: Dict) -> str:
        """Create manufacturing instruction sheet"""
        lines = ["=== MANUFACTURING INSTRUCTIONS ===\n"]
        
        if "material_and_treatment" in data:
            mat = data["material_and_treatment"]
            lines.append("=== MATERIAL REQUIREMENTS ===")
            lines.append(f"Base Material: {mat.get('base_material', 'N/A')}")
            lines.append(f"Heat Treatment: {mat.get('heat_treatment', 'N/A')}")
            lines.append(f"Hardness: {mat.get('hardness_requirement', 'N/A')}\n")
        
        if "manufacturing_notes" in data and data["manufacturing_notes"]:
            lines.append("=== MANUFACTURING NOTES ===")
            for note in data["manufacturing_notes"]:
                lines.append(f"• {note.get('note_text', 'N/A')} ({note.get('note_type', 'General')})")
            lines.append("")
        
        return "\n".join(lines)