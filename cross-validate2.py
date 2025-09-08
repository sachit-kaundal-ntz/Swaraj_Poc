#!/usr/bin/env python3
"""
Enhanced Technical Drawing JSON Cross-Validation Script
Cross-validates extracted JSON data against technical drawings using Gemini 2.5 Flash
Enhanced focus on dimension ID validation with improved gear component classification
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
    status: str  # 'PASS', 'FAIL', 'WARNING', 'MISSING'
    confidence: float
    details: str

class TechnicalDrawingValidator:
    """Cross-validates JSON extracted data against technical drawings"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """Initialize the validator with Gemini API"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.validation_results = []
        
        # Enhanced gear component dimension and feature classification rules
        self.DIMENSION_RULES = """
### DIMENSION IDENTIFICATION PRIORITY
- **Hub Diameter**: Starting and end point of the hub groove/bore and not part of main rim.
- **Outer Diameter**: Starting and the end point of the rim (It is the outermost length to the tip of tooth)
- **Hub Height/Length**: Starting and end point of the hub's axial extent along the bore centerline, measured between the hub faces that are perpendicular to the shaft axis and not including the main gear rim thickness.
- **Face Width**: Axial dimension of the main gear body/rim section.
- **Bore Diameter**: Internal diameter dimensions (often with fit tolerances like H7).

### FEATURE CLASSIFICATION RULES
- **Root diameter is NOT a cavity** – it's the gear tooth root, use only for gear data.
- **Face width** = largest axial dimension (main gear body width).
- **Hub extension** = any additional axial lengths beyond face width.
- **Bore subtraction** applies through full axial stack (face_width + hub_extension).

### DIMENSION ID VALIDATION REQUIREMENTS
- Each dimension ID in JSON must be matched to its exact corresponding dimension in the drawing
- Focus on precise value matching including tolerances, units, and symbols
- Validate that dimension placement and leaders match the geometric context
- Check for consistency between dimension ID naming and actual geometric feature
"""
        
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
    
    def parse_gemini_response(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Enhanced parsing of Gemini response into ValidationResult objects"""
        if debug:
            print(f"DEBUG: Raw Gemini response:\n{response_text}\n" + "="*50)
        
        results = []
        
        # Try multiple parsing strategies with improved pattern matching
        results.extend(self._parse_structured_format(response_text, debug))
        results.extend(self._parse_json_format(response_text, debug))
        results.extend(self._parse_table_format(response_text, debug))
        results.extend(self._parse_bullet_format(response_text, debug))
        results.extend(self._parse_dimension_id_format(response_text, debug))
        
        if debug:
            print(f"DEBUG: Parsed {len(results)} validation results")
        
        # Remove duplicates based on item_id
        seen_ids = set()
        unique_results = []
        for result in results:
            if result.item_id not in seen_ids:
                unique_results.append(result)
                seen_ids.add(result.item_id)
        
        return unique_results
    
    def _parse_dimension_id_format(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Parse responses specifically formatted for dimension ID validation"""
        results = []
        
        # Look for dimension ID patterns like "dim_outer_dia", "dim_hub_dia", etc.
        dim_id_pattern = r'(?:VALIDATION_ITEM:|ITEM:|ID:)\s*(dim_[a-zA-Z_]+)'
        matches = re.finditer(dim_id_pattern, response_text, re.IGNORECASE)
        
        for match in matches:
            dim_id = match.group(1)
            start_pos = match.start()
            
            # Extract the validation block for this dimension ID
            block_end = response_text.find('VALIDATION_ITEM:', start_pos + 1)
            if block_end == -1:
                block_end = len(response_text)
            
            block_text = response_text[start_pos:block_end]
            
            # Parse the block
            result_data = {'item_id': dim_id}
            
            # Extract fields from the block
            field_patterns = {
                'category': r'CATEGORY:\s*([^\n]+)',
                'json_value': r'JSON_VALUE:\s*([^\n]+)',
                'image_value': r'IMAGE_VALUE:\s*([^\n]+)',
                'status': r'STATUS:\s*([^\n]+)',
                'confidence': r'CONFIDENCE:\s*([^\n]+)',
                'details': r'DETAILS:\s*([^\n]+(?:\n(?!VALIDATION_ITEM:|ITEM:|ID:|CATEGORY:|JSON_VALUE:|IMAGE_VALUE:|STATUS:|CONFIDENCE:|DETAILS:)[^\n]*)*)'
            }
            
            for field, pattern in field_patterns.items():
                match_field = re.search(pattern, block_text, re.IGNORECASE | re.MULTILINE)
                if match_field:
                    value = match_field.group(1).strip()
                    if field == 'status':
                        value = value.upper()
                    elif field == 'confidence':
                        try:
                            conf_str = ''.join(c for c in value if c.isdigit() or c == '.')
                            value = min(float(conf_str), 1.0) if conf_str else 0.5
                        except:
                            value = 0.5
                    result_data[field] = value
            
            # Create validation result if we have minimum required fields
            if 'status' in result_data and result_data['status'] in ['PASS', 'FAIL', 'WARNING', 'MISSING']:
                result = self._create_validation_result(result_data)
                if result:
                    results.append(result)
                    if debug:
                        print(f"DEBUG: Created dimension ID result for {result.item_id}")
        
        return results
    
    def _parse_structured_format(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Parse structured format with ITEM_ID, CATEGORY, etc."""
        results = []
        
        # Split into blocks by VALIDATION_ITEM or similar markers
        block_pattern = r'(?:VALIDATION_ITEM|ITEM|ID):\s*([^\n]+)'
        blocks = re.split(block_pattern, response_text, flags=re.IGNORECASE)
        
        for i in range(1, len(blocks), 2):
            if i + 1 >= len(blocks):
                break
                
            item_id = blocks[i].strip()
            block_content = blocks[i + 1]
            
            current_result = {'item_id': item_id}
            
            # Parse the block content
            lines = block_content.split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        key = key.strip().lower().replace('_', '').replace(' ', '')
                        value = value.strip()
                        
                        if key in ['category', 'type']:
                            current_result['category'] = value
                        elif key in ['jsonvalue', 'json']:
                            current_result['json_value'] = value
                        elif key in ['imagevalue', 'image', 'drawing']:
                            current_result['image_value'] = value
                        elif key in ['status', 'result']:
                            current_result['status'] = value.upper()
                        elif key in ['confidence', 'conf']:
                            try:
                                conf_str = ''.join(c for c in value if c.isdigit() or c == '.')
                                current_result['confidence'] = min(float(conf_str), 1.0) if conf_str else 0.5
                            except:
                                current_result['confidence'] = 0.5
                        elif key in ['details', 'explanation', 'note', 'comment']:
                            current_result['details'] = value
            
            if self._has_minimum_fields(current_result):
                result = self._create_validation_result(current_result)
                if result:
                    results.append(result)
                    if debug:
                        print(f"DEBUG: Created structured result for {result.item_id}")
        
        return results
    
    def _parse_json_format(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Try to parse JSON format responses"""
        results = []
        try:
            # Look for JSON objects or arrays in the response
            json_pattern = r'\{[^{}]*\}'
            json_matches = re.findall(json_pattern, response_text)
            
            for match in json_matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict) and any(key in data for key in ['item_id', 'status', 'category']):
                        result = self._create_validation_result(data)
                        if result:
                            results.append(result)
                except:
                    continue
        except:
            pass
        
        return results
    
    def _parse_table_format(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Parse table-like format with | separators"""
        results = []
        lines = response_text.split('\n')
        
        for line in lines:
            if '|' in line and not line.strip().startswith('|--'):
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # Remove empty parts
                
                if len(parts) >= 4:
                    # Try to map parts to validation fields
                    result_data = {
                        'item_id': parts[0] if parts[0] else 'unknown',
                        'category': parts[1] if len(parts) > 1 else 'unknown',
                        'status': parts[2].upper() if len(parts) > 2 else 'UNKNOWN',
                        'details': parts[3] if len(parts) > 3 else '',
                        'confidence': 0.7
                    }
                    
                    if result_data['status'] in ['PASS', 'FAIL', 'WARNING', 'MISSING']:
                        result = self._create_validation_result(result_data)
                        if result:
                            results.append(result)
        
        return results
    
    def _parse_bullet_format(self, response_text: str, debug: bool = False) -> List[ValidationResult]:
        """Parse bullet point or numbered list format"""
        results = []
        lines = response_text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for lines starting with bullets, numbers, or dashes
            if re.match(r'^[\-\*\•\d\.\)]\s*', line):
                # Try to extract validation info from the line
                if any(status in line.upper() for status in ['PASS', 'FAIL', 'WARNING', 'MISSING']):
                    status = 'UNKNOWN'
                    for s in ['PASS', 'FAIL', 'WARNING', 'MISSING']:
                        if s in line.upper():
                            status = s
                            break
                    
                    # Extract item identifier (look for dimension IDs)
                    dim_id_match = re.search(r'dim_[a-zA-Z_]+', line)
                    if dim_id_match:
                        item_id = dim_id_match.group(0)
                    else:
                        item_id = line.split(':')[0].strip('- *•0123456789.)').strip()
                        if not item_id:
                            item_id = f"item_{len(results)}"
                    
                    result_data = {
                        'item_id': item_id,
                        'category': 'general',
                        'status': status,
                        'details': line,
                        'confidence': 0.6
                    }
                    
                    result = self._create_validation_result(result_data)
                    if result:
                        results.append(result)
        
        return results
    
    def _has_minimum_fields(self, data: Dict) -> bool:
        """Check if data has minimum required fields"""
        return ('item_id' in data or 'id' in data) and 'status' in data
    
    def _create_validation_result(self, data: Dict) -> Optional[ValidationResult]:
        """Create ValidationResult from parsed data"""
        try:
            return ValidationResult(
                category=data.get('category', 'unknown'),
                item_id=data.get('item_id', data.get('id', 'unknown')),
                description=data.get('details', data.get('description', '')),
                json_value=data.get('json_value', ''),
                image_value=data.get('image_value', ''),
                status=data.get('status', 'UNKNOWN'),
                confidence=float(data.get('confidence', 0.5)),
                details=data.get('details', data.get('description', ''))
            )
        except Exception as e:
            print(f"Error creating validation result: {e}")
            return None
    
    def validate_dimensions_by_id(self, json_data: Dict[str, Any], image: Image.Image, debug: bool = False) -> List[ValidationResult]:
        """Enhanced validation focusing specifically on dimension IDs"""
        if 'dimensions' not in json_data:
            return []
            
        dimensions = json_data['dimensions']
        
        # Create a detailed mapping for each dimension ID
        dimension_details = []
        for dim in dimensions:
            dim_detail = {
                'id': dim.get('id', 'unknown'),
                'raw_text': dim.get('raw_text', ''),
                'value': dim.get('value', ''),
                'unit': dim.get('unit', ''),
                'symbol': dim.get('symbol', ''),
                'tolerance': dim.get('tolerance', ''),
                'view_id': dim.get('view_id', '')
            }
            dimension_details.append(dim_detail)
        
        prompt = f"""
You are a technical drawing validation expert focusing on DIMENSION ID VALIDATION for gear components.

CRITICAL VALIDATION RULES:
{self.DIMENSION_RULES}

Your task: For EACH dimension ID listed below, find the exact corresponding dimension in the technical drawing and validate it.

DIMENSION IDs TO VALIDATE:
{json.dumps(dimension_details, indent=2)}

VALIDATION FORMAT (MANDATORY):
For each dimension ID, respond with EXACTLY this structure:

VALIDATION_ITEM: [exact dimension ID from JSON]
CATEGORY: dimensions
JSON_VALUE: [complete dimension specification from JSON including value, unit, symbol, tolerance]
IMAGE_VALUE: [exact dimension text/notation you see in the drawing]
STATUS: PASS/FAIL/WARNING/MISSING
CONFIDENCE: [0.0 to 1.0]
DETAILS: [specific location in drawing and validation explanation]

VALIDATION CRITERIA:
- PASS: Dimension found in drawing with exact match of value, unit, symbol, and tolerance
- FAIL: Dimension found but values/tolerances don't match
- WARNING: Dimension found but with minor discrepancies (e.g., formatting differences)
- MISSING: Dimension not found in drawing

CRITICAL REQUIREMENTS:
1. Validate ALL dimension IDs listed above - do not skip any
2. Look for exact matches of dimension notation (⌀, ±, H7, etc.)
3. Pay attention to tolerance formats (+0.62/-0.25, ±0.1, H7, etc.)
4. Identify the geometric location of each dimension in the drawing
5. Match dimension placement with the expected feature (hub, rim, bore, etc.)

Start validation now for ALL dimension IDs listed above.
"""
        
        try:
            response = self.model.generate_content([prompt, image])
            if debug:
                print(f"DEBUG Dimension ID validation response: {response.text[:1000]}...")
            return self.parse_gemini_response(response.text, debug)
        except Exception as e:
            print(f"Error validating dimensions by ID: {e}")
            return []
    
    def validate_critical_dimensions(self, json_data: Dict[str, Any], image: Image.Image, debug: bool = False) -> List[ValidationResult]:
        """Validate the most critical dimensions for gear components"""
        if 'dimensions' not in json_data:
            return []
        
        dimensions = json_data['dimensions']
        
        # Identify critical dimensions based on common gear component dimension IDs
        critical_patterns = [
            'outer_dia', 'hub_dia', 'bore', 'face_width', 'hub_height',
            'pitch_circle', 'major_dia', 'minor_dia', 'pcd'
        ]
        
        critical_dims = []
        for dim in dimensions:
            dim_id = dim.get('id', '')
            if any(pattern in dim_id.lower() for pattern in critical_patterns):
                critical_dims.append(dim)
        
        if not critical_dims:
            critical_dims = dimensions[:5]  # Take first 5 if no critical patterns found
        
        prompt = f"""
You are validating CRITICAL DIMENSIONS for a gear component. Focus on precision and accuracy.

GEAR COMPONENT CLASSIFICATION RULES:
{self.DIMENSION_RULES}

CRITICAL DIMENSIONS TO VALIDATE:
{json.dumps(critical_dims, indent=2)}

For EACH critical dimension, provide validation in this EXACT format:

VALIDATION_ITEM: [dimension_id]
CATEGORY: critical_dimensions
JSON_VALUE: [full dimension spec from JSON]
IMAGE_VALUE: [exact dimension from drawing]
STATUS: PASS/FAIL/WARNING/MISSING
CONFIDENCE: [0.0 to 1.0]
DETAILS: [precise location and validation reasoning]

Focus on:
1. Outer diameter dimensions (⌀xxx) - gear tip diameter
2. Hub diameter dimensions - hub outer/inner diameters
3. Bore diameter (often with H7 tolerance) - shaft bore
4. Face width - axial dimension of gear body
5. Hub height/length - axial hub extension

Validate each dimension ID with high precision.
"""
        
        try:
            response = self.model.generate_content([prompt, image])
            if debug:
                print(f"DEBUG Critical dimensions response: {response.text[:1000]}...")
            return self.parse_gemini_response(response.text, debug)
        except Exception as e:
            print(f"Error validating critical dimensions: {e}")
            return []
    
    def validate_tables(self, json_data: Dict[str, Any], image: Image.Image, debug: bool = False) -> List[ValidationResult]:
        """Validate tabulated data with focus on gear specifications"""
        if 'tables' not in json_data:
            return []
            
        # Focus on key table entries for validation
        key_entries = []
        for table in json_data['tables'][:2]:  # Limit to first 2 tables
            table_id = table.get('id', 'unknown')
            for cell in table.get('cells', [])[:5]:  # First 5 cells per table
                key_entries.append({
                    'table_id': table_id,
                    
                    'value': cell.get('value', ''),
                    'unit': cell.get('unit', '')
                })
        
        prompt = f"""
You are validating technical drawing table data for a gear component.

GEAR COMPONENT RULES:
{self.DIMENSION_RULES}

TABLE ENTRIES FROM JSON:
{json.dumps(key_entries, indent=2)}

For EACH table entry, respond in EXACTLY this format:

VALIDATION_ITEM: {table_id}
CATEGORY: tables
JSON_VALUE: [value from JSON with unit]
IMAGE_VALUE: [value from drawing table]
STATUS: PASS/FAIL/WARNING/MISSING
CONFIDENCE: [0.0 to 1.0]
DETAILS: [table location and validation explanation]

Look for tables like:
- GEAR DATA (module, teeth count, pressure angle, etc.)
- SPLINE DATA (teeth, pitch, diameters, etc.)
- Tolerance specifications

Check each  pair precisely against the drawing tables.
"""
        
        try:
            response = self.model.generate_content([prompt, image])
            if debug:
                print(f"DEBUG Tables response: {response.text[:1000]}...")
            return self.parse_gemini_response(response.text, debug)
        except Exception as e:
            print(f"Error validating tables: {e}")
            return []
    
    def validate_metadata(self, json_data: Dict[str, Any], image: Image.Image, debug: bool = False) -> List[ValidationResult]:
        """Validate metadata and title block information"""
        if 'metadata' not in json_data:
            return []
            
        metadata = json_data['metadata']
        
        prompt = f"""
You are validating technical drawing title block and metadata for a gear component.

GEAR COMPONENT CLASSIFICATION:
{self.DIMENSION_RULES}

METADATA FROM JSON:
{json.dumps(metadata, indent=2)}

For EACH metadata field, respond in EXACTLY this format:

VALIDATION_ITEM: [metadata_field_name]
CATEGORY: metadata
JSON_VALUE: [value from JSON]
IMAGE_VALUE: [value from drawing title block]
STATUS: PASS/FAIL/WARNING/MISSING
CONFIDENCE: [0.0 to 1.0]
DETAILS: [title block location and validation explanation]

Focus on title block elements:
1. Drawing number - must match exactly
2. Part name/description - should match or be equivalent
3. Material specification - check chemical designation
4. Scale - drawing scale notation
5. Revision marks or other metadata

Examine the title block area carefully for exact matches.
"""
        
        try:
            response = self.model.generate_content([prompt, image])
            if debug:
                print(f"DEBUG Metadata response: {response.text[:1000]}...")
            return self.parse_gemini_response(response.text, debug)
        except Exception as e:
            print(f"Error validating metadata: {e}")
            return []
    
    def validate_features(self, json_data: Dict[str, Any], image: Image.Image, debug: bool = False) -> List[ValidationResult]:
        """Validate geometric features using enhanced gear component rules"""
        if 'features' not in json_data:
            return []
            
        features = json_data['features']
        
        prompt = f"""
You are validating geometric features for a gear component using expert classification rules.

GEAR COMPONENT FEATURE RULES:
{self.DIMENSION_RULES}

FEATURES FROM JSON:
{json.dumps(features, indent=2)}

For EACH feature ID, respond in EXACTLY this format:

VALIDATION_ITEM: [feature_id]
CATEGORY: features
JSON_VALUE: [feature type and role from JSON]
IMAGE_VALUE: [corresponding geometric feature in drawing]
STATUS: PASS/FAIL/WARNING/MISSING
CONFIDENCE: [0.0 to 1.0]
DETAILS: [geometric location and feature validation explanation]

Validate:
1. Feature type accuracy (cylindrical_rim, cylindrical_bore, internal_spline, etc.)
2. Feature role correctness (gear_tip, through_bore, spline_bore, hub_outer, etc.)
3. Associated dimension IDs match the feature geometry
4. Feature hierarchy and assembly order logic

Focus on gear-specific features like rim (gear teeth area), hub (mounting section), bore (shaft hole), and splines (coupling features).
"""
        
        try:
            response = self.model.generate_content([prompt, image])
            if debug:
                print(f"DEBUG Features response: {response.text[:1000]}...")
            return self.parse_gemini_response(response.text, debug)
        except Exception as e:
            print(f"Error validating features: {e}")
            return []
    
    def run_comprehensive_validation(self, json_path: str, image_path: str, debug: bool = False) -> Dict[str, Any]:
        """Run comprehensive validation of JSON against image with enhanced dimension ID focus"""
        print(f"Loading JSON data from: {json_path}")
        json_data = self.load_json_data(json_path)
        
        print(f"Loading image from: {image_path}")
        image = self.load_image(image_path)
        
        print("Starting enhanced validation with gear component classification rules...")
        
        # Get extracted_data if it exists (nested structure)
        if 'extracted_data' in json_data:
            data_to_validate = json_data['extracted_data']
        else:
            data_to_validate = json_data
        
        # Run all validations with enhanced focus on dimension IDs
        self.validation_results = []
        
        print("Validating dimensions by ID (primary focus)...")
        dim_id_results = self.validate_dimensions_by_id(data_to_validate, image, debug)
        self.validation_results.extend(dim_id_results)
        print(f"  Found {len(dim_id_results)} dimension ID validation results")
        
        print("Validating critical dimensions...")
        critical_dim_results = self.validate_critical_dimensions(data_to_validate, image, debug)
        self.validation_results.extend(critical_dim_results)
        print(f"  Found {len(critical_dim_results)} critical dimension validation results")
        
        print("Validating tables...")
        table_results = self.validate_tables(data_to_validate, image, debug)
        self.validation_results.extend(table_results)
        print(f"  Found {len(table_results)} table validation results")
        
        print("Validating metadata...")
        meta_results = self.validate_metadata(data_to_validate, image, debug)
        self.validation_results.extend(meta_results)
        print(f"  Found {len(meta_results)} metadata validation results")
        
        print("Validating features...")
        feature_results = self.validate_features(data_to_validate, image, debug)
        self.validation_results.extend(feature_results)
        print(f"  Found {len(feature_results)} feature validation results")
        
        print(f"Total validation results: {len(self.validation_results)}")
        
        # If no results, create a basic validation
        if not self.validation_results:
            print("No validation results found, creating basic validation...")
            basic_result = ValidationResult(
                category='system',
                item_id='basic_check',
                description='Basic image-JSON compatibility check',
                json_value='JSON structure detected',
                image_value='Image loaded successfully',
                status='WARNING',
                confidence=0.5,
                details='No specific validations could be parsed from AI response'
            )
            self.validation_results.append(basic_result)
        
        # Generate summary
        summary = self.generate_summary()
        
        return {
            'validation_timestamp': datetime.now().isoformat(),
            'json_file': json_path,
            'image_file': image_path,
            'enhanced_gear_classification_applied': True,
            'dimension_id_focused_validation': True,
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
        """Generate enhanced validation summary statistics"""
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
        
        # Dimension-specific analysis
        dimension_results = [r for r in self.validation_results if 'dimension' in r.category.lower()]
        dimension_stats = {
            'total_dimensions_validated': len(dimension_results),
            'dimension_pass_rate': (sum(1 for r in dimension_results if r.status == 'PASS') / len(dimension_results) * 100) if dimension_results else 0
        }
        
        return {
            'total_checks': total,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'missing': missing,
            'pass_rate': passed / total * 100,
            'average_confidence': avg_confidence,
            'category_breakdown': categories,
            'dimension_analysis': dimension_stats
        }
    
    def save_results(self, results: Dict[str, Any], output_path: str):
        """Save validation results to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {output_path}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Enhanced cross-validation of JSON extracted data against technical drawings with focus on dimension ID validation')
    parser.add_argument('json_file', help='Path to JSON file with extracted data')
    parser.add_argument('image_file', help='Path to technical drawing image')
    parser.add_argument('--api-key', required=True, help='Google Gemini API key')
    parser.add_argument('--model', default='gemini-2.5-flash', help='Gemini model to use')
    parser.add_argument('--output', help='Output file for validation results (default: auto-generated)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Validate input files exist
    if not os.path.exists(args.json_file):
        print(f"Error: JSON file not found: {args.json_file}")
        sys.exit(1)
    
    if not os.path.exists(args.image_file):
        print(f"Error: Image file not found: {args.image_file}")
        sys.exit(1)
    
    # Generate output filename if not provided
    if not args.output:
        base_name = os.path.splitext(os.path.basename(args.json_file))[0]
        args.output = f"{base_name}_enhanced_validation_results.json"
    
    try:
        # Initialize validator
        validator = TechnicalDrawingValidator(args.api_key, args.model)
        
        # Run validation
        results = validator.run_comprehensive_validation(args.json_file, args.image_file, args.debug)
        
        # Save results
        validator.save_results(results, args.output)
        
        # Print enhanced summary
        summary = results['summary']
        print("\n" + "="*70)
        print("ENHANCED GEAR COMPONENT VALIDATION SUMMARY")
        print("="*70)
        
        if 'error' in summary:
            print(f"Error: {summary['error']}")
        else:
            print(f"Total checks: {summary['total_checks']}")
            print(f"Passed: {summary['passed']} ({summary['pass_rate']:.1f}%)")
            print(f"Failed: {summary['failed']}")
            print(f"Warnings: {summary['warnings']}")
            print(f"Missing: {summary['missing']}")
            print(f"Average confidence: {summary['average_confidence']:.2f}")
            
            # Print dimension-specific analysis
            if 'dimension_analysis' in summary:
                dim_stats = summary['dimension_analysis']
                print(f"\nDIMENSION ID VALIDATION:")
                print(f"  Total dimensions validated: {dim_stats['total_dimensions_validated']}")
                print(f"  Dimension pass rate: {dim_stats['dimension_pass_rate']:.1f}%")
            
            # Print category breakdown
            if 'category_breakdown' in summary:
                print(f"\nCATEGORY BREAKDOWN:")
                for category, counts in summary['category_breakdown'].items():
                    total_cat = sum(counts.values())
                    print(f"  {category.upper()}: {total_cat} checks")
                    for status, count in counts.items():
                        if count > 0:
                            print(f"    {status.upper()}: {count}")
            
            # Print dimension-specific failed items
            dimension_failures = [r for r in validator.validation_results 
                                if r.status == 'FAIL' and 'dimension' in r.category.lower()]
            if dimension_failures:
                print(f"\nFAILED DIMENSION VALIDATIONS ({len(dimension_failures)}):")
                print("-" * 50)
                for item in dimension_failures:
                    print(f"• {item.item_id}: {item.details}")
            
            # Print all failed items
            failed_items = [r for r in validator.validation_results if r.status == 'FAIL']
            if failed_items:
                print(f"\nALL FAILED VALIDATIONS ({len(failed_items)}):")
                print("-" * 50)
                for item in failed_items:
                    print(f"• {item.category}/{item.item_id}: {item.details}")
            
            # Print successful dimension ID validations
            dimension_passes = [r for r in validator.validation_results 
                              if r.status == 'PASS' and 'dimension' in r.category.lower()]
            if dimension_passes and args.debug:
                print(f"\nSUCCESSFUL DIMENSION ID VALIDATIONS ({len(dimension_passes)}):")
                print("-" * 50)
                for item in dimension_passes:
                    print(f"• {item.item_id}: JSON='{item.json_value}' | Drawing='{item.image_value}'")
            
            # Print all results if debug
            if args.debug:
                print(f"\nALL VALIDATION RESULTS:")
                print("-" * 50)
                for item in validator.validation_results:
                    print(f"• {item.status} - {item.category}/{item.item_id}: {item.details}")
                    if item.json_value or item.image_value:
                        print(f"    JSON: {item.json_value}")
                        print(f"    Drawing: {item.image_value}")
        
        print(f"\nEnhanced validation completed. Results saved to: {args.output}")
        
    except Exception as e:
        print(f"Error during validation: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()


     #python cross-validate2.py crosscheck.json image2.jpeg --api-key AIzaSyCr9f9e8ns0nvs3dmU2lIA7GdOIRod4n1A