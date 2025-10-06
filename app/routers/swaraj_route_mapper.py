from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
from app.schemas.drawingSchema import (
    DrawingProcessingResult,
    DrawingProcessingStatus,
    DrawingUploadResponse,
    ErrorResponse,
)
from app.service.swaraj_route_mapper_services import map_operations
from app.log.logger import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Router definition
router = APIRouter(prefix="/api", tags=["Swaraj Route Mapper (machine operations)"])


@router.post("/map_route_upload_file")
async def map_route_file(file: UploadFile = File(...)):
    """
    Accept a JSON file containing extracted part data and map it to operations & machines.

    Parameters:
    - file: JSON file upload (extracted part data)

    Returns:
    - route_operations: List of operations with machines, reason, confidence
    - sequence: Ordered operation names
    - machine_pool: Unique list of suggested machines
    - notes: Part summary (material, OD, module, teeth, internal spline)
    """
    logger.info("Received request for route mapping.")

    # Validate file type
    if file.content_type != "application/json":
        logger.warning(f"Invalid file type uploaded: {file.content_type}")
        raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")

    try:
        logger.debug("Reading uploaded file contents...")
        contents = await file.read()
        part_data: Dict[str, Any] = json.loads(contents)
        logger.info(f"File '{file.filename}' successfully parsed. Starting route mapping.")

        # Perform route mapping
        result = map_operations(part_data)
        logger.info(
            f"Route mapping successful for file '{file.filename}'. "
            f"Total operations mapped: {len(result.get('route_operations', []))}"
        )

        return result

    except json.JSONDecodeError as json_err:
        logger.error(f"Invalid JSON file uploaded: {file.filename} | Error: {json_err}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON file.")

    except Exception as e:
        logger.exception(f"Route mapping failed for file '{file.filename}': {e}")
        raise HTTPException(status_code=500, detail=f"Route mapping failed: {e}")
