# app/schema/pdfschema.py (updated)
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID

# ---------------------
# Core Response Models
# ---------------------

class ExtractionResponse(BaseModel):
    """Basic response after file upload."""
    task_id: Optional[UUID] = None  
    filename: str
    status: str
    message: str

class ExtractionStatus(BaseModel):
    """Returned when checking processing status."""
    task_id: UUID
    status: str
    output_path: Optional[str] = None
    message: str

class ExtractionSummary(BaseModel):
    """Returned when extraction is complete with summary."""
    task_id: UUID
    source_pdf: str
    filename: str
    total_pages: int
    output_file: str

# ---------------------
# Content Response Models
# ---------------------

class ExtractionContentResponse(BaseModel):
    """Response model for content endpoint with format options"""
    task_id: UUID
    filename: str
    format: str  # 'json' or 'csv'
    content: Optional[Dict] = None  # For JSON response
    download_url: Optional[str] = None  # For CSV download
    status: str

# ---------------------
# Page Content Models
# ---------------------

class PageContentBase(BaseModel):
    page_number: int
    text_content: str

class PageContentCreate(PageContentBase):
    pass

class PageContent(PageContentBase):
    id: UUID
    document_id: UUID
    class Config:
        from_attributes = True

# ---------------------
# PDF Document Models
# ---------------------

class PDFDocumentBase(BaseModel):
    original_filename: str
    task_id: UUID

class PDFDocumentCreate(PDFDocumentBase):
    stored_filename: str
    file_path: str
    output_path: str
    total_pages: int
    status: str

class PDFDocumentUpdate(BaseModel):
    status: Optional[str] = None
    total_pages: Optional[int] = None

class PDFDocument(PDFDocumentBase):
    stored_filename: str
    file_path: str
    output_path: Optional[str] = None
    total_pages: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    pages: List[PageContent] = []
    class Config:
        from_attributes = True