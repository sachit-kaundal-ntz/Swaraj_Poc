
import os
import uuid
import json
import csv
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional, Any
from PIL import Image
import base64
import io
import streamlit as st
import pandas as pd
import time

# Set page config
st.set_page_config(
    page_title="Technical Drawing Extraction",
    page_icon="📐",
    layout="wide"
)

# Load environment variables
load_dotenv()

# Ensure the Google API key is provided via environment variable and is not empty.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error(
        "GOOGLE_API_KEY is not set.\n"
        "Steps to fix:\n"
        "1) Rotate the leaked API key in Google Cloud Console (disable/delete the exposed key).\n"
        "2) Create a new API key and restrict it (HTTP referrers, IPs, and enabled APIs).\n"
        "3) Set the new key in environment variable GOOGLE_API_KEY (do NOT commit it).\n"
        "4) For local dev, add it to your shell profile or a local .env (ensure .env is in .gitignore).\n"
    )
    st.stop()

genai.configure(api_key=st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
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
            st.warning(f"Failed to get accurate token count, using estimation: {str(e)}")
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
            st.warning(f"Could not estimate image tokens: {str(e)}")
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

    def upload_image_to_gemini(self, image_path: str) -> Any:
        """Upload image file to Gemini"""
        try:
            st.info(f"Uploading image file to Gemini: {image_path}")
            
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
                
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                raise ValueError("Image file is empty")
                
            uploaded_file = genai.upload_file(image_path)
            st.info(f"Successfully uploaded image to Gemini")
            return uploaded_file
            
        except Exception as e:
            st.error(f"Failed to upload image to Gemini: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Image upload failed: {str(e)}")

    def extract_technical_drawing_data(self, image_path: str) -> Dict:
        """Extract technical drawing data from image using Gemini - Universal Version"""
        try:
            st.info(f"Starting technical drawing extraction for: {image_path}")
            
            PROMPT = """
            You are an expert mechanical drawing interpreter. Your role is to extract ONLY the explicitly printed information from a mechanical gear drawing and return a structured JSON.

            ABSOLUTE RULES
            1. Never invent values. If a requested value is not visible, set `"value": null` and `"source": "missing_on_drawing"`.
            2. Root diameter is not a cavity. Do not treat root_diameter as an internal hollow for volume. Net section for mass uses outer tip diameter vs. bore.
            3. Face width vs hub height - CRITICAL DISTINCTION:  
            - **Face width** = axial dimension of ONLY the gear rim/toothed section (smaller value)
            - **Hub height** = TOTAL axial dimension including hub extension (larger value)
            - **Hub height is ALWAYS greater than face width**
            4. Bore subtraction passes through the full axial stack (face_width + hub_extension).  
            5. Preserve all units, tolerances, and symbols exactly (⌀, ±, H7, -0.1, etc.).  
            6. Copy source text exactly into `raw_text`.  
            7. Always include `view_id` and leader arrow mapping if visible.  
            8. All tables (gear data, spline data, permissible deviations, heat-treat, material) must be represented in `"tables"` and linked through `features[*].table_links`.

            ---

            ## COMPONENT DEFINITIONS & IDENTIFICATION GUIDE

            ### 1. BORE (Internal Hollow)
            **Definition**: The central hole that runs axially through the gear for shaft mounting.
            **Visual Identification**:
            - Look for: Circular hole in center of sectional view
            - Common symbols: ⌀ symbol with diameter dimension
            - Tolerance markings: H7, H8, or similar fit designations
            - **Starting Point**: One face of the gear (left or right side)
            - **Ending Point**: Opposite face of the gear
            - **Keywords on drawing**: "BORE", "⌀", "H7", "SHAFT FIT", bore diameter dimensions
            - **Location indicators**: Center of all sectional views, may show splines or keyways inside

            ### 2. RIM (Main Gear Body)
            **Definition**: The outer circular section that contains the gear teeth.
            **Visual Identification**:
            - Look for: Largest circular outline with teeth profile
            - **Starting Point**: Root of gear teeth (smallest circle of tooth profile)
            - **Ending Point**: Tip of gear teeth (largest circle of tooth profile)  
            - **Keywords on drawing**: "ADDENDUM", "DEDENDUM", "PITCH DIA", "TIP DIA", "ROOT DIA"
            - **Face Width**: Axial thickness of ONLY the toothed section (NOT total length)
            - **Location indicators**: Outermost section with gear tooth geometry

            ### 3. HUB (Cylindrical Extension)
            **Definition**: The central cylindrical section that extends beyond the main gear rim, typically for bearing mounting.
            **Visual Identification**:
            - Look for: Smaller diameter cylindrical section extending from gear body
            - Usually has multiple stepped diameters
            - **Starting Point**: One end face of the complete assembly
            - **Ending Point**: Opposite end face of the complete assembly
            - **Keywords on drawing**: "HUB DIA", "BEARING SEAT", "SHOULDER", stepped dimensions
            - **Hub Height/Length**: TOTAL axial dimension of entire gear assembly
            - **Location indicators**: Cylindrical sections with diameters smaller than rim OD

            ### 4. SPLINE (Internal Tooth Profile)
            **Definition**: Internal teeth inside the bore for torque transmission with shaft.
            **Visual Identification**:
            - Look for: Tooth-like profile inside the bore in sectional view
            - Hatched/cross-hatched internal features
            - **Starting Point**: Hub face or bore entry
            - **Ending Point**: End of splined section (may not be full length)
            - **Keywords on drawing**: "SPLINE DATA", "MAJOR DIA", "MINOR DIA", "SPLINE TEETH"
            - **Location indicators**: Internal features within bore, separate data table

            ---

            ## CRITICAL DIMENSION IDENTIFICATION KEYWORDS

            ### HUB HEIGHT/LENGTH Identification:
            - **Look for**: TOTAL axial dimension of the entire gear assembly
            - **Keywords**: Largest axial dimension value, overall length
            - **Visual cues**: Dimension lines spanning the complete gear from end to end
            - **Common values**: 40-80mm for typical automotive gears
            - **Starting point**: One end face of complete gear assembly
            - **Ending point**: Opposite end face of complete gear assembly
            - **CRITICAL**: This is the LARGER of the two main axial dimensions
            - **Leader identification**: "full axial length" or "total length" or similar

            ### FACE WIDTH Identification:
            - **Look for**: Axial dimension of ONLY the gear rim/toothed section
            - **Keywords**: "FACE WIDTH", "b", smaller axial dimension
            - **Visual cues**: Dimension lines only across the gear teeth section
            - **Common values**: 20-50mm for typical automotive gears
            - **Starting point**: One face of gear rim only
            - **Ending point**: Opposite face of gear rim only
            - **CRITICAL**: This is the SMALLER of the two main axial dimensions
            - **Leader identification**: "gear rim thickness" or "toothed section width"

            ### HUB DIAMETER Identification:
            - **Look for**: ⌀ symbol with dimensions on hub sections
            - **Keywords**: Smaller diameter values than outer gear diameter
            - **Visual cues**: Dimension lines across hub diameter
            - **Common values**: 40-100mm for automotive gears
            - **Starting point**: One side of hub circumference
            - **Ending point**: Opposite side of hub circumference

            ### OUTER DIAMETER (Tip Diameter) Identification:
            - **Look for**: Largest ⌀ dimension value on the drawing
            - **Keywords**: "TIP DIA", "ADDENDUM DIA", "OD", largest diameter measurement
            - **Visual cues**: Dimension lines across the full gear including teeth
            - **Common values**: 100-300mm for automotive gears
            - **Starting point**: Tip of gear tooth on one side
            - **Ending point**: Tip of gear tooth on opposite side

            ### BORE DIAMETER Identification:
            - **Look for**: ⌀ symbol with tolerance (H7, H8)
            - **Keywords**: "BORE", "⌀", "H7", "SHAFT FIT"
            - **Visual cues**: Dimension lines across central hole
            - **Common values**: 20-80mm for automotive gears
            - **Starting point**: One side of bore circumference
            - **Ending point**: Opposite side of bore circumference

            ---

            ## DIMENSION VALUE LOGIC CHECKS

            ### Mandatory Relationships:
            1. **Hub Height > Face Width** (ALWAYS - if not, swap the assignments)
            2. **Outer Diameter > Hub Diameter > Bore Diameter**
            3. **If two axial dimensions exist**: 
               - Larger value = Hub Height
               - Smaller value = Face Width

            ### Dimension Assignment Rules:
            - **If you find 54mm and 45mm for axial dimensions**:
              - 54mm = Hub Height (larger value)
              - 45mm = Face Width (smaller value)
            - **If leader arrows are confusing, use the VALUE SIZE rule above**

            ---

            ## DRAWING LAYOUT RECOGNITION HINTS

            ### Main Sectional View:
            - Usually largest view showing cross-section
            - Contains most critical dimensions
            - Shows internal features (bore, splines)
            - Labeled as "SECTION A-A" or similar

            ### Detail Views:
            - Smaller views showing specific features
            - "LEAD CROWNING DETAIL" - tooth modifications
            - "GEAR TIP CHAMFER" - tooth edge details
            - "ISOMETRIC VIEW" - 3D representation

            ### Data Tables:
            - "GEAR DATA" table: Module, teeth count, angles
            - "SPLINE DATA" table: Spline dimensions and specifications
            - "PERMISSIBLE DEVIATIONS" table: Tolerance information
            - Located typically on right side or bottom of drawing

            ### Title Block:
            - Contains part number, material, scale
            - Usually in bottom right corner
            - Company logo and drawing information

            ---

     ### 3. DIMENSION IDENTIFICATION PRIORITY
            - **Hub Diameter**: starting and end point of the hub groove/bore and not part of main rim.
            - **Outer Diameter**: Starting and the end point of the rim (It is the outermost length to the tip of tooth)
            - **Hub Height/Length**: TOTAL axial length of complete gear assembly (LARGER axial dimension)
            - **Face Width**: Axial dimension of ONLY the gear rim/toothed section (SMALLER axial dimension)
            - **Bore Diameter**: Internal diameter dimensions (often with fit tolerances like H7).

            ### 4. FEATURE CLASSIFICATION RULES
            - **Root diameter is NOT a cavity** – it's the gear tooth root, use only for gear data.
            - **Face width** = SMALLER axial dimension (gear rim only).
            - **Hub height** = LARGER axial dimension (total assembly length).
            - **Bore subtraction** applies through full axial stack (face_width + hub_extension).

            ### 5. TABLE DATA EXTRACTION
            - Extract all tabular data (gear data, spline data, material properties).
            - Link tables to relevant features via `table_links`.
            - Preserve exact formatting and units from tables.

            ### 6. MISSING DATA HANDLING
            - If a dimension is not visible: set `"value": null, "source": "missing_on_drawing"`.
            - Do not invent or calculate missing values.
            - Only extract what is explicitly shown.

            ### 7. DIMENSION VALIDATION
            - **Face Width vs Hub Height**: Hub height should always be greater than face width
            - **If Hub Height < Face Width**: SWAP the dimension assignments
            - **Diameter Relationships**: Outer diameter > Hub diameter > Bore diameter
            - **If contradictions exist**: Double-check dimension identification and leader line mapping

            ---

            ## OUTPUT JSON SCHEMA (Template)

            ```json
            {
            "units": "mm",
            "views": [
                {"id": "view_main", "name": "SECTION A-A", "bbox": [x1,y1,x2,y2]}
            ],
            "tables": [
                {
                "id": "tbl_gear_data",
                "view_id": null,
                "cells": [
                    {"label": "MODULE", "value": null, "unit": "mm"},
                    {"label": "NO OF TEETH", "value": null, "unit": null},
                    {"label": "ADDENDUM", "value": null, "unit": "mm"}
                ]
                },
                {
                "id": "tbl_spline_data",
                "view_id": null,
                "cells": [
                    {"label": "MAJOR DIAMETER", "value": null, "unit": "mm"},
                    {"label": "MINOR DIAMETER", "value": null, "unit": "mm"}
                ]
                }
            ],
            "dimensions": [
                {
                "id": "dim_outer_dia",
                "view_id": "view_main",
                "raw_text": null,
                "value": null,
                "unit": "mm",
                "symbol": "⌀",
                "tolerance": null,
                "leaders": []
                },
                {
                "id": "dim_hub_dia",
                "view_id": "view_main",
                "raw_text": null,
                "value": null,
                "unit": "mm",
                "symbol": "⌀",
                "tolerance": null,
                "leaders": []
                },
                {
                "id": "dim_face_width",
                "view_id": "view_main",
                "raw_text": null,
                "value": null,
                "unit": "mm",
                "symbol": null,
                "tolerance": null,
                "leaders": []
                },
                {
                "id": "dim_hub_height",
                "view_id": "view_main",
                "raw_text": null,
                "value": null,
                "unit": "mm",
                "symbol": null,
                "tolerance": null,
                "leaders": []
                },
                {
                "id": "dim_bore",
                "view_id": "view_main",
                "raw_text": null,
                "value": null,
                "unit": "mm",
                "symbol": "⌀",
                "tolerance": "H7",
                "leaders": []
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
                "length_dim_ids": [],
                "fit_class": null
                },
                {
                "id": "feat_spline",
                "type": "internal_spline",
                "role": "spline_bore",
                "table_links": ["tbl_spline_data"]
                }
            ],
            "assembly_order": [
                {"op": "revolve", "feature_id": "feat_rim"},
                {"op": "revolve", "feature_id": "feat_hub"},
                {"op": "subtract", "feature_id": "feat_bore_main"},
                {"op": "subtract", "feature_id": "feat_spline"}
            ],
            "metadata": {
                "title_block": {
                "drawing_no": null,
                "material": null,
                "scale": null,
                "part_name": null
                }
            }
            }

            ```

            ---

            ## SPECIFIC EXTRACTION INSTRUCTIONS

            ### For Hub Features:
            - Look for stepped cylindrical sections with smaller diameters.
            - Hub diameter = starting and end point of the hub groove/bore and not the part of main gear.
            - Hub height/extension = TOTAL axial dimension of complete gear assembly (LARGER value)
            - Search for dimensions with arrows spanning complete gear length
            - Look for ⌀ symbols on smaller diameter sections

            ### For Main Gear Body:
            - Outer diameter = largest diameter dimension (gear tip circle).
            - Face width = axial dimension of ONLY the toothed section (SMALLER axial value)
            - Link to gear data table for teeth count, module, etc.
            - Look for largest ⌀ value on drawing
            - Search for axial dimensions on toothed section only

            ### For Bore Features:
            - Extract bore diameter with any fit specifications (H7, etc.).
            - Bore extends through entire axial length unless otherwise specified.
            - Separate spline bores as distinct features with `table_links`.
            - Look for ⌀ with tolerance markings (H7, H8)
            - Check for internal spline data tables

            ### For Dimension Text:
            - Copy raw dimension text exactly: "⌀58", "25 ±0.1", "H7".
            - Preserve symbols and tolerance notations.
            - Map leader lines when identifiable.
            - Note dimension line start and end points
            - **CRITICAL**: Use value size logic - larger axial value = hub height, smaller = face width

            ## OUTPUT REQUIREMENTS
            - Return ONLY the JSON – no commentary.
            - All dimensions must have explicit `raw_text` field.
            - Link all tabular data through `table_links`.
            - Preserve exact formatting from drawing.
            - Each dimension must have unique descriptive ID.
            - Include measurement start/end point descriptions where identifiable.
            - **MANDATORY**: Ensure hub_height > face_width in final output
"""  
            input_token_info = self.count_total_tokens_for_request(PROMPT, image_path)
            st.info(f"Input tokens - Prompt: {input_token_info['prompt_tokens']}, Image: {input_token_info['image_tokens']}, Total: {input_token_info['total_input_tokens']}")
            
            uploaded_file = self.upload_image_to_gemini(image_path)
            
            with st.spinner("Extracting data from technical drawing..."):
                response = model.generate_content(
                    [PROMPT, uploaded_file],
                    generation_config={"temperature": 0.0}
                )
            
            response_text = response.text.strip()
            
            output_tokens = self.count_tokens_accurate(response_text)
            total_tokens = input_token_info['total_input_tokens'] + output_tokens
            
            st.info(f"Token usage - Input: {input_token_info['total_input_tokens']}, Output: {output_tokens}, Total: {total_tokens}")
            
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            parsed_data = json.loads(response_text)
            st.success("Successfully parsed JSON response from Gemini")
            
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
            st.error(f"JSON parsing error: {str(e)}")
            st.error(f"Response text: {response_text[:1000]}...")
            
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
            st.error(f"Technical drawing extraction failed: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            
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

    def process_all_data(self, data: Dict, filename: str) -> List[Dict]:
        """Process all data into a flat structure for CSV output with universal organization"""
        try:
            st.info(f"Processing data for CSV output: {filename}")
            
            records = []
            
            def create_universal_records(data, filename):
                universal_records = []
                
                if "drawing_metadata" in data:
                    metadata_record = {
                        "Filename": filename,
                        "Record_Type": "Drawing_Metadata",
                        **{f"Meta_{k}": v for k, v in data["drawing_metadata"].items()}
                    }
                    universal_records.append(metadata_record)
                
                if "overall_dimensions" in data:
                    overall_record = {
                        "Filename": filename,
                        "Record_Type": "Overall_Dimensions",
                        **{f"Overall_{k}": v for k, v in data["overall_dimensions"].items()}
                    }
                    universal_records.append(overall_record)
                
                if "feature_dimensions" in data and isinstance(data["feature_dimensions"], list):
                    for i, feature in enumerate(data["feature_dimensions"]):
                        feature_record = {
                            "Filename": filename,
                            "Record_Type": "Feature_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Feature_{k}": v for k, v in feature.items()}
                        }
                        universal_records.append(feature_record)
                
                if "tolerances" in data:
                    tol_record = {
                        "Filename": filename,
                        "Record_Type": "Tolerances",
                        **{f"Tol_{k}": v for k, v in data["tolerances"].items()}
                    }
                    universal_records.append(tol_record)
                
                if "geometric_tolerances" in data and isinstance(data["geometric_tolerances"], list):
                    for i, geo_tol in enumerate(data["geometric_tolerances"]):
                        geo_record = {
                            "Filename": filename,
                            "Record_Type": "Geometric_Tolerance",
                            "Tolerance_Index": i + 1,
                            **{f"GeoTol_{k}": v for k, v in geo_tol.items()}
                        }
                        universal_records.append(geo_record)
                
                if "surface_specifications" in data and isinstance(data["surface_specifications"], list):
                    for i, surface in enumerate(data["surface_specifications"]):
                        surface_record = {
                            "Filename": filename,
                            "Record_Type": "Surface_Specification",
                            "Surface_Index": i + 1,
                            **{f"Surface_{k}": v for k, v in surface.items()}
                        }
                        universal_records.append(surface_record)
                
                if "threaded_features" in data and isinstance(data["threaded_features"], list):
                    for i, thread in enumerate(data["threaded_features"]):
                        thread_record = {
                            "Filename": filename,
                            "Record_Type": "Threaded_Feature",
                            "Thread_Index": i + 1,
                            **{f"Thread_{k}": v for k, v in thread.items()}
                        }
                        universal_records.append(thread_record)
                
                if "section_views" in data and isinstance(data["section_views"], list):
                    for i, section in enumerate(data["section_views"]):
                        section_record = {
                            "Filename": filename,
                            "Record_Type": "Section_View",
                            "Section_Index": i + 1,
                            **{f"Section_{k}": v for k, v in section.items()}
                        }
                        universal_records.append(section_record)
                
                if "manufacturing_notes" in data and isinstance(data["manufacturing_notes"], list):
                    for i, note in enumerate(data["manufacturing_notes"]):
                        note_record = {
                            "Filename": filename,
                            "Record_Type": "Manufacturing_Note",
                            "Note_Index": i + 1,
                            **{f"Note_{k}": v for k, v in note.items()}
                        }
                        universal_records.append(note_record)
                
                if "tables_and_data" in data and isinstance(data["tables_and_data"], list):
                    for i, table in enumerate(data["tables_and_data"]):
                        table_record = {
                            "Filename": filename,
                            "Record_Type": "Table_Data",
                            "Table_Index": i + 1,
                            **{f"Table_{k}": v for k, v in table.items()}
                        }
                        universal_records.append(table_record)
                
                if "material_and_treatment" in data:
                    material_record = {
                        "Filename": filename,
                        "Record_Type": "Material_Treatment",
                        **{f"Material_{k}": v for k, v in data["material_and_treatment"].items()}
                    }
                    universal_records.append(material_record)
                
                if "quality_requirements" in data:
                    quality_record = {
                        "Filename": filename,
                        "Record_Type": "Quality_Requirements",
                        **{f"Quality_{k}": v for k, v in data["quality_requirements"].items()}
                    }
                    universal_records.append(quality_record)
                
                return universal_records
            
            records = create_universal_records(data, filename)
            
            if not records:
                def flatten_dict(d, parent_key='', record=None):
                    if record is None:
                        record = {"Filename": filename, "Record_Type": "General"}
                    
                    for k, v in d.items():
                        new_key = f"{parent_key}_{k}" if parent_key else k
                        
                        if isinstance(v, dict):
                            flatten_dict(v, new_key, record)
                        elif isinstance(v, list):
                            if v and isinstance(v[0], dict):
                                for i, item in enumerate(v):
                                    list_record = {"Filename": filename, "Record_Type": f"{new_key}_Item_{i+1}"}
                                    flatten_dict(item, new_key, list_record)
                                    records.append(list_record)
                            else:
                                record[new_key] = "; ".join(str(x) for x in v)
                        else:
                            record[new_key] = str(v)
                    
                    return record
                
                main_record = flatten_dict(data)
                records.append(main_record)
            
            st.info(f"Processed {len(records)} total records")
            return records
            
        except Exception as e:
            st.error(f"Data processing error: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            return [{
                "Filename": filename,
                "Error": f"Data processing error: {str(e)}",
                "Record_Type": "Error"
            }]

    def process_image_file(
        self,
        task_id: str,
        file_path: str,
        output_dir: str
    ) -> Dict:
        """Process image file using Gemini extraction"""
        try:
            st.info(f"Starting image processing for task: {task_id}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")
                
            file_size = os.path.getsize(file_path)
            st.info(f"File size: {file_size} bytes")
            
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
            
            extracted_data = self.extract_technical_drawing_data(file_path)
            
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
            st.info(f"JSON output saved to: {json_file_path}")
            
            csv_file_path = f"{base_filename}.csv"
            processed_data = self.process_all_data(extracted_data, os.path.basename(file_path))
            
            if processed_data and len(processed_data) > 0:
                with open(csv_file_path, "w", newline="", encoding='utf-8') as csvfile:
                    fieldnames = set()
                    for record in processed_data:
                        fieldnames.update(record.keys())
                    
                    writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
                    writer.writeheader()
                    writer.writerows(processed_data)
                st.info(f"CSV output saved to: {csv_file_path}")
            
            return {
                "status": status,
                "output_path": base_filename,
                "file_size": file_size,
                "has_errors": "error" in extracted_data,
                "json_path": json_file_path,
                "csv_path": csv_file_path,
                "token_usage": extracted_data.get("token_usage", {})
            }
            
        except FileNotFoundError as e:
            st.error(f"File not found error: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"File not found: {str(e)}",
                "error_type": "file_not_found"
            }
        except ValueError as e:
            st.error(f"Value error: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"Invalid file or data: {str(e)}",
                "error_type": "invalid_data"
            }
        except Exception as e:
            st.error(f"Unexpected error in image processing: {str(e)}")
            st.error(f"Traceback: {traceback.format_exc()}")
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
            st.warning(f"Error extracting critical dimensions: {str(e)}")
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
            st.error(f"Error generating summary report: {str(e)}")
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
            st.error(f"Export format error: {str(e)}")
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
    
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import numpy as np

class ConfusionMatrixGenerator:
    def __init__(self, output_dir="./evaluation"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _parse_predictions(self, extracted_data: Dict) -> Dict[str, int]:
        """
        Parses the Gemini JSON response to determine which features were detected.
        Returns a binary dictionary (1 = Detected/Value Found, 0 = Not Detected/Null).
        """
        # Define the critical dimension IDs based on your PROMPT schema
        critical_ids = [
            "dim_outer_dia", 
            "dim_hub_dia", 
            "dim_face_width", 
            "dim_hub_height", 
            "dim_bore"
        ]
        
        # Initialize all predictions to 0 (not detected)
        predictions = {k: 0 for k in critical_ids}
        
        try:
            # Check if we have extracted data
            if "extracted_data" not in extracted_data:
                return predictions
            
            data = extracted_data["extracted_data"]
            
            # Check dimensions
            if "dimensions" in data and isinstance(data["dimensions"], list):
                for dim in data["dimensions"]:
                    if isinstance(dim, dict):
                        dim_id = dim.get("id")
                        value = dim.get("value")
                        
                        # Check if this is a critical dimension and has a valid value
                        if dim_id in critical_ids and value is not None:
                            # Also check if it's not an empty string or "null"
                            if str(value).strip().lower() not in ["", "null", "none"]:
                                predictions[dim_id] = 1
        except Exception as e:
            st.warning(f"Error parsing predictions: {str(e)}")
        
        return predictions
    
    def generate_and_save_matrix(self, extracted_data: Dict, ground_truth: Dict[str, int], filename_prefix: str):
        """
        Generates a Confusion Matrix comparing Extracted Data vs Ground Truth.
        
        Args:
            extracted_data: The full JSON output from the Gemini model.
            ground_truth: A dictionary indicating if features REALLY exist in the image.
                          Example: {"dim_outer_dia": 1, "dim_hub_dia": 0, ...}
            filename_prefix: String to prefix the saved image file.
        """
        try:
            # 1. Get Predictions vector
            preds_dict = self._parse_predictions(extracted_data)
            
            # 2. Ensure we have the same keys in both dictionaries
            all_keys = set(list(preds_dict.keys()) + list(ground_truth.keys()))
            
            # Use sorted keys for consistency
            keys = sorted(all_keys)
            y_pred = [preds_dict.get(k, 0) for k in keys]
            y_true = [ground_truth.get(k, 0) for k in keys]
            
            # 3. Generate Confusion Matrix
            # Labels: [0=Not Detected, 1=Detected]
            cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
            
            # 4. Plotting
            plt.figure(figsize=(8, 6))
            sns.heatmap(
                cm, 
                annot=True, 
                fmt='d', 
                cmap='Blues',
                xticklabels=['Predicted Absent', 'Predicted Present'],
                yticklabels=['Actually Absent', 'Actually Present'],
                cbar_kws={'label': 'Count'}
            )
            
            # Add accuracy score
            accuracy = np.trace(cm) / np.sum(cm) if np.sum(cm) > 0 else 0
            plt.title(f'Feature Detection Confusion Matrix\n{filename_prefix}\nAccuracy: {accuracy:.2%}')
            plt.ylabel('Actual (Ground Truth)')
            plt.xlabel('Predicted (Model)')
            
            plt.tight_layout()
            
            # 5. Save to System
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c for c in filename_prefix if c.isalnum() or c in ('-', '_')).rstrip()
            save_path = os.path.join(self.output_dir, f"conf_matrix_{safe_filename}_{timestamp}.png")
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            return save_path
            
        except Exception as e:
            st.error(f"Failed to generate confusion matrix: {str(e)}")
            return None

# Streamlit UI
def main():
    st.title("📐 Technical Drawing Extraction Service")
    st.markdown("Extract technical data from gear drawings using Gemini AI")
    
    # Initialize service
    if 'service' not in st.session_state:
        st.session_state.service = TechnicalDrawingExtractionService()
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = {}
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        output_dir = st.text_input("Output Directory", value="./output")
        
        st.header("File Management")
        if st.button("Clear All Processed Files"):
            st.session_state.processed_files = {}
            st.session_state.service = TechnicalDrawingExtractionService()
            st.rerun()
    
    # Main content
    tab1, tab2, tab3 = st.tabs(["Upload & Process", "View Results", "Export Data"])
    
    with tab1:
        st.header("Upload Technical Drawing")
        
        uploaded_file = st.file_uploader(
            "Choose an image file", 
            type=['png', 'jpg', 'jpeg', 'bmp', 'tiff'],
            help="Upload a technical drawing image for data extraction"
        )
        
        if uploaded_file is not None:
            # Display image
            col1, col2 = st.columns(2)
            with col1:
                st.image(uploaded_file, caption="Uploaded Drawing", use_container_width=True)
            
            with col2:
                file_details = {
                    "Filename": uploaded_file.name,
                    "File size": f"{uploaded_file.size / 1024:.2f} KB",
                    "File type": uploaded_file.type
                }
                st.write("File Details:")
                st.json(file_details)
            
            # Process button
            if st.button("Extract Data from Drawing", type="primary"):
                with st.spinner("Processing..."):
                    # Save uploaded file temporarily
                    temp_dir = "./temp"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Generate task ID
                    task_id = str(uuid.uuid4())[:8]
                    
                    # Process file
                    result = st.session_state.service.process_image_file(
                        task_id=task_id,
                        file_path=temp_path,
                        output_dir=output_dir
                    )
                    
                    # Store result
                    st.session_state.processed_files[task_id] = {
                        **result,
                        "filename": uploaded_file.name,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Display result
                    if result["status"] == "completed":
                        st.success("✅ Data extraction completed successfully!")
                    elif result["status"] == "completed_with_errors":
                        st.warning("⚠️ Data extraction completed with some errors")
                    else:
                        st.error("❌ Data extraction failed")
                    
                    # Show file paths
                    st.info(f"JSON Output: `{result.get('json_path', 'N/A')}`")
                    st.info(f"CSV Output: `{result.get('csv_path', 'N/A')}`")
                    
                    # Clean up temp file
                    try:
                        os.remove(temp_path)
                    except:
                        pass
    
    with tab2:
        st.header("View Extracted Data")
        
        if not st.session_state.processed_files:
            st.info("No processed files yet. Upload a file in the first tab.")
        else:
            # File selection
            file_options = {
                f"{task_id} - {info.get('filename', 'Unknown')}": task_id
                for task_id, info in st.session_state.processed_files.items()
            }
            
            selected_file = st.selectbox(
                "Select a processed file:",
                options=list(file_options.keys())
            )
            
            if selected_file:
                task_id = file_options[selected_file]
                file_info = st.session_state.processed_files[task_id]
                
                # Display file info
                st.subheader("File Information")
                info_cols = st.columns(4)
                with info_cols[0]:
                    st.metric("Status", file_info.get("status", "Unknown"))
                with info_cols[1]:
                    st.metric("File Size", f"{file_info.get('file_size', 0) / 1024:.1f} KB")
                with info_cols[2]:
                    has_errors = file_info.get("has_errors", False)
                    st.metric("Has Errors", "Yes" if has_errors else "No")
                with info_cols[3]:
                    if file_info.get("token_usage"):
                        total_tokens = file_info["token_usage"].get("total_tokens", 0)
                        st.metric("Total Tokens", total_tokens)
                
                # Load and display extracted data
                json_path = file_info.get("json_path")
                if json_path and os.path.exists(json_path):
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            extracted_data = json.load(f)
                        
                        # Create tabs for different data views
                        # view_tabs = st.tabs(["JSON View", "Summary", "Dimensions", "Tables", "Features"])
                        view_tabs = st.tabs(["JSON View", "Summary", "Dimensions", "Tables", "Features", "Evaluation"])

                        
                        with view_tabs[0]:
                            st.subheader("Full JSON Data")
                            st.json(extracted_data)
                        
                        with view_tabs[1]:
                            st.subheader("Summary Report")
                            summary = st.session_state.service.generate_summary_report(
                                extracted_data.get("extracted_data", {}),
                                file_info.get("filename", "Unknown")
                            )
                            st.json(summary)
                            
                            # Critical dimensions
                            critical_dims = st.session_state.service.get_critical_dimensions(
                                extracted_data.get("extracted_data", {})
                            )
                            if critical_dims:
                                st.subheader("Critical Dimensions")
                                dim_df = pd.DataFrame(critical_dims)
                                st.dataframe(dim_df, use_container_width=True)
                        
                        with view_tabs[2]:
                            if "extracted_data" in extracted_data and "dimensions" in extracted_data["extracted_data"]:
                                st.subheader("Dimensions")
                                dims = extracted_data["extracted_data"]["dimensions"]
                                if dims:
                                    dim_df = pd.DataFrame(dims)
                                    st.dataframe(dim_df, use_container_width=True)
                                else:
                                    st.info("No dimensions extracted")
                            else:
                                st.info("No dimensions data available")
                        
                        with view_tabs[3]:
                            if "extracted_data" in extracted_data and "tables" in extracted_data["extracted_data"]:
                                st.subheader("Tables")
                                tables = extracted_data["extracted_data"]["tables"]
                                for table in tables:
                                    with st.expander(f"Table: {table.get('id', 'Unknown')}"):
                                        if "cells" in table:
                                            table_df = pd.DataFrame(table["cells"])
                                            st.dataframe(table_df, use_container_width=True)
                            else:
                                st.info("No table data available")
                        
                        with view_tabs[4]:
                            if "extracted_data" in extracted_data and "features" in extracted_data["extracted_data"]:
                                st.subheader("Features")
                                features = extracted_data["extracted_data"]["features"]
                                if features:
                                    feat_df = pd.DataFrame(features)
                                    st.dataframe(feat_df, use_container_width=True)
                                else:
                                    st.info("No features extracted")
                            else:
                                st.info("No features data available")

                        # Add a new tab for Evaluation
                        with view_tabs[5]:
                            with st.expander("📊 Generate Confusion Matrix (Validation)"):
                                st.write("Compare model results against actual image features.")
                                
                                # Create a form to input Ground Truth (what actually exists in the image)
                                with st.form("ground_truth_form"):
                                    st.write("Check the features that are visible in the drawing:")
                                    col_a, col_b = st.columns(2)
                                    gt_inputs = {}
                                    with col_a:
                                        gt_inputs["dim_outer_dia"] = st.checkbox("Outer Diameter (Tip)", value=True)
                                        gt_inputs["dim_hub_dia"] = st.checkbox("Hub Diameter", value=True)
                                        gt_inputs["dim_bore"] = st.checkbox("Bore Diameter", value=True)
                                    with col_b:
                                        gt_inputs["dim_face_width"] = st.checkbox("Face Width", value=True)
                                        gt_inputs["dim_hub_height"] = st.checkbox("Hub Height", value=True)
                                    
                                    submit_matrix = st.form_submit_button("Generate & Save Matrix")
                                    
                                    if submit_matrix:
                                        # Convert booleans to 1/0
                                        ground_truth = {k: 1 if v else 0 for k, v in gt_inputs.items()}
                                        
                                        # Initialize generator
                                        cm_gen = ConfusionMatrixGenerator(output_dir="./output/matrices")
                                        
                                        # Generate
                                        saved_path = cm_gen.generate_and_save_matrix(
                                            extracted_data, 
                                            ground_truth, 
                                            file_info.get('filename', 'unknown')
                                        )
                                        
                                        if saved_path:
                                            st.image(saved_path, caption="Confusion Matrix", width=500)
                            
                        # Download buttons
                        st.subheader("Download Data")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if os.path.exists(json_path):
                                with open(json_path, 'rb') as f:
                                    st.download_button(
                                        label="Download JSON",
                                        data=f,
                                        file_name=f"{task_id}_extracted_data.json",
                                        mime="application/json"
                                    )
                        
                        with col2:
                            csv_path = file_info.get("csv_path")
                            if csv_path and os.path.exists(csv_path):
                                with open(csv_path, 'rb') as f:
                                    st.download_button(
                                        label="Download CSV",
                                        data=f,
                                        file_name=f"{task_id}_processed_data.csv",
                                        mime="text/csv"
                                    )
                        
                        with col3:
                            # Generate summary text
                            summary_text = st.session_state.service.export_to_specific_format(
                                extracted_data.get("extracted_data", {}),
                                "inspection_sheet"
                            )
                            st.download_button(
                                label="Download Inspection Sheet",
                                data=summary_text,
                                file_name=f"{task_id}_inspection_sheet.txt",
                                mime="text/plain"
                            )
                    
                    except Exception as e:
                        st.error(f"Error loading data: {str(e)}")
                else:
                    st.warning("JSON output file not found")
    
    with tab3:
        st.header("Export Data Formats")
        
        if not st.session_state.processed_files:
            st.info("No processed files to export. Upload a file in the first tab.")
        else:
            # Format selection
            export_format = st.selectbox(
                "Select export format:",
                ["inspection_sheet", "cad_import", "manufacturing_sheet"]
            )
            
            # File selection for export
            export_options = {
                f"{task_id} - {info.get('filename', 'Unknown')}": task_id
                for task_id, info in st.session_state.processed_files.items()
            }
            
            selected_export = st.selectbox(
                "Select file to export:",
                options=list(export_options.keys())
            )
            
            if selected_export and export_format:
                task_id = export_options[selected_export]
                file_info = st.session_state.processed_files[task_id]
                json_path = file_info.get("json_path")
                
                if json_path and os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        extracted_data = json.load(f)
                    
                    # Generate export
                    export_text = st.session_state.service.export_to_specific_format(
                        extracted_data.get("extracted_data", {}),
                        export_format
                    )
                    
                    st.subheader(f"{export_format.replace('_', ' ').title()} Preview")
                    st.code(export_text, language="text")
                    
                    # Download button
                    format_names = {
                        "inspection_sheet": "Inspection_Sheet",
                        "cad_import": "CAD_Import",
                        "manufacturing_sheet": "Manufacturing_Sheet"
                    }
                    
                    st.download_button(
                        label=f"Download {format_names[export_format]}",
                        data=export_text,
                        file_name=f"{task_id}_{format_names[export_format]}.txt",
                        mime="text/plain"
                    )
                else:
                    st.warning("Could not load data for export")

if __name__ == "__main__":
    main()