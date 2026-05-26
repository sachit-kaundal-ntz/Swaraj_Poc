
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.dependencies import drawing_service
from app.log.logger import get_logger
from app.schemas.drawingSchema import (
    AnalyzeDirectRequest,
    DrawingProcessingResult,
    DrawingProcessingStatus,
    DrawingUploadResponse,
    ErrorResponse,
)
from app.service.pipeline_service import run_full_pipeline

logger = get_logger(__name__)

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/google", tags=["GOOGLE Technical Drawings"])

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_DIR         = "uploads/drawings"
OUTPUT_DIR         = "outputs/drawings"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
MAX_FILE_SIZE      = 10 * 1024 * 1024   # 10 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def validate_image_file(file: UploadFile) -> bool:
    """Validate uploaded image file."""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False
    if hasattr(file, "size") and file.size > MAX_FILE_SIZE:
        return False
    return True


async def process_drawing_background(task_id: str, file_path: str, output_dir: str):
    """Background task to process technical drawing via drawing_service."""
    try:
        result = await drawing_service.process_image_file(task_id, file_path, output_dir)
        logger.info(f"Background processing completed for task: {task_id}")
        return result
    except Exception as e:
        logger.error(f"Background processing failed for task {task_id}: {str(e)}")
        drawing_service.update_file_status(task_id, "failed")


def _load_extracted_data(task_id: str) -> Optional[dict]:
    """
    Read the Gemini-extracted JSON saved to disk by drawing_service.
    Returns None if the file doesn't exist or can't be parsed.
    """
    file_info = drawing_service.get_file_info(task_id)
    if not file_info:
        return None
    json_path = f"{file_info['output_path']}.json"
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        return result_data.get("extracted_data", result_data)
    except Exception as e:
        logger.warning(f"Could not read extracted_data for task {task_id}: {e}")
        return None


def _build_ui_report(pipeline_result: dict, extracted_data: dict) -> dict:
    """Build the structured 6-section UI report dict (all costs in INR)."""
    tb  = (extracted_data.get("metadata") or {}).get("title_block", {})
    cb  = pipeline_result.get("cost_breakdown", {})
    val = pipeline_result.get("validation_report", {})
    mat = pipeline_result.get("material_info", {})

    return {
        "section_1_drawing_info": {
            "part_name":   tb.get("part_name",  "N/A"),
            "drawing_no":  tb.get("drawing_no", "N/A"),
            "material":    mat.get("matched_material", "N/A"),
            "gear_family": pipeline_result.get("gear_family", "N/A"),
        },
        "section_2_volume":        pipeline_result.get("volume", {}),
        "section_3_material_cost": mat,
        "section_4_operations":    pipeline_result.get("operations_detail", []),
        "section_5_cost_breakdown": {
            **cb,
            "summary": (
                f"Material: ₹{cb.get('material_cost', 0):.2f} | "
                f"Operations: ₹{cb.get('operations_cost', 0):.2f} | "
                f"Overhead ({cb.get('overhead_pct', 0)}%): ₹{cb.get('overhead_cost', 0):.2f} | "
                f"Margin ({cb.get('margin_pct', 0)}%): ₹{cb.get('margin_cost', 0):.2f} | "
                f"TOTAL: ₹{cb.get('total_cost', 0):.2f}"
            ),
        },
        "section_6_validation": val,
    }


def _build_markdown_report(pipeline_result: dict, extracted_data: dict) -> str:
    """Build a Markdown-formatted report string (all costs in INR)."""
    tb  = (extracted_data.get("metadata") or {}).get("title_block", {})
    cb  = pipeline_result.get("cost_breakdown", {})
    val = pipeline_result.get("validation_report", {})
    ops = pipeline_result.get("operations_detail", [])
    mat = pipeline_result.get("material_info", {})
    vol = pipeline_result.get("volume", {})

    lines = [
        "# Gear Drawing Cost Estimation Report",
        "",
        f"**Part:** {tb.get('part_name', 'N/A')}  |  "
        f"**Drawing No:** {tb.get('drawing_no', 'N/A')}",
        f"**Gear Family:** {pipeline_result.get('gear_family', 'N/A')}  |  "
        f"**Material:** {mat.get('matched_material', 'N/A')}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Section 1 — Drawing Info",
        f"- Part Name   : {tb.get('part_name',  'N/A')}",
        f"- Drawing No  : {tb.get('drawing_no', 'N/A')}",
        f"- Gear Family : {pipeline_result.get('gear_family', 'N/A')}",
        f"- Material    : {mat.get('matched_material', 'N/A')}",
        "",
        "## Section 2 — Volume & Mass",
        f"- Net Volume  : {(vol.get('volume_summary') or {}).get('total_volume_cm3', 'N/A')} cm³",
        f"- Mass (calc) : {mat.get('mass_kg', 'N/A')} kg",
        "",
        "## Section 3 — Material Cost",
        f"- Density     : {mat.get('density_g_cm3', 'N/A')} g/cm³",
        f"- Rate        : ₹{mat.get('rate_per_kg', 'N/A')}/kg",
        f"- **Material Cost: ₹{mat.get('cost', 'N/A')}**",
        "",
        "## Section 4 — Operations",
        "",
        "| Step | Operation | Time (min) | Rate (₹/hr) | Cost (₹) | Source |",
        "|:----:|-----------|:----------:|:-----------:|:--------:|--------|",
    ]

    for op in ops:
        lines.append(
            f"| {op['step']} | {op['operation']} | {op.get('estimated_time_min', '—')} | "
            f"₹{op.get('rate_per_hour', 0):.0f} | ₹{op.get('cost', 0):.2f} | {op.get('source', '—')} |"
        )

    lines += [
        "",
        "## Section 5 — Cost Breakdown",
        "",
        "| Item | Amount (₹) |",
        "|------|:----------:|",
        f"| Material Cost | ₹{cb.get('material_cost',   0):.2f} |",
        f"| Operations Cost | ₹{cb.get('operations_cost', 0):.2f} |",
        f"| Overhead ({cb.get('overhead_pct', 0)}%) | ₹{cb.get('overhead_cost', 0):.2f} |",
        f"| **Subtotal** | **₹{cb.get('subtotal',      0):.2f}** |",
        f"| Margin ({cb.get('margin_pct', 0)}%) | ₹{cb.get('margin_cost',    0):.2f} |",
        f"| **TOTAL** | **₹{cb.get('total_cost',       0):.2f}** |",
        "",
        "## Section 6 — Validation",
        "",
        f"- Confidence Score : **{val.get('confidence_score', 'N/A')}** "
        f"({val.get('confidence_level', 'N/A')})",
        f"- Ready for Quote  : {'✅ YES' if val.get('ready_for_quote') else '❌ NO'}",
        f"- Errors  : {val.get('error_count', 0)}",
        f"- Warnings: {val.get('warn_count',  0)}",
        "",
        "### Validation Rules",
        "",
        "| Rule | Layer | Severity | Passed | Message |",
        "|------|:-----:|:--------:|:------:|---------|",
    ]

    for rule in val.get("rules", []):
        status = "✓" if rule.get("passed") else "✗"
        lines.append(
            f"| {rule['rule_id']} | {rule['layer']} | {rule['severity']} | "
            f"{status} | {rule['message']} |"
        )

    lines += ["", "---", "*GearForge AI Cost Estimation — All amounts in INR*"]
    return "\n".join(lines)


# =============================================================================
# EXISTING ENDPOINTS — preserved exactly
# =============================================================================

@router.post("/upload", response_model=DrawingUploadResponse)
async def upload_technical_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a technical drawing/engineering diagram for processing."""
    try:
        if not validate_image_file(file):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid file. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. "
                    f"Max size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                ),
            )

        task_id = str(uuid.uuid4())

        content   = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE / 1024 / 1024}MB",
            )

        file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        task_output_dir = os.path.join(OUTPUT_DIR, task_id)

        background_tasks.add_task(
            process_drawing_background, task_id, file_path, task_output_dir
        )

        logger.info(f"Technical drawing uploaded successfully: {file.filename}, Task ID: {task_id}")

        return DrawingUploadResponse(
            task_id=task_id,
            filename=file.filename,
            file_size=file_size,
            status="processing",
            message="Technical drawing uploaded successfully and is being processed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading technical drawing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{task_id}", response_model=DrawingProcessingStatus)
async def get_processing_status(task_id: str):
    """Get the processing status of a technical drawing."""
    try:
        file_info = drawing_service.get_file_info(task_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        return DrawingProcessingStatus(
            task_id=file_info["task_id"],
            filename=file_info["original_filename"],
            status=file_info["status"],
            created_at=file_info["created_at"],
            updated_at=file_info.get("updated_at"),
            file_size=file_info["file_size"],
            output_path=file_info.get("output_path"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/result/{task_id}", response_model=DrawingProcessingResult)
async def get_processing_result(
    task_id: str,
    include_data: bool = Query(True, description="Include extracted data in response"),
):
    """Get the processing result of a technical drawing."""
    try:
        file_info = drawing_service.get_file_info(task_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        if file_info["status"] == "processing":
            raise HTTPException(status_code=202, detail="Processing still in progress")

        json_path = f"{file_info['output_path']}.json"

        extracted_data = None
        if include_data and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
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
            json_path=json_path if os.path.exists(json_path) else None,
            extracted_data=extracted_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting result for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Result retrieval failed: {str(e)}")


@router.get("/download/{task_id}/json")
async def download_json_result(task_id: str):
    """Download the JSON result file for a processed technical drawing."""
    try:
        file_info = drawing_service.get_file_info(task_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        json_path = f"{file_info['output_path']}.json"

        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail="JSON result file not found")

        return FileResponse(
            json_path,
            media_type="application/json",
            filename=f"drawing_analysis_{task_id}.json",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading JSON for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/list", response_model=List[DrawingProcessingStatus])
async def list_processed_drawings(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
):
    """List all processed technical drawings."""
    try:
        all_files = drawing_service.get_all_processed_files()

        file_list = []
        for task_id, file_info in all_files.items():
            if status is None or file_info["status"] == status:
                file_list.append(
                    DrawingProcessingStatus(
                        task_id=file_info["task_id"],
                        filename=file_info["original_filename"],
                        status=file_info["status"],
                        created_at=file_info["created_at"],
                        updated_at=file_info.get("updated_at"),
                        file_size=file_info["file_size"],
                        output_path=file_info.get("output_path"),
                    )
                )

        file_list.sort(key=lambda x: x.created_at, reverse=True)
        return file_list[:limit]

    except Exception as e:
        logger.error(f"Error listing drawings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"List retrieval failed: {str(e)}")


@router.delete("/delete/{task_id}")
async def delete_processed_drawing(task_id: str):
    """Delete a processed technical drawing and its files."""
    try:
        file_info = drawing_service.get_file_info(task_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        files_to_delete = [
            file_info["file_path"],
            f"{file_info['output_path']}.json",
        ]

        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")

        output_dir = os.path.dirname(file_info["output_path"])
        try:
            if os.path.exists(output_dir) and not os.listdir(output_dir):
                os.rmdir(output_dir)
        except OSError:
            pass

        drawing_service.delete_file_info(task_id)

        return {"message": f"Technical drawing {task_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for the technical drawing service."""
    try:
        total_files = len(drawing_service.get_all_processed_files())

        return {
            "status":               "healthy",
            "service":              "Technical Drawing Extraction Service",
            "timestamp":            datetime.now().isoformat(),
            "total_processed_files": total_files,
            "upload_directory":     UPLOAD_DIR,
            "output_directory":     OUTPUT_DIR,
            "allowed_extensions":   list(ALLOWED_EXTENSIONS),
            "max_file_size_mb":     MAX_FILE_SIZE / 1024 / 1024,
            "pipeline_currency":    "INR",
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status":    "unhealthy",
            "service":   "Technical Drawing Extraction Service",
            "timestamp": datetime.now().isoformat(),
            "error":     str(e),
        }


@router.post("/batch-upload", response_model=List[DrawingUploadResponse])
async def batch_upload_drawings(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """Upload multiple technical drawings for batch processing (max 10)."""
    try:
        if len(files) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed in batch upload",
            )

        responses = []

        for file in files:
            try:
                if not validate_image_file(file):
                    responses.append(
                        DrawingUploadResponse(
                            task_id="",
                            filename=file.filename,
                            file_size=0,
                            status="failed",
                            message=f"Invalid file format or size: {file.filename}",
                        )
                    )
                    continue

                task_id = str(uuid.uuid4())
                content   = await file.read()
                file_size = len(content)

                if file_size > MAX_FILE_SIZE:
                    responses.append(
                        DrawingUploadResponse(
                            task_id="",
                            filename=file.filename,
                            file_size=file_size,
                            status="failed",
                            message=f"File too large: {file.filename}",
                        )
                    )
                    continue

                file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
                with open(file_path, "wb") as f:
                    f.write(content)

                task_output_dir = os.path.join(OUTPUT_DIR, task_id)

                background_tasks.add_task(
                    process_drawing_background, task_id, file_path, task_output_dir
                )

                responses.append(
                    DrawingUploadResponse(
                        task_id=task_id,
                        filename=file.filename,
                        file_size=file_size,
                        status="processing",
                        message="File uploaded successfully and is being processed",
                    )
                )

                await file.seek(0)

            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                responses.append(
                    DrawingUploadResponse(
                        task_id="",
                        filename=file.filename,
                        file_size=0,
                        status="failed",
                        message=f"Processing error: {str(e)}",
                    )
                )

        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@router.get("/stats")
async def get_processing_stats():
    """Get processing statistics."""
    try:
        all_files = drawing_service.get_all_processed_files()

        stats = {
            "total_files":           len(all_files),
            "completed":             0,
            "processing":            0,
            "failed":                0,
            "completed_with_errors": 0,
            "total_size_mb":         0,
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
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.post("/reprocess/{task_id}")
async def reprocess_drawing(task_id: str, background_tasks: BackgroundTasks):
    """Reprocess a technical drawing."""
    try:
        file_info = drawing_service.get_file_info(task_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        if not os.path.exists(file_info["file_path"]):
            raise HTTPException(status_code=404, detail="Original file not found")

        drawing_service.update_file_status(task_id, "processing")

        task_output_dir = os.path.join(OUTPUT_DIR, task_id)

        background_tasks.add_task(
            process_drawing_background,
            task_id,
            file_info["file_path"],
            task_output_dir,
        )

        return {
            "message": f"Reprocessing started for task {task_id}",
            "task_id": task_id,
            "status":  "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")


# =============================================================================
# NEW PIPELINE ENDPOINTS
# =============================================================================

@router.post("/analyze-direct")
def analyze_direct(request: AnalyzeDirectRequest):
    """
    Run the complete 6-step cost estimation pipeline on an already-extracted
    drawing JSON. No Gemini call — use for testing or when the caller already
    has the extracted_data. All costs returned in INR.
    """
    try:
        result = run_full_pipeline(
            extracted_data=request.extracted_data,
            overhead_pct=request.overhead_pct,
            margin_pct=request.margin_pct,
            currency=request.currency,
        )
        return {"pipeline_result": result}
    except Exception as e:
        logger.error(f"Pipeline error in analyze-direct: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report")
def generate_report(request: AnalyzeDirectRequest):
    """
    Run the full pipeline + return a structured 6-section UI report alongside
    the raw pipeline result. All costs in INR.
    """
    try:
        result = run_full_pipeline(
            extracted_data=request.extracted_data,
            overhead_pct=request.overhead_pct,
            margin_pct=request.margin_pct,
            currency=request.currency,
        )
        report = _build_ui_report(result, request.extracted_data)
        return {"pipeline_result": result, "report": report}
    except Exception as e:
        logger.error(f"Pipeline error in report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/report/markdown",
    response_class=PlainTextResponse,
)
def generate_markdown_report(request: AnalyzeDirectRequest):
    """
    Same as /report but returns a Markdown document suitable for download
    or email. All costs in INR.
    """
    try:
        result = run_full_pipeline(
            extracted_data=request.extracted_data,
            overhead_pct=request.overhead_pct,
            margin_pct=request.margin_pct,
            currency=request.currency,
        )
        md = _build_markdown_report(result, request.extracted_data)
        return PlainTextResponse(content=md, media_type="text/markdown")
    except Exception as e:
        logger.error(f"Pipeline error in report/markdown: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-result/{task_id}")
async def get_full_pipeline_result(
    task_id: str,
    overhead_pct: float = Query(15.0, ge=0, le=100, description="Overhead %"),
    margin_pct:   float = Query(20.0, ge=0, le=100, description="Margin %"),
):
    """
    For a completed upload task: load the saved Gemini extraction from disk
    and run the full 6-step pipeline on it. Returns extracted_data + full
    pipeline result (all costs in INR).
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        if file_info["status"] == "processing":
            raise HTTPException(status_code=202, detail="Processing still in progress")

        if file_info["status"] == "failed":
            raise HTTPException(status_code=500, detail="Task processing failed")

        extracted_data = _load_extracted_data(task_id)
        if extracted_data is None:
            raise HTTPException(
                status_code=404,
                detail="Extracted data not found on disk — has the task completed successfully?",
            )

        pipeline_result = run_full_pipeline(
            extracted_data=extracted_data,
            overhead_pct=overhead_pct,
            margin_pct=margin_pct,
            currency="INR",
        )

        return {
            "task_id":         task_id,
            "extracted_data":  extracted_data,
            "pipeline_result": pipeline_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline error in full-result for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{task_id}")
async def get_task_report(
    task_id: str,
    overhead_pct: float = Query(15.0, ge=0, le=100, description="Overhead %"),
    margin_pct:   float = Query(20.0, ge=0, le=100, description="Margin %"),
):
    """
    For a completed upload task: run the full pipeline and return the
    structured 6-section UI report. All costs in INR.
    """
    try:
        file_info = drawing_service.get_file_info(task_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Task not found")

        if file_info["status"] == "processing":
            raise HTTPException(status_code=202, detail="Processing still in progress")

        if file_info["status"] == "failed":
            raise HTTPException(status_code=500, detail="Task processing failed")

        extracted_data = _load_extracted_data(task_id)
        if extracted_data is None:
            raise HTTPException(
                status_code=404,
                detail="Extracted data not found on disk — has the task completed successfully?",
            )

        pipeline_result = run_full_pipeline(
            extracted_data=extracted_data,
            overhead_pct=overhead_pct,
            margin_pct=margin_pct,
            currency="INR",
        )
        report = _build_ui_report(pipeline_result, extracted_data)

        return {
            "task_id":         task_id,
            "pipeline_result": pipeline_result,
            "report":          report,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline error in report/{task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))