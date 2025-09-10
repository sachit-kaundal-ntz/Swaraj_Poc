from fastapi import APIRouter,HTTPException,UploadFile,File
from fastapi.responses import JSONResponse
from app.service.processes_form_json_service import identify_manufacturing_processes
import json

router = APIRouter(
    prefix="/ProcessesFormJSON",
    tags=["Processes Form JSON"],
)

@router.post("/identify_processes/")
async def identify_processes(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    try:
        processes = identify_manufacturing_processes(data)
        return JSONResponse(content={"processes": processes})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")