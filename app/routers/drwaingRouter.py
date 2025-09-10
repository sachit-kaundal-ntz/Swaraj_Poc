import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse, ErrorResponse
from app.service.techinalDrawingService import TechnicalDrawingExtractionService
from app.log.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

drawing_service = TechnicalDrawingExtractionService()

UPLOAD_DIR = "uploads/drawings"
OUTPUT_DIR = "outputs/drawings"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def validate_image_file(file: UploadFile) -> bool:
    """Validate uploaded image file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False
    
    if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
        return False
    
    return True

async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
    """Background task to process technical drawing"""
    try:
        result = await drawing_service.process_image_file(task_id, file_path, output_dir)
        logger.info(f"Background processing completed for task: {task_id}")
        return result
    except Exception as e:
        logger.error(f"Background processing failed for task {task_id}: {str(e)}")
        drawing_service.update_file_status(task_id, "failed")

@router.post("/upload", response_model=DrawingUploadResponse)
async def upload_technical_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a technical drawing/engineering diagram for processing
    """
    try:
        # Validate file
        if not validate_image_file(file):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. Max size: {MAX_FILE_SIZE/1024/1024}MB"
            )
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE/1024/1024}MB"
            )
        
        # Save uploaded file
        file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create output directory for this task
        task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        
        # Add background task for processing
        background_tasks.add_task(
            process_drawing_background,
            task_id,
            file_path,
            task_output_dir
        )
        
        logger.info(f"Technical drawing uploaded successfully: {file.filename}, Task ID: {task_id}")
        
        return DrawingUploadResponse(
            task_id=task_id,
            filename=file.filename,
            file_size=file_size,
            status="processing",
            message="Technical drawing uploaded successfully and is being processed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading technical drawing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
async def get_processing_status(task_id: str):
    """
    Get the processing status of a technical drawing
    """
    try:
        file_info = await drawing_service.get_file_info(task_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return DrawingProcessingStatus(
            task_id=file_info["task_id"],
            filename=file_info["original_filename"],
            status=file_info["status"],
            created_at=file_info["created_at"],
            updated_at=file_info.get("updated_at"),
            file_size=file_info["file_size"],
            output_path=file_info.get("output_path")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.get("/result/{task_id}", response_model=DrawingProcessingResult)
async def get_processing_result(
    task_id: str,
    include_data: bool = Query(True, description="Include extracted data in response")
):
    """
    Get the processing result of a technical drawing
    """
    try:
        file_info = await drawing_service.get_file_info(task_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if file_info["status"] == "processing":
            raise HTTPException(status_code=202, detail="Processing still in progress")
        
        # Try to read the JSON result file
        json_path = f"{file_info['output_path']}.json"
        csv_path = f"{file_info['output_path']}.csv"
        
        extracted_data = None
        if include_data and os.path.exists(json_path):
            try:
                import json
                with open(json_path, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                    extracted_data = result_data.get("extracted_data")
            except Exception as e:
                logger.warning(f"Could not read result data: {str(e)}")
        
        return DrawingProcessingResult(
            task_id=task_id,
            filename=file_info["original_filename"],
            status=file_info["status"],
            file_size=file_info["file_size"],
            has_errors=file_info["status"] == "completed_with_errors",
            json_path=json_path if  os.path.exists(json_path) else None,
            extracted_data=extracted_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting result for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Result retrieval failed: {str(e)}")

@router.get("/download/{task_id}/json")
async def download_json_result(task_id: str):
    """
    Download the JSON result file for a processed technical drawing
    """
    try:
        file_info = await  drawing_service.get_file_info(task_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        json_path = f"{file_info['output_path']}.json"
        
        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail="JSON result file not found")
        
        return FileResponse(
            json_path,
            media_type="application/json",
            filename=f"drawing_analysis_{task_id}.json"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading JSON for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.delete("/delete/{task_id}")
async def delete_processed_drawing(task_id: str):
    """
    Delete a processed technical drawing and its files
    """
    try:
        file_info = await drawing_service.get_file_info(task_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Delete files
        files_to_delete = [
            file_info["file_path"],  # Original uploaded file
            f"{file_info['output_path']}.json",
            f"{file_info['output_path']}.csv"
        ]
        
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        
        # Delete output directory if empty
        output_dir = os.path.dirname(file_info['output_path'])
        try:
            if os.path.exists(output_dir) and not os.listdir(output_dir):
                os.rmdir(output_dir)
        except OSError:
            pass  # Directory not empty or other issue, ignore
        
        # Remove from memory
        drawing_service.delete_file_info(task_id)
        
        return {"message": f"Technical drawing {task_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.post("/batch-upload", response_model=List[DrawingUploadResponse])
async def batch_upload_drawings(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """
    Upload multiple technical drawings for batch processing
    """
    try:
        if len(files) > 10:  # Limit batch size
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed in batch upload"
            )
        
        responses = []
        
        for file in files:
            try:
                # Validate each file
                if not validate_image_file(file):
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=0,
                        status="failed",
                        message=f"Invalid file format or size: {file.filename}"
                    ))
                    continue
                
                # Generate task ID
                task_id = str(uuid.uuid4())
                
                # Read file content
                content = await file.read()
                file_size = len(content)
                
                if file_size > MAX_FILE_SIZE:
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=file_size,
                        status="failed",
                        message=f"File too large: {file.filename}"
                    ))
                    continue
                
                # Save uploaded file
                file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # Create output directory for this task
                task_output_dir = os.path.join(OUTPUT_DIR, task_id)
                
                # Add background task for processing
                background_tasks.add_task(
                    process_drawing_background,
                    task_id,
                    file_path,
                    task_output_dir
                )
                
                responses.append(DrawingUploadResponse(
                    task_id=task_id,
                    filename=file.filename,
                    file_size=file_size,
                    status="processing",
                    message="File uploaded successfully and is being processed"
                ))
                
                # Reset file pointer for next iteration
                await file.seek(0)
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                responses.append(DrawingUploadResponse(
                    task_id="",
                    filename=file.filename,
                    file_size=0,
                    status="failed",
                    message=f"Processing error: {str(e)}"
                ))
        
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")

# @router.get("/stats")
# async def get_processing_stats():
#     """
#     Get processing statistics
#     """
#     try:
#         all_files = drawing_service.get_all_processed_files()
        
#         stats = {
#             "total_files": len(all_files),
#             "completed": 0,
#             "processing": 0,
#             "failed": 0,
#             "completed_with_errors": 0,
#             "total_size_mb": 0
#         }
        
#         for file_info in all_files.values():
#             status = file_info["status"]
#             if status == "completed":
#                 stats["completed"] += 1
#             elif status == "processing":
#                 stats["processing"] += 1
#             elif status == "failed":
#                 stats["failed"] += 1
#             elif status == "completed_with_errors":
#                 stats["completed_with_errors"] += 1
            
#             stats["total_size_mb"] += file_info["file_size"] / 1024 / 1024
        
#         stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        
#         return stats
        
#     except Exception as e:
#         logger.error(f"Error getting stats: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

# @router.post("/reprocess/{task_id}")
# async def reprocess_drawing(task_id: str, background_tasks: BackgroundTasks):
#     """
#     Reprocess a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
        
#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         if not os.path.exists(file_info["file_path"]):
#             raise HTTPException(status_code=404, detail="Original file not found")
        
#         # Update status to processing
#         drawing_service.update_file_status(task_id, "processing")
        
#         # Create output directory for this task
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        
#         # Add background task for reprocessing
#         background_tasks.add_task(
#             process_drawing_background,
#             task_id,
#             file_info["file_path"],
#             task_output_dir
#         )
        
#         return {
#             "message": f"Reprocessing started for task {task_id}",
#             "task_id": task_id,
#             "status": "processing"
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error reprocessing task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")


