import os
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.service.VolumeCalculationService import VolumeCalculationService
#from app.service.techinalDrawingService import TechnicalDrawingExtractionService
from app.log.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

volume_service = VolumeCalculationService()
#drawing_service = TechnicalDrawingExtractionService()

OUTPUT_DIR = "outputs/drawings"
from app.dependencies import drawing_service


# ── Request / Response schemas ─────────────────────────────────────────────── #

class VolumeFromDataRequest(BaseModel):
    extracted_data: Dict[str, Any]
    include_bore_subtraction: bool = True


class VolumeResult(BaseModel):
    status: str
    task_id: Optional[str] = None
    filename: Optional[str] = None
    volume_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────── #

@router.get("/volume/{task_id}", response_model=VolumeResult)
async def calculate_volume_for_task(
    task_id: str,
    include_bore_subtraction: bool = Query(True, description="Subtract bore cylinder from volume"),
):
    """
    Calculate gear volume and mass for an already-processed drawing task.

    The task must be in `completed` or `completed_with_errors` status
    (i.e. the JSON output file must exist on disk).
    """
    file_info = drawing_service.get_file_info(task_id)

    if not file_info:
        raise HTTPException(status_code=404, detail="Task not found")

    if file_info["status"] == "processing":
        raise HTTPException(status_code=202, detail="Extraction still in progress — try again shortly")

    json_path = f"{file_info['output_path']}.json"
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Extracted JSON file not found for this task")

    logger.info(f"Computing volume for task {task_id} from {json_path}")
    result = volume_service.calculate_from_json_file(json_path, include_bore_subtraction)

    if result.get("status") == "error":
        return VolumeResult(
            status="error",
            task_id=task_id,
            filename=file_info["original_filename"],
            error=result.get("error"),
        )

    return VolumeResult(
        status="success",
        task_id=task_id,
        filename=file_info["original_filename"],
        volume_result=result,
    )


@router.post("/volume/calculate", response_model=VolumeResult)
async def calculate_volume_from_data(body: VolumeFromDataRequest):
    """
    Calculate gear volume and mass directly from extracted_data JSON payload.

    Pass the `extracted_data` object you received from the `/result/{task_id}`
    endpoint (or from any drawing extraction response) directly in the request body.
    """
    logger.info("Computing volume from inline extracted_data payload")
    result = volume_service.calculate_from_extracted_data(
        body.extracted_data,
        body.include_bore_subtraction,
    )

    if result.get("status") == "error":
        return VolumeResult(status="error", error=result.get("error"))

    return VolumeResult(status="success", volume_result=result)


@router.get("/volume/{task_id}/summary")
async def get_volume_summary(task_id: str):
    """
    Returns a compact summary (mass only + key dims) for quick display.
    """
    file_info = drawing_service.get_file_info(task_id)

    if not file_info:
        raise HTTPException(status_code=404, detail="Task not found")

    if file_info["status"] == "processing":
        raise HTTPException(status_code=202, detail="Extraction still in progress")

    json_path = f"{file_info['output_path']}.json"
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Extracted JSON file not found")

    result = volume_service.calculate_from_json_file(json_path, include_bore_subtraction=True)

    if result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result.get("error"))

    mass = result["mass_calculation"]
    dims = result["dimensions_used"]

    return {
        "task_id": task_id,
        "filename": file_info["original_filename"],
        "calculated_mass_kg": mass["calculated_mass_kg"],
        "calculated_mass_g": mass["calculated_mass_g"],
        "total_volume_cm3": result["volume_summary"]["total_volume_cm3"],
        "material": mass["material"],
        "key_dimensions": {
            "gear_outer_diameter_mm": dims["gear_outer_diameter_mm"],
            "gear_face_width_mm": dims["gear_face_width_mm"],
            "hub_outer_diameter_mm": dims["hub_outer_diameter_mm"],
            "hub_height_mm": dims["hub_height_mm"],
            "bore_diameter_mm": dims["bore_diameter_mm"],
        },
    }

# import os
# import json

# from fastapi import APIRouter, HTTPException, Query
# from pydantic import BaseModel
# from typing import Any, Dict, Optional

# from app.service.VolumeCalculationService import compute_volume
# from app.log.logger import get_logger
# from app.dependencies import drawing_service

# logger = get_logger(__name__)

# router = APIRouter(
#     prefix="/api/google",
#     tags=["GOOGLE Technical Drawings"]
# )

# OUTPUT_DIR = "outputs/drawings"


# # ─────────────────────────────────────────────────────────────────────────────
# # Request / Response schemas
# # ─────────────────────────────────────────────────────────────────────────────

# class VolumeFromDataRequest(BaseModel):
#     extracted_data: Dict[str, Any]


# class VolumeResult(BaseModel):
#     status: str
#     task_id: Optional[str] = None
#     filename: Optional[str] = None
#     volume_result: Optional[Dict[str, Any]] = None
#     error: Optional[str] = None


# # ─────────────────────────────────────────────────────────────────────────────
# # Endpoints
# # ─────────────────────────────────────────────────────────────────────────────

# @router.get("/volume/{task_id}", response_model=VolumeResult)
# async def calculate_volume_for_task(task_id: str):
#     """
#     Calculate volume using extracted JSON from processed drawing task.
#     """

#     file_info = drawing_service.get_file_info(task_id)

#     if not file_info:
#         raise HTTPException(status_code=404, detail="Task not found")

#     if file_info["status"] == "processing":
#         raise HTTPException(
#             status_code=202,
#             detail="Extraction still in progress"
#         )

#     json_path = f"{file_info['output_path']}.json"

#     if not os.path.exists(json_path):
#         raise HTTPException(
#             status_code=404,
#             detail="Extracted JSON file not found"
#         )

#     try:
#         with open(json_path, "r") as f:
#             extracted_data = json.load(f)

#         logger.info(f"Computing volume for task {task_id}")

#         result = compute_volume(extracted_data)

#         return VolumeResult(
#             status="success",
#             task_id=task_id,
#             filename=file_info["original_filename"],
#             volume_result=result,
#         )

#     except Exception as e:
#         logger.exception("Volume calculation failed")

#         return VolumeResult(
#             status="error",
#             task_id=task_id,
#             filename=file_info["original_filename"],
#             error=str(e),
#         )


# @router.post("/volume/calculate", response_model=VolumeResult)
# async def calculate_volume_from_data(body: VolumeFromDataRequest):
#     """
#     Calculate volume directly from extracted_data payload.
#     """

#     try:
#         logger.info("Computing volume from inline extracted_data payload")

#         result = compute_volume(body.extracted_data)

#         return VolumeResult(
#             status="success",
#             volume_result=result
#         )

#     except Exception as e:
#         logger.exception("Inline volume calculation failed")

#         return VolumeResult(
#             status="error",
#             error=str(e)
#         )


# @router.get("/volume/{task_id}/summary")
# async def get_volume_summary(task_id: str):
#     """
#     Compact volume summary endpoint.
#     """

#     file_info = drawing_service.get_file_info(task_id)

#     if not file_info:
#         raise HTTPException(status_code=404, detail="Task not found")

#     if file_info["status"] == "processing":
#         raise HTTPException(
#             status_code=202,
#             detail="Extraction still in progress"
#         )

#     json_path = f"{file_info['output_path']}.json"

#     if not os.path.exists(json_path):
#         raise HTTPException(
#             status_code=404,
#             detail="Extracted JSON file not found"
#         )

#     try:
#         with open(json_path, "r") as f:
#             extracted_data = json.load(f)

#         result = compute_volume(extracted_data)

#         return {
#             "task_id": task_id,
#             "filename": file_info["original_filename"],
#             "net_volume_mm3": result["net_volume_mm3"],
#             "net_volume_cm3": result["net_volume_cm3"],
#             "method": result["method"],
#             "feature_count": len(result["feature_breakdown"]),
#         }

#     except Exception as e:
#         logger.exception("Volume summary failed")

#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )