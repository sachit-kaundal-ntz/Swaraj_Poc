"""
Complete Gear Manufacturing Weight Calculator
 
Calculates forged weight with manufacturing tolerances, then applies industry-standard
losses to determine gross material weight and manufacturing operations.
 
Features:
- Adds manufacturing tolerances to dimensions
- Calculates both nominal and tolerance-adjusted weights
- Applies forging-to-raw material loss calculations
- Detects manufacturing operations from JSON data
- Provides complete weight progression analysis
 
Usage:
    python complete_gear_calculator.py /path/to/extracted_json.json
"""
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.gear_manufacturing_wt_calculator_schema import *
from app.utils.rules_for_manufacturing import MATERIAL_DATABASE, OPERATION_RULES

class CompleteGearCalculator:
    def __init__(self):
        self.calculation_steps: List[CalculationStep] = []
        self.total_volume_mm3 = 0.0
        self.debug_info = []
        self.operations = []
   
    def add_debug(self, message: str):
        """Add debug information"""
        self.debug_info.append(message)
   
    def add_calculation_step(self, operation: str, component: str, volume: float,
                           description: str, dimensions: Dict[str, float] = None):
        """Add a calculation step and update total volume"""
        if dimensions is None:
            dimensions = {}
           
        step = CalculationStep(operation, component, volume, description, dimensions)
        self.calculation_steps.append(step)
       
        if operation == 'add' or operation == 'initialize':
            self.total_volume_mm3 += volume
        elif operation == 'subtract':
            self.total_volume_mm3 -= volume
           
        self.add_debug(f"{operation.upper()}: {component} = {volume:.2f} mm³ ({description})")
   
    def parse_material_from_drawing(self, extracted_data: Dict[str, Any]) -> MaterialProperties:
        """Extract material information from drawing metadata"""
        try:
            title_block = extracted_data.get('metadata', {}).get('title_block', {})
            material_raw = title_block.get('material', '').lower().strip()
           
            self.add_debug(f"Raw material string: '{material_raw}'")
           
            # Clean and parse material string
            material_clean = re.sub(r'[;:\s]+.*$', '', material_raw)
            material_clean = material_clean.replace(' ', '_')
           
            self.add_debug(f"Cleaned material identifier: '{material_clean}'")
           
            # Look up density
            density = None
            matched_key = None
            for key, dens in self.MATERIAL_DATABASE.items():
                if key in material_clean:
                    density = dens
                    matched_key = key
                    break
           
            if density is None:
                density = self.MATERIAL_DATABASE['default_steel']
                matched_key = 'default_steel'
                self.add_debug("Warning: Material not found in database, using default steel density")
           
            return MaterialProperties(
                name=material_raw,
                density_g_per_cm3=density,
                density_g_per_mm3=density / 1000.0,
                source=f"Database lookup: {matched_key}"
            )
           
        except Exception as e:
            self.add_debug(f"Error parsing material: {e}")
            return MaterialProperties(
                name="Unknown",
                density_g_per_cm3=7.85,
                density_g_per_mm3=0.00785,
                source="Default fallback"
            )
   
    def find_dimension_by_id(self, dimensions: List[Dict], dim_id: str) -> Optional[float]:
        """Find dimension value by ID"""
        for dim in dimensions:
            if dim.get('id') == dim_id:
                value = dim.get('value')
                if isinstance(value, (int, float)):
                    return float(value)
                try:
                    return float(str(value))
                except (ValueError, TypeError):
                    self.add_debug(f"Warning: Could not parse dimension {dim_id} value: {value}")
                    return None
        return None
   
    def find_best_hub_diameter(self, dimensions: List[Dict], part_name: str) -> Optional[float]:
        """Find the most appropriate hub diameter based on the part"""
        part_lower = part_name.lower()
       
        # For Z-33 gear, specifically look for the inner hub diameter (58mm)
        if 'z-33' in part_lower or 'z33' in part_lower:
            hub_inner = self.find_dimension_by_id(dimensions, 'dim_hub_dia_inner')
            if hub_inner:
                self.add_debug(f"Using inner hub diameter for Z-33: {hub_inner} mm")
                return hub_inner
       
        # General hub diameter search
        hub_candidates = [
            ('dim_hub_dia_inner', 'Inner hub diameter'),
            ('dim_hub_dia_step', 'Hub step diameter'),
            ('dim_hub_dia_small', 'Small hub diameter'),
            ('dim_hub_dia', 'Main hub diameter')
        ]
       
        for dim_id, description in hub_candidates:
            value = self.find_dimension_by_id(dimensions, dim_id)
            if value:
                self.add_debug(f"Found hub diameter: {description} = {value} mm")
                return value
       
        self.add_debug("Warning: No hub diameter found")
        return None
   
    def apply_manufacturing_tolerances(self, dimensions: Dict[str, Optional[float]],
                                     tolerance_mm: float = 2.0) -> Dict[str, Dict[str, float]]:
        """Apply manufacturing tolerances to dimensions for forging allowance"""
        toleranced_dims = {}
       
        for key, value in dimensions.items():
            if key == 'part_name' or value is None:
                continue
               
            if 'diameter' in key.lower():
                # Add tolerance to diameters (forging needs extra material)
                toleranced_dims[key] = {
                    'nominal': value,
                    'with_tolerance': value + tolerance_mm,
                    'tolerance_added': tolerance_mm
                }
                self.add_debug(f"Applied tolerance to {key}: {value} → {value + tolerance_mm} mm (+{tolerance_mm}mm)")
           
            elif key in ['gear_face_width', 'hub_height']:
                # Add tolerance to lengths (forging needs extra length)
                toleranced_dims[key] = {
                    'nominal': value,
                    'with_tolerance': value + tolerance_mm,
                    'tolerance_added': tolerance_mm
                }
                self.add_debug(f"Applied tolerance to {key}: {value} → {value + tolerance_mm} mm (+{tolerance_mm}mm)")
           
            elif 'bore' in key.lower():
                # Bore is machined, so forging is solid (no bore in forging)
                toleranced_dims[key] = {
                    'nominal': value,
                    'with_tolerance': 0.0,  # No bore in forging
                    'tolerance_added': -value
                }
                self.add_debug(f"Removed bore for forging: {key}: {value} → 0 mm (machined later)")
           
            else:
                # Keep other dimensions nominal
                toleranced_dims[key] = {
                    'nominal': value,
                    'with_tolerance': value,
                    'tolerance_added': 0.0
                }
       
        return toleranced_dims
   
    def calculate_cylinder_volume(self, outer_diameter: float, height: float,
                                inner_diameter: float = 0.0) -> float:
        """Calculate volume of a cylinder (hollow if inner_diameter > 0)"""
        if outer_diameter <= 0 or height <= 0:
            return 0.0
           
        r_outer = outer_diameter / 2.0
        r_inner = inner_diameter / 2.0 if inner_diameter > 0 else 0.0
       
        volume = math.pi * height * (r_outer**2 - r_inner**2)
        return max(0.0, volume)
   
    def extract_gear_dimensions(self, extracted_data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Extract all relevant dimensions from the gear drawing"""
        dimensions = extracted_data.get('dimensions', [])
        part_name = extracted_data.get('metadata', {}).get('title_block', {}).get('part_name', '')
       
        self.add_debug(f"Analyzing part: {part_name}")
        self.add_debug(f"Total dimensions found: {len(dimensions)}")
       
        result = {
            'gear_outer_diameter': self.find_dimension_by_id(dimensions, 'dim_outer_dia'),
            'gear_face_width': self.find_dimension_by_id(dimensions, 'dim_face_width'),
            'hub_outer_diameter': self.find_best_hub_diameter(dimensions, part_name),
            'hub_height': self.find_dimension_by_id(dimensions, 'dim_hub_height'),
            'bore_diameter': self.find_dimension_by_id(dimensions, 'dim_bore'),
            'part_name': part_name
        }
       
        # Log all found dimensions
        for key, value in result.items():
            if key != 'part_name':
                status = f"{value} mm" if value else "NOT FOUND"
                self.add_debug(f"{key}: {status}")
       
        return result
   
    def calculate_volume_with_tolerances(self, dimensions: Dict[str, Optional[float]],
                                       use_tolerances: bool = False) -> float:
        """Calculate volume using either nominal or tolerance-adjusted dimensions"""
        # Reset calculation state
        self.calculation_steps = []
        self.total_volume_mm3 = 0.0
       
        # Apply tolerances if requested
        if use_tolerances:
            toleranced_dims = self.apply_manufacturing_tolerances(dimensions)
            working_dims = {k: v['with_tolerance'] for k, v in toleranced_dims.items()}
            calc_type = "forged (with tolerances)"
        else:
            working_dims = {k: v for k, v in dimensions.items() if k != 'part_name'}
            calc_type = "finished (nominal)"
       
        self.add_debug(f"Calculating {calc_type} volume...")
       
        # 1. GEAR RIM CALCULATION
        gear_outer = working_dims.get('gear_outer_diameter')
        face_width = working_dims.get('gear_face_width')
       
        if gear_outer and face_width:
            gear_rim_volume = self.calculate_cylinder_volume(gear_outer, face_width)
            self.add_calculation_step(
                'initialize', 'gear_rim', gear_rim_volume,
                f'Solid cylinder: π × ({gear_outer}/2)² × {face_width}',
                {'outer_diameter': gear_outer, 'height': face_width}
            )
        else:
            raise ValueError("Missing required gear dimensions")
       
        # 2. HUB CALCULATION
        hub_outer = working_dims.get('hub_outer_diameter')
        hub_height = working_dims.get('hub_height')
       
        if hub_outer and hub_height:
            hub_volume = self.calculate_cylinder_volume(hub_outer, hub_height)
            self.add_calculation_step(
                'add', 'hub', hub_volume,
                f'Hub cylinder: π × ({hub_outer}/2)² × {hub_height}',
                {'outer_diameter': hub_outer, 'height': hub_height}
            )
       
        # 3. BORE SUBTRACTION (only for finished weight)
        bore_diameter = working_dims.get('bore_diameter', 0.0)
        total_height = max(face_width or 0, hub_height or 0)
       
        if bore_diameter and total_height > 0:
            bore_volume = self.calculate_cylinder_volume(bore_diameter, total_height)
            self.add_calculation_step(
                'subtract', 'bore', bore_volume,
                f'Through bore: π × ({bore_diameter}/2)² × {total_height}',
                {'diameter': bore_diameter, 'height': total_height}
            )
       
        return self.total_volume_mm3
   
    def detect_manufacturing_operations(self, extracted_data: Dict[str, Any]) -> List[Dict]:
        """Detect manufacturing operations from JSON data"""
        operations = []
        part_name = extracted_data.get('metadata', {}).get('title_block', {}).get('part_name', '')
       
        # Extract heat treatment info
        heat_treatment_info = self.extract_heat_treatment_data(extracted_data)
       
        # 1. Forging (always first for gear parts)
        operations.append({
            'sequence': 1,
            'operation': 'Forging',
            'evidence': f"Complex gear geometry requires forging",
            'details': "Hot forging to near-net shape"
        })
       
        # 2. Normalizing (initial heat treatment)
        operations.append({
            'sequence': 2,
            'operation': 'Normalizing',
            'evidence': "Stress relief and grain refinement post-forging",
            'details': heat_treatment_info.get('normalizing', "155-220 BHN typical")
        })
       
        # 3-4. Turning operations
        operations.append({
            'sequence': 3,
            'operation': 'Rough Turning',
            'evidence': "Machine to approximate dimensions",
            'details': "Remove forging scale and achieve rough dimensions"
        })
       
        operations.append({
            'sequence': 4,
            'operation': 'Finish Turning',
            'evidence': "Achieve final external dimensions and tolerances",
            'details': "Precision turning for final OD, faces, and hub"
        })
       
        # 5. Broaching (internal features)
        if self.check_for_internal_features(extracted_data):
            operations.append({
                'sequence': 5,
                'operation': 'Broaching',
                'evidence': "Internal spline or keyway machining required",
                'details': "Machine internal splines and bores"
            })
       
        # 6. Hobbing (external teeth)
        if self.check_for_gear_teeth(extracted_data):
            operations.append({
                'sequence': 6,
                'operation': 'Hobbing',
                'evidence': "External gear teeth cutting required",
                'details': "Cut gear teeth with hobbing machine"
            })
       
        # 7. Gear finishing operations
        operations.append({
            'sequence': 7,
            'operation': 'Gear Tooth Chamfering',
            'evidence': "Chamfer gear tooth edges",
            'details': "Remove sharp edges and burrs from gear teeth"
        })
       
        # 8. Carburizing (case hardening)
        if heat_treatment_info.get('carburizing'):
            operations.append({
                'sequence': 8,
                'operation': 'Carburizing',
                'evidence': heat_treatment_info['carburizing'],
                'details': "Case hardening to specified depth and hardness"
            })
       
        # 9-10. Final grinding operations
        operations.append({
            'sequence': 9,
            'operation': 'Grinding',
            'evidence': "Final surface finishing post heat treatment",
            'details': "Grind critical surfaces to final tolerance"
        })
       
        return operations
   
    def extract_heat_treatment_data(self, extracted_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract heat treatment information from tables"""
        heat_treatment = {}
        tables = extracted_data.get('tables', [])
       
        for table in tables:
            table_id = table.get('id', '').lower()
           
            if 'heat' in table_id or 'treatment' in table_id:
                cells = table.get('cells', [])
                for cell in cells:
                    label = cell.get('label', '').lower()
                    value = cell.get('value', '')
                   
                    if 'carburiz' in label:
                        heat_treatment['carburizing'] = f"Case depth: {value}"
                    elif 'harden' in label:
                        heat_treatment['hardening'] = f"Hardness: {value}"
                    elif 'normaliz' in label:
                        heat_treatment['normalizing'] = f"Normalize to: {value}"
       
        return heat_treatment
   
    def check_for_internal_features(self, extracted_data: Dict[str, Any]) -> bool:
        """Check for internal splines or complex bores"""
        tables = extracted_data.get('tables', [])
        for table in tables:
            if 'spline' in table.get('id', '').lower():
                return True
        return False
   
    def check_for_gear_teeth(self, extracted_data: Dict[str, Any]) -> bool:
        """Check for external gear teeth"""
        tables = extracted_data.get('tables', [])
        for table in tables:
            if 'gear' in table.get('id', '').lower():
                cells = table.get('cells', [])
                for cell in cells:
                    if 'teeth' in cell.get('label', '').lower():
                        return True
        return False
   
    def calculate_gross_weight_from_forged(self, forged_weight_kg: float) -> WeightProgression:
        """Calculate gross weight from forged weight using industry loss factors"""
       
        # Material losses based on industry standards for gear forging
        losses = {
            'machining': 0.35,  # 35% material removed during machining
            'flash': self.get_flash_factor(forged_weight_kg),  # Flash loss varies by size
            'scale': 0.03,  # 3% scale loss during heating
            'tong_hold': 0,  # 2% for tong holding area
            'die_wear': 0,  # 4% allowance for die wear
            'saw_cut': 0,  # 3% for sawing billet to length
            'bar_end': 0   # 5% crop ends of bar stock
        }
       
        self.add_debug("Calculating gross weight progression...")
        self.add_debug(f"Starting forged weight: {forged_weight_kg:.4f} kg")
       
        # Calculate finished weight (forged weight minus machining)
        finished_weight = forged_weight_kg * (1 - losses['machining'])
        self.add_debug(f"Finished weight after {losses['machining']*100}% machining: {finished_weight:.4f} kg")
       
        # Reverse calculate gross weight
        # Work backwards through the process
       
        # Step 1: Add flash to forged weight
        weight_with_flash = forged_weight_kg * (1 + losses['flash'])
        self.add_debug(f"Weight with {losses['flash']*100}% flash: {weight_with_flash:.4f} kg")
       
        # Step 2: Account for scale loss during heating
        weight_before_heating = weight_with_flash / (1 - losses['scale'])
        self.add_debug(f"Weight before {losses['scale']*100}% scale loss: {weight_before_heating:.4f} kg")
       
        # Step 3: Account for handling losses
        weight_with_handling = weight_before_heating / (1 - losses['tong_hold'] - losses['die_wear'])
        self.add_debug(f"Weight with handling allowances: {weight_with_handling:.4f} kg")
       
        # Step 4: Account for cutting losses
        gross_weight = weight_with_handling / (1 - losses['saw_cut'] - losses['bar_end'])
        self.add_debug(f"Final gross weight: {gross_weight:.4f} kg")
       
        # Calculate material utilization
        material_utilization = (finished_weight / gross_weight) * 100
       
        # Prepare detailed breakdown
        weight_progression = WeightProgression(
            finished_weight_kg=finished_weight,
            forged_weight_kg=forged_weight_kg,
            gross_weight_kg=gross_weight,
            material_utilization_percent=material_utilization,
            losses_breakdown={
                'machining_loss_kg': forged_weight_kg - finished_weight,
                'flash_loss_kg': weight_with_flash - forged_weight_kg,
                'scale_loss_kg': weight_before_heating - weight_with_flash,
                'handling_loss_kg': weight_with_handling - weight_before_heating,
                'cutting_loss_kg': gross_weight - weight_with_handling,
                'total_loss_kg': gross_weight - finished_weight
            }
        )
       
        return weight_progression
   
    def get_flash_factor(self, weight_kg: float) -> float:
        """Get flash loss factor based on forged part weight"""
        if weight_kg < 2:
            return 0.18  # 18% flash for small parts
        elif weight_kg < 5:
            return 0.15  # 15% flash for medium parts
        elif weight_kg < 10:
            return 0.12  # 12% flash for larger parts
        else:
            return 0.10  # 10% flash for very large parts
   
    def generate_comprehensive_report(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete manufacturing analysis report"""
       
        # Extract material properties
        material = self.parse_material_from_drawing(extracted_data)
       
        # Extract dimensions
        dimensions = self.extract_gear_dimensions(extracted_data)
       
        # Calculate finished volume and weight (nominal dimensions)
        finished_volume_mm3 = self.calculate_volume_with_tolerances(dimensions, use_tolerances=False)
        finished_mass_kg = finished_volume_mm3 * material.density_g_per_mm3 / 1000.0
        finished_steps = self.calculation_steps.copy()
       
        # Calculate forged volume and weight (with tolerances, no bore)
        forged_volume_mm3 = self.calculate_volume_with_tolerances(dimensions, use_tolerances=True)
        forged_mass_kg = forged_volume_mm3 * material.density_g_per_mm3 / 1000.0
        forged_steps = self.calculation_steps.copy()
       
        # Calculate gross weight progression
        weight_progression = self.calculate_gross_weight_from_forged(forged_mass_kg)
       
        # Detect manufacturing operations
        operations = self.detect_manufacturing_operations(extracted_data)
       
        # Prepare comprehensive report
        report = {
            "part_information": {
                "drawing_number": extracted_data.get('metadata', {}).get('title_block', {}).get('drawing_no', 'Unknown'),
                "part_name": dimensions['part_name'],
                "material": material.name,
                "scale": extracted_data.get('metadata', {}).get('title_block', {}).get('scale', 'Unknown')
            },
           
            "material_properties": {
                "material_name": material.name,
                "density_g_per_cm3": material.density_g_per_cm3,
                "density_g_per_mm3": material.density_g_per_mm3,
                "source": material.source
            },
           
            "dimensions_analysis": {
                "extracted_dimensions": {k: v for k, v in dimensions.items() if k != 'part_name'},
                "manufacturing_tolerances_applied": "2mm added to external dimensions, bore removed for forging"
            },
           
            "weight_calculations": {
                "finished_part": {
                    "volume_mm3": round(finished_volume_mm3, 2),
                    "mass_kg": round(finished_mass_kg, 4),
                    "calculation_steps": [
                        {
                            "step": i + 1,
                            "operation": step.operation,
                            "component": step.component,
                            "volume_mm3": round(step.volume_mm3, 2),
                            "description": step.description,
                            "dimensions_used": step.dimensions_used
                        }
                        for i, step in enumerate(finished_steps)
                    ]
                },
               
                "forged_part": {
                    "volume_mm3": round(forged_volume_mm3, 2),
                    "mass_kg": round(forged_mass_kg, 4),
                    "calculation_steps": [
                        {
                            "step": i + 1,
                            "operation": step.operation,
                            "component": step.component,
                            "volume_mm3": round(step.volume_mm3, 2),
                            "description": step.description,
                            "dimensions_used": step.dimensions_used
                        }
                        for i, step in enumerate(forged_steps)
                    ]
                }
            },
           
            "gross_weight_analysis": {
                "weight_progression_kg": {
                    "finished_weight": round(weight_progression.finished_weight_kg, 4),
                    "forged_weight": round(weight_progression.forged_weight_kg, 4),
                    "gross_raw_material": round(weight_progression.gross_weight_kg, 4)
                },
                "material_losses_kg": weight_progression.losses_breakdown,
                "material_utilization_percent": round(weight_progression.material_utilization_percent, 2)
            },
           
            "manufacturing_operations": operations,
           
            "summary": {
                "target_finished_weight_kg": round(weight_progression.finished_weight_kg, 4),
                "required_raw_material_kg": round(weight_progression.gross_weight_kg, 4),
                "material_efficiency_percent": round(weight_progression.material_utilization_percent, 2),
                "total_manufacturing_steps": len(operations)
            },
           
            "debug_information": self.debug_info,
           
            "assumptions_and_notes": [
                "2mm manufacturing tolerance added to external dimensions for forging",
                "Bore assumed to be machined (not present in forging)",
                "Industry-standard loss factors applied for gross weight calculation",
                "Material density assumed uniform throughout part",
                "Complex geometry features (splines, chamfers) simplified for calculation"
            ]
        }
       
        return report
def load_and_process_complete_analysis(file_path: str) -> Dict[str, Any]:
    """Load and process a gear JSON file with complete manufacturing analysis"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}")
   
    # Handle nested structure
    if isinstance(data, dict) and 'extracted_data' in data:
        extracted_data = data['extracted_data']
    else:
        extracted_data = data
   
    # Generate complete analysis
    calculator = CompleteGearCalculator()
    report = calculator.generate_comprehensive_report(extracted_data)
   
    return report