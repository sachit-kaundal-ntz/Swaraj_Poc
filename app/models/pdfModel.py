from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.database.db import Base
import uuid

class PDFDocument(Base):
    """
    Model for storing PDF document information
    """
    __tablename__ = "pdf_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    task_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    original_filename = Column(String)
    stored_filename = Column(String)
    file_path = Column(String)
    output_path = Column(String)
    total_pages = Column(Integer)
    status = Column(String)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to PageContent
    pages = relationship(
        "PageContent",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class PageContent(Base):
    """
    Model for storing extracted page content
    """
    __tablename__ = "page_contents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("pdf_documents.id", ondelete="CASCADE"))
    page_number = Column(Integer)
    text_content = Column(Text)
    
    document = relationship(
        "PDFDocument",
        back_populates="pages",
        lazy="selectin"
    )
