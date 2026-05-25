# import os
# import uuid
# import shutil
# from datetime import datetime
# from typing import Optional, List
# from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
# from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel
# from pathlib import Path
# from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse, ErrorResponse
# from app.service.techinalDrawingService import TechnicalDrawingExtractionService
# from app.log.logger import get_logger

# logger = get_logger(__name__)

# # Initialize router
# router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

# # Initialize service (no database required)
# drawing_service = TechnicalDrawingExtractionService()

# # Configuration
# UPLOAD_DIR = "uploads/drawings"
# OUTPUT_DIR = "outputs/drawings"
# ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# # Ensure directories exist
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(OUTPUT_DIR, exist_ok=True)


# def validate_image_file(file: UploadFile) -> bool:
#     """Validate uploaded image file"""
#     # Check file extension
#     file_ext = Path(file.filename).suffix.lower()
#     if file_ext not in ALLOWED_EXTENSIONS:
#         return False
    
#     # Check file size (this is approximate since we haven't read the file yet)
#     if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
#         return False
    
#     return True

# async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
#     """Background task to process technical drawing"""
#     try:
#         result = await drawing_service.process_image_file(task_id, file_path, output_dir)
#         logger.info(f"Background processing completed for task: {task_id}")
#         return result
#     except Exception as e:
#         logger.error(f"Background processing failed for task {task_id}: {str(e)}")
#         drawing_service.update_file_status(task_id, "failed")

# @router.post("/upload", response_model=DrawingUploadResponse)
# async def upload_technical_drawing(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...)
# ):
#     """
#     Upload a technical drawing/engineering diagram for processing
#     """
#     try:
#         # Validate file
#         if not validate_image_file(file):
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. Max size: {MAX_FILE_SIZE/1024/1024}MB"
#             )
        
#         # Generate task ID
#         task_id = str(uuid.uuid4())
        
#         # Read file content
#         content = await file.read()
#         file_size = len(content)
        
#         if file_size > MAX_FILE_SIZE:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE/1024/1024}MB"
#             )
        
#         # Save uploaded file
#         file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#         with open(file_path, "wb") as f:
#             f.write(content)
        
#         # Create output directory for this task
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        
#         # Add background task for processing
#         background_tasks.add_task(
#             process_drawing_background,
#             task_id,
#             file_path,
#             task_output_dir
#         )
        
#         logger.info(f"Technical drawing uploaded successfully: {file.filename}, Task ID: {task_id}")
        
#         return DrawingUploadResponse(
#             task_id=task_id,
#             filename=file.filename,
#             file_size=file_size,
#             status="processing",
#             message="Technical drawing uploaded successfully and is being processed"
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error uploading technical drawing: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# @router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
# async def get_processing_status(task_id: str):
#     """
#     Get the processing status of a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
        
#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")
        
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
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         if file_info["status"] == "processing":
#             raise HTTPException(status_code=202, detail="Processing still in progress")
        
#         # Try to read the JSON result file
#         json_path = f"{file_info['output_path']}.json"
#         csv_path = f"{file_info['output_path']}.csv"
        
#         extracted_data = None
#         if include_data and os.path.exists(json_path):
#             try:
#                 import json
#                 with open(json_path, 'r', encoding='utf-8') as f:
#                     result_data = json.load(f)
#                     extracted_data = result_data.get("extracted_data")
#             except Exception as e:
#                 logger.warning(f"Could not read result data: {str(e)}")
        
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
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         json_path = f"{file_info['output_path']}.json"
        
#         if not os.path.exists(json_path):
#             raise HTTPException(status_code=404, detail="JSON result file not found")
        
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
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         csv_path = f"{file_info['output_path']}.csv"
        
#         if not os.path.exists(csv_path):
#             raise HTTPException(status_code=404, detail="CSV result file not found")
        
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
#         raise HTTPException(status_code=500, detail=f"List retrieval failed: {str(e)}")

# @router.delete("/delete/{task_id}")
# async def delete_processed_drawing(task_id: str):
#     """
#     Delete a processed technical drawing and its files
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
        
#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         # Delete files
#         files_to_delete = [
#             file_info["file_path"],  # Original uploaded file
#             f"{file_info['output_path']}.json",
#             f"{file_info['output_path']}.csv"
#         ]
        
#         for file_path in files_to_delete:
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#                 logger.info(f"Deleted file: {file_path}")
        
#         # Delete output directory if empty
#         output_dir = os.path.dirname(file_info['output_path'])
#         try:
#             if os.path.exists(output_dir) and not os.listdir(output_dir):
#                 os.rmdir(output_dir)
#         except OSError:
#             pass  # Directory not empty or other issue, ignore
        
#         # Remove from memory
#         drawing_service.delete_file_info(task_id)
        
#         return {"message": f"Technical drawing {task_id} deleted successfully"}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

# @router.get("/health")
# async def health_check():
#     """
#     Health check endpoint for the technical drawing service
#     """
#     try:
#         total_files = len(drawing_service.get_all_processed_files())
        
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
        
#     except Exception as e:
#         logger.error(f"Health check failed: {str(e)}")
#         return {
#             "status": "unhealthy",
#             "service": "Technical Drawing Extraction Service",
#             "timestamp": datetime.now().isoformat(),
#             "error": str(e)
#         }

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
#                 status_code=400,
#                 detail="Maximum 10 files allowed in batch upload"
#             )
        
#         responses = []
        
#         for file in files:
#             try:
#                 # Validate each file
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
#                 with open(file_path, "wb") as f:
#                     f.write(content)
                
#                 # Create output directory for this task
#                 task_output_dir = os.path.join(OUTPUT_DIR, task_id)
                
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
#         raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")

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



# import os
# import uuid
# import shutil
# from datetime import datetime
# from typing import Optional, List
# from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
# from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel
# from pathlib import Path
# from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse, ErrorResponse
# #from app.service.techinalDrawingService import TechnicalDrawingExtractionService
# from app.log.logger import get_logger

# logger = get_logger(__name__)

# # Initialize router
# router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

# # Initialize service (no database required)
# #drawing_service = TechnicalDrawingExtractionService()
# from app.dependencies import drawing_service

# # Configuration
# UPLOAD_DIR = "uploads/drawings"
# OUTPUT_DIR = "outputs/drawings"
# ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# # Ensure directories exist
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(OUTPUT_DIR, exist_ok=True)


# def validate_image_file(file: UploadFile) -> bool:
#     """Validate uploaded image file"""
#     file_ext = Path(file.filename).suffix.lower()
#     if file_ext not in ALLOWED_EXTENSIONS:
#         return False
    
#     if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
#         return False
    
#     return True

# async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
#     """Background task to process technical drawing"""
#     try:
#         result = await drawing_service.process_image_file(task_id, file_path, output_dir)
#         logger.info(f"Background processing completed for task: {task_id}")
#         return result
#     except Exception as e:
#         logger.error(f"Background processing failed for task {task_id}: {str(e)}")
#         drawing_service.update_file_status(task_id, "failed")

# @router.post("/upload", response_model=DrawingUploadResponse)
# async def upload_technical_drawing(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...)
# ):
#     """
#     Upload a technical drawing/engineering diagram for processing
#     """
#     try:
#         if not validate_image_file(file):
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. Max size: {MAX_FILE_SIZE/1024/1024}MB"
#             )
        
#         task_id = str(uuid.uuid4())
        
#         content = await file.read()
#         file_size = len(content)
        
#         if file_size > MAX_FILE_SIZE:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE/1024/1024}MB"
#             )
        
#         file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#         with open(file_path, "wb") as f:
#             f.write(content)
        
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        
#         background_tasks.add_task(
#             process_drawing_background,
#             task_id,
#             file_path,
#             task_output_dir
#         )
        
#         logger.info(f"Technical drawing uploaded successfully: {file.filename}, Task ID: {task_id}")
        
#         return DrawingUploadResponse(
#             task_id=task_id,
#             filename=file.filename,
#             file_size=file_size,
#             status="processing",
#             message="Technical drawing uploaded successfully and is being processed"
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error uploading technical drawing: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# @router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
# async def get_processing_status(task_id: str):
#     """
#     Get the processing status of a technical drawing
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
        
#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")
        
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
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         if file_info["status"] == "processing":
#             raise HTTPException(status_code=202, detail="Processing still in progress")
        
#         json_path = f"{file_info['output_path']}.json"
        
#         extracted_data = None
#         if include_data and os.path.exists(json_path):
#             try:
#                 import json
#                 with open(json_path, 'r', encoding='utf-8') as f:
#                     result_data = json.load(f)
#                     extracted_data = result_data.get("extracted_data")
#             except Exception as e:
#                 logger.warning(f"Could not read result data: {str(e)}")
        
#         return DrawingProcessingResult(
#             task_id=task_id,
#             filename=file_info["original_filename"],
#             status=file_info["status"],
#             file_size=file_info["file_size"],
#             has_errors=file_info["status"] == "completed_with_errors",
#             json_path=json_path if os.path.exists(json_path) else None,
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
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         json_path = f"{file_info['output_path']}.json"
        
#         if not os.path.exists(json_path):
#             raise HTTPException(status_code=404, detail="JSON result file not found")
        
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
        
#         file_list.sort(key=lambda x: x.created_at, reverse=True)
#         return file_list[:limit]
        
#     except Exception as e:
#         logger.error(f"Error listing drawings: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"List retrieval failed: {str(e)}")

# @router.delete("/delete/{task_id}")
# async def delete_processed_drawing(task_id: str):
#     """
#     Delete a processed technical drawing and its files
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)
        
#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")
        
#         files_to_delete = [
#             file_info["file_path"],
#             f"{file_info['output_path']}.json",
#         ]
        
#         for file_path in files_to_delete:
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#                 logger.info(f"Deleted file: {file_path}")
        
#         output_dir = os.path.dirname(file_info['output_path'])
#         try:
#             if os.path.exists(output_dir) and not os.listdir(output_dir):
#                 os.rmdir(output_dir)
#         except OSError:
#             pass
        
#         drawing_service.delete_file_info(task_id)
        
#         return {"message": f"Technical drawing {task_id} deleted successfully"}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

# @router.get("/health")
# async def health_check():
#     """
#     Health check endpoint for the technical drawing service
#     """
#     try:
#         total_files = len(drawing_service.get_all_processed_files())
        
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
        
#     except Exception as e:
#         logger.error(f"Health check failed: {str(e)}")
#         return {
#             "status": "unhealthy",
#             "service": "Technical Drawing Extraction Service",
#             "timestamp": datetime.now().isoformat(),
#             "error": str(e)
#         }

# @router.post("/batch-upload", response_model=List[DrawingUploadResponse])
# async def batch_upload_drawings(
#     background_tasks: BackgroundTasks,
#     files: List[UploadFile] = File(...)
# ):
#     """
#     Upload multiple technical drawings for batch processing
#     """
#     try:
#         if len(files) > 10:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Maximum 10 files allowed in batch upload"
#             )
        
#         responses = []
        
#         for file in files:
#             try:
#                 if not validate_image_file(file):
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=0,
#                         status="failed",
#                         message=f"Invalid file format or size: {file.filename}"
#                     ))
#                     continue
                
#                 task_id = str(uuid.uuid4())
                
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
                
#                 file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#                 with open(file_path, "wb") as f:
#                     f.write(content)
                
#                 task_output_dir = os.path.join(OUTPUT_DIR, task_id)
                
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
#         raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")

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
        
#         drawing_service.update_file_status(task_id, "processing")
        
#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        
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

# import os
# import uuid
# import shutil
# from datetime import datetime
# from typing import Optional, List, Dict, Any
# from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
# from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
# from pydantic import BaseModel
# from pathlib import Path
# from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse, ErrorResponse
# from app.log.logger import get_logger

# logger = get_logger(__name__)

# # Initialize router
# router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

# from app.dependencies import drawing_service

# # ── NEW: Import pipeline & report services ───────────────────────────────────
# from app.service.pipeline_service import run_full_pipeline
# # from app.service.report_service import generate_ui_report, generate_markdown_report

# # Configuration
# UPLOAD_DIR = "uploads/drawings"
# OUTPUT_DIR = "outputs/drawings"
# ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# # Ensure directories exist
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(OUTPUT_DIR, exist_ok=True)


# # ── NEW: Request model for analyze-direct & report endpoints ─────────────────
# class AnalyzeDirectRequest(BaseModel):
#     extracted_data: Dict[str, Any]


# # ── Existing helpers ─────────────────────────────────────────────────────────

# def validate_image_file(file: UploadFile) -> bool:
#     """Validate uploaded image file"""
#     file_ext = Path(file.filename).suffix.lower()
#     if file_ext not in ALLOWED_EXTENSIONS:
#         return False
#     if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
#         return False
#     return True

# async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
#     """Background task to process technical drawing"""
#     try:
#         result = await drawing_service.process_image_file(task_id, file_path, output_dir)
#         logger.info(f"Background processing completed for task: {task_id}")
#         return result
#     except Exception as e:
#         logger.error(f"Background processing failed for task {task_id}: {str(e)}")
#         drawing_service.update_file_status(task_id, "failed")


# # ════════════════════════════════════════════════════════════════════════════
# # NEW ENDPOINTS (from spec)
# # ════════════════════════════════════════════════════════════════════════════

# @router.post("/analyze-direct")
# async def analyze_direct(body: AnalyzeDirectRequest):
#     """
#     Run full 6-step pipeline on supplied extracted_data JSON.
#     No Gemini call — use for testing.
#     """
#     try:
#         pipeline_result = run_full_pipeline(body.extracted_data)
#         return {"pipeline_result": pipeline_result}
#     except Exception as e:
#         logger.error(f"analyze-direct failed: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


# @router.post("/report")
# async def report_from_data(body: AnalyzeDirectRequest):
#     """
#     Run full pipeline + generate structured 6-section UI report with confidence score.
#     """
#     try:
#         pipeline_result = run_full_pipeline(body.extracted_data)
#         report = generate_ui_report(pipeline_result, body.extracted_data)
#         return {"pipeline_result": pipeline_result, "report": report}
#     except Exception as e:
#         logger.error(f"report generation failed: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


# @router.post("/report/markdown", response_class=PlainTextResponse)
# async def report_markdown_from_data(body: AnalyzeDirectRequest):
#     """
#     Same as /report but returns Markdown plain text for download or email.
#     """
#     try:
#         pipeline_result = run_full_pipeline(body.extracted_data)
#         md = generate_markdown_report(pipeline_result, body.extracted_data)
#         return md
#     except Exception as e:
#         logger.error(f"markdown report failed: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Markdown report failed: {str(e)}")


# @router.get("/full-result/{task_id}")
# async def get_full_result(task_id: str):
#     """
#     Get extraction + full pipeline result for a previously processed task.
#     Runs the 6-step pipeline on the stored extracted_data and returns both.
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         if file_info["status"] == "processing":
#             raise HTTPException(status_code=202, detail="Processing still in progress")

#         # Load extracted_data from the saved JSON output
#         json_path = f"{file_info['output_path']}.json"
#         if not os.path.exists(json_path):
#             raise HTTPException(status_code=404, detail="Result file not found. Task may have failed.")

#         import json
#         with open(json_path, 'r', encoding='utf-8') as f:
#             result_data = json.load(f)

#         extracted_data = result_data.get("extracted_data")
#         if not extracted_data:
#             raise HTTPException(status_code=500, detail="No extracted_data found in result file.")

#         pipeline_result = run_full_pipeline(extracted_data)

#         return {
#             "task_id": task_id,
#             "extracted_data": extracted_data,
#             "pipeline_result": pipeline_result,
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting full-result for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Full result retrieval failed: {str(e)}")


# @router.get("/report/{task_id}")
# async def get_report_by_task(task_id: str):
#     """
#     Generate full UI report for a previously processed task.
#     """
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         if file_info["status"] == "processing":
#             raise HTTPException(status_code=202, detail="Processing still in progress")

#         json_path = f"{file_info['output_path']}.json"
#         if not os.path.exists(json_path):
#             raise HTTPException(status_code=404, detail="Result file not found. Task may have failed.")

#         import json
#         with open(json_path, 'r', encoding='utf-8') as f:
#             result_data = json.load(f)

#         extracted_data = result_data.get("extracted_data")
#         if not extracted_data:
#             raise HTTPException(status_code=500, detail="No extracted_data found in result file.")

#         pipeline_result = run_full_pipeline(extracted_data)
#         report = generate_ui_report(pipeline_result, extracted_data)

#         return {
#             "task_id": task_id,
#             "pipeline_result": pipeline_result,
#             "report": report,
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error generating report for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


# # ════════════════════════════════════════════════════════════════════════════
# # EXISTING ENDPOINTS (unchanged)
# # ════════════════════════════════════════════════════════════════════════════

# @router.post("/upload", response_model=DrawingUploadResponse)
# async def upload_technical_drawing(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...)
# ):
#     """Upload a technical drawing/engineering diagram for processing"""
#     try:
#         if not validate_image_file(file):
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. Max size: {MAX_FILE_SIZE/1024/1024}MB"
#             )

#         task_id = str(uuid.uuid4())
#         content = await file.read()
#         file_size = len(content)

#         if file_size > MAX_FILE_SIZE:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE/1024/1024}MB"
#             )

#         file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#         with open(file_path, "wb") as f:
#             f.write(content)

#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)

#         background_tasks.add_task(
#             process_drawing_background,
#             task_id,
#             file_path,
#             task_output_dir
#         )

#         logger.info(f"Technical drawing uploaded successfully: {file.filename}, Task ID: {task_id}")

#         return DrawingUploadResponse(
#             task_id=task_id,
#             filename=file.filename,
#             file_size=file_size,
#             status="processing",
#             message="Technical drawing uploaded successfully and is being processed"
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error uploading technical drawing: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# @router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
# async def get_processing_status(task_id: str):
#     """Get the processing status of a technical drawing"""
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

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
#     """Get the processing result of a technical drawing"""
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         if file_info["status"] == "processing":
#             raise HTTPException(status_code=202, detail="Processing still in progress")

#         json_path = f"{file_info['output_path']}.json"

#         extracted_data = None
#         if include_data and os.path.exists(json_path):
#             try:
#                 import json
#                 with open(json_path, 'r', encoding='utf-8') as f:
#                     result_data = json.load(f)
#                     extracted_data = result_data.get("extracted_data")
#             except Exception as e:
#                 logger.warning(f"Could not read result data: {str(e)}")

#         return DrawingProcessingResult(
#             task_id=task_id,
#             filename=file_info["original_filename"],
#             status=file_info["status"],
#             file_size=file_info["file_size"],
#             has_errors=file_info["status"] == "completed_with_errors",
#             json_path=json_path if os.path.exists(json_path) else None,
#             extracted_data=extracted_data
#         )

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting result for task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Result retrieval failed: {str(e)}")


# @router.get("/download/{task_id}/json")
# async def download_json_result(task_id: str):
#     """Download the JSON result file for a processed technical drawing"""
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         json_path = f"{file_info['output_path']}.json"

#         if not os.path.exists(json_path):
#             raise HTTPException(status_code=404, detail="JSON result file not found")

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


# @router.get("/list", response_model=List[DrawingProcessingStatus])
# async def list_processed_drawings(
#     status: Optional[str] = Query(None, description="Filter by status"),
#     limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
# ):
#     """List all processed technical drawings"""
#     try:
#         all_files = drawing_service.get_all_processed_files()

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

#         file_list.sort(key=lambda x: x.created_at, reverse=True)
#         return file_list[:limit]

#     except Exception as e:
#         logger.error(f"Error listing drawings: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"List retrieval failed: {str(e)}")


# @router.delete("/delete/{task_id}")
# async def delete_processed_drawing(task_id: str):
#     """Delete a processed technical drawing and its files"""
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         files_to_delete = [
#             file_info["file_path"],
#             f"{file_info['output_path']}.json",
#         ]

#         for file_path in files_to_delete:
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#                 logger.info(f"Deleted file: {file_path}")

#         output_dir = os.path.dirname(file_info['output_path'])
#         try:
#             if os.path.exists(output_dir) and not os.listdir(output_dir):
#                 os.rmdir(output_dir)
#         except OSError:
#             pass

#         drawing_service.delete_file_info(task_id)
#         return {"message": f"Technical drawing {task_id} deleted successfully"}

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting task {task_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


# @router.get("/health")
# async def health_check():
#     """Health check endpoint for the technical drawing service"""
#     try:
#         total_files = len(drawing_service.get_all_processed_files())

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

#     except Exception as e:
#         logger.error(f"Health check failed: {str(e)}")
#         return {
#             "status": "unhealthy",
#             "service": "Technical Drawing Extraction Service",
#             "timestamp": datetime.now().isoformat(),
#             "error": str(e)
#         }


# @router.post("/batch-upload", response_model=List[DrawingUploadResponse])
# async def batch_upload_drawings(
#     background_tasks: BackgroundTasks,
#     files: List[UploadFile] = File(...)
# ):
#     """Upload multiple technical drawings for batch processing"""
#     try:
#         if len(files) > 10:
#             raise HTTPException(status_code=400, detail="Maximum 10 files allowed in batch upload")

#         responses = []

#         for file in files:
#             try:
#                 if not validate_image_file(file):
#                     responses.append(DrawingUploadResponse(
#                         task_id="",
#                         filename=file.filename,
#                         file_size=0,
#                         status="failed",
#                         message=f"Invalid file format or size: {file.filename}"
#                     ))
#                     continue

#                 task_id = str(uuid.uuid4())
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

#                 file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
#                 with open(file_path, "wb") as f:
#                     f.write(content)

#                 task_output_dir = os.path.join(OUTPUT_DIR, task_id)

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
#         raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


# @router.get("/stats")
# async def get_processing_stats():
#     """Get processing statistics"""
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
#     """Reprocess a technical drawing"""
#     try:
#         file_info = drawing_service.get_file_info(task_id)

#         if not file_info:
#             raise HTTPException(status_code=404, detail="Task not found")

#         if not os.path.exists(file_info["file_path"]):
#             raise HTTPException(status_code=404, detail="Original file not found")

#         drawing_service.update_file_status(task_id, "processing")

#         task_output_dir = os.path.join(OUTPUT_DIR, task_id)

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

"""
drwaingRouter.py
FastAPI Router — all cost estimation endpoints.
Location: app/routers/drwaingRouter.py

Endpoints:
  POST /api/google/analyze-direct   → run full pipeline on supplied extracted_data JSON
  POST /api/google/report            → full pipeline + structured 6-section UI report
  POST /api/google/report/markdown   → same as /report but returns Markdown plain text
  POST /api/google/upload            → upload drawing image → Gemini extraction → background task
  GET  /api/google/status/{id}       → check processing status
  GET  /api/google/result/{id}       → raw Gemini extraction result
  GET  /api/google/full-result/{id}  → extraction + full pipeline result
  GET  /api/google/report/{id}       → full UI report for previously processed task
  GET  /api/google/health            → health check
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# ── Import pipeline steps ─────────────────────────────────────────────────────
# These resolve to app/service/*.py files
from app.service.gear_rule import classify_and_plan
from app.service.volume_calculation_service import compute_volume
from app.service.cost_service import compute_full_cost
from app.service.validation_service import validate_all

# Gemini extraction service (existing file in your project)
# If this import fails, check app/service/techinalDrawingService.py
try:
    from app.service.techinalDrawingService import extract_drawing_data
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

router = APIRouter(prefix="/api/google", tags=["Cost Estimation"])

# ── In-memory task store (replace with DB/Redis for production) ───────────────
# Structure: { task_id: { status, extracted_data, pipeline_result, error, created_at } }
_tasks: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class AnalyzeDirectRequest(BaseModel):
    extracted_data: dict
    overhead_pct: float = 15.0
    margin_pct:   float = 20.0
    currency:     str   = "USD"


class ReportRequest(BaseModel):
    extracted_data: dict
    overhead_pct: float = 15.0
    margin_pct:   float = 20.0
    currency:     str   = "USD"


# ══════════════════════════════════════════════════════════════════════════════
# SHARED PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def _run_pipeline(
    extracted_data: dict,
    overhead_pct: float = 15.0,
    margin_pct:   float = 20.0,
    currency:     str   = "USD",
) -> dict:
    """
    Runs all 6 steps in order and returns the full pipeline_result dict.
    Called by every endpoint that needs cost data.
    """
    # Step 1 — Gear Classification
    classification  = classify_and_plan(extracted_data)
    gear_family     = classification["gear_family"]
    gear_rule_ops   = classification["operations_sequence"]

    # Step 2 — Volume Calculation
    volume_result   = compute_volume(extracted_data)
    net_volume_cm3  = volume_result["net_volume_cm3"]

    # Steps 3 + 4 + 5 — Material, Operations, Breakdown
    cost_result     = compute_full_cost(
        extracted_data  = extracted_data,
        net_volume_cm3  = net_volume_cm3,
        gear_family     = gear_family,
        gear_rule_ops   = gear_rule_ops,
        overhead_pct    = overhead_pct,
        margin_pct      = margin_pct,
        currency        = currency,
    )

    # Step 6 — Validation
    validation      = validate_all(
        extracted_data  = extracted_data,
        volume_result   = volume_result,
        cost_result     = cost_result,
    )

    return {
        "gear_family":            gear_family,
        "classification_evidence": classification.get("evidence", []),
        "volume": {
            "net_volume_mm3":    volume_result["net_volume_mm3"],
            "net_volume_cm3":    volume_result["net_volume_cm3"],
            "method":            volume_result["method"],
            "feature_breakdown": volume_result["feature_breakdown"],
        },
        "material_info":    cost_result["material_info"],
        "operations_detail": cost_result["operations_detail"],
        "cost_breakdown":   cost_result["cost_breakdown"],
        "validation_report": {
            "validation_passed":  validation["validation_passed"],
            "confidence_score":   validation["confidence_score"],
            "confidence_level":   validation["confidence_level"],
            "ready_for_quote":    validation["ready_for_quote"],
            "error_count":        validation["error_count"],
            "warn_count":         validation["warn_count"],
            "rules":              validation["rules"],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# REPORT BUILDER  (6-section structured report)
# ══════════════════════════════════════════════════════════════════════════════

def _build_report(pipeline_result: dict) -> dict:
    """Build the structured 6-section UI report from a pipeline result."""
    cb  = pipeline_result["cost_breakdown"]
    val = pipeline_result["validation_report"]
    mat = pipeline_result["material_info"]
    vol = pipeline_result["volume"]
    ops = pipeline_result["operations_detail"]

    # Confidence badge
    level = val["confidence_level"]
    badge = "✅ READY FOR QUOTATION"        if level == "HIGH"   else \
            "⚠️ REVIEW WARNINGS BEFORE QUOTING" if level == "MEDIUM" else \
            "❌ CRITICAL ISSUES — DO NOT QUOTE"

    return {
        "report_sections": {
            "1_classification": {
                "title":       "Gear Classification",
                "gear_family": pipeline_result["gear_family"].upper(),
                "evidence":    pipeline_result.get("classification_evidence", []),
            },
            "2_volume": {
                "title":             "Volume Calculation",
                "method":            vol["method"],
                "net_volume_mm3":    vol["net_volume_mm3"],
                "net_volume_cm3":    vol["net_volume_cm3"],
                "feature_breakdown": vol["feature_breakdown"],
            },
            "3_material": {
                "title":            "Material Cost",
                "matched_material": mat["matched_material"],
                "matched_pattern":  mat.get("matched_pattern"),
                "density_g_cm3":    mat["density_g_cm3"],
                "rate_per_kg":      mat["rate_per_kg"],
                "mass_kg":          mat["mass_kg"],
                "material_cost":    mat["cost"],
                "currency":         mat.get("currency", "USD"),
            },
            "4_operations": {
                "title":      "Operations Cost",
                "operations": [
                    {
                        "step":       op["step"],
                        "operation":  op["operation"],
                        "time_min":   op["estimated_time_min"],
                        "rate_hr":    op["rate_per_hour"],
                        "cost":       op["cost"],
                        "machines":   op["machine_options"],
                        "source":     op["source"],
                    }
                    for op in ops
                ],
                "total_operations_cost": cb["operations_cost"],
            },
            "5_cost_breakdown": {
                "title":            "Cost Breakdown",
                "material_cost":    cb["material_cost"],
                "operations_cost":  cb["operations_cost"],
                "overhead_pct":     cb["overhead_pct"],
                "overhead_cost":    cb["overhead_cost"],
                "subtotal":         cb["subtotal"],
                "margin_pct":       cb["margin_pct"],
                "margin_cost":      cb["margin_cost"],
                "total_cost":       cb["total_cost"],
                "currency":         cb["currency"],
            },
            "6_validation": {
                "title":            "Validation Report",
                "confidence_score": val["confidence_score"],
                "confidence_level": val["confidence_level"],
                "confidence_badge": badge,
                "ready_for_quote":  val["ready_for_quote"],
                "validation_passed": val["validation_passed"],
                "error_count":      val["error_count"],
                "warn_count":       val["warn_count"],
                "failed_rules": [
                    r for r in val["rules"] if not r["passed"]
                ],
            },
        },
        "summary": {
            "gear_family":      pipeline_result["gear_family"],
            "total_cost":       cb["total_cost"],
            "currency":         cb["currency"],
            "confidence_score": val["confidence_score"],
            "confidence_level": val["confidence_level"],
            "ready_for_quote":  val["ready_for_quote"],
        },
    }


def _build_markdown(pipeline_result: dict) -> str:
    """Build a Markdown plain-text report from a pipeline result."""
    cb  = pipeline_result["cost_breakdown"]
    val = pipeline_result["validation_report"]
    mat = pipeline_result["material_info"]
    vol = pipeline_result["volume"]
    ops = pipeline_result["operations_detail"]

    level = val["confidence_level"]
    badge = "✅ READY FOR QUOTATION"             if level == "HIGH"   else \
            "⚠️ REVIEW WARNINGS BEFORE QUOTING"  if level == "MEDIUM" else \
            "❌ CRITICAL ISSUES — DO NOT QUOTE"

    lines = [
        "# Gear Drawing Cost Estimation Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## 1. Gear Classification",
        f"- **Gear Family:** {pipeline_result['gear_family'].upper()}",
        "",
        "## 2. Volume Calculation",
        f"- **Method:** {vol['method']}",
        f"- **Net Volume:** {vol['net_volume_mm3']:,.2f} mm³ = {vol['net_volume_cm3']:.4f} cm³",
        "",
        "## 3. Material",
        f"- **Material:** {mat['matched_material']}  (matched: `{mat.get('matched_pattern')}`)",
        f"- **Density:** {mat['density_g_cm3']} g/cm³",
        f"- **Rate:** ${mat['rate_per_kg']}/kg",
        f"- **Mass:** {mat['mass_kg']:.4f} kg",
        f"- **Material Cost:** ${mat['cost']:.2f}",
        "",
        "## 4. Operations",
        "",
        "| # | Operation | Min | $/hr | Cost | Source |",
        "|---|-----------|-----|------|------|--------|",
    ]
    for op in ops:
        lines.append(
            f"| {op['step']} | {op['operation']} | {op['estimated_time_min']} "
            f"| ${op['rate_per_hour']} | ${op['cost']:.2f} | {op['source']} |"
        )

    lines += [
        "",
        "## 5. Cost Breakdown",
        "",
        f"| Item | Amount |",
        f"|------|--------|",
        f"| Material Cost | ${cb['material_cost']:.2f} |",
        f"| Operations Cost | ${cb['operations_cost']:.2f} |",
        f"| Overhead ({cb['overhead_pct']}%) | ${cb['overhead_cost']:.2f} |",
        f"| Subtotal | ${cb['subtotal']:.2f} |",
        f"| Margin ({cb['margin_pct']}%) | ${cb['margin_cost']:.2f} |",
        f"| **TOTAL** | **${cb['total_cost']:.2f} {cb['currency']}** |",
        "",
        "## 6. Validation",
        "",
        f"- **Confidence Score:** {val['confidence_score']}/100",
        f"- **Status:** {badge}",
        f"- **Errors:** {val['error_count']}  |  **Warnings:** {val['warn_count']}",
        "",
    ]

    failed = [r for r in val["rules"] if not r["passed"]]
    if failed:
        lines.append("### Failed Rules")
        for r in failed:
            icon = "🔴" if r["severity"] == "ERROR" else "🟡"
            lines.append(f"- {icon} **[{r['rule_id']}]** {r['message']}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
def health_check():
    """GET /api/google/health — confirms service is running."""
    return {
        "status":          "ok",
        "gemini_available": GEMINI_AVAILABLE,
        "timestamp":       datetime.utcnow().isoformat(),
    }


@router.post("/analyze-direct")
def analyze_direct(request: AnalyzeDirectRequest):
    """
    POST /api/google/analyze-direct
    Run full pipeline on supplied extracted_data JSON.
    No Gemini call — use for testing or when you already have extracted JSON.
    """
    try:
        pipeline_result = _run_pipeline(
            extracted_data = request.extracted_data,
            overhead_pct   = request.overhead_pct,
            margin_pct     = request.margin_pct,
            currency       = request.currency,
        )
        return {"pipeline_result": pipeline_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report")
def get_report(request: ReportRequest):
    """
    POST /api/google/report
    Run full pipeline + generate structured 6-section UI report with confidence score.
    """
    try:
        pipeline_result = _run_pipeline(
            extracted_data = request.extracted_data,
            overhead_pct   = request.overhead_pct,
            margin_pct     = request.margin_pct,
            currency       = request.currency,
        )
        report = _build_report(pipeline_result)
        return {
            "pipeline_result": pipeline_result,
            "report":          report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/markdown", response_class=PlainTextResponse)
def get_report_markdown(request: ReportRequest):
    """
    POST /api/google/report/markdown
    Same as /report but returns Markdown plain text for download or email.
    """
    try:
        pipeline_result = _run_pipeline(
            extracted_data = request.extracted_data,
            overhead_pct   = request.overhead_pct,
            margin_pct     = request.margin_pct,
            currency       = request.currency,
        )
        return _build_markdown(pipeline_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    POST /api/google/upload
    Upload drawing image → Gemini extraction → background processing task.
    Returns a task_id to poll with /status/{id} and /full-result/{id}.
    """
    if not GEMINI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Gemini extraction service not available. Check GOOGLE_API_KEY in .env and techinalDrawingService.py."
        )

    task_id = str(uuid.uuid4())
    image_bytes = await file.read()

    _tasks[task_id] = {
        "status":          "processing",
        "extracted_data":  None,
        "pipeline_result": None,
        "error":           None,
        "created_at":      datetime.utcnow().isoformat(),
        "filename":        file.filename,
    }

    async def process_task(tid: str, img_bytes: bytes, fname: str):
        try:
            # Save to temp file for Gemini
            import tempfile, os
            suffix = os.path.splitext(fname)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name

            extracted = await asyncio.to_thread(extract_drawing_data, tmp_path)
            os.unlink(tmp_path)

            pipeline_result = _run_pipeline(extracted)

            _tasks[tid]["extracted_data"]  = extracted
            _tasks[tid]["pipeline_result"] = pipeline_result
            _tasks[tid]["status"]          = "completed"
        except Exception as e:
            _tasks[tid]["status"] = "failed"
            _tasks[tid]["error"]  = str(e)

    background_tasks.add_task(process_task, task_id, image_bytes, file.filename)

    return {
        "task_id":    task_id,
        "status":     "processing",
        "message":    "Drawing uploaded. Poll /api/google/status/{task_id} for progress.",
        "created_at": _tasks[task_id]["created_at"],
    }


@router.get("/status/{task_id}")
def get_status(task_id: str):
    """GET /api/google/status/{id} — check processing status of uploaded drawing."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return {
        "task_id":    task_id,
        "status":     task["status"],
        "filename":   task.get("filename"),
        "created_at": task.get("created_at"),
        "error":      task.get("error"),
    }


@router.get("/result/{task_id}")
def get_result(task_id: str):
    """GET /api/google/result/{id} — get raw Gemini extraction result for a task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    if task["status"] == "processing":
        raise HTTPException(status_code=202, detail="Task still processing.")
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=task.get("error", "Task failed."))
    return {
        "task_id":        task_id,
        "extracted_data": task["extracted_data"],
    }


@router.get("/full-result/{task_id}")
def get_full_result(task_id: str):
    """GET /api/google/full-result/{id} — get extraction + full pipeline result."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    if task["status"] == "processing":
        raise HTTPException(status_code=202, detail="Task still processing.")
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=task.get("error", "Task failed."))
    return {
        "task_id":         task_id,
        "extracted_data":  task["extracted_data"],
        "pipeline_result": task["pipeline_result"],
    }


@router.get("/report/{task_id}")
def get_report_by_id(task_id: str):
    """GET /api/google/report/{id} — generate full UI report for a previously processed task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    if task["status"] == "processing":
        raise HTTPException(status_code=202, detail="Task still processing.")
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=task.get("error", "Task failed."))

    pipeline_result = task["pipeline_result"]
    if not pipeline_result:
        # Re-run if needed
        pipeline_result = _run_pipeline(task["extracted_data"])
        task["pipeline_result"] = pipeline_result

    report = _build_report(pipeline_result)
    return {
        "task_id":         task_id,
        "pipeline_result": pipeline_result,
        "report":          report,
    }