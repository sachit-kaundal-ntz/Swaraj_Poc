

# import json
# import math
# import re
# from pathlib import Path
# from typing import Dict, List, Optional, Tuple
# from dataclasses import dataclass

# @dataclass
# class GearSpecifications:
#     """Extracted gear specifications from JSON"""
#     finished_volume_mm3: float = 0
#     finished_mass_kg: float = 0
#     material: str = ""
#     material_density: float = 7.85  # g/cm³ for steel
#     outer_diameter: float = 0
#     length: float = 0
#     complexity: str = "complex"
#     has_internal_spline: bool = False
#     has_external_teeth: bool = False
#     heat_treatment: str = ""
#     hardness_requirement: str = ""

# class AutomatedGearAnalyzer:
#     """
#     Fully automated gear analysis from JSON
#     """
    
#     # Material densities (g/cm³)
#     MATERIAL_DENSITIES = {
#         '20MnCr5': 7.85,
#         'EN353': 7.85,
#         'IS:9175': 7.85,
#         'SAE8620': 7.85,
#         'SAE8622H': 7.85,
#         '4140': 7.85,
#         '4340': 7.85,
#         'default': 7.85
#     }
    
#     # Manufacturing operations detection rules
#     OPERATION_RULES = {
#         'Forging': {
#             'materials': ['20MnCr5', 'EN353', '4140', '4340', '8620'],
#             'geometry': ['stepped', 'hub', 'complex'],
#             'keywords': ['forged', 'forging']
#         },
#         'Hardening and Tempering': {
#             'keywords': ['normaliz', 'anneal', 'harden', 'temper'],
#             'heat_treatment': True
#         },
#         'Rough Turning': {
#             'geometry': ['cylinder', 'diameter', 'bore'],
#             'always': True  # Always needed for cylindrical parts
#         },
#         'Finish Turning': {
#             'tolerances': ['H7', 'H8', 'H9', '±0.1', '±0.05'],
#             'follows': 'Rough Turning'
#         },
#         'Broaching': {
#             'features': ['internal_spline', 'keyway', 'internal_gear'],
#             'keywords': ['spline', 'DIN 5480']
#         },
#         'Hobbing': {
#             'features': ['external_gear_teeth', 'helical', 'spur'],
#             'keywords': ['teeth', 'module', 'helix']
#         },
#         'Gear Tooth Chamfering': {
#             'features': ['tooth_chamfer', 'gear_tip_chamfer'],
#             'keywords': ['tooth edge chamfer', 'gear tip chamfer']
#         },
#         'Carburising': {
#             'keywords': ['carburiz', 'case harden', 'case depth'],
#             'heat_treatment': ['case', 'HRC']
#         },
#         'Grinding': {
#             'post_heat_treat': True,
#             'tolerances': ['tight', 'H7', 'H6'],
#             'keywords': ['grind', 'ground']
#         }
#     }
    
#     def __init__(self):
#         self.specs = GearSpecifications()
#         self.operations = []
#         self.gross_weight_data = {}
        
#     def analyze_json_file(self, json_file_path: str) -> Dict:
#         """
#         Main entry point - analyzes JSON file and returns complete results
        
#         Args:
#             json_file_path: Path to the JSON file
            
#         Returns:
#             Dictionary with operations and weight calculations
#         """
#         # Load JSON
#         with open(json_file_path, 'r') as f:
#             json_data = json.load(f)
        
#         # Extract specifications
#         self.extract_specifications(json_data)
        
#         # Detect manufacturing operations
#         self.operations = self.detect_operations(json_data)
        
#         # Calculate gross weight
#         self.gross_weight_data = self.calculate_gross_weight()
        
#         # Compile results
#         results = {
#             'file': Path(json_file_path).name,
#             'part_info': self.get_part_info(json_data),
#             'specifications': {
#                 'material': self.specs.material,
#                 'density_g_cm3': self.specs.material_density,
#                 'finished_mass_kg': self.specs.finished_mass_kg,
#                 'outer_diameter_mm': self.specs.outer_diameter,
#                 'length_mm': self.specs.length,
#                 'complexity': self.specs.complexity
#             },
#             'manufacturing_operations': self.operations,
#             'weight_analysis': self.gross_weight_data,
#             'summary': {
#                 'finished_weight_kg': self.specs.finished_mass_kg,
#                 'gross_weight_kg': self.gross_weight_data.get('gross_weight_kg', 0),
#                 'material_utilization_percent': self.gross_weight_data.get('material_utilization_percent', 0),
#                 'total_operations': len(self.operations)
#             }
#         }
        
#         return results
    
#     def extract_specifications(self, json_data: Dict):
#         """
#         Extract all specifications from JSON data
#         """
#         extracted_data = json_data.get('extracted_data', {})
        
#         # Get material
#         material_data = extracted_data.get('material_and_treatment', {})
#         self.specs.material = material_data.get('base_material', '20MnCr5')
#         self.specs.heat_treatment = material_data.get('heat_treatment', '')
#         self.specs.hardness_requirement = material_data.get('hardness_requirement', '')
        
#         # Get material density
#         self.specs.material_density = self.get_material_density(self.specs.material)
        
#         # Get dimensions
#         overall_dims = extracted_data.get('overall_dimensions', {})
        
#         # Extract diameter
#         diameter_data = overall_dims.get('diameter', {})
#         if isinstance(diameter_data, dict):
#             self.specs.outer_diameter = self.extract_number(diameter_data.get('value', 0))
        
#         # Extract length
#         length_data = overall_dims.get('length', {})
#         if isinstance(length_data, dict):
#             self.specs.length = self.extract_number(length_data.get('value', 0))
        
#         # Calculate volume and mass from geometric decomposition
#         self.calculate_volume_and_mass(extracted_data)
        
#         # Determine complexity
#         self.specs.complexity = self.determine_complexity(extracted_data)
        
#         # Check for features
#         geom = extracted_data.get('geometric_decomposition', {})
#         for feature in geom.get('subtracted_features', []):
#             if 'spline' in str(feature).lower():
#                 self.specs.has_internal_spline = True
        
#         for feature in geom.get('additive_features', []):
#             if 'gear' in str(feature).lower() or 'teeth' in str(feature).lower():
#                 self.specs.has_external_teeth = True
    
#     def calculate_volume_and_mass(self, extracted_data: Dict):
#         """
#         Calculate finished volume and mass from geometric decomposition
#         """
#         geom = extracted_data.get('geometric_decomposition', {})
        
#         total_volume = 0
        
#         # Add base shapes
#         for shape in geom.get('base_shapes', []):
#             volume = self.calculate_shape_volume(shape)
#             total_volume += volume
        
#         # Subtract removed features
#         for feature in geom.get('subtracted_features', []):
#             volume = self.calculate_feature_volume(feature)
#             total_volume -= volume
        
#         # Store results
#         self.specs.finished_volume_mm3 = max(total_volume, 0)
        
#         # Calculate mass (volume in mm³ * density in g/cm³ / 1000)
#         self.specs.finished_mass_kg = (self.specs.finished_volume_mm3 * self.specs.material_density) / 1000000
    
#     def calculate_shape_volume(self, shape: Dict) -> float:
#         """Calculate volume of a base shape"""
#         shape_type = shape.get('shape_type', '').lower()
#         dims = shape.get('dimensions', {})
        
#         if shape_type == 'cylinder':
#             d = self.extract_number(dims.get('outer_diameter', dims.get('diameter', 0)))
#             h = self.extract_number(dims.get('height', dims.get('length', 0)))
#             if d and h:
#                 return math.pi * (d/2)**2 * h
                
#         elif shape_type == 'stepped_cylinder':
#             # Main cylinder
#             main_d = self.extract_number(
#                 dims.get('main_outer_diameter', {}).get('value', 0) if isinstance(dims.get('main_outer_diameter'), dict)
#                 else dims.get('main_outer_diameter', 0)
#             )
#             main_h = self.extract_number(
#                 dims.get('main_height', {}).get('value', 0) if isinstance(dims.get('main_height'), dict)
#                 else dims.get('main_height', 0)
#             )
            
#             # Hub cylinder
#             hub_d = self.extract_number(
#                 dims.get('hub_outer_diameter', {}).get('value', 0) if isinstance(dims.get('hub_outer_diameter'), dict)
#                 else dims.get('hub_outer_diameter', 0)
#             )
#             hub_h = self.extract_number(
#                 dims.get('hub_height', {}).get('value', 0) if isinstance(dims.get('hub_height'), dict)
#                 else dims.get('hub_height', 0)
#             )
            
#             volume = 0
#             if main_d and main_h:
#                 volume += math.pi * (main_d/2)**2 * main_h
#             if hub_d and hub_h:
#                 volume += math.pi * (hub_d/2)**2 * hub_h
            
#             return volume
        
#         return 0
    
#     def calculate_feature_volume(self, feature: Dict) -> float:
#         """Calculate volume of a subtracted feature"""
#         feature_type = feature.get('feature_type', '').lower()
#         dims = feature.get('dimensions', {})
        
#         if 'bore' in feature_type:
#             d = self.extract_number(dims.get('diameter', dims.get('main_diameter', 0)))
#             depth = self.extract_number(dims.get('depth', dims.get('height', self.specs.length)))
#             if d and depth:
#                 return math.pi * (d/2)**2 * depth
        
#         elif 'spline' in feature_type:
#             # Approximate spline as bore
#             d = self.extract_number(dims.get('major_diameter', 45))  # Default from your example
#             depth = self.extract_number(dims.get('depth', self.specs.length))
#             if d and depth:
#                 return math.pi * (d/2)**2 * depth * 0.8  # 80% of cylinder volume for spline
        
#         return 0
    
#     def detect_operations(self, json_data: Dict) -> List[Dict]:
#         """
#         Detect manufacturing operations from JSON data
#         """
#         operations = []
#         extracted_data = json_data.get('extracted_data', {})
        
#         # 1. Forging (always first for these materials)
#         if self.check_operation_indicators(extracted_data, 'Forging'):
#             operations.append({
#                 'sequence': 1,
#                 'operation': 'Forging',
#                 'evidence': f"Material: {self.specs.material}, Complex geometry"
#             })
        
#         # 2. Hardening and Tempering (normalization)
#         if 'normaliz' in self.specs.heat_treatment.lower() or self.check_operation_indicators(extracted_data, 'Hardening and Tempering'):
#             operations.append({
#                 'sequence': 2,
#                 'operation': 'Hardening and Tempering',
#                 'evidence': "Initial heat treatment for machinability"
#             })
        
#         # 3-4. Turning operations
#         if self.specs.outer_diameter > 0:
#             operations.append({
#                 'sequence': 3,
#                 'operation': 'Rough Turning',
#                 'evidence': f"Cylindrical part OD: {self.specs.outer_diameter}mm"
#             })
#             operations.append({
#                 'sequence': 4,
#                 'operation': 'Finish Turning',
#                 'evidence': "Achieve final dimensions and tolerances"
#             })
        
#         # 5. Broaching (internal features)
#         if self.specs.has_internal_spline or self.check_operation_indicators(extracted_data, 'Broaching'):
#             operations.append({
#                 'sequence': 5,
#                 'operation': 'Broaching',
#                 'evidence': "Internal spline/keyway machining"
#             })
        
#         # 6. Hobbing (external teeth)
#         if self.specs.has_external_teeth or self.check_operation_indicators(extracted_data, 'Hobbing'):
#             operations.append({
#                 'sequence': 6,
#                 'operation': 'Hobbing',
#                 'evidence': "External gear teeth cutting"
#             })
        
#         # 7. Gear Tooth Chamfering
#         if self.check_for_tooth_chamfer(extracted_data):
#             operations.append({
#                 'sequence': 7,
#                 'operation': 'Gear Tooth Chamfering',
#                 'evidence': "Tooth edge chamfering specified"
#             })
        
#         # 8. Carburising
#         if 'carburiz' in self.specs.heat_treatment.lower() or 'case' in self.specs.heat_treatment.lower():
#             operations.append({
#                 'sequence': 8,
#                 'operation': 'Carburising',
#                 'evidence': self.specs.heat_treatment
#             })
        
#         # 9-10. Grinding
#         if 'HRC' in self.specs.hardness_requirement:
#             operations.append({
#                 'sequence': 9,
#                 'operation': 'Grinding',
#                 'evidence': "Post heat-treatment grinding for accuracy"
#             })
            
#             # Check if bore grinding is needed
#             if self.check_for_bore_grinding(extracted_data):
#                 operations.append({
#                     'sequence': 10,
#                     'operation': 'Grinding',
#                     'evidence': "Bore grinding for tight tolerance"
#                 })
        
#         return operations
    
#     def check_operation_indicators(self, data: Dict, operation: str) -> bool:
#         """Check if operation indicators are present in data"""
#         rules = self.OPERATION_RULES.get(operation, {})
        
#         # Check material indicators
#         if 'materials' in rules:
#             for mat in rules['materials']:
#                 if mat.lower() in self.specs.material.lower():
#                     return True
        
#         # Check keywords in all text
#         if 'keywords' in rules:
#             data_str = str(data).lower()
#             for keyword in rules['keywords']:
#                 if keyword.lower() in data_str:
#                     return True
        
#         return False
    
#     def check_for_tooth_chamfer(self, data: Dict) -> bool:
#         """Check for gear tooth chamfer specifications"""
#         features = data.get('feature_dimensions', [])
#         for feature in features:
#             if 'chamfer' in str(feature).lower() and 'tooth' in str(feature).lower():
#                 return True
        
#         # Check geometric decomposition
#         geom = data.get('geometric_decomposition', {})
#         for mod in geom.get('feature_modifications', []):
#             if 'chamfer' in str(mod).lower() and 'tooth' in str(mod).lower():
#                 return True
        
#         return False
    
#     def check_for_bore_grinding(self, data: Dict) -> bool:
#         """Check if bore grinding is needed"""
#         tolerances = data.get('tolerances', {})
#         for tol in tolerances.get('specific_tolerances', []):
#             if 'bore' in str(tol).lower() and any(x in str(tol) for x in ['H7', 'H8', 'H6']):
#                 return True
#         return False
    
#     def calculate_gross_weight(self) -> Dict:
#         """
#         Calculate gross weight from finished weight using industry factors
#         """
#         finished_weight = self.specs.finished_mass_kg
        
#         # If no finished weight calculated, use default
#         if finished_weight <= 0:
#             finished_weight = 1.47  # Default for POC
        
#         # Material losses based on industry standards
#         losses = {
#             'machining': 0.35,  # 35% typical for gears
#             'flash': self.get_flash_factor(finished_weight),
#             'scale': 0.03,  # 3% for gas furnace
#             'tong_hold': 0.02,
#             'die_wear': 0.04,
#             'saw_cut': 0.03,
#             'bar_end': 0.05
#         }
        
#         # Progressive weight calculation
#         forged_weight = finished_weight / (1 - losses['machining'])
#         weight_with_flash = forged_weight * (1 + losses['flash'])
#         weight_after_scale = weight_with_flash / (1 - losses['scale'])
#         weight_with_handling = weight_after_scale / (1 - losses['tong_hold'] - losses['die_wear'])
#         gross_weight = weight_with_handling / (1 - losses['saw_cut'] - losses['bar_end'])
        
#         # Material utilization
#         material_utilization = (finished_weight / gross_weight) * 100
        
#         return {
#             'finished_weight_kg': round(finished_weight, 3),
#             'forged_weight_kg': round(forged_weight, 3),
#             'gross_weight_kg': round(gross_weight, 3),
#             'material_utilization_percent': round(material_utilization, 1),
#             'weight_progression': {
#                 '1_finished': round(finished_weight, 3),
#                 '2_after_machining': round(forged_weight, 3),
#                 '3_with_flash': round(weight_with_flash, 3),
#                 '4_after_heating': round(weight_after_scale, 3),
#                 '5_gross_billet': round(gross_weight, 3)
#             },
#             'losses_kg': {
#                 'machining': round(forged_weight - finished_weight, 3),
#                 'flash': round(weight_with_flash - forged_weight, 3),
#                 'scale': round(weight_after_scale - weight_with_flash, 3),
#                 'handling': round(weight_with_handling - weight_after_scale, 3),
#                 'cutting': round(gross_weight - weight_with_handling, 3),
#                 'total': round(gross_weight - finished_weight, 3)
#             }
#         }
    
#     def get_flash_factor(self, weight_kg: float) -> float:
#         """Get flash loss factor based on weight"""
#         if weight_kg < 2:
#             return 0.18
#         elif weight_kg < 5:
#             return 0.15
#         elif weight_kg < 10:
#             return 0.12
#         else:
#             return 0.10
    
#     def get_material_density(self, material: str) -> float:
#         """Get material density"""
#         for key in self.MATERIAL_DENSITIES:
#             if key in material:
#                 return self.MATERIAL_DENSITIES[key]
#         return self.MATERIAL_DENSITIES['default']
    
#     def determine_complexity(self, data: Dict) -> str:
#         """Determine part complexity"""
#         complexity_score = 0
        
#         geom = data.get('geometric_decomposition', {})
        
#         # Check for complex features
#         if any('stepped' in str(s).lower() for s in geom.get('base_shapes', [])):
#             complexity_score += 1
        
#         if len(geom.get('subtracted_features', [])) > 2:
#             complexity_score += 1
        
#         if self.specs.has_internal_spline:
#             complexity_score += 1
        
#         if self.specs.has_external_teeth:
#             complexity_score += 1
        
#         return "complex" if complexity_score >= 2 else "simple"
    
#     def extract_number(self, value) -> float:
#         """Extract numeric value from various formats"""
#         if isinstance(value, (int, float)):
#             return float(value)
        
#         if isinstance(value, str):
#             # Remove units and special characters
#             cleaned = re.sub(r'[^\d.-]', '', value)
#             try:
#                 return float(cleaned)
#             except:
#                 return 0
        
#         return 0
    
#     def get_part_info(self, json_data: Dict) -> Dict:
#         """Extract part identification info"""
#         metadata = json_data.get('extracted_data', {}).get('drawing_metadata', {})
#         return {
#             'part_name': metadata.get('part_name', 'Unknown'),
#             'drawing_number': metadata.get('drawing_number', 'Unknown'),
#             'revision': metadata.get('revision', 'Unknown'),
#             'company': metadata.get('company', 'Unknown')
#         }


# def main():
#     """
#     Main function to run the analysis
#     Usage: python automated_gear_analyzer.py path/to/json_file.json
#     """
#     import sys
    
#     if len(sys.argv) < 2:
#         print("Usage: python automated_gear_analyzer.py <json_file_path>")
#         print("\nExample: python automated_gear_analyzer.py 39304e84-99fd-48b6-88b5-f20be86db3d3.json")
#         sys.exit(1)
    
#     json_file_path = sys.argv[1]
    
#     # Check if file exists
#     if not Path(json_file_path).exists():
#         print(f"Error: File not found: {json_file_path}")
#         sys.exit(1)
    
#     # Run analysis
#     analyzer = AutomatedGearAnalyzer()
#     results = analyzer.analyze_json_file(json_file_path)
    
#     # Print results
#     print("=" * 80)
#     print("GEAR MANUFACTURING ANALYSIS REPORT")
#     print("=" * 80)
    
#     print(f"\nFile: {results['file']}")
#     print(f"Part: {results['part_info']['part_name']}")
#     print(f"Drawing: {results['part_info']['drawing_number']}")
    
#     print("\n" + "-" * 40)
#     print("SPECIFICATIONS")
#     print("-" * 40)
#     for key, value in results['specifications'].items():
#         print(f"  {key}: {value}")
    
#     print("\n" + "-" * 40)
#     print("MANUFACTURING OPERATIONS")
#     print("-" * 40)
#     for op in results['manufacturing_operations']:
#         print(f"  {op['sequence']}. {op['operation']}")
#         print(f"     Evidence: {op['evidence']}")
    
#     print("\n" + "-" * 40)
#     print("WEIGHT ANALYSIS")
#     print("-" * 40)
#     weight_data = results['weight_analysis']
#     print(f"  Finished Weight: {weight_data['finished_weight_kg']} kg")
#     print(f"  Gross Weight: {weight_data['gross_weight_kg']} kg")
#     print(f"  Material Utilization: {weight_data['material_utilization_percent']}%")
    
#     print("\n  Weight Progression:")
#     for stage, weight in weight_data['weight_progression'].items():
#         print(f"    {stage}: {weight} kg")
    
#     print("\n  Material Losses:")
#     for loss_type, loss_kg in weight_data['losses_kg'].items():
#         print(f"    {loss_type}: {loss_kg} kg")
    
#     print("\n" + "-" * 40)
#     print("SUMMARY")
#     print("-" * 40)
#     summary = results['summary']
#     print(f"  Total Operations: {summary['total_operations']}")
#     print(f"  Finished → Gross: {summary['finished_weight_kg']} → {summary['gross_weight_kg']} kg")
#     print(f"  Material Efficiency: {summary['material_utilization_percent']}%")
    
#     # Save results to JSON
#     output_file = Path(json_file_path).stem + "_analysis.json"
#     with open(output_file, 'w') as f:
#         json.dump(results, f, indent=2)
#     print(f"\n✓ Full results saved to: {output_file}")


# if __name__ == "__main__":
#     main()

#     # python test.py 39304e84-99fd-48b6-88b5-f20be86db3d3 1.json