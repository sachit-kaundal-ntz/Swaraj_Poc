import os
import uuid
import json
import csv
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai import types
from typing import Dict, List, Optional, Any
from PIL import Image, ImageEnhance
import base64
import io
from app.log.logger import get_logger

logger = get_logger(__name__)
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

class TechnicalDrawingExtractionService:
    MAX_ALLOWED_INPUT_TOKENS = 10000
    MAX_ALLOWED_OUTPUT_TOKENS = 8000

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
        """Accurate token counting using Gemini's count_tokens method."""
        try:
            if not text:
                return 0
            token_count = model.count_tokens(text)
            return token_count.total_tokens
        except Exception as e:
            logger.warning(f"Failed to get accurate token count, using estimation: {str(e)}")
            return self.estimate_tokens(text)

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens for Gemini models."""
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
        """Estimate tokens consumed by an image."""
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
        """Count total tokens for a request."""
        prompt_tokens = self.count_tokens_accurate(prompt)
        image_tokens = self.estimate_image_tokens(image_path) if image_path else 0
        total_tokens = prompt_tokens + image_tokens
        if total_tokens > self.MAX_ALLOWED_INPUT_TOKENS:
            raise ValueError(
                f"Token limit exceeded: {total_tokens} tokens (max allowed: {self.MAX_ALLOWED_INPUT_TOKENS}). "
                f"Breakdown - Prompt: {prompt_tokens}, Image: {image_tokens}"
            )
        return {
            "prompt_tokens": prompt_tokens,
            "image_tokens": image_tokens,
            "total_input_tokens": total_tokens
        }

    async def upload_image_to_gemini(self, image_path: str) -> Any:
        """Upload image file to Gemini."""
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

    def sanitize_for_json(self, obj: Any) -> Any:
        """Recursively convert sets to lists and ensure JSON-serializable output."""
        if isinstance(obj, set):
            return sorted(list(obj))
        elif isinstance(obj, dict):
            return {k: self.sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.sanitize_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self.sanitize_for_json(item) for item in obj]
        else:
            return obj

    def preprocess_image(self, image_path: str, output_path: str = None) -> str:
        """Preprocess image to reduce noise and safety filter triggers."""
        try:
            with Image.open(image_path) as img:
                # Convert to grayscale
                img = img.convert("L")
                # Increase contrast
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                # Sharpen image
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(1.5)
                # Reduce noise with slight blur
                from PIL import ImageFilter
                img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
                if output_path is None:
                    output_path = f"preprocessed_{os.path.basename(image_path)}"
                img.save(output_path)
                logger.info(f"Preprocessed image saved to: {output_path}")
                return output_path
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            return image_path

    def attempt_fix_json(self, text: str) -> str:
        """Attempt to fix incomplete JSON."""
        try:
            text = text.rstrip(',')
            open_braces = text.count('{')
            close_braces = text.count('}')
            open_brackets = text.count('[')
            close_brackets = text.count(']')
            for _ in range(open_brackets - close_brackets):
                text += ']'
            for _ in range(open_braces - close_braces):
                text += '}'
            if text.count('"') % 2 == 1:
                text += '"'
            return text
        except Exception as e:
            logger.warning(f"Failed to fix JSON: {str(e)}")
            return text

    async def extract_technical_drawing_data(self, image_path: str) -> Dict:
        """Extract technical drawing data from image using Gemini."""
        try:
            logger.info(f"Starting technical drawing extraction for: {image_path}")

            PROMPT = """
            You are an expert engineering drawing analysis system. Analyze this technical drawing and extract visible specifications.

            CRITICAL OUTPUT REQUIREMENTS:
            - Respond with COMPLETE, VALID JSON only - no partial or truncated output
            - Ensure all braces and brackets are closed
            - If no data can be extracted or the image is unclear, return: {}
            - Do not include Markdown, comments, or additional text
            - Prioritize drawing_metadata and overall_dimensions if token limits are approached

            EXTRACT:
            1. DRAWING METADATA:
               - drawing_type: "mechanical/electrical/etc"
               - component_type: "gear/shaft/etc"
               - part_name: exact title
               - drawing_number: drawing ID
               - revision: revision level
               - scale: drawing scale
               - date_created: creation date
               - material_specification: material callout
               - standards_referenced: [] (JSON array)

            2. OVERALL DIMENSIONS:
               - length, width, height, diameter: {"value": "exact_value", "unit": "mm/inch", "tolerance": "if_shown"}
               - other_critical_dimensions: [{"feature": "description", "value": "exact_value", "unit": "mm/inch", "tolerance": "if_shown", "location": "where_dimensioned"}]

            Respond ONLY with valid JSON.
            """
            
            # Preprocess image
            image_path = self.preprocess_image(image_path)
            
            # Check token limit
            try:
                input_token_info = self.count_total_tokens_for_request(PROMPT, image_path)
            except ValueError as e:
                logger.error(f"Token limit exceeded: {str(e)}")
                return {
                    "error": str(e),
                    "token_limit_exceeded": True,
                    "file": os.path.basename(image_path),
                    "token_usage": {
                        "error": str(e),
                        "token_counting_method": "gemini_api_with_estimation_fallback"
                    }
                }
            
            logger.info(f"Input tokens - Prompt: {input_token_info['prompt_tokens']}, "
                        f"Image: {input_token_info['image_tokens']}, "
                        f"Total: {input_token_info['total_input_tokens']}")
            
            # Verify image
            image_dims = self._get_image_dimensions(image_path)
            logger.info(f"Image details: {image_dims}")
            if "error" in image_dims:
                raise ValueError(f"Invalid image: {image_dims['error']}")
            
            uploaded_file = await self.upload_image_to_gemini(image_path)
            
            # Retry with adjusted safety settings
            max_retries = 4
            response_text = None
            for attempt in range(max_retries):
                try:
                    safety_settings=[
                        types.SafetySettingDict(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,  # least restrictive
                        ),
                        types.SafetySettingDict(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        types.SafetySettingDict(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        types.SafetySettingDict(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                    ]
                    response = model.generate_content(
                        [PROMPT, uploaded_file],
                        generation_config={
                            "temperature": 0.0,
                            "max_output_tokens": self.MAX_ALLOWED_OUTPUT_TOKENS
                        },
                        safety_settings=safety_settings
                    )
                    
                    # Log response details
                    logger.info(f"Attempt {attempt+1} - Response candidates: {response.candidates}")
                    logger.info(f"Attempt {attempt+1} - Prompt feedback: {response.prompt_feedback}")
                    if response.prompt_feedback:
                        for rating in response.prompt_feedback.safety_ratings:
                            logger.info(f"Attempt {attempt+1} - Safety rating: {rating.category} - {rating.probability}")
                    
                    # Check for valid response parts
                    if not response.candidates or not response.candidates[0].content.parts:
                        finish_reason = response.candidates[0].finish_reason if response.candidates else "unknown"
                        logger.error(f"Attempt {attempt+1} - No valid response parts. Finish reason: {finish_reason}")
                        if finish_reason == 2 and attempt < max_retries - 1:
                            continue
                        return {
                            "error": f"No valid response parts returned (finish_reason: {finish_reason})",
                            "file": os.path.basename(image_path),
                            "raw_response": "",
                            "token_usage": {
                                "input_tokens": input_token_info,
                                "output_tokens": 0,
                                "total_tokens": input_token_info.get('total_input_tokens', 0),
                                "token_counting_method": "gemini_api_with_estimation_fallback"
                            }
                        }
                    
                    response_text = response.text.strip()
                    logger.info(f"Attempt {attempt+1} - Raw response text: {response_text[:2000]}...")
                    
                    # Robust Markdown stripping
                    if response_text.startswith("```json"):
                        response_text = response_text[7:].strip()
                        if response_text.endswith("```"):
                            response_text = response_text[:-3].strip()
                    elif response_text.startswith("```"):
                        response_text = response_text[3:].strip()
                        if response_text.endswith("```"):
                            response_text = response_text[:-3].strip()
                    
                    # Check if response_text is empty
                    if not response_text:
                        logger.error(f"Attempt {attempt+1} - Empty response text")
                        if attempt == max_retries - 1:
                            return {
                                "error": "Empty response from AI model",
                                "file": os.path.basename(image_path),
                                "raw_response": "",
                                "token_usage": {
                                    "input_tokens": input_token_info,
                                    "output_tokens": 0,
                                    "total_tokens": input_token_info.get('total_input_tokens', 0),
                                    "token_counting_method": "gemini_api_with_estimation_fallback"
                                }
                            }
                        continue
                    
                    # Attempt to fix incomplete JSON
                    fixed_response_text = self.attempt_fix_json(response_text)
                    logger.info(f"Attempt {attempt+1} - Fixed response text: {fixed_response_text[:2000]}...")
                    
                    # Validate JSON structure
                    if not (fixed_response_text.startswith('{') and fixed_response_text.endswith('}')):
                        logger.error(f"Attempt {attempt+1} - Response is not a valid JSON object: {fixed_response_text[:2000]}...")
                        if attempt == max_retries - 1:
                            raise json.JSONDecodeError("Invalid JSON structure", fixed_response_text, 0)
                        continue
                    
                    output_tokens = self.count_tokens_accurate(fixed_response_text)
                    if output_tokens >= self.MAX_ALLOWED_OUTPUT_TOKENS * 0.95:
                        logger.warning(f"Attempt {attempt+1} - Response may be truncated. Output tokens: {output_tokens}/{self.MAX_ALLOWED_OUTPUT_TOKENS}")
                    
                    parsed_data = json.loads(fixed_response_text)
                    logger.info(f"Attempt {attempt+1} - Successfully parsed JSON response from Gemini")
                    
                    # Sanitize parsed_data
                    parsed_data = self.sanitize_for_json(parsed_data)
                    
                    total_tokens = input_token_info['total_input_tokens'] + output_tokens
                    
                    parsed_data["token_usage"] = {
                        "input_tokens": input_token_info,
                        "output_tokens": output_tokens,
                        "output_token_limit": self.MAX_ALLOWED_OUTPUT_TOKENS,
                        "total_tokens": total_tokens,
                        "token_counting_method": "gemini_api_with_estimation_fallback",
                        "image_dimensions": image_dims
                    }
                    
                    return parsed_data
                
                except json.JSONDecodeError as e:
                    logger.error(f"Attempt {attempt+1} - JSON parsing error: {str(e)}")
                    logger.error(f"Attempt {attempt+1} - Response text: {response_text[:2000] if response_text else 'None'}...")
                    if attempt == max_retries - 1:
                        partial_data = {}
                        try:
                            json_start = response_text.find('{') if response_text else -1
                            json_end = response_text.rfind('}') if response_text else -1
                            if json_start != -1 and json_end != -1 and json_end > json_start:
                                partial_json = response_text[json_start:json_end+1]
                                partial_json = self.attempt_fix_json(partial_json)
                                partial_data = json.loads(partial_json)
                                logger.info(f"Attempt {attempt+1} - Successfully parsed partial JSON")
                        except Exception as pe:
                            logger.warning(f"Attempt {attempt+1} - Partial JSON parsing failed: {str(pe)}")
                        return {
                            "error": f"Invalid JSON response from AI model: {str(e)}",
                            "extracted_data": self.sanitize_for_json(partial_data),
                            "raw_response": response_text[:2000] if response_text else "",
                            "token_usage": {
                                "input_tokens": input_token_info,
                                "output_tokens": output_tokens if 'output_tokens' in locals() else 0,
                                "total_tokens": input_token_info.get('total_input_tokens', 0) + (output_tokens if 'output_tokens' in locals() else 0),
                                "token_counting_method": "gemini_api_with_estimation_fallback"
                            }
                        }
                except Exception as e:
                    logger.error(f"Attempt {attempt+1} - Unexpected error: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    if attempt == max_retries - 1:
                        return {
                            "error": f"Unexpected error: {str(e)}",
                            "file": os.path.basename(image_path),
                            "raw_response": response_text[:2000] if response_text else "",
                            "token_usage": {
                                "input_tokens": input_token_info,
                                "output_tokens": 0,
                                "total_tokens": input_token_info.get('total_input_tokens', 0),
                                "token_counting_method": "gemini_api_with_estimation_fallback"
                            }
                        }
                    continue
            
        except Exception as e:
            logger.error(f"Technical drawing extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            input_token_info = self.count_total_tokens_for_request(PROMPT, image_path) if 'PROMPT' in locals() else {"prompt_tokens": 0, "image_tokens": 0, "total_input_tokens": 0}
            return {
                "error": str(e),
                "file": os.path.basename(image_path),
                "raw_response": "",
                "token_usage": {
                    "input_tokens": input_token_info,
                    "output_tokens": 0,
                    "total_tokens": input_token_info.get('total_input_tokens', 0),
                    "token_counting_method": "gemini_api_with_estimation_fallback"
                }
            }

    def _get_image_dimensions(self, image_path: str) -> Dict[str, Any]:
        """Get image dimensions."""
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
        """Process data into a flat structure for CSV output."""
        try:
            logger.info(f"Processing data for CSV output: {filename}")
            records = []
            
            def create_universal_records(data, filename):
                universal_records = []
                if "drawing_metadata" in data:
                    metadata_record = {
                        "Filename": filename,
                        "Record_Type": "Drawing_Metadata",
                        **{f"Meta_{k}": self.sanitize_for_json(v) for k, v in data["drawing_metadata"].items()}
                    }
                    universal_records.append(metadata_record)
                if "overall_dimensions" in data:
                    overall_record = {
                        "Filename": filename,
                        "Record_Type": "Overall_Dimensions",
                        **{f"Overall_{k}": self.sanitize_for_json(v) for k, v in data["overall_dimensions"].items()}
                    }
                    universal_records.append(overall_record)
                if "feature_dimensions" in data and isinstance(data["feature_dimensions"], list):
                    for i, feature in enumerate(data["feature_dimensions"]):
                        feature_record = {
                            "Filename": filename,
                            "Record_Type": "Feature_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Feature_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        universal_records.append(feature_record)
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
                                record[new_key] = "; ".join(str(self.sanitize_for_json(x)) for x in v)
                        else:
                            record[new_key] = str(self.sanitize_for_json(v))
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

    async def process_image_file(self, task_id: str, file_path: str, output_dir: str) -> dict:
        """Process image file using Gemini extraction - no database dependency."""
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
            extracted_data = self.sanitize_for_json(extracted_data)
            logger.info(f"Extracted data structure: {json.dumps(extracted_data, default=str)[:2000]}...")
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
        """Retrieve file information by task ID."""
        return self.processed_files.get(task_id)

    def get_all_processed_files(self) -> Dict:
        """Get all processed files."""
        return self.processed_files

    def update_file_status(self, task_id: str, status: str) -> Optional[Dict]:
        """Update file status."""
        if task_id in self.processed_files:
            self.processed_files[task_id]["status"] = status
            self.processed_files[task_id]["updated_at"] = datetime.now().isoformat()
            return self.processed_files[task_id]
        return None

    def delete_file_info(self, task_id: str) -> bool:
        """Delete file information."""
        if task_id in self.processed_files:
            del self.processed_files[task_id]
            return True
        return False

    def get_drawing_type_from_data(self, extracted_data: Dict) -> str:
        """Determine drawing type from extracted data."""
        try:
            if "drawing_metadata" in extracted_data:
                drawing_type = extracted_data["drawing_metadata"].get("drawing_type", "unknown")
                component_type = extracted_data["drawing_metadata"].get("component_type", "")
                return f"{drawing_type}_{component_type}".replace(" ", "_").lower()
            return "unknown"
        except:
            return "unknown"

    def get_critical_dimensions(self, extracted_data: Dict) -> List[Dict]:
        """Extract critical dimensions."""
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
        """Generate a summary report."""
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
        """Export data to specific formats."""
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
        """Create inspection sheet format."""
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
        """Create CAD import format."""
        lines = ["# CAD Import Data"]
        if "overall_dimensions" in data:
            lines.append("## Overall Dimensions")
            for dim_name, dim_data in data["overall_dimensions"].items():
                if isinstance(dim_data, dict) and "value" in dim_data:
                    lines.append(f"{dim_name.upper()},{dim_data['value']},{dim_data.get('unit', 'mm')}")
        return "\n".join(lines)

    def _create_manufacturing_sheet_format(self, data: Dict) -> str:
        """Create manufacturing instruction sheet."""
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