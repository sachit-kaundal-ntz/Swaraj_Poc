  
import os
import uuid
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional, Any
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select  
from app.log.logger import get_logger
from app.models.drawingModel import DrawingProcessingResult
from app.prompt.drawingPrompt import DRAWINGPROMPT

logger = get_logger(__name__)
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

class TechnicalDrawingExtractionService:
    def __init__(self, db_session: AsyncSession = None):
        self.db_session = db_session
        self.processed_files = {}  
        self.extraction_prompt = DRAWINGPROMPT
    
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
   
            PROMPT = self.extraction_prompt
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

    async def save_to_database(self, task_id: str, filename: str, file_path: str, extracted_data: Dict, status: str, file_size: int = 0) -> Optional[DrawingProcessingResult]:
        """Save extraction results to database"""
        try:
            if not self.db_session:
                logger.warning("No database session provided, skipping database save")
                return None
                
            # Check if record already exists
            result = await self.db_session.execute(
                select(DrawingProcessingResult).where(DrawingProcessingResult.task_id == task_id)
            )
            existing_record = result.scalar_one_or_none()
            
            if existing_record:
                # Update existing record
                existing_record.status = status
                existing_record.extracted_data = extracted_data
                existing_record.updated_at = datetime.now()
                existing_record.has_errors = "error" in extracted_data
                record = existing_record
            else:
                # Create new record
                record = DrawingProcessingResult(
                    task_id=task_id,
                    filename=filename,
                    status=status,
                    file_size=file_size,
                    has_errors="error" in extracted_data,
                    extracted_data=extracted_data,
                    json_path=f"{file_path}.json"
                )
                self.db_session.add(record)
            
            await self.db_session.flush()
            await self.db_session.commit()
            
            logger.info(f"Successfully saved extraction results to database for task: {task_id}")
            return record
            
        except Exception as e:
            logger.error(f"Database save error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if self.db_session:
                await self.db_session.rollback()
            return None

    async def process_image_file(
        self,        
        task_id: str,
        file_path: str,
        output_dir: str = None
    ) -> Dict:
        """Process image file using Gemini extraction and save to database"""
        try:
            logger.info(f"Starting image processing for task: {task_id}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")
                
            file_size = os.path.getsize(file_path)
            logger.info(f"File size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError("Image file is empty")
            
            filename = os.path.basename(file_path)
            
            # Store file info for backward compatibility
            file_info = {
                "task_id": task_id,
                "original_filename": filename,
                "stored_filename": f"{task_id}_{filename}",
                "file_path": file_path,
                "output_path": output_dir or f"output_{task_id}",
                "status": "processing",
                "file_size": file_size,
                "created_at": datetime.now().isoformat()
            }
            
            self.processed_files[task_id] = file_info
            
            # Extract technical drawing data using Gemini
            extracted_data = await self.extract_technical_drawing_data(file_path)
            
            # Determine status
            status = "completed" if "error" not in extracted_data else "completed_with_errors"
            self.processed_files[task_id]["status"] = status
            
            # Save to database if session is available
            db_record = None
            if self.db_session:
                db_record = await self.save_to_database(
                    task_id=task_id,
                    filename=filename,
                    file_path=file_path,
                    extracted_data=extracted_data,
                    status=status,
                    file_size=file_size
                )
            
            # Prepare JSON response
            json_response = {
                "task_id": task_id,
                "filename": filename,
                "file_size": file_size,
                "extracted_data": extracted_data,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "token_usage": extracted_data.get("token_usage", {}),
                "database_saved": db_record is not None
            }
            
            # If database save was successful, include database info
            if db_record:
                json_response["database_info"] = {
                    "record_id": db_record.id,
                    "task_id": db_record.task_id,
                    "status": db_record.status
                }
            
            # Save JSON file if output_dir is provided (optional)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                json_file_path = os.path.join(output_dir, f"{task_id}.json")
                with open(json_file_path, "w", encoding='utf-8') as f:
                    json.dump(json_response, f, indent=2, ensure_ascii=False)
                logger.info(f"JSON output saved to: {json_file_path}")
                json_response["json_file_path"] = json_file_path
            
            return json_response
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            error_response = {
                "task_id": task_id,
                "status": "failed",
                "error": f"File not found: {str(e)}",
                "error_type": "file_not_found",
                "timestamp": datetime.now().isoformat()
            }
            
            # Try to save error to database
            if self.db_session:
                try:
                    await self.save_to_database(
                        task_id=task_id,
                        filename=os.path.basename(file_path) if file_path else "unknown",
                        file_path=file_path or "",
                        extracted_data={"error": str(e)},
                        status="failed"
                    )
                    error_response["database_saved"] = True
                except:
                    error_response["database_saved"] = False
                    
            return error_response
            
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            error_response = {
                "task_id": task_id,
                "status": "failed",
                "error": f"Invalid file or data: {str(e)}",
                "error_type": "invalid_data",
                "timestamp": datetime.now().isoformat()
            }
            
            if self.db_session:
                try:
                    await self.save_to_database(
                        task_id=task_id,
                        filename=os.path.basename(file_path) if file_path else "unknown",
                        file_path=file_path or "",
                        extracted_data={"error": str(e)},
                        status="failed"
                    )
                    error_response["database_saved"] = True
                except:
                    error_response["database_saved"] = False
                    
            return error_response
            
        except Exception as e:
            logger.error(f"Unexpected error in image processing: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_response = {
                "task_id": task_id,
                "status": "failed",
                "error": f"Processing error: {str(e)}",
                "error_type": "processing_error",
                "timestamp": datetime.now().isoformat()
            }
            
            if self.db_session:
                try:
                    await self.save_to_database(
                        task_id=task_id,
                        filename=os.path.basename(file_path) if file_path else "unknown",
                        file_path=file_path or "",
                        extracted_data={"error": str(e)},
                        status="failed"
                    )
                    error_response["database_saved"] = True
                except:
                    error_response["database_saved"] = False
                    
            return error_response

    async def get_file_info(self, task_id: str) -> Optional[Dict]:
        """Retrieve file information by task ID - first check database, then memory"""
        try:
            # Try database first if session is available
            if self.db_session:
                result = await self.db_session.execute(
                    select(DrawingProcessingResult).where(DrawingProcessingResult.task_id == task_id)
                )
                record = result.scalar_one_or_none()
                
                if record:
                    return {
                        "task_id": record.task_id,
                        "original_filename": record.filename,
                        "stored_filename": record.filename,
                        "file_path": "",
                        "output_path": record.json_path,
                        "status": record.status,
                        "file_size": record.file_size,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                        "extracted_data": record.extracted_data,
                        "database_record": True
                    }
            
            # Fallback to memory storage
            file_info = self.processed_files.get(task_id)
            if file_info:
                file_info["database_record"] = False
            return file_info
            
        except Exception as e:
            logger.error(f"Error retrieving file info: {str(e)}")
            # Fallback to memory storage
            file_info = self.processed_files.get(task_id)
            if file_info:
                file_info["database_record"] = False
            return file_info

    async def get_all_processed_files(self) -> Dict:
        """Get all processed files from database and memory"""
        all_files = {}
        
        try:
            # Get files from database if session is available
            if self.db_session:
                result = await self.db_session.execute(select(DrawingProcessingResult))
                records = result.scalars().all()
                
                for record in records:
                    task_id = record.task_id
                    all_files[task_id] = {
                        "task_id": record.task_id,
                        "original_filename": record.filename,
                        "stored_filename": record.filename,
                        "file_path": "",
                        "output_path": record.json_path,
                        "status": record.status,
                        "file_size": record.file_size,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                        "extracted_data": record.extracted_data,
                        "database_record": True
                    }
        except Exception as e:
            logger.error(f"Error retrieving files from database: {str(e)}")
        
        # Add files from memory that aren't in database
        for task_id, file_info in self.processed_files.items():
            if task_id not in all_files:
                file_info_copy = file_info.copy()
                file_info_copy["database_record"] = False
                all_files[task_id] = file_info_copy
        
        return all_files

    async def update_file_status(self, task_id: str, status: str) -> Optional[Dict]:
        """Update file status in database and memory"""
        try:
            updated_info = None
            
            # Update in database if session is available
            if self.db_session:
                result = await self.db_session.execute(
                    select(DrawingProcessingResult).where(DrawingProcessingResult.task_id == task_id)
                )
                record = result.scalar_one_or_none()
                
                if record:
                    record.status = status
                    record.updated_at = datetime.now()
                    await self.db_session.flush()
                    await self.db_session.commit()
                    
                    updated_info = {
                        "task_id": record.task_id,
                        "original_filename": record.filename,
                        "status": record.status,
                        "updated_at": record.updated_at.isoformat(),
                        "database_record": True
                    }
            
            # Update in memory
            if task_id in self.processed_files:
                self.processed_files[task_id]["status"] = status
                self.processed_files[task_id]["updated_at"] = datetime.now().isoformat()
                
                if not updated_info:  # If not updated in database, return memory version
                    updated_info = self.processed_files[task_id].copy()
                    updated_info["database_record"] = False
            
            return updated_info
            
        except Exception as e:
            logger.error(f"Error updating file status: {str(e)}")
            # Fallback to memory update
            if task_id in self.processed_files:
                self.processed_files[task_id]["status"] = status
                self.processed_files[task_id]["updated_at"] = datetime.now().isoformat()
                updated_info = self.processed_files[task_id].copy()
                updated_info["database_record"] = False
                return updated_info
            return None

    async def delete_file_info(self, task_id: str) -> bool:
        """Delete file information from database and memory"""
        try:
            deleted = False
            
            # Delete from database if session is available
            if self.db_session:
                result = await self.db_session.execute(
                    select(DrawingProcessingResult).where(DrawingProcessingResult.task_id == task_id)
                )
                record = result.scalar_one_or_none()
                
                if record:
                    await self.db_session.delete(record)
                    await self.db_session.flush()
                    await self.db_session.commit()
                    deleted = True
                    logger.info(f"Deleted record from database: {task_id}")
                        # Delete from memory
            if task_id in self.processed_files:
                del self.processed_files[task_id]
                deleted = True
                logger.info(f"Deleted document from memory: {task_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting file info: {str(e)}")
            if self.db_session:
                await self.db_session.rollback()
            
            # Fallback to memory deletion
            if task_id in self.processed_files:
                del self.processed_files[task_id]
                return True
            return False

    def get_drawing_type_from_data(self, extracted_data: Dict) -> str:
        """Determine drawing type from extracted data"""
        try:
            if "metadata" in extracted_data and "title_block" in extracted_data["metadata"]:
                title_block = extracted_data["metadata"]["title_block"]
                part_name = title_block.get("part_name", "")
                drawing_no = title_block.get("drawing_no", "")
                
                if part_name and "gear" in part_name.lower():
                    return "gear_drawing"
                elif drawing_no and any(keyword in drawing_no.lower() for keyword in ["gear", "cog", "pinion"]):
                    return "gear_drawing"
            
            # Check features for gear-related components
            if "features" in extracted_data:
                feature_types = [f.get("type", "") for f in extracted_data["features"] if isinstance(f, dict)]
                if any("gear" in ft or "rim" in ft or "spline" in ft for ft in feature_types):
                    return "gear_drawing"
            
            return "technical_drawing"
        except:
            return "unknown"
    
    def get_critical_dimensions(self, extracted_data: Dict) -> List[Dict]:
        """Extract only critical dimensions for quick reference"""
        critical_dims = []
        
        try:
            if "dimensions" in extracted_data:
                for dimension in extracted_data["dimensions"]:
                    if isinstance(dimension, dict) and dimension.get("value") is not None:
                        critical_dims.append({
                            "type": "dimension",
                            "feature": dimension.get("id", "unknown"),
                            "value": dimension.get("value"),
                            "unit": dimension.get("unit", ""),
                            "tolerance": dimension.get("tolerance", ""), 
                            "symbol": dimension.get("symbol", "")
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
            
            # Count different types of elements
            element_counts = {}
            if "dimensions" in extracted_data:
                element_counts["dimensions"] = len(extracted_data["dimensions"]) if isinstance(extracted_data["dimensions"], list) else 0
            
            if "features" in extracted_data:
                element_counts["features"] = len(extracted_data["features"]) if isinstance(extracted_data["features"], list) else 0
            
            if "tables" in extracted_data:
                element_counts["tables"] = len(extracted_data["tables"]) if isinstance(extracted_data["tables"], list) else 0
            
            if "views" in extracted_data:
                element_counts["views"] = len(extracted_data["views"]) if isinstance(extracted_data["views"], list) else 0
            
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
        
        if "metadata" in data and "title_block" in data["metadata"]:
            meta = data["metadata"]["title_block"]
            lines.append(f"Part Name: {meta.get('part_name', 'N/A')}")
            lines.append(f"Drawing Number: {meta.get('drawing_no', 'N/A')}")
            lines.append(f"Material: {meta.get('material', 'N/A')}")
            lines.append(f"Scale: {meta.get('scale', 'N/A')}\n")
        
        critical_dims = self.get_critical_dimensions(data)
        if critical_dims:
            lines.append("=== CRITICAL DIMENSIONS FOR INSPECTION ===")
            for dim in critical_dims:
                tolerance_str = f" {dim['tolerance']}" if dim.get('tolerance') else ""
                symbol_str = f"{dim['symbol']}" if dim.get('symbol') else ""
                lines.append(f"• {dim['feature']}: {symbol_str}{dim['value']} {dim['unit']}{tolerance_str}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _create_cad_import_format(self, data: Dict) -> str:
        """Create CAD import compatible format"""
        lines = ["# CAD Import Data"]
        
        if "dimensions" in data:
            lines.append("## Dimensions")
            for dimension in data["dimensions"]:
                if isinstance(dimension, dict) and dimension.get("value") is not None:
                    dim_id = dimension.get("id", "unknown")
                    value = dimension.get("value")
                    unit = dimension.get("unit", "mm")
                    lines.append(f"{dim_id.upper()},{value},{unit}")
        
        return "\n".join(lines)
    
    def _create_manufacturing_sheet_format(self, data: Dict) -> str:
        """Create manufacturing instruction sheet"""
        lines = ["=== MANUFACTURING INSTRUCTIONS ===\n"]
        
        if "metadata" in data and "title_block" in data["metadata"]:
            meta = data["metadata"]["title_block"]
            lines.append("=== MATERIAL REQUIREMENTS ===")
            lines.append(f"Base Material: {meta.get('material', 'N/A')}")
            lines.append("")
        
        # Add feature-based manufacturing notes
        if "features" in data:
            lines.append("=== MANUFACTURING FEATURES ===")
            for feature in data["features"]:
                if isinstance(feature, dict):
                    feature_type = feature.get("type", "Unknown")
                    feature_role = feature.get("role", "N/A")
                    lines.append(f"• {feature_type}: {feature_role}")
            lines.append("")
        
        return "\n".join(lines)