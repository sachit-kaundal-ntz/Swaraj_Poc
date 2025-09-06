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
from sqlalchemy.ext.asyncio import AsyncSession
from app.log.logger import get_logger
from app.models.drawingModel import DrawingProcessingResult as DrawingProcessingResultModel
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger(__name__)
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

class TechnicalDrawingExtractionService:
    MAX_ALLOWED_INPUT_TOKENS = 15000
    MAX_ALLOWED_OUTPUT_TOKENS = 15000

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
        """Extract comprehensive technical drawing data from image using Gemini."""
        try:
            logger.info(f"Starting comprehensive technical drawing extraction for: {image_path}")


            PROMPT = """
You are an expert technical drawing analysis system. Extract ALL visible dimensions with exact shape-wise calculations. Be completely dynamic - never hardcode tolerance values or make assumptions.

🎯 CORE PRINCIPLES:
1. Extract ONLY what is explicitly visible on the drawing
2. Calculate exact min/max for each dimension with visible tolerances
3. Group dimensions by geometric shapes/features
4. Never assume tolerance values - mark as "tolerance_not_specified"
5. Be completely generic for any drawing type

---

### DYNAMIC EXTRACTION METHODOLOGY

#### STEP 1: IDENTIFY ALL GEOMETRIC FEATURES
Scan the drawing and identify every distinct shape:
- Basic shapes: circles, rectangles, cylinders, cones
- Complex features: gears, splines, threads, keyways
- Detail features: chamfers, fillets, grooves, holes
- Composite assemblies: multi-part features

#### STEP 2: EXTRACT VISIBLE DIMENSIONS ONLY
For each feature, extract ONLY explicitly shown:
- Dimension values (exact as written: 50.0, 50.00, 50)
- Tolerance notations (±0.1, +0.05/-0.02, H7/g6, etc.)
- Units (mm, inches, μm, etc.)
- Reference/datum callouts

#### STEP 3: CALCULATE EXACT RANGES (ONLY FOR SPECIFIED TOLERANCES)
When tolerance IS specified:
- Max = Nominal + Upper_Tolerance
- Min = Nominal - Lower_Tolerance
- Show calculation formula

When tolerance NOT specified:
- Mark as "tolerance_not_specified"
- Do NOT assume general tolerance values
- Do NOT calculate min/max ranges

---

### DYNAMIC OUTPUT SCHEMA

```json
{
  "drawing_identification": {
    "title": "exact_title_as_written",
    "drawing_number": "exact_number",
    "revision": "if_visible",
    "scale": "exact_scale",
    "material": "material_spec_if_shown",
    "general_tolerance_statement": "exact_statement_if_present"
  },

  "geometric_features": [
    {
      "feature_id": "AUTO_GENERATED_ID",
      "feature_type": "DETECTED_TYPE", // cylinder, rectangle, circle, gear, spline, etc.
      "feature_description": "descriptive_name",
      "location_reference": "view_name_or_section",
      
      "dimensions": {
        "dimension_name": {
          "nominal_value": "EXACT_AS_WRITTEN",
          "tolerance_notation": "EXACT_AS_SHOWN_OR_not_specified",
          "unit": "EXACT_UNIT",
          "tolerance_type": "bilateral|unilateral|fit_designation|limit|not_specified",
          
          // ONLY calculate if tolerance is specified
          "calculated_range": {
            "max_value": "CALCULATION_OR_not_calculated",
            "min_value": "CALCULATION_OR_not_calculated", 
            "calculation_formula": "SHOW_MATH_OR_not_applicable",
            "final_range": "[min, max] unit OR not_calculated"
          }
        }
      }
    }
  ],

  "tolerance_specifications": {
    "general_tolerances": {
      "statement": "EXACT_STATEMENT_IF_PRESENT",
      "standard_reference": "ISO_2768_etc_IF_SHOWN",
      "applied": false // true only if explicitly stated
    },
    
    "geometric_tolerances": [
      {
        "feature": "EXACT_FEATURE_NAME",
        "tolerance_value": "EXACT_VALUE",
        "tolerance_symbol": "EXACT_SYMBOL", 
        "datum_references": "EXACT_DATUMS",
        "type": "runout|position|profile|etc"
      }
    ],

    "fit_designations": [
      {
        "feature": "FEATURE_NAME",
        "fit_notation": "H7/g6_etc_EXACT",
        "hole_tolerance": "IF_SPECIFIED",
        "shaft_tolerance": "IF_SPECIFIED"
      }
    ]
  },

  "specialized_data": {
    // Only include if present on drawing
    "gear_specifications": [
      {
        "feature_id": "REFERENCE_TO_FEATURE",
        "parameters": {
          "module": "VALUE_IF_SHOWN",
          "teeth_count": "VALUE_IF_SHOWN",
          "pressure_angle": "VALUE_IF_SHOWN",
          // ... only parameters explicitly shown
        }
      }
    ],

    "thread_specifications": [
      {
        "feature_id": "REFERENCE_TO_FEATURE", 
        "thread_callout": "M10x1.5_etc_EXACT",
        "class": "6H_etc_IF_SHOWN"
      }
    ],

    "surface_finish": [
      {
        "feature": "FEATURE_NAME",
        "specification": "Ra_1.6_etc_EXACT",
        "symbol_location": "WHERE_SHOWN"
      }
    ]
  },

  "calculation_verification": {
    "total_features_identified": "COUNT",
    "dimensions_with_tolerances": "COUNT",
    "dimensions_without_tolerances": "COUNT", 
    "calculations_performed": "COUNT",
    "assumptions_made": 0, // Should always be 0
    "missing_tolerance_features": ["LIST_OF_FEATURES"]
  }
}
```

---

### CRITICAL RULES - NO EXCEPTIONS

#### ❌ NEVER DO:
- Hardcode tolerance values (±0.1, ±0.3, etc.)
- Assume general tolerance standards apply
- Calculate ranges without explicit tolerances
- Normalize or convert units unless specified
- Guess missing information
- Apply standard fit tables without callouts

#### ✅ ALWAYS DO:
- Extract dimensions exactly as written
- Preserve all decimal places shown
- Mark unspecified tolerances clearly
- Show calculation formulas when computing
- Maintain original units and notation
- Reference exact location where dimension appears

---

### TOLERANCE HANDLING LOGIC

```
IF tolerance_explicitly_shown:
    EXTRACT exact tolerance notation
    CALCULATE min/max range
    SHOW calculation formula
ELSE:
    tolerance_notation = "not_specified"
    calculated_range = "not_calculated"
    DO NOT assume any tolerance values
```

### FEATURE IDENTIFICATION PATTERNS

```
FOR each_visible_shape:
    IDENTIFY geometric type (circle, rectangle, etc.)
    GENERATE unique feature_id
    EXTRACT all associated dimensions
    GROUP related dimensions together
    CALCULATE only when tolerances present
```

---

### QUALITY VERIFICATION

Before outputting results:
1.  All dimensions extracted exactly as shown?
2. No hardcoded tolerance assumptions? 
3. Calculations only where tolerances specified?
4. All geometric features identified?
5.  Units preserved exactly?
6.  Zero assumptions made?

---

### EXAMPLES OF CORRECT EXTRACTION

**Visible: "50.0 ±0.05"**
```json
{
  "nominal_value": "50.0",
  "tolerance_notation": "±0.05", 
  "calculated_range": {
    "max_value": "50.0 + 0.05 = 50.05",
    "min_value": "50.0 - 0.05 = 49.95",
    "final_range": "[49.95, 50.05] mm"
  }
}
```

**Visible: "25" (no tolerance shown)**
```json
{
  "nominal_value": "25",
  "tolerance_notation": "not_specified",
  "calculated_range": "not_calculated"
}
```

**Visible: "⌀20 H7"**
```json
{
  "nominal_value": "20",
  "tolerance_notation": "H7",
  "tolerance_type": "fit_designation",
  "calculated_range": "requires_standard_lookup"
}
```

This system ensures complete accuracy by only working with explicitly visible information and performing exact calculations where tolerances are specified.
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
            max_retries = 2
            response_text = None
            for attempt in range(max_retries):
                try:
                    # Replace your current safety_settings with this more comprehensive version
                    safety_settings = [
                        types.SafetySettingDict(category=cat, threshold=types.HarmBlockThreshold.BLOCK_NONE)
                        for cat in [
                            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT
                        ]
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
        """Process data into a comprehensive flat structure for CSV output."""
        try:
            logger.info(f"Processing comprehensive data for CSV output: {filename}")
            records = []
            
            # Process drawing metadata
            if "drawing_metadata" in data:
                metadata_record = {
                    "Filename": filename,
                    "Record_Type": "Drawing_Metadata",
                    **{f"Meta_{k}": self.sanitize_for_json(v) for k, v in data["drawing_metadata"].items()}
                }
                records.append(metadata_record)
            
            # Process dimensions by shape
            if "dimensions_by_shape" in data:
                shapes = data["dimensions_by_shape"]
                
                # Circular features
                if "circular_features" in shapes and isinstance(shapes["circular_features"], list):
                    for i, feature in enumerate(shapes["circular_features"]):
                        record = {
                            "Filename": filename,
                            "Record_Type": "Circular_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Circular_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        records.append(record)
                
                # Linear features
                if "linear_features" in shapes and isinstance(shapes["linear_features"], list):
                    for i, feature in enumerate(shapes["linear_features"]):
                        record = {
                            "Filename": filename,
                            "Record_Type": "Linear_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Linear_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        records.append(record)
                
                # Angular features
                if "angular_features" in shapes and isinstance(shapes["angular_features"], list):
                    for i, feature in enumerate(shapes["angular_features"]):
                        record = {
                            "Filename": filename,
                            "Record_Type": "Angular_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Angular_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        records.append(record)
                
                # Threaded features
                if "threaded_features" in shapes and isinstance(shapes["threaded_features"], list):
                    for i, feature in enumerate(shapes["threaded_features"]):
                        record = {
                            "Filename": filename,
                            "Record_Type": "Threaded_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Thread_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        records.append(record)
                
                # Gear features
                if "gear_features" in shapes and isinstance(shapes["gear_features"], list):
                    for i, feature in enumerate(shapes["gear_features"]):
                        record = {
                            "Filename": filename,
                            "Record_Type": "Gear_Dimension",
                            "Feature_Index": i + 1,
                            **{f"Gear_{k}": self.sanitize_for_json(v) for k, v in feature.items()}
                        }
                        records.append(record)
            
            # Process overall dimensions
            if "overall_dimensions" in data:
                overall_record = {
                    "Filename": filename,
                    "Record_Type": "Overall_Dimensions",
                    **{f"Overall_{k}": self.sanitize_for_json(v) for k, v in data["overall_dimensions"].items()}
                }
                records.append(overall_record)
            
            # Process mass and weight information
            if "mass_and_weight_information" in data:
                mass_record = {
                    "Filename": filename,
                    "Record_Type": "Mass_Weight_Information",
                    **{f"Mass_{k}": self.sanitize_for_json(v) for k, v in data["mass_and_weight_information"].items()}
                }
                records.append(mass_record)
            
            # Process tolerances and fits
            if "tolerances_and_fits" in data:
                tolerance_record = {
                    "Filename": filename,
                    "Record_Type": "Tolerances_Fits",
                    **{f"Tolerance_{k}": self.sanitize_for_json(v) for k, v in data["tolerances_and_fits"].items()}
                }
                records.append(tolerance_record)
            
            # Process manufacturing information
            if "manufacturing_information" in data:
                mfg_record = {
                    "Filename": filename,
                    "Record_Type": "Manufacturing_Information",
                    **{f"Mfg_{k}": self.sanitize_for_json(v) for k, v in data["manufacturing_information"].items()}
                }
                records.append(mfg_record)
            
            # Process material properties
            if "material_properties" in data:
                material_record = {
                    "Filename": filename,
                    "Record_Type": "Material_Properties",
                    **{f"Material_{k}": self.sanitize_for_json(v) for k, v in data["material_properties"].items()}
                }
                records.append(material_record)
            
            # Process title block information
            if "title_block_information" in data:
                title_record = {
                    "Filename": filename,
                    "Record_Type": "Title_Block_Information",
                    **{f"Title_{k}": self.sanitize_for_json(v) for k, v in data["title_block_information"].items()}
                }
                records.append(title_record)
            
            # If no specific records found, create a general flattened record
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

    async def process_image_file(self, task_id: str, file_path: str, output_dir: str, db: 'AsyncSession' = None) -> dict:
        """Process image file using comprehensive Gemini extraction."""
        
        try:
            logger.info(f"Starting comprehensive image processing for task: {task_id}")
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
            if db is not None:
                try:
                    db_obj = DrawingProcessingResultModel(
                        task_id=task_id,
                        filename=os.path.basename(file_path),
                        status=status,
                        file_size=file_size,
                        has_errors=("error" in extracted_data),
                        json_path=json_file_path,
                        csv_path=csv_file_path,
                        extracted_data=extracted_data,
                    )
                    db.add(db_obj)
                    await db.commit()
                except SQLAlchemyError as db_exc:
                    logger.error(f"DB error: {db_exc}")
                    await db.rollback()
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
        """Extract critical dimensions from all shape categories."""
        critical_dims = []
        try:
            # Overall dimensions
            if "overall_dimensions" in extracted_data:
                for dim_name, dim_value in extracted_data["overall_dimensions"].items():
                    critical_dims.append({
                        "type": "overall",
                        "feature": dim_name,
                        "value": dim_value,
                        "category": "overall_dimension"
                    })
            
            # Dimensions by shape
            if "dimensions_by_shape" in extracted_data:
                shapes = extracted_data["dimensions_by_shape"]
                
                # Circular features
                if "circular_features" in shapes:
                    for i, feature in enumerate(shapes["circular_features"]):
                        critical_dims.append({
                            "type": "circular",
                            "feature_index": i + 1,
                            "feature_data": feature,
                            "category": "circular_dimension"
                        })
                
                # Linear features
                if "linear_features" in shapes:
                    for i, feature in enumerate(shapes["linear_features"]):
                        critical_dims.append({
                            "type": "linear",
                            "feature_index": i + 1,
                            "feature_data": feature,
                            "category": "linear_dimension"
                        })
                
                # Angular features
                if "angular_features" in shapes:
                    for i, feature in enumerate(shapes["angular_features"]):
                        critical_dims.append({
                            "type": "angular",
                            "feature_index": i + 1,
                            "feature_data": feature,
                            "category": "angular_dimension"
                        })
                
                # Threaded features
                if "threaded_features" in shapes:
                    for i, feature in enumerate(shapes["threaded_features"]):
                        critical_dims.append({
                            "type": "threaded",
                            "feature_index": i + 1,
                            "feature_data": feature,
                            "category": "threaded_dimension"
                        })
                
                # Gear features
                if "gear_features" in shapes:
                    for i, feature in enumerate(shapes["gear_features"]):
                        critical_dims.append({
                            "type": "gear",
                            "feature_index": i + 1,
                            "feature_data": feature,
                            "category": "gear_dimension"
                        })
            
            return critical_dims
        except Exception as e:
            logger.warning(f"Error extracting critical dimensions: {str(e)}")
            return []

    def generate_summary_report(self, extracted_data: Dict, filename: str) -> Dict:
        """Generate a comprehensive summary report."""
        try:
            summary = {
                "filename": filename,
                "drawing_type": self.get_drawing_type_from_data(extracted_data),
                "extraction_timestamp": datetime.now().isoformat(),
                "has_errors": "error" in extracted_data,
                "data_completeness": {}
            }
            
            # Count elements by category
            element_counts = {}
            
            if "dimensions_by_shape" in extracted_data:
                shapes = extracted_data["dimensions_by_shape"]
                element_counts["circular_features"] = len(shapes.get("circular_features", []))
                element_counts["linear_features"] = len(shapes.get("linear_features", []))
                element_counts["angular_features"] = len(shapes.get("angular_features", []))
                element_counts["threaded_features"] = len(shapes.get("threaded_features", []))
                element_counts["gear_features"] = len(shapes.get("gear_features", []))
            
            if "tolerances_and_fits" in extracted_data:
                tol_data = extracted_data["tolerances_and_fits"]
                element_counts["geometric_tolerances"] = len(tol_data.get("geometric_tolerances", []))
                element_counts["dimensional_tolerances"] = len(tol_data.get("dimensional_tolerances", []))
                element_counts["surface_finish"] = len(tol_data.get("surface_finish", []))
            
            if "manufacturing_information" in extracted_data:
                mfg_data = extracted_data["manufacturing_information"]
                element_counts["machining_notes"] = len(mfg_data.get("machining_notes", []))
                element_counts["assembly_notes"] = len(mfg_data.get("assembly_notes", []))
            
            summary["element_counts"] = element_counts
            summary["critical_dimensions"] = self.get_critical_dimensions(extracted_data)
            summary["mass_weight_info"] = extracted_data.get("mass_and_weight_information", {})
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
        """Export data to specific formats with comprehensive information."""
        try:
            if format_type.lower() == "inspection_sheet":
                return self._create_comprehensive_inspection_sheet(extracted_data)
            elif format_type.lower() == "cad_import":
                return self._create_comprehensive_cad_import_format(extracted_data)
            elif format_type.lower() == "manufacturing_sheet":
                return self._create_comprehensive_manufacturing_sheet(extracted_data)
            elif format_type.lower() == "dimension_summary":
                return self._create_dimension_summary_sheet(extracted_data)
            else:
                return "Unsupported format type"
        except Exception as e:
            logger.error(f"Export format error: {str(e)}")
            return f"Export failed: {str(e)}"

    def _create_comprehensive_inspection_sheet(self, data: Dict) -> str:
        """Create comprehensive inspection sheet format."""
        lines = ["=== COMPREHENSIVE INSPECTION SHEET ===\n"]
        
        # Drawing metadata
        if "drawing_metadata" in data:
            meta = data["drawing_metadata"]
            lines.append("=== DRAWING INFORMATION ===")
            for key, value in meta.items():
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        # Mass and weight information
        if "mass_and_weight_information" in data:
            mass_info = data["mass_and_weight_information"]
            lines.append("=== MASS & WEIGHT INFORMATION ===")
            for key, value in mass_info.items():
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        # Overall dimensions
        if "overall_dimensions" in data:
            lines.append("=== OVERALL DIMENSIONS ===")
            for dim_name, dim_value in data["overall_dimensions"].items():
                lines.append(f"• {dim_name.replace('_', ' ').title()}: {dim_value}")
            lines.append("")
        
        # Dimensions by shape
        if "dimensions_by_shape" in data:
            shapes = data["dimensions_by_shape"]
            
            if shapes.get("circular_features"):
                lines.append("=== CIRCULAR FEATURES ===")
                for i, feature in enumerate(shapes["circular_features"], 1):
                    lines.append(f"Feature {i}:")
                    for key, value in feature.items():
                        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
                lines.append("")
            
            if shapes.get("linear_features"):
                lines.append("=== LINEAR FEATURES ===")
                for i, feature in enumerate(shapes["linear_features"], 1):
                    lines.append(f"Feature {i}:")
                    for key, value in feature.items():
                        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
                lines.append("")
            
            if shapes.get("angular_features"):
                lines.append("=== ANGULAR FEATURES ===")
                for i, feature in enumerate(shapes["angular_features"], 1):
                    lines.append(f"Feature {i}:")
                    for key, value in feature.items():
                        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
                lines.append("")
            
            if shapes.get("threaded_features"):
                lines.append("=== THREADED FEATURES ===")
                for i, feature in enumerate(shapes["threaded_features"], 1):
                    lines.append(f"Feature {i}:")
                    for key, value in feature.items():
                        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
                lines.append("")
            
            if shapes.get("gear_features"):
                lines.append("=== GEAR FEATURES ===")
                for i, feature in enumerate(shapes["gear_features"], 1):
                    lines.append(f"Feature {i}:")
                    for key, value in feature.items():
                        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
                lines.append("")
        
        # Tolerances and fits
        if "tolerances_and_fits" in data:
            tol_data = data["tolerances_and_fits"]
            lines.append("=== TOLERANCES & FITS ===")
            for key, value in tol_data.items():
                if isinstance(value, list) and value:
                    lines.append(f"{key.replace('_', ' ').title()}:")
                    for item in value:
                        lines.append(f"  • {item}")
                elif value:
                    lines.append(f"{key.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        return "\n".join(lines)

    def _create_comprehensive_cad_import_format(self, data: Dict) -> str:
        """Create comprehensive CAD import format."""
        lines = ["# Comprehensive CAD Import Data"]
        
        # Overall dimensions
        if "overall_dimensions" in data:
            lines.append("\n## Overall Dimensions")
            for dim_name, dim_value in data["overall_dimensions"].items():
                lines.append(f"{dim_name.upper()},{dim_value}")
        
        # Circular features
        if "dimensions_by_shape" in data and "circular_features" in data["dimensions_by_shape"]:
            lines.append("\n## Circular Features")
            for i, feature in enumerate(data["dimensions_by_shape"]["circular_features"], 1):
                lines.append(f"CIRCULAR_FEATURE_{i}")
                for key, value in feature.items():
                    lines.append(f"{key.upper()},{value}")
        
        # Linear features
        if "dimensions_by_shape" in data and "linear_features" in data["dimensions_by_shape"]:
            lines.append("\n## Linear Features")
            for i, feature in enumerate(data["dimensions_by_shape"]["linear_features"], 1):
                lines.append(f"LINEAR_FEATURE_{i}")
                for key, value in feature.items():
                    lines.append(f"{key.upper()},{value}")
        
        # Mass and weight
        if "mass_and_weight_information" in data:
            lines.append("\n## Mass and Weight")
            for key, value in data["mass_and_weight_information"].items():
                lines.append(f"{key.upper()},{value}")
        
        return "\n".join(lines)

    def _create_comprehensive_manufacturing_sheet(self, data: Dict) -> str:
        """Create comprehensive manufacturing instruction sheet."""
        lines = ["=== COMPREHENSIVE MANUFACTURING INSTRUCTIONS ===\n"]
        
        # Material properties
        if "material_properties" in data:
            mat = data["material_properties"]
            lines.append("=== MATERIAL REQUIREMENTS ===")
            for key, value in mat.items():
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        # Manufacturing information
        if "manufacturing_information" in data:
            mfg_data = data["manufacturing_information"]
            for key, value in mfg_data.items():
                if isinstance(value, list) and value:
                    lines.append(f"=== {key.replace('_', ' ').upper()} ===")
                    for item in value:
                        lines.append(f"• {item}")
                    lines.append("")
                elif value:
                    lines.append(f"=== {key.replace('_', ' ').upper()} ===")
                    lines.append(f"{value}")
                    lines.append("")
        
        # Critical dimensions for manufacturing
        critical_dims = self.get_critical_dimensions(data)
        if critical_dims:
            lines.append("=== CRITICAL DIMENSIONS FOR MANUFACTURING ===")
            for dim in critical_dims:
                lines.append(f"• {dim['type'].title()} - {dim.get('feature', 'Feature')} {dim.get('feature_index', '')}")
                if 'feature_data' in dim:
                    for key, value in dim['feature_data'].items():
                        lines.append(f"  {key}: {value}")
                lines.append("")
        
        return "\n".join(lines)

    def _create_dimension_summary_sheet(self, data: Dict) -> str:
        """Create dimension summary sheet organized by shape."""
        lines = ["=== DIMENSION SUMMARY BY SHAPE ===\n"]
        
        # Overall dimensions
        if "overall_dimensions" in data:
            lines.append("=== OVERALL DIMENSIONS ===")
            for dim_name, dim_value in data["overall_dimensions"].items():
                lines.append(f"{dim_name}: {dim_value}")
            lines.append("")
        
        # Shape-wise dimensions
        if "dimensions_by_shape" in data:
            shapes = data["dimensions_by_shape"]
            
            shape_types = [
                ("circular_features", "CIRCULAR DIMENSIONS"),
                ("linear_features", "LINEAR DIMENSIONS"),
                ("angular_features", "ANGULAR DIMENSIONS"),
                ("threaded_features", "THREADED DIMENSIONS"),
                ("gear_features", "GEAR DIMENSIONS")
            ]
            
            for shape_key, shape_title in shape_types:
                if shape_key in shapes and shapes[shape_key]:
                    lines.append(f"=== {shape_title} ===")
                    for i, feature in enumerate(shapes[shape_key], 1):
                        lines.append(f"Feature {i}:")
                        for key, value in feature.items():
                            lines.append(f"  {key}: {value}")
                        lines.append("")
        
        # Mass and weight summary
        if "mass_and_weight_information" in data:
            lines.append("=== MASS & WEIGHT SUMMARY ===")
            for key, value in data["mass_and_weight_information"].items():
                lines.append(f"{key}: {value}")
            lines.append("")
        
        return "\n".join(lines)

