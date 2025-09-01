import os
import uuid
import shutil
import json
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Depends, status, Body
from fastapi.responses import FileResponse
from pathlib import Path
from app.schemas.drawingSchema import DrawingProcessingResult, DrawingProcessingStatus, DrawingUploadResponse
from app.service.volume_calculation_service import extract_dimensions_and_calculate_volumes, calculate_net_volume
from app.log.logger import get_logger
from typing import Optional, Tuple
from app.service.volume_calculation_service import (
    extract_dimensions_and_calculate_volumes, 
    calculate_net_volume,
    calculate_mass_with_tolerance,
    get_available_materials,
    calculate_mass_from_volume,
    calculate_simple_mass
)
from app.service.techinalDrawingService2 import TechnicalDrawingExtractionService
from app.schemas.drawingSchema import MassCalculationRequest, MaterialInfo, SimpleMassResponse


logger = get_logger(__name__)
drawing_service = TechnicalDrawingExtractionService()
 
router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])
  
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


@router.post("/upload", response_model=DrawingUploadResponse)
async def upload_technical_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
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
                status_code=404,  
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
                status_code=404,  
                detail="Task not found"
            )
       
        if file_info["status"] == "processing":
            raise HTTPException(
                status_code=202,  
                detail="Processing still in progress"
            )
       
        if file_info["status"] == "failed":
            raise HTTPException(
                status_code=424, 
                detail="Processing failed for this file"
            )
       
        json_path = f"{file_info['output_path']}.json"
        csv_path = f"{file_info['output_path']}.csv"
       
        extracted_data = None
        if include_data:
            if not os.path.exists(json_path):
                raise HTTPException(
                    status_code=424,  
                    detail="Result data not available"
                )
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                    extracted_data = result_data.get("extracted_data")
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=422,  
                    detail="Result data is corrupted"
                )
            except Exception as e:
                logger.warning(f"Could not read result data: {str(e)}")
                raise HTTPException(
                    status_code=422,  
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
                status_code=404,  
                detail="Task not found"
            )
        json_path = f"{file_info['output_path']}.json"
       
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,  
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

@router.get("/calculate-volume/{task_id}")
async def calculate_volume_by_task_id(task_id: str):
    """
    Calculate volumes for a drawing by task_id (loads the corresponding JSON file).
    """
    try:
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

@router.post("/calculate-mass/{task_id}", response_model=SimpleMassResponse)
async def calculate_mass_by_task_id(
    task_id: str, 
    request: MassCalculationRequest = MassCalculationRequest()
):
    """
    Calculate mass for a drawing by task_id with specified material.
    Returns simple response with total mass.
    """
    try:
        json_path = os.path.join(OUTPUT_DIR, task_id, f"{task_id}.json")
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"Result file not found for task_id {task_id}"
            )
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        components = extract_dimensions_and_calculate_volumes(
            data, 
            tolerance_mm=request.tolerance_mm
        )
        
        if not components:
            raise HTTPException(
                status_code=422,
                detail="No valid components found for mass calculation"
            )

        mass_result = calculate_simple_mass(components, request.material_name)

        return SimpleMassResponse(**mass_result)

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Result file not found for task_id {task_id}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Invalid JSON data in result file"
        )
    except Exception as e:
        logger.error(f"Mass calculation error for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Mass calculation failed: {str(e)}"
        )

@router.get("/materials")
async def get_available_materials_list():
    """
    Get list of available materials and their properties.
    """
    try:
        materials = get_available_materials()
        
        materials_list = []
        for name, properties in materials.items():
            materials_list.append(MaterialInfo(
                name=name,
                density_g_per_mm3=properties['density_g_per_mm3'],
                density_g_per_cm3=properties['density_g_per_cm3'],
                density_kg_per_m3=properties['density_kg_per_m3']
            ))

        return {
            "total_materials": len(materials_list),
            "materials": materials_list,
            "default_material": "20MnCr5",
            "note": "All steel alloys have similar density of ~7.85 g/cm³"
        }

    except Exception as e:
        logger.error(f"Error retrieving materials list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve materials list"
        )

@router.post("/calculate-mass-direct")
async def calculate_mass_direct(
    volume_mm3: float,
    material_name: str = "20MnCr5"
):
    """
    Calculate mass directly from volume and material name.
    Useful for quick calculations without processing a drawing.
    """
    try:
        if volume_mm3 <= 0:
            raise HTTPException(
                status_code=400,
                detail="Volume must be greater than 0"
            )

        mass_data = calculate_mass_from_volume(volume_mm3, material_name)
        
        return {
            "input": {
                "volume_mm3": volume_mm3,
                "material_requested": material_name
            },
            "result": mass_data,
            "conversions": {
                "volume_cm3": round(volume_mm3 / 1000, 6),
                "volume_m3": round(volume_mm3 / 1000000000, 9),
                "density_kg_per_m3": mass_data['density_g_per_mm3'] * 1000000
            }
        }

    except Exception as e:
        logger.error(f"Direct mass calculation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Mass calculation failed: {str(e)}"
        )

@router.get("/calculate-volume-and-mass/{task_id}")
async def calculate_volume_and_mass_combined(
    task_id: str,
    material_name: str = Query("20MnCr5", description="Material name for mass calculation"),
    tolerance_mm: float = Query(4.0, description="Tolerance in mm", ge=0)):
    """
    Combined endpoint that calculates both volume and mass for a drawing.
    This is a convenience endpoint that combines the functionality.
    """
    try:
        json_path = os.path.join(OUTPUT_DIR, task_id, f"{task_id}.json")
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=404,
                detail=f"Result file not found for task_id {task_id}"
            )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        components = extract_dimensions_and_calculate_volumes(data, tolerance_mm)
        
        if not components:
            raise HTTPException(
                status_code=422,
                detail="No valid components found for calculations"
            )
        volume_summary = calculate_net_volume(components)
        mass_data = calculate_mass_with_tolerance(components, material_name)

        return {
            "task_id": task_id,
            "calculation_parameters": {
                "material_name": material_name,
                "tolerance_mm": tolerance_mm,
                "density_g_per_mm3": mass_data['density_g_per_mm3']
            },
            "volume_analysis": {
                "components": components,
                "summary": volume_summary
            },
            "mass_analysis": {
                "material_used": mass_data['material_used'],
                "components": mass_data['components'],
                "summary": mass_data['summary']
            },
            "key_results": {
                "net_volume_mm3": volume_summary['nominal_volumes']['net_volume_mm3'],
                "net_volume_with_tolerance_mm3": volume_summary['tolerance_volumes']['net_volume_mm3'],
                "net_mass_grams": mass_data['summary']['nominal_masses']['net_mass_grams'],
                "net_mass_kg": mass_data['summary']['nominal_masses']['net_mass_kg'],
                "net_mass_with_tolerance_grams": mass_data['summary']['tolerance_masses']['net_mass_grams'],
                "net_mass_with_tolerance_kg": mass_data['summary']['tolerance_masses']['net_mass_kg']
            }
        }

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Result file not found for task_id {task_id}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="Invalid JSON data in result file"
        )
    except Exception as e:
        logger.error(f"Combined calculation error for task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Combined calculation failed: {str(e)}"
        )

