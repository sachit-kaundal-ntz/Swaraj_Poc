# Defines dependencies used by the routers.
from app.service.techinalDrawingService import TechnicalDrawingExtractionService

# Single shared instance — import this everywhere instead of creating new instances
drawing_service = TechnicalDrawingExtractionService()