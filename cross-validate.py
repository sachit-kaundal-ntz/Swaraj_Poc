#!/usr/bin/env python3
"""
Technical Drawing JSON Cross-Validation Script
Cross-validates extracted JSON data against technical drawings using Gemini 2.5 Flash
"""

import json
import base64
import os
import sys
import argparse
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import io

@dataclass
class ValidationResult:
    """Result of a validation check"""
    category: str
    item_id: str
    description: str
    json_value: Any
    image_value: Any
    status: str  
    confidence: float
    details: str

class TechnicalDrawingValidator:
    """Cross-validates JSON extracted data against technical drawings"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """Initialize the validator with Gemini API"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.validation_results = []
        
    def load_json_data(self, json_path: str) -> Dict[str, Any]:
        """Load JSON data from file"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Error loading JSON file: {e}")
    
    def load_image(self, image_path: str) -> Image.Image:
        """Load image file"""
        try:
            return Image.open(image_path)
        except Exception as e:
            raise Exception(f"Error loading image file: {e}")
    
    def generate_validation_prompt(self, json_data: Dict[str, Any], validation_type: str) -> str:
        """Generate dynamic validation prompt based on JSON structure"""
        
        base_prompt = f"""
                You are an expert technical drawing analyst. I need you to cross-validate extracted JSON data against the technical drawing image.

                VALIDATION TYPE: {validation_type}

                EXTRACTED JSON DATA:
                {json.dumps(json_data, indent=2)}

                Please carefully examine the technical drawing and verify the following:

                1. DIMENSIONS - Compare all dimensional values, tolerances, and units
                2. TABLES - Verify all tabulated data (gear data, spline data, tolerances, etc.)
                3. FEATURES - Confirm geometric features and their properties
                4. METADATA - Check drawing number, material, scale, part name
                5. VIEWS - Validate view names and orientations

                For each item, provide:
                - ITEM_ID: Unique identifier from JSON
                - CATEGORY: (dimensions/tables/features/metadata/views)
                - JSON_VALUE: Value from JSON
                - IMAGE_VALUE: Value visible in drawing
                - STATUS: PASS/FAIL/WARNING/MISSING
                - CONFIDENCE: 0.0-1.0 confidence score
                - DETAILS: Explanation of finding

                Format your response as a structured analysis with clear validation results.
                Focus on accuracy and provide specific details about any discrepancies found.
                """
        
        if 'dimensions' in json_data:
            base_prompt += f"\nFound {len(json_data['dimensions'])} dimensions to validate."
            
        if 'tables' in json_data:
            base_prompt += f"\nFound {len(json_data['tables'])} tables to validate."
            
        if 'features' in json_data:
            base_prompt += f"\nFound {len(json_data['features'])} features to validate."
            
        return base_prompt
    
    def parse_gemini_response(self, response_text: str) -> List[ValidationResult]:
        """Parse Gemini response into ValidationResult objects"""
        results = []
        
        lines = response_text.split('\n')
        current_result = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'item_id':
                    current_result['item_id'] = value
                elif key == 'category':
                    current_result['category'] = value
                elif key == 'json_value':
                    current_result['json_value'] = value
                elif key == 'image_value':
                    current_result['image_value'] = value
                elif key == 'status':
                    current_result['status'] = value
                elif key == 'confidence':
                    try:
                        current_result['confidence'] = float(value)
                    except:
                        current_result['confidence'] = 0.5
                elif key == 'details':
                    current_result['details'] = value
                    
                    if all(k in current_result for k in ['item_id', 'category', 'status']):
                        result = ValidationResult(
                            category=current_result.get('category', 'unknown'),
                            item_id=current_result.get('item_id', 'unknown'),
                            description=current_result.get('details', ''),
                            json_value=current_result.get('json_value', ''),
                            image_value=current_result.get('image_value', ''),
                            status=current_result.get('status', 'UNKNOWN'),
                            confidence=current_result.get('confidence', 0.5),
                            details=current_result.get('details', '')
                        )
                        results.append(result)
                        current_result = {}
        
        return results
    
    def validate_dimensions(self, json_data: Dict[str, Any], image: Image.Image) -> List[ValidationResult]:
        """Validate dimensional data"""
        if 'dimensions' not in json_data:
            return []
            
        prompt = f"""
            Analyze the technical drawing for dimensional information and validate against this JSON data:

            DIMENSIONS TO VALIDATE:
            {json.dumps(json_data['dimensions'], indent=2)}

            For each dimension, check:
            1. The dimensional value matches what's shown in the drawing
            2. The tolerance notation is correct
            3. The units are properly specified
            4. The dimension symbol (⌀, R, etc.) is accurate

            Provide validation results in this format:
            ITEM_ID: [dimension_id]
            CATEGORY: dimensions
            JSON_VALUE: [value from JSON]
            IMAGE_VALUE: [value from drawing]
            STATUS: PASS/FAIL/WARNING/MISSING
            CONFIDENCE: [0.0-1.0]
            DETAILS: [explanation]
            """
        
        try:
            response = self.model.generate_content([prompt, image])
            return self.parse_gemini_response(response.text)
        except Exception as e:
            print(f"Error validating dimensions: {e}")
            return []
    
    def validate_tables(self, json_data: Dict[str, Any], image: Image.Image) -> List[ValidationResult]:
        """Validate tabulated data"""
        if 'tables' not in json_data:
            return []
            
        prompt = f"""
            Analyze the technical drawing for tabulated data and validate against this JSON data:

            TABLES TO VALIDATE:
            {json.dumps(json_data['tables'], indent=2)}

            For each table and cell, check:
            1. The table exists in the drawing
            2. Labels match exactly
            3. Values are correctly extracted
            4. Units are properly identified

            Provide validation results in this format:
            ITEM_ID: [table_id].[cell_label]
            CATEGORY: tables
            JSON_VALUE: [value from JSON]
            IMAGE_VALUE: [value from drawing]
            STATUS: PASS/FAIL/WARNING/MISSING
            CONFIDENCE: [0.0-1.0]
            DETAILS: [explanation]
            """
        
        try:
            response = self.model.generate_content([prompt, image])
            return self.parse_gemini_response(response.text)
        except Exception as e:
            print(f"Error validating tables: {e}")
            return []
    
    def validate_metadata(self, json_data: Dict[str, Any], image: Image.Image) -> List[ValidationResult]:
        """Validate metadata and title block information"""
        if 'metadata' not in json_data:
            return []
            
        prompt = f"""
            Analyze the technical drawing title block and metadata information:

            METADATA TO VALIDATE:
            {json.dumps(json_data['metadata'], indent=2)}

            Check the title block for:
            1. Drawing number
            2. Part name/description
            3. Material specification
            4. Scale
            5. Any other metadata fields

            Provide validation results in this format:
            ITEM_ID: [metadata_field]
            CATEGORY: metadata
            JSON_VALUE: [value from JSON]
            IMAGE_VALUE: [value from drawing]
            STATUS: PASS/FAIL/WARNING/MISSING
            CONFIDENCE: [0.0-1.0]
            DETAILS: [explanation]
            """
        
        try:
            response = self.model.generate_content([prompt, image])
            return self.parse_gemini_response(response.text)
        except Exception as e:
            print(f"Error validating metadata: {e}")
            return []
    
    def validate_features(self, json_data: Dict[str, Any], image: Image.Image) -> List[ValidationResult]:
        """Validate geometric features"""
        if 'features' not in json_data:
            return []
            
        prompt = f"""
            Analyze the technical drawing for geometric features:

            FEATURES TO VALIDATE:
            {json.dumps(json_data['features'], indent=2)}

            For each feature, verify:
            1. The feature exists in the drawing
            2. The feature type is correctly identified
            3. Associated dimensions are linked properly
            4. The role/function is accurately described

            Provide validation results in this format:
            ITEM_ID: [feature_id]
            CATEGORY: features
            JSON_VALUE: [feature description from JSON]
            IMAGE_VALUE: [what's visible in drawing]
            STATUS: PASS/FAIL/WARNING/MISSING
            CONFIDENCE: [0.0-1.0]
            DETAILS: [explanation]
            """
        
        try:
            response = self.model.generate_content([prompt, image])
            return self.parse_gemini_response(response.text)
        except Exception as e:
            print(f"Error validating features: {e}")
            return []
    
    def run_comprehensive_validation(self, json_path: str, image_path: str) -> Dict[str, Any]:
        """Run comprehensive validation of JSON against image"""
        print(f"Loading JSON data from: {json_path}")
        json_data = self.load_json_data(json_path)
        
        print(f"Loading image from: {image_path}")
        image = self.load_image(image_path)
        
        print("Starting validation...")
        
        if 'extracted_data' in json_data:
            data_to_validate = json_data['extracted_data']
        else:
            data_to_validate = json_data
        
        # Run all validations
        self.validation_results = []
        
        print("Validating dimensions...")
        self.validation_results.extend(self.validate_dimensions(data_to_validate, image))
        
        print("Validating tables...")
        self.validation_results.extend(self.validate_tables(data_to_validate, image))
        
        print("Validating metadata...")
        self.validation_results.extend(self.validate_metadata(data_to_validate, image))
        
        print("Validating features...")
        self.validation_results.extend(self.validate_features(data_to_validate, image))
        
        summary = self.generate_summary()
        
        return {
            'validation_timestamp': datetime.now().isoformat(),
            'json_file': json_path,
            'image_file': image_path,
            'summary': summary,
            'detailed_results': [
                {
                    'category': r.category,
                    'item_id': r.item_id,
                    'description': r.description,
                    'json_value': r.json_value,
                    'image_value': r.image_value,
                    'status': r.status,
                    'confidence': r.confidence,
                    'details': r.details
                }
                for r in self.validation_results
            ]
        }
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary statistics"""
        if not self.validation_results:
            return {'error': 'No validation results available'}
        
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.status == 'PASS')
        failed = sum(1 for r in self.validation_results if r.status == 'FAIL')
        warnings = sum(1 for r in self.validation_results if r.status == 'WARNING')
        missing = sum(1 for r in self.validation_results if r.status == 'MISSING')
        
        avg_confidence = sum(r.confidence for r in self.validation_results) / total
        
        # Category breakdown
        categories = {}
        for result in self.validation_results:
            cat = result.category
            if cat not in categories:
                categories[cat] = {'pass': 0, 'fail': 0, 'warning': 0, 'missing': 0}
            categories[cat][result.status.lower()] += 1
        
        return {
            'total_checks': total,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'missing': missing,
            'pass_rate': passed / total * 100,
            'average_confidence': avg_confidence,
            'category_breakdown': categories
        }
    
    def save_results(self, results: Dict[str, Any], output_path: str):
        """Save validation results to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {output_path}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Cross-validate JSON extracted data against technical drawings')
    parser.add_argument('json_file', help='Path to JSON file with extracted data')
    parser.add_argument('image_file', help='Path to technical drawing image')
    parser.add_argument('--api-key', required=True, help='Google Gemini API key')
    parser.add_argument('--model', default='gemini-2.5-flash', help='Gemini model to use')
    parser.add_argument('--output', help='Output file for validation results (default: auto-generated)')
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Error: JSON file not found: {args.json_file}")
        sys.exit(1)
    
    if not os.path.exists(args.image_file):
        print(f"Error: Image file not found: {args.image_file}")
        sys.exit(1)
    
    if not args.output:
        base_name = os.path.splitext(os.path.basename(args.json_file))[0]
        args.output = f"{base_name}_validation_results.json"
    
    try:
        validator = TechnicalDrawingValidator(args.api_key, args.model)
        results = validator.run_comprehensive_validation(args.json_file, args.image_file)
        validator.save_results(results, args.output)
        summary = results['summary']
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Total checks: {summary['total_checks']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Warnings: {summary['warnings']}")
        print(f"Missing: {summary['missing']}")
        print(f"Average confidence: {summary['average_confidence']:.2f}")
        
        failed_items = [r for r in validator.validation_results if r.status == 'FAIL']
        if failed_items:
            print(f"\nFAILED VALIDATIONS ({len(failed_items)}):")
            print("-" * 40)
            for item in failed_items:
                print(f"• {item.category}/{item.item_id}: {item.details}")
        
    except Exception as e:
        print(f"Error during validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


    #python cross-validate.py crosscheck.json image.png --api-key AIzaSyCr9f9e8ns0nvs3dmU2lIA7GdOIRod4n1A