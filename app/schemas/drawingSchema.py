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