# import os
# import uuid
# import shutil
# import json
# from datetime import datetime
# from typing import Optional, List
# from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Depends, status, Body
# from fastapi.responses import FileResponse
# from pathlib import Path
# from requests import Session
# from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse
# from app.service.techinalDrawingService2 import TechnicalDrawingExtractionService
# from app.service.volume_calculation_service import extract_dimensions_and_calculate_volumes, calculate_net_volume
# from app.log.logger import get_logger
# from app.database.db import get_db
# from typing import Optional, Tuple

# logger = get_logger(__name__)
 
# # Initialize router
# router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])
 
# # Initialize service (no database required)
# drawing_service = TechnicalDrawingExtractionService()
 
# # Configuration
# UPLOAD_DIR = "uploads/drawings"
# OUTPUT_DIR = "outputs/drawings"
# ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
# MAX_FILE_SIZE = 10 * 1024 * 1024  
# MIN_FILE_SIZE = 1 * 1024 
 
# # Ensure directories exist
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(OUTPUT_DIR, exist_ok=True)
 
 
# def validate_image_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
#     """Validate uploaded image file (only checks filename and extension)"""
#     if not file.filename:
#         return False, "No filename provided"
    
#     file_ext = Path(file.filename).suffix.lower()
#     if file_ext not in ALLOWED_EXTENSIONS:
#         return False, f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
#     return True, None
 
# async def process_drawing_background(task_id: str, file_path: str, output_dir: str, db):
#     """Background task to process technical drawing"""
#     try:
#         result = await drawing_service.process_image_file(task_id, file_path, output_dir, db)
#         logger.info(f"Background processing completed for task: {task_id}")
#         return result
#     except ValueError as e:
#         if "Token limit exceeded" in str(e):
#             drawing_service.update_file_status(task_id, "failed")
#             logger.error(f"Token limit exceeded for task {task_id}: {str(e)}")
#             return {
#                 "status": "failed",
#                 "error": str(e),
#                 "token_limit_exceeded": True
#             }
#         raise
#     except Exception as e:
#         logger.error(f"Background processing failed for task {task_id}: {str(e)}")
#         drawing_service.update_file_status(task_id, "failed")
#         raise


# @router.post("/upload", response_model=DrawingUploadResponse)
# async def upload_technical_drawing(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db)
# ):
#     try:
#         # Validate basic file properties
#         if not file.filename:
#             raise HTTPException(
#                 status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#                 detail="No filename provided"
#             )
        
#         is_valid, error_message = validate_image_file(file)
#         if not is_valid:
#             raise HTTPException(
#                 status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#                 detail=error_message
#             )

#         # Read file content and validate size
#         content = await file.read()
#         file_size = len(content)
        
#         if file_size < MIN_FILE_SIZE:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST, 
#                 detail=f"File too small. Minimum size: {MIN_FILE_SIZE/1024/1024}MB"
#             )
#         if file_size > MAX_FILE_SIZE:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"File too large. Maximum size: {MAX_FILE_SIZE/1024/1024}MB"
#             )

#         # Generate unique task ID
#         task_id = str(uuid.uuid4())
#         file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

#         # Ensure upload directory exists
#         os.makedirs(UPLOAD_DIR, exist_ok=True)

#         # Save file
#         try:
#             with open(file_path, "wb") as f:
#                 f.write(content)
#         except IOError as e:
#             raise HTTPException(
#                 status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
#                 detail=f"Could not save file: {str(e)}"
#             )

#         # Create output directory
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
#         os.makedirs(task_output_dir, exist_ok=True)

#         # Add background task with error handling for token limit
#         try:
#             background_tasks.add_task(
#                 process_drawing_background,
#                 task_id,
#                 file_path,
#                 task_output_dir,
#                 db
#             )
#         except ValueError as e:
#             if "Token limit exceeded" in str(e):
#                 raise HTTPException(
#                     status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
#                     detail=str(e)
#                 )
#             raise

#         logger.info(f"File uploaded: {file.filename}, Size: {file_size} bytes, Task ID: {task_id}")

#         return DrawingUploadResponse(
#             task_id=task_id,
#             filename=file.filename,
#             file_size=file_size,
#             status="processing",
#             message="File uploaded successfully"
#         )

#     except HTTPException as he:
#         # Handle token limit exceeded specifically
#         if he.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
#             logger.error(f"Token limit exceeded for file {file.filename}")
#         raise he
#     except Exception as e:
#         logger.error(f"Upload error: {str(e)}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="File upload failed"
#         )



# @router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
# async def get_processing_status(task_id: str):
#     """
#     Get the processing status of a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         return DrawingProcessingStatus(
#             task_id=file_info["task_id"],
#             filename=file_info["original_filename"],
#             status=file_info["status"],
#             created_at=file_info["created_at"],
#             updated_at=file_info.get("updated_at"),
#             file_size=file_info["file_size"],
#             output_path=file_info.get("output_path")
#         )
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting status for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
 
# @router.get("/result/{task_id}", response_model=DrawingProcessingResult)
# async def get_processing_result(
#     task_id: str,
#     include_data: bool = Query(True, description="Include extracted data in response")
# ):
#     """
#     Get the processing result of a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         if file_info["status"] == "processing":
#             raise HTTPException(
#                 status_code=202,  # Accepted (still processing)
#                 detail="Processing still in progress"
#             )
       
#         if file_info["status"] == "failed":
#             raise HTTPException(
#                 status_code=424,  # Failed Dependency
#                 detail="Processing failed for this file"
#             )
       
#         # Try to read the JSON result file
#         json_path = f"{file_info['output_path']}.json"
#         csv_path = f"{file_info['output_path']}.csv"
       
#         extracted_data = None
#         if include_data:
#             if not os.path.exists(json_path):
#                 raise HTTPException(
#                     status_code=424,  # Failed Dependency
#                     detail="Result data not available"
#                 )
#             try:
#                 import json
#                 with open(json_path, 'r', encoding='utf-8') as f:
#                     result_data = json.load(f)
#                     extracted_data = result_data.get("extracted_data")
#             except json.JSONDecodeError as e:
#                 raise HTTPException(
#                     status_code=422,  # Unprocessable Entity
#                     detail="Result data is corrupted"
#                 )
#             except Exception as e:
#                 logger.warning(f"Could not read result data: {str(e)}")
#                 raise HTTPException(
#                     status_code=422,  # Unprocessable Entity
#                     detail="Could not parse result data"
#                 )
       
#         return DrawingProcessingResult(
#             task_id=task_id,
#             filename=file_info["original_filename"],
#             status=file_info["status"],
#             file_size=file_info["file_size"],
#             has_errors=file_info["status"] == "completed_with_errors",
#             json_path=json_path if os.path.exists(json_path) else None,
#             csv_path=csv_path if os.path.exists(csv_path) else None,
#             extracted_data=extracted_data
#         )
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting result for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Result retrieval failed: {str(e)}")
 
# @router.get("/download/{task_id}/json")
# async def download_json_result(task_id: str):
#     """
#     Download the JSON result file for a processed technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         json_path = f"{file_info['output_path']}.json"
       
#         if not os.path.exists(json_path):
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="JSON result file not found"
#             )
       
#         return FileResponse(
#             json_path,
#             media_type="application/json",
#             filename=f"drawing_analysis_{task_id}.json"
#         )
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error downloading JSON for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
 
# @router.get("/download/{task_id}/csv")
# async def download_csv_result(task_id: str):
#     """
#     Download the CSV result file for a processed technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         csv_path = f"{file_info['output_path']}.csv"
       
#         if not os.path.exists(csv_path):
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="CSV result file not found"
#             )
       
#         return FileResponse(
#             csv_path,
#             media_type="text/csv",
#             filename=f"drawing_analysis_{task_id}.csv"
#         )
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error downloading CSV for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
 
# @router.get("/list", response_model=List[DrawingProcessingStatus])
# async def list_processed_drawings(
#     status: Optional[str] = Query(None, description="Filter by status"),
#     limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
# ):
#     """
#     List all processed technical drawings
#     """
#     try:
#         all_files = drawing_service.get_all_processed_files()
       
#         # Convert to list and filter if needed
#         file_list = []
#         for task_id, file_info in all_files.items():
#             if status is None or file_info["status"] == status:
#                 file_list.append(DrawingProcessingStatus(
#                     task_id=file_info["task_id"],
#                     filename=file_info["original_filename"],
#                     status=file_info["status"],
#                     created_at=file_info["created_at"],
#                     updated_at=file_info.get("updated_at"),
#                     file_size=file_info["file_size"],
#                     output_path=file_info.get("output_path")
#                 ))
       
#         # Sort by creation time (newest first) and limit
#         file_list.sort(key=lambda x: x.created_at, reverse=True)
#         return file_list[:limit]
       
#     except Exception as e:
#         logger.error(f"Error listing drawings: {str(e)}")
#         raise HTTPException(
#             status_code=503,  # Service Unavailable
#             detail="Could not retrieve file list"
#         )

# @router.get("/calculate-volume/{task_id}")
# async def calculate_volume_by_task_id(task_id: str):
#     """
#     Calculate volumes for a drawing by task_id (loads the corresponding JSON file).
#     """
#     try:
#         # Build the path to the JSON file
#         json_path = os.path.join(OUTPUT_DIR, task_id, f"{task_id}.json")
#         if not os.path.exists(json_path):
#             return {"error": f"Result file not found for task_id {task_id}"}
#         with open(json_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         components = extract_dimensions_and_calculate_volumes(data)
#         volume_summary = calculate_net_volume(components)
#         return {
#             "components": components,
#             "volume_summary": volume_summary
#         }
#     except Exception as e:
#         return {"error": str(e)}

# @router.delete("/delete/{task_id}")
# async def delete_processed_drawing(task_id: str):
#     """
#     Delete a processed technical drawing and its files
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         # Delete files
#         files_to_delete = [
#             file_info["file_path"],  # Original uploaded file
#             f"{file_info['output_path']}.json",
#             f"{file_info['output_path']}.csv"
#         ]
       
#         deleted_count = 0
#         for file_path in files_to_delete:
#             try:
#                 if os.path.exists(file_path):
#                     os.remove(file_path)
#                     deleted_count += 1
#                     logger.info(f"Deleted file: {file_path}")
#             except IOError as e:
#                 logger.warning(f"Could not delete file {file_path}: {str(e)}")
       
#         if deleted_count == 0:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="No files found to delete"
#             )
       
#         # Delete output directory if empty
#         output_dir = os.path.dirname(file_info['output_path'])
#         try:
#             if os.path.exists(output_dir) and not os.listdir(output_dir):
#                 os.rmdir(output_dir)
#         except OSError:
#             pass
       
#         # Remove from memory
#         drawing_service.delete_file_info(task_id)
       
#         return {"message": f"Technical drawing {task_id} deleted successfully"}
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting task {task_id}: {str(e)}")
#         raise HTTPException(
#             status_code=500,  # Internal Server Error
#             detail=f"Deletion failed: {str(e)}"
#         )
 
# @router.get("/health")
# async def health_check():
#     """
#     Health check endpoint for the technical drawing service
#     """
#     try:
#         total_files = len(drawing_service.get_all_processed_files())
       
#         # Check if directories are writable
#         try:
#             test_file = os.path.join(UPLOAD_DIR, "healthcheck.tmp")
#             with open(test_file, "w") as f:
#                 f.write("test")
#             os.remove(test_file)
#         except IOError as e:
#             raise HTTPException(
#                 status_code=507,  # Insufficient Storage
#                 detail=f"Storage not writable: {str(e)}"
#             )
       
#         return {
#             "status": "healthy",
#             "service": "Technical Drawing Extraction Service",
#             "timestamp": datetime.now().isoformat(),
#             "total_processed_files": total_files,
#             "upload_directory": UPLOAD_DIR,
#             "output_directory": OUTPUT_DIR,
#             "allowed_extensions": list(ALLOWED_EXTENSIONS),
#             "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024
#         }
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Health check failed: {str(e)}")
#         raise HTTPException(
#             status_code=503,  # Service Unavailable
#             detail="Service is unhealthy"
#         )
 
# @router.post("/batch-upload", response_model=List[DrawingUploadResponse])
# async def batch_upload_drawings(
#     background_tasks: BackgroundTasks,
#     files: List[UploadFile] = File(...)
# ):
#     """
#     Upload multiple technical drawings for batch processing
#     """
#     try:
#         if len(files) > 10:  # Limit batch size
#             raise HTTPException(
#                 status_code=413,  # Payload Too Large
#                 detail="Maximum 10 files allowed in batch upload"
#             )
       
#         responses = []
       
#         for file in files:
#             try:
#                 # Validate each file
#                 if not file.filename:
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename="",
#                         file_size=0,
#                         status="failed",
#                         message="No filename provided"
#                     ))
#                     continue
                   
#                 if not validate_image_file(file):
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=0,
#                         status="failed",
#                         message=f"Invalid file format or size: {file.filename}"
#                     ))
#                     continue
               
#                 # Generate task ID
#                 task_id = str(uuid.uuid4())
               
#                 # Read file content
#                 content = await file.read()
#                 file_size = len(content)
               
#                 if file_size > MAX_FILE_SIZE:
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=file_size,
#                         status="failed",
#                         message=f"File too large: {file.filename}"
#                     ))
#                     continue
               
#                 # Save uploaded file
#                 file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#                 try:
#                     with open(file_path, "wb") as f:
#                         f.write(content)
#                 except IOError as e:
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=file_size,
#                         status="failed",
#                         message=f"Could not save file: {str(e)}"
#                     ))
#                     continue
               
#                 # Create output directory for this task
#                 task_output_dir = os.path.join(OUTPUT_DIR, task_id)
#                 try:
#                     os.makedirs(task_output_dir, exist_ok=True)
#                 except IOError as e:
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=file_size,
#                         status="failed",
#                         message=f"Could not create output directory: {str(e)}"
#                     ))
#                     continue
               
#                 # Add background task for processing
#                 background_tasks.add_task(
#                     process_drawing_background,
#                     task_id,
#                     file_path,
#                     task_output_dir
#                 )
               
#                 responses.append(DrawingUploadResponse(
#                     task_id=task_id,
#                     filename=file.filename,
#                     file_size=file_size,
#                     status="processing",
#                     message="File uploaded successfully and is being processed"
#                 ))
               
#                 # Reset file pointer for next iteration
#                 await file.seek(0)
               
#             except Exception as e:
#                 logger.error(f"Error processing file {file.filename}: {str(e)}")
#                 responses.append(DrawingUploadResponse(
#                     task_id="",
#                     filename=file.filename,
#                     file_size=0,
#                     status="failed",
#                     message=f"Processing error: {str(e)}"
#                 ))
       
#         return responses
       
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error in batch upload: {str(e)}")
#         raise HTTPException(
#             status_code=500,  # Internal Server Error
#             detail=f"Batch upload failed: {str(e)}"
#         )
 
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
#         raise HTTPException(
#             status_code=503,  # Service Unavailable
#             detail="Could not retrieve statistics"
#         )
 
# @router.post("/reprocess/{task_id}")
# async def reprocess_drawing(task_id: str, background_tasks: BackgroundTasks):
#     """
#     Reprocess a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
       
#         if not file_info:
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Task not found"
#             )
       
#         if not os.path.exists(file_info["file_path"]):
#             raise HTTPException(
#                 status_code=404,  # Not Found
#                 detail="Original file not found"
#             )
       
#         # Check if processing is already in progress
#         if file_info["status"] == "processing":
#             raise HTTPException(
#                 status_code=409,  # Conflict
#                 detail="File is already being processed"
#             )
       
#         # Update status to processing
#         drawing_service.update_file_status(task_id, "processing")
       
#         # Create output directory for this task
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
#         try:
#             os.makedirs(task_output_dir, exist_ok=True)
#         except IOError as e:
#             raise HTTPException(
#                 status_code=507,  # Insufficient Storage
#                 detail=f"Could not create output directory: {str(e)}"
#             )
       
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
#         raise HTTPException(
#             status_code=500,  # Internal Server Error
#             detail=f"Reprocessing failed: {str(e)}"
#         )


import os
import uuid
import shutil
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import FileResponse
from pathlib import Path
from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse
from app.service.techinalDrawingService2 import TechnicalDrawingExtractionService
from app.service.volume_calculation_service import extract_dimensions_and_calculate_volumes, calculate_net_volume
from app.log.logger import get_logger
from typing import Optional, Tuple

logger = get_logger(__name__)
 
# Initialize router
router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])
 
# Initialize service (no database required)
drawing_service = TechnicalDrawingExtractionService()
 
# Configuration
UPLOAD_DIR = "uploads/drawings"
OUTPUT_DIR = "outputs/drawings"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  
MIN_FILE_SIZE = 1 * 1024 
 
# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
 
 
def validate_image_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
    """Validate uploaded image file (only checks filename and extension)"""
    if not file.filename:
        return False, "No filename provided"
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    return True, None
 
async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
    """Background task to process technical drawing"""
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


@router.post("/upload", response_model=DrawingUploadResponse)
async def upload_technical_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    try:
        # Validate basic file properties
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No filename provided"
            )
        
        is_valid, error_message = validate_image_file(file)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=error_message
            )

        # Read file content and validate size
        content = await file.read()
        file_size = len(content)
        
        if file_size < MIN_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"File too small. Minimum size: {MIN_FILE_SIZE/1024/1024}MB"
            )
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE/1024/1024}MB"
            )

        # Generate unique task ID
        task_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except IOError as e:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=f"Could not save file: {str(e)}"
            )

        # Create output directory
        task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        os.makedirs(task_output_dir, exist_ok=True)

        # Add background task with error handling for token limit
        try:
            background_tasks.add_task(
                process_drawing_background,
                task_id,
                file_path,
                task_output_dir
            )
        except ValueError as e:
            if "Token limit exceeded" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=str(e)
                )
            raise

        logger.info(f"File uploaded: {file.filename}, Size: {file_size} bytes, Task ID: {task_id}")

        return DrawingUploadResponse(
            task_id=task_id,
            filename=file.filename,
            file_size=file_size,
            status="processing",
            message="File uploaded successfully"
        )

    except HTTPException as he:
        # Handle token limit exceeded specifically
        if he.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            logger.error(f"Token limit exceeded for file {file.filename}")
        raise he
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )



@router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
async def get_processing_status(task_id: str):
    """
    Get the processing status of a technical drawing
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
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
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
        if file_info["status"] == "processing":
            raise HTTPException(
                status_code=202,  # Accepted (still processing)
                detail="Processing still in progress"
            )
       
        if file_info["status"] == "failed":
            raise HTTPException(
                status_code=424,  # Failed Dependency
                detail="Processing failed for this file"
            )
       
        # Try to read the JSON result file
        json_path = f"{file_info['output_path']}.json"
        csv_path = f"{file_info['output_path']}.csv"
       
        extracted_data = None
        if include_data:
            if not os.path.exists(json_path):
                raise HTTPException(
                    status_code=424,  # Failed Dependency
                    detail="Result data not available"
                )
            try:
                import json
                with open(json_path, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                    extracted_data = result_data.get("extracted_data")
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=422,  # Unprocessable Entity
                    detail="Result data is corrupted"
                )
            except Exception as e:
                logger.warning(f"Could not read result data: {str(e)}")
                raise HTTPException(
                    status_code=422,  # Unprocessable Entity
                    detail="Could not parse result data"
                )
       
        return DrawingProcessingResult(
            task_id=task_id,
            filename=file_info["original_filename"],
            status=file_info["status"],
            file_size=file_info["file_size"],
            has_errors=file_info["status"] == "completed_with_errors",
            json_path=json_path if os.path.exists(json_path) else None,
            csv_path=csv_path if os.path.exists(csv_path) else None,
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
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
        json_path = f"{file_info['output_path']}.json"
       
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,  # Not Found
                detail="JSON result file not found"
            )
       
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
 
@router.get("/download/{task_id}/csv")
async def download_csv_result(task_id: str):
    """
    Download the CSV result file for a processed technical drawing
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
        csv_path = f"{file_info['output_path']}.csv"
       
        if not os.path.exists(csv_path):
            raise HTTPException(
                status_code=404,  # Not Found
                detail="CSV result file not found"
            )
       
        return FileResponse(
            csv_path,
            media_type="text/csv",
            filename=f"drawing_analysis_{task_id}.csv"
        )
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading CSV for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
 
@router.get("/list", response_model=List[DrawingProcessingStatus])
async def list_processed_drawings(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
):
    """
    List all processed technical drawings
    """
    try:
        all_files = drawing_service.get_all_processed_files()
       
        # Convert to list and filter if needed
        file_list = []
        for task_id, file_info in all_files.items():
            if status is None or file_info["status"] == status:
                file_list.append(DrawingProcessingStatus(
                    task_id=file_info["task_id"],
                    filename=file_info["original_filename"],
                    status=file_info["status"],
                    created_at=file_info["created_at"],
                    updated_at=file_info.get("updated_at"),
                    file_size=file_info["file_size"],
                    output_path=file_info.get("output_path")
                ))
       
        # Sort by creation time (newest first) and limit
        file_list.sort(key=lambda x: x.created_at, reverse=True)
        return file_list[:limit]
       
    except Exception as e:
        logger.error(f"Error listing drawings: {str(e)}")
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail="Could not retrieve file list"
        )

@router.get("/calculate-volume/{task_id}")
async def calculate_volume_by_task_id(task_id: str):
    """
    Calculate volumes for a drawing by task_id (loads the corresponding JSON file).
    """
    try:
        # Build the path to the JSON file
        json_path = os.path.join(OUTPUT_DIR, task_id, f"{task_id}.json")
        if not os.path.exists(json_path):
            return {"error": f"Result file not found for task_id {task_id}"}
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        components = extract_dimensions_and_calculate_volumes(data)
        volume_summary = calculate_net_volume(components)
        return {
            "components": components,
            "volume_summary": volume_summary
        }
    except Exception as e:
        return {"error": str(e)}

@router.delete("/delete/{task_id}")
async def delete_processed_drawing(task_id: str):
    """
    Delete a processed technical drawing and its files
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
        # Delete files
        files_to_delete = [
            file_info["file_path"],  # Original uploaded file
            f"{file_info['output_path']}.json",
            f"{file_info['output_path']}.csv"
        ]
       
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted file: {file_path}")
            except IOError as e:
                logger.warning(f"Could not delete file {file_path}: {str(e)}")
       
        if deleted_count == 0:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="No files found to delete"
            )
       
        # Delete output directory if empty
        output_dir = os.path.dirname(file_info['output_path'])
        try:
            if os.path.exists(output_dir) and not os.listdir(output_dir):
                os.rmdir(output_dir)
        except OSError:
            pass
       
        # Remove from memory
        drawing_service.delete_file_info(task_id)
       
        return {"message": f"Technical drawing {task_id} deleted successfully"}
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,  # Internal Server Error
            detail=f"Deletion failed: {str(e)}"
        )
 
@router.get("/health")
async def health_check():
    """
    Health check endpoint for the technical drawing service
    """
    try:
        total_files = len(drawing_service.get_all_processed_files())
       
        # Check if directories are writable
        try:
            test_file = os.path.join(UPLOAD_DIR, "healthcheck.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except IOError as e:
            raise HTTPException(
                status_code=507,  # Insufficient Storage
                detail=f"Storage not writable: {str(e)}"
            )
       
        return {
            "status": "healthy",
            "service": "Technical Drawing Extraction Service",
            "timestamp": datetime.now().isoformat(),
            "total_processed_files": total_files,
            "upload_directory": UPLOAD_DIR,
            "output_directory": OUTPUT_DIR,
            "allowed_extensions": list(ALLOWED_EXTENSIONS),
            "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024
        }
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail="Service is unhealthy"
        )
 
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
                status_code=413,  # Payload Too Large
                detail="Maximum 10 files allowed in batch upload"
            )
       
        responses = []
       
        for file in files:
            try:
                # Validate each file
                if not file.filename:
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename="",
                        file_size=0,
                        status="failed",
                        message="No filename provided"
                    ))
                    continue
                   
                is_valid, error_message = validate_image_file(file)
                if not is_valid:
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=0,
                        status="failed",
                        message=error_message
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
                try:
                    with open(file_path, "wb") as f:
                        f.write(content)
                except IOError as e:
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=file_size,
                        status="failed",
                        message=f"Could not save file: {str(e)}"
                    ))
                    continue
               
                # Create output directory for this task
                task_output_dir = os.path.join(OUTPUT_DIR, task_id)
                try:
                    os.makedirs(task_output_dir, exist_ok=True)
                except IOError as e:
                    responses.append(DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=file_size,
                        status="failed",
                        message=f"Could not create output directory: {str(e)}"
                    ))
                    continue
               
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
                    filename=file.filename if hasattr(file, 'filename') else "",
                    file_size=0,
                    status="failed",
                    message=f"Processing error: {str(e)}"
                ))
       
        return responses
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch upload: {str(e)}")
        raise HTTPException(
            status_code=500,  # Internal Server Error
            detail=f"Batch upload failed: {str(e)}"
        )
 
@router.get("/stats")
async def get_processing_stats():
    """
    Get processing statistics
    """
    try:
        all_files = drawing_service.get_all_processed_files()
       
        stats = {
            "total_files": len(all_files),
            "completed": 0,
            "processing": 0,
            "failed": 0,
            "completed_with_errors": 0,
            "total_size_mb": 0
        }
       
        for file_info in all_files.values():
            status = file_info["status"]
            if status == "completed":
                stats["completed"] += 1
            elif status == "processing":
                stats["processing"] += 1
            elif status == "failed":
                stats["failed"] += 1
            elif status == "completed_with_errors":
                stats["completed_with_errors"] += 1
           
            stats["total_size_mb"] += file_info["file_size"] / 1024 / 1024
       
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
       
        return stats
       
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail="Could not retrieve statistics"
        )
 
@router.post("/reprocess/{task_id}")
async def reprocess_drawing(task_id: str, background_tasks: BackgroundTasks):
    """
    Reprocess a technical drawing
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Task not found"
            )
       
        if not os.path.exists(file_info["file_path"]):
            raise HTTPException(
                status_code=404,  # Not Found
                detail="Original file not found"
            )
       
        # Check if processing is already in progress
        if file_info["status"] == "processing":
            raise HTTPException(
                status_code=409,  # Conflict
                detail="File is already being processed"
            )
       
        # Update status to processing
        drawing_service.update_file_status(task_id, "processing")
       
        # Create output directory for this task
        task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        try:
            os.makedirs(task_output_dir, exist_ok=True)
        except IOError as e:
            raise HTTPException(
                status_code=507,  # Insufficient Storage
                detail=f"Could not create output directory: {str(e)}"
            )
       
        # Add background task for reprocessing
        background_tasks.add_task(
            process_drawing_background,
            task_id,
            file_info["file_path"],
            task_output_dir
        )
       
        return {
            "message": f"Reprocessing started for task {task_id}",
            "task_id": task_id,
            "status": "processing"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,  # Internal Server Error
            detail=f"Reprocessing failed: {str(e)}"
        )