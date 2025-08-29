# Pydantic models
from pydantic import BaseModel
from typing import Optional


class DrawingUploadResponse(BaseModel):
    task_id: str
    filename: str
    file_size: int
    status: str
    message: str

class DrawingProcessingStatus(BaseModel):
    task_id: str
    filename: str
    status: str
    created_at: str
    updated_at: Optional[str] = None
    file_size: int
    output_path: Optional[str] = None

class DrawingProcessingResult(BaseModel):
    task_id: str
    filename: str
    status: str
    file_size: int
    has_errors: bool
    json_path: Optional[str] = None
    csv_path: Optional[str] = None
    extracted_data: Optional[dict] = None

class ErrorResponse(BaseModel):
    error: str
    error_type: str
    task_id: Optional[str] = None

class MassCalculationRequest(BaseModel):
    material_name: Optional[str] = "20MnCr5"
    tolerance_mm: Optional[float] = 4.0

class MaterialInfo(BaseModel):
    name: str
    density_g_per_mm3: float
    density_g_per_cm3: float
    density_kg_per_m3: float

class SimpleMassResponse(BaseModel):
    message: str
    total_mass_grams: float
    total_mass_kg: float
    material: str
    net_volume_with_tolerance_mm3: float