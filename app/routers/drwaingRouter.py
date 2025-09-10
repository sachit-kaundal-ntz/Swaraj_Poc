
import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Depends, status
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from sqlalchemy.orm import Session
from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse
from app.service.techinalDrawingService import TechnicalDrawingExtractionService
from app.log.logger import get_logger
from app.database.db import get_db
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)
 
router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])
 
drawing_service = TechnicalDrawingExtractionService()
 
UPLOAD_DIR = "uploads/drawings"
OUTPUT_DIR = "outputs/drawings"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  
MIN_FILE_SIZE = 1 * 1024  
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
 
async def process_drawing_background(task_id: str, file_path: str, output_dir: str, db: Session):
    """Background task to process technical drawing"""
    try:
        service_with_db = TechnicalDrawingExtractionService(db_session=db)
        result = await service_with_db.process_image_file(task_id, file_path, output_dir)
        logger.info(f"Background processing completed for task: {task_id}")
        return result
    except ValueError as e:
        if "Token limit exceeded" in str(e):
            service_with_db.update_file_status(task_id, "failed")
            logger.error(f"Token limit exceeded for task {task_id}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "token_limit_exceeded": True
            }
        raise
    except Exception as e:
        logger.error(f"Background processing failed for task {task_id}: {str(e)}")
        if 'service_with_db' in locals():
            service_with_db.update_file_status(task_id, "failed")
        raise


@router.post("/upload", response_model=DrawingUploadResponse)
async def upload_technical_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
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

        task_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except IOError as e:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=f"Could not save file: {str(e)}"
            )

        task_output_dir = os.path.join(OUTPUT_DIR, task_id)
        os.makedirs(task_output_dir, exist_ok=True)

        try:
            background_tasks.add_task(
                process_drawing_background,
                task_id,
                file_path,
                task_output_dir,
                db
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
        if he.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            logger.error(f"Token limit exceeded for file {file.filename}")
        raise he
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )

@router.get("/api/google/status/{task_id}")
async def get_status(task_id: str, db: AsyncSession = Depends(get_db)):
    service = TechnicalDrawingExtractionService(db_session=db)
    file_info = await service.get_file_info(task_id)  # Note the 'await'
    if not file_info:
        raise HTTPException(status_code=404, detail="Task not found")
    return file_info
 
@router.get("/download/{task_id}/json")
async def download_json_result(task_id: str, db: Session = Depends(get_db)):
    """
    Download the JSON result file for a processed technical drawing
    """
    try:
        service_with_db = TechnicalDrawingExtractionService(db_session=db)
        file_info = service_with_db.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  
                detail="Task not found"
            )
       
        json_path = os.path.join(file_info.get("output_path", ""), f"{task_id}.json")
       
        if not os.path.exists(json_path):
            if "extracted_data" not in file_info:
                raise HTTPException(
                    status_code=404, 
                    detail="JSON result not available"
                )
            
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                import json
                json.dump({
                    "task_id": task_id,
                    "filename": file_info["original_filename"],
                    "extracted_data": file_info["extracted_data"],
                    "status": file_info["status"],
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
       
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
async def delete_processed_drawing(task_id: str, db: Session = Depends(get_db)):
    """
    Delete a processed technical drawing and its files
    """
    try:
        service_with_db = TechnicalDrawingExtractionService(db_session=db)
        file_info = service_with_db.get_file_info(task_id)
       
        if not file_info:
            raise HTTPException(
                status_code=404,  
                detail="Task not found"
            )
       
        # Delete files
        files_to_delete = [
            file_info.get("file_path"),  
            os.path.join(file_info.get("output_path", ""), f"{task_id}.json")
        ]
       
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted file: {file_path}")
            except IOError as e:
                logger.warning(f"Could not delete file {file_path}: {str(e)}")
       
        db_deleted = service_with_db.delete_file_info(task_id)
       
        if deleted_count == 0 and not db_deleted:
            raise HTTPException(
                status_code=404,  
                detail="No files or records found to delete"
            )
       
        output_dir = file_info.get("output_path")
        try:
            if output_dir and os.path.exists(output_dir) and not os.listdir(output_dir):
                os.rmdir(output_dir)
        except OSError:
            pass
       
        return {"message": f"Technical drawing {task_id} deleted successfully"}
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,  
            detail=f"Deletion failed: {str(e)}"
        )
 
@router.post("/batch-upload", response_model=List[DrawingUploadResponse])
async def batch_upload_drawings(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload multiple technical drawings for batch processing
    """
    try:
        if len(files) > 10:  
            raise HTTPException(
                status_code=413,  
                detail="Maximum 10 files allowed in batch upload"
            )
       
        responses = []
       
        for file in files:
            try:
                
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
               
                task_id = str(uuid.uuid4())
               
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
               
                background_tasks.add_task(
                    process_drawing_background,
                    task_id,
                    file_path,
                    task_output_dir,
                    db
                )
               
                responses.append(DrawingUploadResponse(
                    task_id=task_id,
                    filename=file.filename,
                    file_size=file_size,
                    status="processing",
                    message="File uploaded successfully and is being processed"
                ))
               
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
        raise HTTPException(
            status_code=500,  
            detail=f"Batch upload failed: {str(e)}"
        )
 