# Initializes the FastAPI application.
from fastapi import FastAPI
from app.routers import pdfRouter as pdf_router 
from app.routers import drwaingRouter, groqDrawingRouter
from app.log.logger import setup_logging
from app.routers import tsa_router

setup_logging()
app = FastAPI()

app.include_router(pdf_router.router)
app.include_router(drwaingRouter.router)
app.include_router(groqDrawingRouter.router)
app.include_router(tsa_router.router)