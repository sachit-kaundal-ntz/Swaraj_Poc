# Initializes the FastAPI application.
from fastapi import FastAPI
from app.routers import drwaingRouter
from app.log.logger import setup_logging

setup_logging()
app = FastAPI()

app.include_router(drwaingRouter.router)
