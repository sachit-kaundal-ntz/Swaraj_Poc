from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from app.database.db import Base
import datetime
 
class DrawingProcessingResult(Base):
    __tablename__ = "drawing_processing_results"
 
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    has_errors = Column(Boolean, default=False)
    json_path = Column(String, nullable=True)
    csv_path = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
 