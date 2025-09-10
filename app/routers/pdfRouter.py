from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import json
from pathlib import Path
from app.database.db import get_db
from app.schemas.pdfschema import ExtractionResponse, ExtractionStatus
from app.service.pdfService import PDFExtractionService
from app.log.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["PDF Extraction"])

UPLOAD_FOLDER = "uploads/pdf"
OUTPUT_FOLDER = "output/pdf"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

async def process_pdf_background(
    task_id: str,
    file_path: str,
    output_dir: str,
    filename: str,
    db: AsyncSession
):
    """Background task for processing PDF file"""
    try:
        logger.info(f"Starting background processing for task: {task_id}")
        service = PDFExtractionService(db)
        await service.process_pdf_file(
            task_id=task_id,
            file_path=file_path,
            output_dir=output_dir
        )
        logger.info(f"Background processing completed for task: {task_id}")
    except Exception as e:
        logger.error(f"Error in background processing for task {task_id}: {str(e)}")

@router.post("/upload", response_model=ExtractionResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Received PDF upload request for file: {file.filename}")
        
        if not file.filename.lower().endswith('.pdf'):
            logger.error(f"Invalid file format attempted: {file.filename}")
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        task_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
        
        logger.debug(f"Saving uploaded file to: {file_path}")
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())
        
        background_tasks.add_task(
            process_pdf_background,
            task_id=task_id,
            file_path=file_path,
            output_dir=OUTPUT_FOLDER,
            filename=file.filename,
            db=db
        )
        
        logger.info(f"Started background processing for task: {task_id}")
        return {
            "task_id": task_id,
            "filename": file.filename,
            "status": "processing",
            "message": "PDF upload accepted and processing started in background"
        }
    
    except HTTPException as he:
        logger.error(f"HTTPException during PDF upload: {str(he.detail)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during PDF upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=ExtractionStatus)
async def get_processing_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Checking status for task: {task_id}")
        service = PDFExtractionService(db)
        pdf_document = await service.get_pdf_document(task_id)
        
        if not pdf_document:
            logger.warning(f"Task not found: {task_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        
        json_file = f"{pdf_document.output_path}.json"
        if pdf_document.output_path and os.path.exists(json_file):
            status_info = {
                "task_id": task_id,
                "status": "completed",
                "output_path": pdf_document.output_path,
                "message": f"Processed {pdf_document.total_pages} pages"
            }
            logger.debug(f"Status check completed for task {task_id}: {status_info}")
            return status_info
        else:
            status_info = {
                "task_id": task_id,
                "status": pdf_document.status,
                "message": "Processing in progress" if pdf_document.status == "processing" else "Processing failed"
            }
            logger.debug(f"Status check for incomplete task {task_id}: {status_info}")
            return status_info
    
    except HTTPException as he:
        logger.error(f"HTTPException during status check for task {task_id}: {str(he.detail)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during status check for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking status: {str(e)}")

@router.get("/content/{task_id}")
async def get_extraction_content(
    task_id: str,
    format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    """
    Get the extracted content in specified format (json/csv)
    """
    try:
        logger.info(f"Content request for task: {task_id} in format: {format}")
        service = PDFExtractionService(db)
        pdf_document = await service.get_pdf_document(task_id)
        
        if not pdf_document:
            logger.warning(f"Task not found for content request: {task_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        
        if not pdf_document.output_path:
            logger.warning(f"Extraction not available yet for task: {task_id}")
            raise HTTPException(status_code=404, detail="Extraction not yet available")
        
        if format.lower() == "json":
            json_file = f"{pdf_document.output_path}.json"
            if not os.path.exists(json_file):
                logger.error(f"JSON output not found for task: {task_id}")
                raise HTTPException(status_code=404, detail="JSON output not found")
            
            logger.debug(f"Returning JSON content for task: {task_id}")
            with open(json_file, 'r', encoding='utf-8') as f:
                return JSONResponse(content=json.load(f))
        
        elif format.lower() == "csv":
            csv_file = f"{pdf_document.output_path}.csv"
            if not os.path.exists(csv_file):
                logger.error(f"CSV output not found for task: {task_id}")
                raise HTTPException(status_code=404, detail="CSV output not found")
            
            logger.debug(f"Returning CSV file for task: {task_id}")
            return FileResponse(
                path=csv_file,
                media_type="text/csv",
                filename=f"{Path(pdf_document.original_filename).stem}_extracted.csv"
            )
        
        else:
            logger.error(f"Invalid format requested: {format}")
            raise HTTPException(status_code=400, detail="Invalid format specified. Use 'json' or 'csv'")
    
    except HTTPException as he:
        logger.error(f"HTTPException during content retrieval for task {task_id}: {str(he.detail)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during content retrieval for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting content: {str(e)}")