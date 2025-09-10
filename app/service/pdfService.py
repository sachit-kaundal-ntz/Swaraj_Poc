
import os
import uuid
import json
import csv
import pdfplumber
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional, Any
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.pdfModel import PDFDocument, PageContent
from app.log.logger import get_logger

logger = get_logger(__name__)
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-pro')

class PDFExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def clean_text(self, text: str) -> str:
        """Remove non-UTF-8 characters and null bytes from text"""
        if not text:
            return ""
        
        text = text.replace('\x00', '')
        
        try:
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            text = text.encode('ascii', errors='ignore').decode('ascii')
        
        return text.strip()

    async def upload_pdf_to_gemini(self, pdf_path: str) -> Any:
        """Upload PDF file to Gemini using simple path-based upload"""
        try:
            logger.info(f"Uploading PDF file to Gemini: {pdf_path}")
            
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
                
            file_size = os.path.getsize(pdf_path)
            if file_size == 0:
                raise ValueError("PDF file is empty")
                
            uploaded_file = genai.upload_file(pdf_path)
            logger.info(f"Successfully uploaded file to Gemini")
            return uploaded_file
            
        except Exception as e:
            logger.error(f"Failed to upload PDF to Gemini: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"PDF upload failed: {str(e)}")

    async def extract_invoice_data_direct(self, pdf_path: str) -> Dict:
        """Extract invoice data directly from PDF using Gemini"""
        try:
            logger.info(f"Starting direct PDF extraction for: {pdf_path}")
            
            PROMPT = """
                You are an expert invoice extraction system. Given the content of an invoice (which may vary in format and language), your task is to extract all relevant data and return a clean, structured JSON.

                Instructions:
                1. Handle invoices from different vendors, each having different layouts and terminology.
                2. Extract all available invoice fields, including metadata, totals, charges, taxes, and payment details.
                3. Be flexible with keys—extract what is present in the invoice and skip what's missing.
                4. Group related data together clearly (e.g., totals, payment, customer, company, charges).
                5. If line items exist, represent them as a list of dictionaries under `"line_items"`.

                ### Output JSON Format (Example Structure):

                {
                "metadata": {
                    "company_name": "",
                    "company_address": "",
                    "company_gstin": "",
                    "invoice_number": "",
                    "invoice_date": "",
                    "due_date": "",
                    "purchase_order": "",
                    "customer_name": "",
                    "customer_address": "",
                    "customer_gstin": "",
                    "place_of_supply": "",
                    "state_code": ""
                },
                "line_items": [
                    {
                    "description": "",
                    "quantity": "",
                    "unit_price": "",
                    "rate_type": "",
                    "amount": "",
                    "hsn_sac": "",
                    "taxable_value": "",
                    "cgst_rate": "",
                    "cgst_amount": "",
                    "sgst_rate": "",
                    "sgst_amount": "",
                    "igst_rate": "",
                    "igst_amount": "",
                    "total": ""
                    }
                ],
                "totals": {
                    "subtotal": "",
                    "cgst_total": "",
                    "sgst_total": "",
                    "igst_total": "",
                    "discount": "",
                    "round_off": "",
                    "total_amount": "",
                    "amount_in_words": ""
                },
                "payment_details": {
                    "bank_name": "",
                    "account_number": "",
                    "ifsc_code": "",
                    "payment_terms": "",
                    "remittance_email": ""
                },
                "notes": [
                    "..."
                ]
                }

                Strict Rules:
                - Return only valid JSON, don't add any extra content or markdown.
                - Omit any fields that are not found in the invoice.
                - Preserve all numeric fields as strings without currency symbols.
                - Do not include any explanations or markdown.
                - If certain fields are handwritten or unclear, try to interpret them accurately.
                """
            uploaded_file = await self.upload_pdf_to_gemini(pdf_path)
            
            response = model.generate_content(
                [PROMPT, uploaded_file],
                generation_config={"temperature": 0.1}
            )
            response_text = response.text.strip()
            
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            parsed_data = json.loads(response_text)
            logger.info("Successfully parsed JSON response from Gemini")
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response text: {response_text[:1000]}...")
            return {
                "error": f"Invalid JSON response from AI model: {str(e)}",
                "metadata": {},
                "line_items": [],
                "totals": {},
                "payment_details": {}
            }
        except Exception as e:
            logger.error(f"Direct PDF extraction failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "error": str(e),
                "file": os.path.basename(pdf_path)
            }

    async def process_all_data(self, data: Dict, filename: str) -> List[Dict]:
        """Process all data into a single flat structure for CSV output"""
        try:
            logger.info(f"Processing data for CSV output: {filename}")
            
            metadata = data.get("metadata", {})
            payment_details = data.get("payment_details", {})
            totals = data.get("totals", {})
            
            all_fields = {
                "Filename": filename,
                "Company": metadata.get("company_name", ""),
                "Invoice Number": metadata.get("invoice_number", ""),
                "Invoice Date": metadata.get("invoice_date", ""),
                "Customer Name": metadata.get("customer_name", ""),
                "Customer Address": metadata.get("customer_address", ""),
                "Payment Terms": payment_details.get("payment_terms", ""),
                "Bank Name": payment_details.get("bank_name", ""),
                "Account Number": payment_details.get("account_number", ""),
                "Subtotal": totals.get("subtotal", ""),
                "Tax Total": totals.get("cgst_total", ""),
                "Invoice Total": totals.get("total_amount", ""),
                "Remittance Email": payment_details.get("remittance_email", ""),
                "Notes": "\n".join(data.get("notes", [])),
                "Record Type": "Metadata",
                
                "Description": "",
                "Quantity": "",
                "Unit Price": "",
                "Amount": "",
                "HSN/SAC": "",
                "Tax Rate": "",
                "Tax Amount": "",
                "Total": ""
            }
            
            base_record = all_fields.copy()
            line_item_records = []
            
            for item in data.get("line_items", []):
                record = base_record.copy()
                record.update({
                    "Record Type": "Line Item",
                    "Description": item.get("description", ""),
                    "Quantity": item.get("quantity", ""),
                    "Unit Price": item.get("unit_price", ""),
                    "Amount": item.get("amount", ""),
                    "HSN/SAC": item.get("hsn_sac", ""),
                    "Tax Rate": item.get("cgst_rate", ""),
                    "Tax Amount": item.get("cgst_amount", ""),
                    "Total": item.get("total", "")
                })
                line_item_records.append(record)
            
            logger.info(f"Processed {len(line_item_records)} line items")
            return [base_record] + line_item_records
            
        except Exception as e:
            logger.error(f"Data processing error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [{
                "Filename": filename,
                "Error": f"Data processing error: {str(e)}",
                "Record Type": "Error"
            }]

    async def process_pdf_file(
        self,
        task_id: str,
        file_path: str,
        output_dir: str
    ) -> Dict:
        """Process PDF file using direct Gemini extraction"""
        try:
            logger.info(f"Starting PDF processing for task: {task_id}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"PDF file not found: {file_path}")
                
            file_size = os.path.getsize(file_path)
            logger.info(f"File size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError("PDF file is empty")
                
            os.makedirs(output_dir, exist_ok=True)
            base_filename = os.path.join(output_dir, task_id)
            
            pdf_document = PDFDocument(
                task_id=uuid.UUID(task_id),
                original_filename=os.path.basename(file_path),
                stored_filename=f"{task_id}_{os.path.basename(file_path)}",
                file_path=file_path,
                output_path=base_filename,
                status="processing",
                total_pages=0
            )
            self.db.add(pdf_document)
            await self.db.commit()
            await self.db.refresh(pdf_document)
            
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                pdf_document.total_pages = total_pages
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        text = page.extract_text() or ""
                        cleaned_text = self.clean_text(text)
                        page_content = PageContent(
                            document_id=pdf_document.id,
                            page_number=page_num,
                            text_content=cleaned_text
                        )
                        self.db.add(page_content)
                    except Exception as page_error:
                        logger.error(f"Error processing page {page_num}: {str(page_error)}")
                        continue
            
            await self.db.commit()
            
            extracted_data = await self.extract_invoice_data_direct(file_path)
            
            pdf_document.status = "completed" if "error" not in extracted_data else "completed_with_errors"
            await self.db.commit()
            
            json_output = {
                "task_id": task_id,
                "filename": os.path.basename(file_path),
                "file_size": file_size,
                "extracted_data": extracted_data,
                "status": pdf_document.status,
                "timestamp": datetime.now().isoformat()
            }
            
            json_file_path = f"{base_filename}.json"
            with open(json_file_path, "w", encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON output saved to: {json_file_path}")
            
            csv_file_path = f"{base_filename}.csv"
            processed_data = await self.process_all_data(extracted_data, os.path.basename(file_path))
            
            if processed_data and len(processed_data) > 0:
                with open(csv_file_path, "w", newline="", encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=processed_data[0].keys())
                    writer.writeheader()
                    writer.writerows(processed_data)
                logger.info(f"CSV output saved to: {csv_file_path}")
            
            return {
                "status": pdf_document.status,
                "output_path": base_filename,
                "total_pages": total_pages,
                "file_size": file_size,
                "has_errors": "error" in extracted_data
            }
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"File not found: {str(e)}",
                "error_type": "file_not_found"
            }
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"Invalid file or data: {str(e)}",
                "error_type": "invalid_data"
            }
        except Exception as e:
            logger.error(f"Unexpected error in PDF processing: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "status": "failed",
                "error": f"Processing error: {str(e)}",
                "error_type": "processing_error"
            }

    async def create_pdf_document(
        self,
        task_id: str,
        original_filename: str,
        stored_filename: str,
        file_path: str,
        output_path: str,
        total_pages: int,
        status: str
    ) -> PDFDocument:
        """Create a new PDF document record in the database"""
        try:
            pdf_document = PDFDocument(
                task_id=uuid.UUID(task_id),
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                output_path=output_path,
                total_pages=total_pages,
                status=status
            )
            self.db.add(pdf_document)
            await self.db.commit()
            await self.db.refresh(pdf_document)
            return pdf_document
        except Exception as e:
            logger.error(f"Error creating PDF document: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_pdf_document(self, task_id: str) -> Optional[PDFDocument]:
        """Retrieve a PDF document by task ID"""
        try:
            result = await self.db.execute(
                select(PDFDocument).where(PDFDocument.task_id == uuid.UUID(task_id))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving PDF document: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def update_pdf_document(
        self,
        task_id: str,
        status: Optional[str] = None,
        total_pages: Optional[int] = None
    ) -> Optional[PDFDocument]:
        """Update a PDF document's status and/or total pages"""
        try:
            pdf_document = await self.get_pdf_document(task_id)
            if not pdf_document:
                return None
                
            if status:
                pdf_document.status = status
            if total_pages:
                pdf_document.total_pages = total_pages
                
            await self.db.commit()
            await self.db.refresh(pdf_document)
            return pdf_document
        except Exception as e:
            logger.error(f"Error updating PDF document: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None