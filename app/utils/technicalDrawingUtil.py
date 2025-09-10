import os
from fastapi import UploadFile
from typing import Optional, Tuple
from app.service.techinalDrawingService2 import TechnicalDrawingExtractionService
from app.log.logger import get_logger
from pathlib import Path

# Configuration
UPLOAD_DIR = "uploads/drawings"
OUTPUT_DIR = "outputs/drawings"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  
MIN_FILE_SIZE = 1 * 1024 
 
# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger = get_logger(__name__)

drawing_service = TechnicalDrawingExtractionService()

def validate_image_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
    """Validate uploaded image file (only checks filename and extension)"""
    if not file.filename:
        return False, "No filename provided"
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    return True, None
 
async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
    """Background task to process technical drawing (db removed)"""
    try:
        result = await drawing_service.process_image_file(task_id, file_path, output_dir)
        logger.info(f"Background processing completed for task: {task_id}")
        return result
    except ValueError as e:
        if "Token limit exceeded" in str(e):
            drawing_service.update_file_status(task_id, "failed")
            logger.error(f"Token limit exceeded for task {task_id}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "token_limit_exceeded": True
            }
        raise
    except Exception as e:
        logger.error(f"Background processing failed for task {task_id}: {str(e)}")
        drawing_service.update_file_status(task_id, "failed")
        raise

