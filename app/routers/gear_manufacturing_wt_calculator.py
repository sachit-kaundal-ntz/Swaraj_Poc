from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import tempfile
import shutil
import traceback
from app.log.logger import get_logger
from app.service.gear_manufacturing_wt_calculator_service import *

# Initialize logger for this module
logger = get_logger(__name__)

# Router definition
router = APIRouter(prefix="/api", tags=["Gear Manufacturing Weight Calculator"])


@router.post("/analyze_gear_json")
async def analyze_gear_json(file: UploadFile = File(...)):
    """
    Accepts a gear JSON file, runs complete analysis, and returns structured result.
    """
    logger.info("Received request for gear JSON analysis.")

    # 1. Validate file type
    if not file.filename.endswith(".json"):
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        raise HTTPException(status_code=400, detail="Only .json files are allowed")

    # 2. Save temporarily to disk for processing
    try:
        logger.debug(f"Saving uploaded file '{file.filename}' to temporary location...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        logger.info(f"File '{file.filename}' successfully saved as temp file: {temp_file_path}")
    except Exception as e:
        logger.exception(f"Failed to save uploaded file '{file.filename}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # 3. Run analysis function
    try:
        logger.info(f"Starting gear analysis for file '{file.filename}'...")
        result = load_and_process_complete_analysis(temp_file_path)
        logger.info(f"Gear analysis completed successfully for '{file.filename}'.")
        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        # Capture traceback and log detailed error
        logger.exception(f"Error occurred while analyzing gear JSON file '{file.filename}': {e}")
        error_trace = traceback.format_exc()
        error_response = {
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_trace,
            "status": "calculation_failed"
        }
        return JSONResponse(content=error_response, status_code=500)

    finally:
        try:
            file.file.close()
            logger.debug(f"Closed uploaded file stream for '{file.filename}'.")
        except Exception as close_err:
            logger.warning(f"Error closing file stream for '{file.filename}': {close_err}")
