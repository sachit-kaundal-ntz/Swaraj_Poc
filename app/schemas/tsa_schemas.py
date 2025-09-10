from pydantic import BaseModel
from typing import Dict, Any

class InputData(BaseModel):
    task_id: str
    filename: str
    status: str
    file_size: int
    has_errors: bool
    json_path: str
    csv_path: str
    extracted_data: Dict[str, Any]

class OutputData(BaseModel):
    task_id: str
    total_surface_area_mm2: float
