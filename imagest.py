import os
import uuid
import json
import csv
import traceback
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, List, Optional, Any
from PIL import Image
import streamlit as st
import pandas as pd

# Set page config
st.set_page_config(
    page_title="Vehicle Assembly Extractor",
    page_icon="🚗",
    layout="wide"
)

# Load environment variables
load_dotenv()

# Ensure the Google API key is provided
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error(
        "GOOGLE_API_KEY is not set.\n"
        "Please set your Google API key in environment variables or Streamlit secrets."
    )
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

class VehicleAssemblyExtractor:
    def __init__(self):
        self.processed_files = {}  
    
    def extract_vehicle_assembly_data(self, image_path: str) -> Dict:
        """Extract ONLY visible vehicle assembly information from image"""
        try:
            PROMPT = """
            You are analyzing a vehicle assembly diagram. Extract ONLY the exact text visible in the image.
            
            CRITICAL RULES:
            1. Extract ONLY text that is actually visible in the image
            2. DO NOT add any interpretations, categories, or connections
            3. DO NOT create IDs, positions, or spatial data
            4. DO NOT group components into assemblies or systems
            5. DO NOT infer any relationships
            6. DO NOT add any descriptive text or explanations
            7. If something says "Type", extract it exactly as shown
            8. If the same component appears multiple times (like "Leaf spring"), list each occurrence separately
            9. Do NOT add dimensions if they are not visible in the image
            
            OUTPUT FORMAT:
            Return a JSON object with this exact structure:
            {
                "extracted_text": [
                    {
                        "text": "Exact text as it appears in the image",
                        "location": "general area where text appears (e.g., top-left, center-right, bottom)",
                        "component_type": "whether it's a component label or type indicator or other"
                    }
                ],
                "component_labels": [
                    "Steering gear box assembly",
                    "Steering wheel",
                    "Leaf spring",
                    "Frame",
                    "Engine",
                    "Front axle",
                    "Propeller shaft",
                    "Gear box",
                    "Clutch",
                    "Differential assembly or rear axle",
                    "Tyres"
                ],
                "type_indicators": [
                    "Type"  // only if "Type" appears in the image
                ],
                "notes": "No interpretations added. Only extracted visible text."
            }
            
            Remember: NO interpretations, NO categories, NO connections, NO positions, NO IDs, NO assemblies.
            Just list what you can actually see in the image.
            """
            
            # Upload image
            uploaded_file = genai.upload_file(image_path)
            
            with st.spinner("Extracting visible text from diagram..."):
                response = model.generate_content(
                    [PROMPT, uploaded_file],
                    generation_config={"temperature": 0.0}  # Zero temperature for exact extraction
                )
            
            response_text = response.text.strip()
            
            # Clean JSON response
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            # Parse JSON
            parsed_data = json.loads(response_text)
            
            # Process to remove any interpretations
            clean_data = self._clean_extracted_data(parsed_data)
            
            return clean_data
            
        except json.JSONDecodeError as e:
            st.error(f"JSON parsing error: {str(e)}")
            return {
                "error": f"Invalid JSON response: {str(e)}",
                "raw_response": response_text[:500] if 'response_text' in locals() else "No response"
            }
        except Exception as e:
            st.error(f"Extraction failed: {str(e)}")
            return {"error": str(e)}
    
    def _clean_extracted_data(self, data: Dict) -> Dict:
        """Clean extracted data to remove interpretations"""
        cleaned = {
            "visible_text": [],
            "component_list": [],
            "type_indicators": [],
            "extraction_timestamp": datetime.now().isoformat(),
            "note": "Only exact text from image. No interpretations added."
        }
        
        # Extract visible text
        if "extracted_text" in data:
            for item in data["extracted_text"]:
                if "text" in item and item["text"].strip():
                    cleaned["visible_text"].append({
                        "text": item["text"].strip(),
                        "area": item.get("location", "unknown")
                    })
        
        # Get unique component labels
        if "component_labels" in data:
            cleaned["component_list"] = list(set(data["component_labels"]))
        
        # Get type indicators
        if "type_indicators" in data:
            cleaned["type_indicators"] = data["type_indicators"]
        
        return cleaned
    
    def process_to_structured_csv(self, extracted_data: Dict, filename: str) -> List[Dict]:
        """Process extracted data to structured CSV format"""
        records = []
        
        try:
            # Skip if error
            if "error" in extracted_data:
                return [{
                    "Filename": filename,
                    "Error": extracted_data["error"],
                    "Record_Type": "Error"
                }]
            
            # Create records for visible text
            for i, text_item in enumerate(extracted_data.get("visible_text", [])):
                record = {
                    "Filename": filename,
                    "Record_Type": "Visible_Text",
                    "Item_ID": f"text_{i+1:03d}",
                    "Text_Content": text_item.get("text", ""),
                    "Area_in_Diagram": text_item.get("area", ""),
                    "Extraction_Time": extracted_data.get("extraction_timestamp", "")
                }
                records.append(record)
            
            # Create records for components
            for i, component in enumerate(extracted_data.get("component_list", [])):
                record = {
                    "Filename": filename,
                    "Record_Type": "Component",
                    "Item_ID": f"comp_{i+1:03d}",
                    "Component_Name": component,
                    "Extraction_Time": extracted_data.get("extraction_timestamp", "")
                }
                records.append(record)
            
            # Create records for type indicators
            for i, type_indicator in enumerate(extracted_data.get("type_indicators", [])):
                record = {
                    "Filename": filename,
                    "Record_Type": "Type_Indicator",
                    "Item_ID": f"type_{i+1:03d}",
                    "Type_Text": type_indicator,
                    "Extraction_Time": extracted_data.get("extraction_timestamp", "")
                }
                records.append(record)
            
            # Add summary record
            summary_record = {
                "Filename": filename,
                "Record_Type": "Summary",
                "Total_Text_Items": len(extracted_data.get("visible_text", [])),
                "Total_Components": len(extracted_data.get("component_list", [])),
                "Total_Type_Indicators": len(extracted_data.get("type_indicators", [])),
                "Extraction_Note": extracted_data.get("note", ""),
                "Extraction_Time": extracted_data.get("extraction_timestamp", "")
            }
            records.append(summary_record)
            
            return records
            
        except Exception as e:
            return [{
                "Filename": filename,
                "Error": f"Processing error: {str(e)}",
                "Record_Type": "Error"
            }]
    
    def process_image_file(self, task_id: str, file_path: str, output_dir: str) -> Dict:
        """Process vehicle assembly diagram image"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")
            
            os.makedirs(output_dir, exist_ok=True)
            base_filename = os.path.join(output_dir, task_id)
            
            # Extract data
            extracted_data = self.extract_vehicle_assembly_data(file_path)
            
            # Prepare output
            output_data = {
                "task_id": task_id,
                "filename": os.path.basename(file_path),
                "timestamp": datetime.now().isoformat(),
                "extracted_data": extracted_data,
                "status": "completed" if "error" not in extracted_data else "error"
            }
            
            # Save JSON
            json_path = f"{base_filename}.json"
            with open(json_path, "w", encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            # Save CSV
            csv_path = f"{base_filename}.csv"
            csv_data = self.process_to_structured_csv(extracted_data, os.path.basename(file_path))
            
            if csv_data:
                with open(csv_path, "w", newline="", encoding='utf-8') as csvfile:
                    fieldnames = set()
                    for record in csv_data:
                        fieldnames.update(record.keys())
                    
                    writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames))
                    writer.writeheader()
                    writer.writerows(csv_data)
            
            return {
                "status": "completed" if "error" not in extracted_data else "error",
                "json_path": json_path,
                "csv_path": csv_path,
                "has_error": "error" in extracted_data
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

# Streamlit UI
def main():
    st.title("🚗 Vehicle Assembly Text Extractor")
    st.markdown("Extract ONLY visible text from vehicle assembly diagrams")
    
    # Initialize service
    if 'extractor' not in st.session_state:
        st.session_state.extractor = VehicleAssemblyExtractor()
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = {}
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        output_dir = st.text_input("Output Directory", value="./output")
        
        st.header("📁 File Management")
        if st.button("Clear All Files"):
            st.session_state.processed_files = {}
            st.session_state.extractor = VehicleAssemblyExtractor()
            st.rerun()
    
    # Main tabs
    tab1, tab2 = st.tabs(["📤 Upload & Extract", "👁️ View Results"])
    
    with tab1:
        st.header("Upload Vehicle Assembly Diagram")
        
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=['png', 'jpg', 'jpeg', 'bmp', 'tiff'],
            help="Upload a vehicle assembly diagram image"
        )
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            with col1:
                st.image(uploaded_file, caption="Uploaded Diagram", use_container_width=True)
            
            with col2:
                file_info = {
                    "Filename": uploaded_file.name,
                    "Size": f"{uploaded_file.size / 1024:.1f} KB",
                    "Type": uploaded_file.type
                }
                st.write("📄 File Details:")
                st.json(file_info)
            
            if st.button("🔍 Extract Text Only", type="primary", use_container_width=True):
                with st.spinner("Extracting visible text..."):
                    # Save uploaded file
                    temp_dir = "./temp"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Process file
                    task_id = str(uuid.uuid4())[:8]
                    
                    result = st.session_state.extractor.process_image_file(
                        task_id=task_id,
                        file_path=temp_path,
                        output_dir=output_dir
                    )
                    
                    # Store result
                    st.session_state.processed_files[task_id] = {
                        **result,
                        "filename": uploaded_file.name,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Cleanup
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                    
                    # Show result
                    if result["status"] == "completed":
                        st.success("✅ Extraction completed!")
                        st.info(f"JSON saved to: `{result.get('json_path')}`")
                        st.info(f"CSV saved to: `{result.get('csv_path')}`")
                    else:
                        st.error("❌ Extraction failed")
    
    with tab2:
        st.header("View Extracted Text")
        
        if not st.session_state.processed_files:
            st.info("No files processed yet. Upload a diagram first.")
        else:
            # File selection
            file_options = {
                f"{task_id} - {info.get('filename', 'Unknown')}": task_id
                for task_id, info in st.session_state.processed_files.items()
            }
            
            selected_file = st.selectbox(
                "📂 Select processed file:",
                options=list(file_options.keys())
            )
            
            if selected_file:
                task_id = file_options[selected_file]
                file_info = st.session_state.processed_files[task_id]
                
                # Load JSON data
                json_path = file_info.get("json_path")
                if json_path and os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    extracted_data = data.get("extracted_data", {})
                    
                    # Create tabs for different views
                    view_tabs = st.tabs(["📋 Summary", "📝 Visible Text", "🔧 Components", "📊 JSON Data"])
                    
                    with view_tabs[0]:
                        st.subheader("Extraction Summary")
                        
                        if "error" in extracted_data:
                            st.error(f"Extraction Error: {extracted_data['error']}")
                        else:
                            cols = st.columns(3)
                            with cols[0]:
                                text_count = len(extracted_data.get("visible_text", []))
                                st.metric("Text Items", text_count)
                            with cols[1]:
                                comp_count = len(extracted_data.get("component_list", []))
                                st.metric("Components", comp_count)
                            with cols[2]:
                                type_count = len(extracted_data.get("type_indicators", []))
                                st.metric("Type Indicators", type_count)
                            
                            st.write("---")
                            st.write("**Note:** Only exact visible text extracted. No interpretations added.")
                    
                    with view_tabs[1]:
                        st.subheader("All Visible Text")
                        if extracted_data.get("visible_text"):
                            text_df = pd.DataFrame(extracted_data["visible_text"])
                            st.dataframe(text_df, use_container_width=True)
                        else:
                            st.info("No text extracted")
                    
                    with view_tabs[2]:
                        st.subheader("Component List")
                        if extracted_data.get("component_list"):
                            comp_df = pd.DataFrame({
                                "Component": extracted_data["component_list"]
                            })
                            st.dataframe(comp_df, use_container_width=True)
                            
                            # Show count of each component
                            st.subheader("Component Frequency")
                            from collections import Counter
                            comp_counts = Counter(extracted_data["component_list"])
                            count_df = pd.DataFrame({
                                "Component": list(comp_counts.keys()),
                                "Count": list(comp_counts.values())
                            })
                            st.dataframe(count_df, use_container_width=True)
                        else:
                            st.info("No components extracted")
                    
                    with view_tabs[3]:
                        st.subheader("Complete JSON Data")
                        st.json(extracted_data)
                        
                        # Download buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            if os.path.exists(json_path):
                                with open(json_path, 'rb') as f:
                                    st.download_button(
                                        label="📥 Download JSON",
                                        data=f,
                                        file_name=f"{task_id}_extracted.json",
                                        mime="application/json"
                                    )
                        
                        csv_path = file_info.get("csv_path")
                        with col2:
                            if csv_path and os.path.exists(csv_path):
                                with open(csv_path, 'rb') as f:
                                    st.download_button(
                                        label="📥 Download CSV",
                                        data=f,
                                        file_name=f"{task_id}_text_data.csv",
                                        mime="text/csv"
                                    )

if __name__ == "__main__":
    main()