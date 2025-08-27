
import requests
import base64
import json
import os
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import argparse
import time


@dataclass
class TechnicalSpecification:
    """Data structure to hold extracted technical information"""
    part_name: str = ""
    drawing_number: str = ""
    material: str = ""
    dimensions: Dict[str, str] = None
    tolerances: Dict[str, str] = None
    surface_treatments: List[str] = None
    manufacturing_notes: List[str] = None
    quantity_info: Dict[str, str] = None
    additional_specs: Dict[str, str] = None

    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}
        if self.tolerances is None:
            self.tolerances = {}
        if self.surface_treatments is None:
            self.surface_treatments = []
        if self.manufacturing_notes is None:
            self.manufacturing_notes = []
        if self.quantity_info is None:
            self.quantity_info = {}
        if self.additional_specs is None:
            self.additional_specs = {}


class HuggingFaceTechnicalDrawingExtractor:
    """Technical drawing extractor using Hugging Face API"""
    
    def __init__(self, api_key: str, model_name: str = "OpenGVLab/InternVL3-78B"):
        """
        Initialize the extractor for Hugging Face API
        
        Args:
            api_key: Hugging Face API key (starts with hf_)
            model_name: Model name on Hugging Face
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = f"https://api-inference.huggingface.co/models/{model_name}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def encode_image_to_base64(self, image_path: str) -> str:
        """
        Encode image to base64 string
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def create_extraction_prompt(self) -> str:
        """
        Create a detailed prompt for technical drawing analysis
        
        Returns:
            Formatted prompt string
        """
        prompt = """
        Please analyze this technical engineering drawing image and extract the following information:

        **PART IDENTIFICATION:**
        - Part name or description
        - Drawing number
        - Sheet number
        - Date and revision information

        **MATERIAL & SPECIFICATIONS:**
        - Material type and grade
        - Heat treatment requirements
        - Surface finish specifications

        **DIMENSIONS & MEASUREMENTS:**
        - Overall dimensions with units
        - Critical dimensions (diameters, lengths, heights)
        - Hole sizes and positions
        - Thread specifications
        - Angular measurements

        **TOLERANCES & PRECISION:**
        - General tolerance information
        - Specific dimensional tolerances
        - Geometric dimensioning and tolerancing (GD&T)

        **MANUFACTURING DETAILS:**
        - Manufacturing processes mentioned
        - Assembly instructions
        - Special manufacturing notes
        - Quality requirements

        **QUANTITY & ASSEMBLY:**
        - Quantity required
        - Assembly information
        - Related part numbers

        Please provide a detailed analysis focusing on accuracy. Extract all visible text, numbers, and technical specifications. If any information is unclear or not visible, please indicate this clearly.

        Format your response as clear, structured text with sections for each category above.
        """
        return prompt

    def wait_for_model(self, max_wait_time: int = 300) -> bool:
        """
        Wait for the model to be ready (in case it's loading)
        
        Args:
            max_wait_time: Maximum time to wait in seconds
            
        Returns:
            True if model is ready, False if timeout
        """
        print("Checking if model is ready...")
        
        # Simple payload to check model status
        test_payload = {
            "inputs": "Test message",
            "parameters": {
                "max_new_tokens": 10,
                "temperature": 0.1
            }
        }
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=test_payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    print("✅ Model is ready!")
                    return True
                elif response.status_code == 503:
                    result = response.json()
                    if "estimated_time" in result:
                        wait_time = result["estimated_time"]
                        print(f"⏳ Model is loading, estimated wait time: {wait_time} seconds")
                        time.sleep(min(wait_time + 5, 60))  # Wait but cap at 60 seconds
                    else:
                        print("⏳ Model is loading, waiting 30 seconds...")
                        time.sleep(30)
                else:
                    print(f"❌ Unexpected status code: {response.status_code}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                print(f"⏳ Connection issue, retrying in 10 seconds... ({e})")
                time.sleep(10)
        
        print("❌ Timeout waiting for model to be ready")
        return False

    def extract_information(self, image_path: str, custom_prompt: Optional[str] = None) -> Dict:
        """
        Extract technical information from a drawing image using Hugging Face API
        
        Args:
            image_path: Path to the image file
            custom_prompt: Custom prompt to override default
            
        Returns:
            Dictionary containing extracted information
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Check if model is ready
        if not self.wait_for_model():
            return {
                "success": False,
                "error": "Model is not ready or unavailable",
                "image_path": image_path
            }

        # Encode image
        try:
            base64_image = self.encode_image_to_base64(image_path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to encode image: {str(e)}",
                "image_path": image_path
            }
        
        # Use custom prompt or default
        prompt = custom_prompt if custom_prompt else self.create_extraction_prompt()

        # Prepare the request payload for Hugging Face Inference API
        # Note: Different models may have different input formats
        payload = {
            "inputs": {
                "question": prompt,
                "image": base64_image
            },
            "parameters": {
                "max_new_tokens": 2000,
                "temperature": 0.1,
                "do_sample": False
            }
        }

        try:
            print(f"🔍 Analyzing image: {Path(image_path).name}")
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=120
            )
            
            print(f"📊 API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle different response formats
                if isinstance(result, list) and len(result) > 0:
                    content = result[0].get('generated_text', str(result))
                elif isinstance(result, dict):
                    content = result.get('generated_text', str(result))
                else:
                    content = str(result)
                
                return {
                    "success": True,
                    "extracted_text": content,
                    "raw_response": result,
                    "image_path": image_path
                }
            
            elif response.status_code == 503:
                error_detail = response.json() if response.content else {}
                estimated_time = error_detail.get('estimated_time', 'unknown')
                return {
                    "success": False,
                    "error": f"Model is loading. Estimated time: {estimated_time} seconds",
                    "image_path": image_path,
                    "retry_after": estimated_time
                }
            
            else:
                error_detail = response.text
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}: {error_detail}",
                    "image_path": image_path
                }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout - image analysis took too long",
                "image_path": image_path
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "image_path": image_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "image_path": image_path
            }

    def parse_extracted_data(self, extracted_text: str) -> TechnicalSpecification:
        """
        Parse the extracted text into a structured format
        
        Args:
            extracted_text: Raw extracted text from the model
            
        Returns:
            TechnicalSpecification object
        """
        spec = TechnicalSpecification()
        
        # Clean the text
        text = extracted_text.strip()
        lines = text.split('\n')
        
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Identify sections based on keywords
            line_upper = line.upper()
            
            if any(keyword in line_upper for keyword in ["PART IDENTIFICATION", "PART NAME", "DRAWING"]):
                current_section = "part"
            elif any(keyword in line_upper for keyword in ["MATERIAL", "SPECIFICATION"]):
                current_section = "material"
            elif any(keyword in line_upper for keyword in ["DIMENSION", "MEASUREMENT"]):
                current_section = "dimensions"
            elif any(keyword in line_upper for keyword in ["TOLERANCE", "PRECISION"]):
                current_section = "tolerances"
            elif any(keyword in line_upper for keyword in ["MANUFACTURING", "PROCESS"]):
                current_section = "manufacturing"
            elif any(keyword in line_upper for keyword in ["QUANTITY", "ASSEMBLY"]):
                current_section = "quantity"
            
            # Extract information based on current section
            if current_section == "part":
                if ":" in line:
                    key, value = line.split(":", 1)
                    key_lower = key.lower()
                    if any(word in key_lower for word in ["name", "description"]):
                        spec.part_name = value.strip()
                    elif any(word in key_lower for word in ["number", "drawing"]):
                        spec.drawing_number = value.strip()
                        
            elif current_section == "material":
                if ":" in line:
                    spec.material = line.split(":", 1)[1].strip()
                else:
                    if spec.material:
                        spec.material += " " + line
                    else:
                        spec.material = line
                        
            elif current_section == "dimensions":
                if ":" in line:
                    key, value = line.split(":", 1)
                    spec.dimensions[key.strip()] = value.strip()
                elif any(char.isdigit() for char in line):
                    # Try to extract dimensions from lines with numbers
                    spec.dimensions[f"dimension_{len(spec.dimensions)}"] = line
                    
            elif current_section == "manufacturing":
                spec.manufacturing_notes.append(line)
        
        return spec

    def process_multiple_images(self, image_directory: str, output_file: Optional[str] = None) -> List[Dict]:
        """
        Process multiple images in a directory
        
        Args:
            image_directory: Directory containing images
            output_file: Optional file to save results
            
        Returns:
            List of extraction results
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        image_dir = Path(image_directory)
        
        if not image_dir.exists():
            raise FileNotFoundError(f"Directory not found: {image_directory}")
        
        results = []
        image_files = [f for f in image_dir.iterdir() if f.suffix.lower() in image_extensions]
        
        print(f"📁 Found {len(image_files)} images to process")
        
        for i, image_file in enumerate(image_files, 1):
            print(f"\n🔄 Processing {i}/{len(image_files)}: {image_file.name}")
            
            result = self.extract_information(str(image_file))
            
            if result["success"]:
                print("✅ Extraction successful")
                spec = self.parse_extracted_data(result["extracted_text"])
                result["parsed_data"] = spec.__dict__
            else:
                print(f"❌ Extraction failed: {result['error']}")
                # If model is loading, wait and retry once
                if "retry_after" in result:
                    wait_time = min(int(result.get("retry_after", 60)), 300)  # Cap at 5 minutes
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    result = self.extract_information(str(image_file))
                    if result["success"]:
                        print("✅ Retry successful")
                        spec = self.parse_extracted_data(result["extracted_text"])
                        result["parsed_data"] = spec.__dict__
            
            results.append(result)
        
        # Save results if output file specified
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"💾 Results saved to: {output_file}")
                
        return results


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description="Extract technical information from engineering drawings using Hugging Face API")
    parser.add_argument("--api-key", required=True, help="Hugging Face API key (starts with hf_)")
    parser.add_argument("--model", default="OpenGVLab/InternVL3-78B", help="Hugging Face model name")
    parser.add_argument("--image", help="Single image file to process")
    parser.add_argument("--directory", help="Directory containing images to process")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--custom-prompt", help="Custom prompt file")
    
    args = parser.parse_args()
    
    # Validate API key format
    if not args.api_key.startswith('hf_'):
        print("⚠️  Warning: API key should start with 'hf_' for Hugging Face")
    
    # Initialize extractor
    print(f"🚀 Initializing extractor with model: {args.model}")
    extractor = HuggingFaceTechnicalDrawingExtractor(args.api_key, args.model)
    
    # Load custom prompt if provided
    custom_prompt = None
    if args.custom_prompt:
        with open(args.custom_prompt, 'r') as f:
            custom_prompt = f.read().strip()
    
    if args.image:
        # Process single image
        print(f"\n📷 Processing single image: {args.image}")
        result = extractor.extract_information(args.image, custom_prompt)
        
        if result["success"]:
            print("\n✅ Extraction successful!")
            print("\n📋 Extracted Information:")
            print("-" * 50)
            print(result["extracted_text"])
            
            # Parse and display structured data
            spec = extractor.parse_extracted_data(result["extracted_text"])
            print(f"\n📊 Parsed Data Summary:")
            print(f"Part Name: {spec.part_name or 'Not found'}")
            print(f"Drawing Number: {spec.drawing_number or 'Not found'}")
            print(f"Material: {spec.material or 'Not found'}")
            print(f"Dimensions found: {len(spec.dimensions)}")
            print(f"Manufacturing notes: {len(spec.manufacturing_notes)}")
            
        else:
            print(f"\n❌ Extraction failed: {result['error']}")
            
    elif args.directory:
        # Process multiple images
        print(f"\n📁 Processing directory: {args.directory}")
        results = extractor.process_multiple_images(args.directory, args.output)
        
        successful = sum(1 for r in results if r["success"])
        print(f"\n📊 Processing Summary:")
        print(f"Total images: {len(results)}")
        print(f"Successful extractions: {successful}")
        print(f"Failed extractions: {len(results) - successful}")
        
        if args.output:
            print(f"💾 Results saved to: {args.output}")
    
    else:
        print("❌ Please specify either --image or --directory")
        parser.print_help()


if __name__ == "__main__":
    main()




# Example usage:
"""
# For single image:
python test.py --api-key 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 --image images/UVW_0001_page_14_png.rf.a674e5e077f0bf6682c9f47dc4139ff1.jpg

# For multiple images:
python technical_drawing_extractor.py --api-key YOUR_API_KEY --directory ./drawings --output results.json --report summary_report.md

# Using in code:
extractor = TechnicalDrawingExtractor("your_api_key")
result = extractor.extract_information("path/to/drawing.jpg")
if result["success"]:
    spec = extractor.parse_extracted_data(result["extracted_text"])
    print(f"Part: {spec.part_name}")
"""