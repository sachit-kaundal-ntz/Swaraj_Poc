from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import pdfRouter as pdf_router 
from app.routers import drwaingRouter, groqDrawingRouter
from app.log.logger import setup_logging
from app.routers.volume_router import router as volume_router

setup_logging()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf_router.router)
app.include_router(drwaingRouter.router)
app.include_router(groqDrawingRouter.router)
app.include_router(volume_router)