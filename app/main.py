# Initializes the FastAPI application.
from fastapi import FastAPI
from app.routers import pdfRouter as pdf_router 
from app.routers import drwaingRouter, groqDrawingRouter, swaraj_route_mapper,gear_manufacturing_wt_calculator
from app.log.logger import setup_logging

setup_logging()
app = FastAPI()

app.include_router(pdf_router.router)
app.include_router(drwaingRouter.router)
app.include_router(groqDrawingRouter.router)
app.include_router(swaraj_route_mapper.router)
app.include_router(gear_manufacturing_wt_calculator.router)