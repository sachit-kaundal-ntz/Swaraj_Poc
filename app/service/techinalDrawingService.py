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

from app.log.logger import get_logger

logger = get_logger(__name__)
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
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
            You are an expert mechanical drawing interpreter. Your role is to extract ONLY the explicitly printed information from a mechanical gear drawing and return a structured JSON.

            ABSOLUTE RULES
            1. Never invent values. If a requested value is not visible, set `"value": null` and `"source": "missing_on_drawing"`.
            2. Root diameter is not a cavity. Do not treat root_diameter as an internal hollow for volume. Net section for mass uses outer tip diameter vs. bore.
            3. Face width vs hub extension:  
            - The **largest axial length** in the gear body = face_width.  
            - Any additional axial lengths (e.g., hub protrusions) = hub_extension.  
            4. Bore subtraction passes through the full axial stack (face_width + hub_extension).  
            5. Preserve all units, tolerances, and symbols exactly (⌀, ±, H7, -0.1, etc.).  
            6. Copy source text exactly into `raw_text`.  
            7. Always include `view_id` and leader arrow mapping if visible.  
            8. All tables (gear data, spline data, permissible deviations, heat-treat, material) must be represented in `"tables"` and linked through `features[*].table_links`.

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

     ### 3. DIMENSION IDENTIFICATION PRIORITY
            - **Hub Diameter**: starting and end point of the hub groove/bore and not part of main rim.
            - **Outer Diameter**: Starting and the end point of the rim (It is the outermost length to the tip of tooth)
            - **Hub Height/Length**: Starting and end point of the hub's axial extent along the bore centerline, measured between the hub faces that are perpendicular to the shaft axis and not including the main gear rim thickness.
            - **Face Width**: Axial dimension of the main gear body/rim section.
            - **Bore Diameter**: Internal diameter dimensions (often with fit tolerances like H7).

            ### 4. FEATURE CLASSIFICATION RULES
            - **Root diameter is NOT a cavity** – it's the gear tooth root, use only for gear data.
            - **Face width** = largest axial dimension (main gear body width).
            - **Hub extension** = any additional axial lengths beyond face width.
            - **Bore subtraction** applies through full axial stack (face_width + hub_extension).

            ### 5. TABLE DATA EXTRACTION
            - Extract all tabular data (gear data, spline data, material properties).
            - Link tables to relevant features via `table_links`.
            - Preserve exact formatting and units from tables.

            ### 6. MISSING DATA HANDLING
            - If a dimension is not visible: set `"value": null, "source": "missing_on_drawing"`.
            - Do not invent or calculate missing values.
            - Only extract what is explicitly shown.

            ---

            ## SPECIFIC EXTRACTION INSTRUCTIONS

            ### For Hub Features:
            - Look for stepped cylindrical sections with smaller diameters.
            - Hub diameter = starting and end point of the hub groove/bore
            - Hub height/extension = axial dimension of hub section.

            ### For Main Gear Body:
            - Outer diameter = largest diameter dimension (gear tip circle).
            - Face width = main axial dimension of gear body.
            - Link to gear data table for teeth count, module, etc.

            ### For Bore Features:
            - Extract bore diameter with any fit specifications (H7, etc.).
            - Bore extends through entire axial length unless otherwise specified.
            - Separate spline bores as distinct features with `table_links`.

            ### For Dimension Text:
            - Copy raw dimension text exactly: "⌀…", "…", "±…".
            - Preserve symbols and tolerance notations.
            - Map leader lines when identifiable.

            ## OUTPUT REQUIREMENTS
            - Return ONLY the JSON – no commentary.
            - All dimensions must have explicit `raw_text` field.
            - Link all tabular data through `table_links`.
            - Preserve exact formatting from drawing.
            - Each dimension must have unique descriptive ID.

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

    async def process_all_data(self, data: Dict, filename: str) -> List[Dict]:
        """Process all data into a flat structure for CSV output with universal organization"""
        try:
            logger.info(f"Processing data for CSV output: {filename}")
            
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
            
            logger.info(f"Processed {len(records)} total records")
            return records
            
        except Exception as e:
            logger.error(f"Data processing error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [{
                "Filename": filename,
                "Error": f"Data processing error: {str(e)}",
                "Record_Type": "Error"
            }]

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
            
            csv_file_path = f"{base_filename}.csv"
            processed_data = await self.process_all_data(extracted_data, os.path.basename(file_path))
            
            if processed_data and len(processed_data) > 0:
                with open(csv_file_path, "w", newline="", encoding='utf-8') as csvfile:
                    fieldnames = set()
                    for record in processed_data:
                        fieldnames.update(record.keys())
                    
                    writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
                    writer.writeheader()
                    writer.writerows(processed_data)
                logger.info(f"CSV output saved to: {csv_file_path}")
            
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

