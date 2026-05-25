# # Pydantic models
# from pydantic import BaseModel
# from typing import Optional


# class DrawingUploadResponse(BaseModel):
#     task_id: str
#     filename: str
#     file_size: int
#     status: str
#     message: str

# class DrawingProcessingStatus(BaseModel):
#     task_id: str
#     filename: str
#     status: str
#     created_at: str
#     updated_at: Optional[str] = None
#     file_size: int
#     output_path: Optional[str] = None

# class DrawingProcessingResult(BaseModel):
#     task_id: str
#     filename: str
#     status: str
#     file_size: int
#     has_errors: bool
#     json_path: Optional[str] = None
#     csv_path: Optional[str] = None
#     extracted_data: Optional[dict] = None

# class ErrorResponse(BaseModel):
#     error: str
#     error_type: str
#     task_id: Optional[str] = None

# Update on 25/05/2025

"""
drawingSchema.py
Pydantic schemas for the gear drawing cost estimation API.
Location: app/schemas/drawingSchema.py

Existing models (preserved as-is):
  - DrawingUploadResponse
  - DrawingProcessingStatus
  - DrawingProcessingResult
  - ErrorResponse

Pipeline models (new):
  - AnalyzeDirectRequest
  - MaterialInfo, OperationDetail, CostBreakdown
  - VolumeResult, ValidationRule, ValidationReport
  - PipelineResult
  - AnalyzeDirectResponse, ReportResponse
  - TaskStatusResponse, TaskResultResponse, TaskFullResultResponse
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING MODELS — preserved exactly as written
# ─────────────────────────────────────────────────────────────────────────────

class DrawingUploadResponse(BaseModel):
    task_id:   str
    filename:  str
    file_size: int
    status:    str
    message:   str


class DrawingProcessingStatus(BaseModel):
    task_id:     str
    filename:    str
    status:      str
    created_at:  str
    updated_at:  Optional[str] = None
    file_size:   int
    output_path: Optional[str] = None


class DrawingProcessingResult(BaseModel):
    task_id:        str
    filename:       str
    status:         str
    file_size:      int
    has_errors:     bool
    json_path:      Optional[str]  = None
    csv_path:       Optional[str]  = None
    extracted_data: Optional[dict] = None


class ErrorResponse(BaseModel):
    error:      str
    error_type: str
    task_id:    Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeDirectRequest(BaseModel):
    """
    POST /api/google/analyze-direct
    POST /api/google/report
    POST /api/google/report/markdown

    Supply pre-extracted drawing JSON — no Gemini call, ideal for testing.
    """
    extracted_data: Dict[str, Any] = Field(
        ...,
        description="Gemini-extracted drawing JSON (dimensions, features, tables, …)",
    )
    overhead_pct: float = Field(
        default=15.0, ge=0.0, le=100.0,
        description="Overhead % applied on top of material + operations cost",
    )
    margin_pct: float = Field(
        default=20.0, ge=0.0, le=100.0,
        description="Profit margin % applied on the subtotal",
    )
    currency: str = Field(
        default="INR",
        description="Output currency code (default: INR)",
    )


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE NESTED RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class DimensionsUsed(BaseModel):
    gear_outer_diameter_mm:   Optional[float] = None
    gear_face_width_mm:       Optional[float] = None
    hub_outer_diameter_mm:    Optional[float] = None
    hub_height_mm:            Optional[float] = None
    bore_diameter_mm:         Optional[float] = None
    bore_subtraction_applied: Optional[bool]  = None


class VolumeBreakdownMM3(BaseModel):
    gear_rim_gross_mm3: Optional[float] = None
    hub_gross_mm3:      Optional[float] = None
    bore_cylinder_mm3:  Optional[float] = None
    total_net_mm3:      Optional[float] = None


class VolumeSummary(BaseModel):
    total_volume_mm3:    Optional[float] = None
    total_volume_cm3:    Optional[float] = None
    total_volume_liters: Optional[float] = None


class MassCalculation(BaseModel):
    material:                    Optional[str]   = None
    density_g_per_mm3:           Optional[float] = None
    calculated_mass_g:           Optional[float] = None
    calculated_mass_kg:          Optional[float] = None
    drawing_specified_weight_kg: Optional[float] = None
    weight_difference_percent:   Optional[float] = None


class VolumeResult(BaseModel):
    status:               Optional[str]              = None
    dimensions_used:      Optional[DimensionsUsed]   = None
    volume_breakdown_mm3: Optional[VolumeBreakdownMM3] = None
    volume_summary:       Optional[VolumeSummary]    = None
    mass_calculation:     Optional[MassCalculation]  = None
    calculation_notes:    Optional[List[str]]         = None
    error:                Optional[str]              = None   # None on success


class MaterialInfo(BaseModel):
    matched_material:  Optional[str]   = None
    matched_pattern:   Optional[str]   = None
    density_g_cm3:     Optional[float] = None
    rate_per_kg:       Optional[float] = None   # INR/kg
    net_volume_cm3:    Optional[float] = None
    mass_kg:           Optional[float] = None
    cost:              Optional[float] = None   # INR
    currency:          Optional[str]   = None
    source:            Optional[str]   = None


class OperationDetail(BaseModel):
    step:               int
    operation:          str
    description:        Optional[str]       = None
    estimated_time_min: Optional[float]     = None
    rate_per_hour:      Optional[float]     = None   # INR/hr
    cost:               Optional[float]     = None   # INR
    machine_options:    Optional[List[str]] = None
    source:             Optional[str]       = None


class CostBreakdown(BaseModel):
    material_cost:   float   # INR
    operations_cost: float   # INR
    overhead_pct:    float
    overhead_cost:   float   # INR
    subtotal:        float   # INR
    margin_pct:      float
    margin_cost:     float   # INR
    total_cost:      float   # INR
    currency:        str


class ValidationRule(BaseModel):
    rule_id:  str
    layer:    int
    severity: str   # ERROR | WARN | INFO
    passed:   bool
    message:  str


class ValidationReport(BaseModel):
    validation_passed: bool
    confidence_score:  int
    confidence_level:  str          # HIGH | MEDIUM | LOW
    ready_for_quote:   bool
    error_count:       int
    warn_count:        int
    rules:             List[ValidationRule]


class PipelineResult(BaseModel):
    gear_family:              str
    classification_evidence:  List[str]
    volume:                   Optional[Dict[str, Any]]       = None
    material_info:            Optional[MaterialInfo]         = None
    operations_detail:        Optional[List[OperationDetail]] = None
    cost_breakdown:           Optional[CostBreakdown]        = None
    validation_report:        Optional[ValidationReport]     = None


# ─────────────────────────────────────────────────────────────────────────────
# TOP-LEVEL RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeDirectResponse(BaseModel):
    pipeline_result: PipelineResult


class ReportResponse(BaseModel):
    pipeline_result: PipelineResult
    report:          Dict[str, Any]


class TaskStatusResponse(BaseModel):
    task_id:     str
    status:      str
    created_at:  Optional[str] = None
    error:       Optional[str] = None


class TaskResultResponse(BaseModel):
    task_id:        str
    extracted_data: Optional[Dict[str, Any]] = None


class TaskFullResultResponse(BaseModel):
    task_id:         str
    extracted_data:  Optional[Dict[str, Any]] = None
    pipeline_result: Optional[PipelineResult] = None