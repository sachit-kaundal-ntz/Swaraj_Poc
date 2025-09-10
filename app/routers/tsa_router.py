from fastapi import APIRouter
from app.schemas.tsa_schemas import InputData, OutputData
from app.service.tsa_service import calculate_surface_area

router = APIRouter(
    prefix="/tsa",
    tags=["Surface Area Calculator"]
)

@router.post("/calculate", response_model=OutputData)
def calculate_tsa(input_data: InputData):
    dimensions = input_data.extracted_data.get("dimensions", [])
    total_surface_area_mm2 = calculate_surface_area(dimensions)

    return {
        "task_id": input_data.task_id,
        "total_surface_area_mm2": total_surface_area_mm2
    }
