import math
import json
import re

# Material density mapping in g/mm³
MATERIAL_DENSITIES = {
    "20MnCr5 (IS:1570)": 0.00785,
    "20Ni55Cr50Mo20 (IS:1570)": 0.00785,
    "20MnCr5 (IS:9175)": 0.00785,
    "SAE 8620": 0.00785,
    "EN43D (BS970)": 0.00785,
    "EN353 (BS970)": 0.00785,
    "SAE 8622H": 0.00785,
    # Simplified material names for easier lookup
    "20MnCr5": 0.00785,
    "20Ni55Cr50Mo20": 0.00785,
    "SAE8620": 0.00785,
    "EN43D": 0.00785,
    "EN353": 0.00785,
    "SAE8622H": 0.00785
}

def extract_dimensions_and_calculate_volumes(json_data, tolerance_mm=4.0):
    """
    Extract dimensions from LLM response and calculate volumes programmatically
    Updated to work with the actual JSON structure from TechnicalDrawingExtractionService
    
    Args:
        json_data: The JSON data from the drawing extraction
        tolerance_mm: Universal tolerance to apply in mm (default: 4.0mm)
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    results = []
    
    # Extract from the actual structure
    extracted_data = data.get('extracted_data', {})
    
    # Process main geometric shape from geometric_decomposition
    geom_data = extracted_data.get('geometric_decomposition', {})
    if geom_data:
        main_shape = extract_main_shape_volume(geom_data, tolerance_mm)
        if main_shape:
            results.append(main_shape)
    
    # Process overall dimensions if geometric_decomposition is missing
    if not results:
        overall_dims = extracted_data.get('overall_dimensions', {})
        if overall_dims:
            overall_shape = extract_from_overall_dimensions(overall_dims, tolerance_mm)
            if overall_shape:
                results.append(overall_shape)
    
    # Process feature dimensions (holes, cuts, etc.) as subtracted features
    feature_dims = extracted_data.get('feature_dimensions', [])
    if isinstance(feature_dims, list):
        for feature in feature_dims:
            feature_info = extract_feature_volume(feature, tolerance_mm)
            if feature_info:
                results.append(feature_info)
    
    return results

def extract_main_shape_volume(geom_data, tolerance_mm=4.0):
    """
    Extract volume from geometric_decomposition section with tolerance calculations
    """
    shape_type = geom_data.get('3d shape', '').strip()
    dimensions = geom_data.get('dimentions', {})  # Note: typo in original "dimentions"
    
    if not shape_type or not dimensions:
        return None
    
    # Extract dimensions
    extracted_dims = {}
    for key, value in dimensions.items():
        dim_value = get_base_dimension_value(value)
        if dim_value:
            extracted_dims[key] = dim_value
    
    # Calculate volumes: nominal and with tolerance
    nominal_volume = calculate_volume_by_shape(shape_type, extracted_dims)
    
    # Apply tolerance to dimensions for tolerance volume calculation
    tolerance_dims = apply_tolerance_to_dimensions(extracted_dims, tolerance_mm, is_additive=True)
    tolerance_volume = calculate_volume_by_shape(shape_type, tolerance_dims)
    
    return {
        'name': f"Main {shape_type}",
        'is_subtracted': False,
        'dimensions': extracted_dims,
        'calculated_volume_mm3': round(nominal_volume, 2),
        'volume_with_tolerance_mm3': round(tolerance_volume, 2),
        'tolerance_applied': tolerance_mm,
        'volume_change_mm3': round(tolerance_volume - nominal_volume, 2)
    }

def extract_from_overall_dimensions(overall_dims, tolerance_mm=4.0):
    """
    Extract volume from overall_dimensions section when geometric_decomposition is not available
    """
    extracted_dims = {}
    
    # Extract all dimension values
    for key, value in overall_dims.items():
        if key == 'other_critical_dimensions':
            continue
        dim_value = get_base_dimension_value(value)
        if dim_value:
            extracted_dims[key] = dim_value
    
    if not extracted_dims:
        return None
    
    # Determine shape type based on available dimensions
    shape_type = "Cuboid"  # Default assumption
    if 'diameter' in extracted_dims:
        shape_type = "Cylinder"
    
    # Calculate volumes: nominal and with tolerance
    nominal_volume = calculate_volume_by_shape(shape_type, extracted_dims)
    
    # Apply tolerance to dimensions
    tolerance_dims = apply_tolerance_to_dimensions(extracted_dims, tolerance_mm, is_additive=True)
    tolerance_volume = calculate_volume_by_shape(shape_type, tolerance_dims)
    
    return {
        'name': f"Main {shape_type}",
        'is_subtracted': False,
        'dimensions': extracted_dims,
        'calculated_volume_mm3': round(nominal_volume, 2),
        'volume_with_tolerance_mm3': round(tolerance_volume, 2),
        'tolerance_applied': tolerance_mm,
        'volume_change_mm3': round(tolerance_volume - nominal_volume, 2)
    }

def extract_feature_volume(feature_data, tolerance_mm=4.0):
    """
    Extract volume from feature_dimensions array items with tolerance calculations
    """
    if not isinstance(feature_data, dict):
        return None
    
    feature_type = feature_data.get('feature_type', 'Unknown Feature')
    dimensions = feature_data.get('dimensions', {})
    
    if not dimensions:
        return None
    
    # Extract dimensions from the nested structure
    extracted_dims = {}
    if isinstance(dimensions, dict):
        for key, value in dimensions.items():
            dim_value = get_base_dimension_value(value)
            if dim_value:
                extracted_dims[key] = dim_value
    
    # Calculate volumes: nominal and with tolerance
    nominal_volume = calculate_feature_volume(feature_type, extracted_dims)
    
    # Most features are subtractive (holes, cuts, etc.)
    is_subtracted = is_subtractive_feature(feature_type)
    
    # Apply tolerance - for subtractive features, tolerance makes them larger (removes more material)
    # For additive features, tolerance makes them larger (adds more material)
    tolerance_dims = apply_tolerance_to_dimensions(extracted_dims, tolerance_mm, is_additive=not is_subtracted)
    tolerance_volume = calculate_feature_volume(feature_type, tolerance_dims)
    
    return {
        'name': feature_type,
        'is_subtracted': is_subtracted,
        'dimensions': extracted_dims,
        'calculated_volume_mm3': round(nominal_volume, 2),
        'volume_with_tolerance_mm3': round(tolerance_volume, 2),
        'tolerance_applied': tolerance_mm,
        'volume_change_mm3': round(tolerance_volume - nominal_volume, 2)
    }

def calculate_volume_by_shape(shape_type, dimensions):
    """
    Calculate volume based on shape type and dimensions
    """
    shape_type = shape_type.lower().strip()
    
    if shape_type in ['cylinder', 'cylindrical', 'pipe', 'tube']:
        diameter = dimensions.get('diameter', 0)
        # Try multiple keys for height/length
        height = dimensions.get('height', dimensions.get('length', dimensions.get('depth', 0)))
        if diameter and height:
            radius = diameter / 2
            return math.pi * (radius ** 2) * height
    
    elif shape_type in ['cuboid', 'cube', 'rectangular', 'box']:
        length = dimensions.get('length', 0)
        width = dimensions.get('width', 0)
        height = dimensions.get('height', 0)
        if length and width and height:
            return length * width * height
    
    elif shape_type in ['sphere', 'spherical']:
        diameter = dimensions.get('diameter', 0)
        if diameter:
            radius = diameter / 2
            return (4/3) * math.pi * (radius ** 3)
    
    elif shape_type in ['cone', 'conical']:
        diameter = dimensions.get('diameter', 0)
        height = dimensions.get('height', 0)
        if diameter and height:
            radius = diameter / 2
            return (1/3) * math.pi * (radius ** 2) * height
    
    return 0

def calculate_feature_volume(feature_type, dimensions):
    """
    Calculate volume for specific feature types
    """
    feature_type = feature_type.lower()
    
    if 'hole' in feature_type or 'bore' in feature_type:
        # Cylindrical hole
        diameter = dimensions.get('primary', dimensions.get('diameter', 0))
        depth = dimensions.get('secondary', dimensions.get('depth', dimensions.get('height', dimensions.get('length', 0))))
        
        # If no depth specified, assume it goes through the full length of the main part
        if diameter and not depth:
            depth = 50  # Assume full depth based on your main cylinder length
        
        if diameter and depth:
            radius = diameter / 2
            return math.pi * (radius ** 2) * depth
    
    elif 'recess' in feature_type or 'hub' in feature_type:
        # Cylindrical recess or hub feature
        diameter = dimensions.get('primary', dimensions.get('diameter', 0))
        depth = dimensions.get('secondary', dimensions.get('depth', 0))
        
        if diameter and depth:
            radius = diameter / 2
            return math.pi * (radius ** 2) * depth
        elif diameter and not depth:
            # For hub features without depth, assume a small depth
            radius = diameter / 2
            return math.pi * (radius ** 2) * 2  # Assume 2mm depth
    
    elif 'groove' in feature_type or 'slot' in feature_type or 'keyway' in feature_type:
        # Rectangular groove/keyway
        width = dimensions.get('primary', dimensions.get('width', 0))
        depth = dimensions.get('secondary', dimensions.get('depth', 0))
        length = dimensions.get('length', 50)  # Assume full length of part if not specified
        
        if width and depth:
            return width * depth * length
    
    elif 'teeth' in feature_type:
        # Gear teeth - simplified calculation
        outer_diameter = dimensions.get('primary', 0)
        tooth_height = dimensions.get('secondary', 0)
        
        if outer_diameter and tooth_height:
            # Approximate as annular volume
            outer_radius = outer_diameter / 2
            inner_radius = outer_radius - tooth_height
            thickness = 50  # Assume full width of gear
            return math.pi * (outer_radius**2 - inner_radius**2) * thickness
    
    elif 'chamfer' in feature_type:
        # Simplified chamfer volume calculation
        size = dimensions.get('primary', 0)
        angle = dimensions.get('secondary', 45)  # Default 45 degree chamfer
        if size:
            # Approximate as small triangular volume around circumference
            circumference = math.pi * 137  # Use main cylinder diameter
            return size * size * circumference * 0.5
    
    elif 'fillet' in feature_type:
        # Simplified fillet volume - usually additive but small
        radius = dimensions.get('primary', 0)
        if radius:
            return math.pi * (radius ** 2) * radius * 0.25
    
    return 0

def is_subtractive_feature(feature_type):
    """
    Determine if a feature type is typically subtractive (removes material)
    """
    feature_type = feature_type.lower()
    subtractive_keywords = ['hole', 'bore', 'cut', 'groove', 'slot', 'recess', 'chamfer']
    additive_keywords = ['fillet', 'boss', 'rib']
    
    for keyword in subtractive_keywords:
        if keyword in feature_type:
            return True
    
    for keyword in additive_keywords:
        if keyword in feature_type:
            return False
    
    # Default to subtractive for unknown features
    return True

def get_base_dimension_value(dim_data):
    """
    Extract the base dimension value from various formats
    """
    if not dim_data:
        return None
    
    # Handle different data types
    if isinstance(dim_data, (int, float)):
        return float(dim_data)
    
    if isinstance(dim_data, dict):
        # Handle {"value": "50", "unit": "mm", "tolerance": "±0.1"} format
        value_str = dim_data.get('value', '')
    elif isinstance(dim_data, str):
        value_str = dim_data
    else:
        return None
    
    if not value_str:
        return None
    
    # Clean the string and extract numeric value
    # Remove common symbols and units
    cleaned = re.sub(r'[⌀∅RΦφ±≥≤°\[\]()]', '', str(value_str))
    cleaned = re.sub(r'[a-zA-Z]', '', cleaned)  # Remove units like mm, inch
    cleaned = cleaned.strip()
    
    # Handle tolerance notation (e.g., "137+4" -> "137", "50±0.1" -> "50")
    base_value = cleaned.split('+')[0].split('-')[0].split('±')[0]
    
    # Extract first number found
    number_match = re.search(r'-?\d+\.?\d*', base_value)
    if number_match:
        try:
            return float(number_match.group())
        except (ValueError, TypeError):
            pass
    
    return None

def apply_tolerance_to_dimensions(dimensions, tolerance_mm, is_additive=True):
    """
    Apply tolerance to dimensions based on whether the feature is additive or subtractive.
    
    Args:
        dimensions: Dictionary of dimension values
        tolerance_mm: Tolerance value in mm
        is_additive: True for additive features (base shapes), False for subtractive features (holes)
        
    Returns:
        Dictionary with tolerance-adjusted dimensions
    """
    tolerance_dims = dimensions.copy()
    
    for key, value in dimensions.items():
        if isinstance(value, (int, float)) and value > 0:
            if is_additive:
                # For additive features (base shapes), tolerance increases dimensions
                tolerance_dims[key] = value + tolerance_mm
            else:
                # For subtractive features (holes), tolerance increases the hole size (removes more material)
                tolerance_dims[key] = value + tolerance_mm
                
    return tolerance_dims

def calculate_net_volume(components):
    """
    Calculate net volume by subtracting removed material from base shapes
    Now includes both nominal and tolerance-adjusted calculations
    """
    # Nominal volumes
    base_volume = sum(comp['calculated_volume_mm3'] for comp in components if not comp['is_subtracted'])
    subtracted_volume = sum(comp['calculated_volume_mm3'] for comp in components if comp['is_subtracted'])
    nominal_net = base_volume - subtracted_volume
    
    # Tolerance-adjusted volumes
    base_volume_tol = sum(comp.get('volume_with_tolerance_mm3', comp['calculated_volume_mm3']) 
                         for comp in components if not comp['is_subtracted'])
    subtracted_volume_tol = sum(comp.get('volume_with_tolerance_mm3', comp['calculated_volume_mm3']) 
                               for comp in components if comp['is_subtracted'])
    tolerance_net = base_volume_tol - subtracted_volume_tol
    
    return {
        'nominal_volumes': {
            'base_volume_mm3': round(base_volume, 2),
            'subtracted_volume_mm3': round(subtracted_volume, 2),
            'net_volume_mm3': round(nominal_net, 2)
        },
        'tolerance_volumes': {
            'base_volume_mm3': round(base_volume_tol, 2),
            'subtracted_volume_mm3': round(subtracted_volume_tol, 2),
            'net_volume_mm3': round(tolerance_net, 2)
        },
        'volume_changes': {
            'base_volume_change_mm3': round(base_volume_tol - base_volume, 2),
            'subtracted_volume_change_mm3': round(subtracted_volume_tol - subtracted_volume, 2),
            'net_volume_change_mm3': round(tolerance_net - nominal_net, 2)
        }
    }

def get_material_density(material_name):
    """
    Get material density based on material name with flexible matching
    
    Args:
        material_name: Name of the material
        
    Returns:
        Density in g/mm³ or None if not found
    """
    if not material_name:
        return None
    
    # Direct lookup
    if material_name in MATERIAL_DENSITIES:
        return MATERIAL_DENSITIES[material_name]
    
    # Flexible matching - remove spaces, hyphens, and case variations
    normalized_input = material_name.replace(' ', '').replace('-', '').upper()
    
    for material, density in MATERIAL_DENSITIES.items():
        normalized_material = material.replace(' ', '').replace('-', '').upper()
        if normalized_input in normalized_material or normalized_material in normalized_input:
            return density
    
    # If no match found, return default steel density
    return 0.00785

def calculate_mass_from_volume(volume_mm3, material_name="20MnCr5"):
    """
    Calculate mass based on volume and material density
    
    Args:
        volume_mm3: Volume in cubic millimeters
        material_name: Name of the material (default: "20MnCr5")
        
    Returns:
        Dictionary with mass calculations in different units
    """
    if volume_mm3 <= 0:
        return {
            'mass_grams': 0.0,
            'mass_kg': 0.0,
            'material_used': material_name,
            'density_g_per_mm3': 0.0,
            'volume_mm3': volume_mm3
        }
    
    density = get_material_density(material_name)
    mass_grams = volume_mm3 * density
    
    return {
        'mass_grams': round(mass_grams, 3),
        'mass_kg': round(mass_grams / 1000, 6),
        'material_used': material_name,
        'density_g_per_mm3': density,
        'volume_mm3': round(volume_mm3, 2)
    }

def calculate_mass_with_tolerance(components, material_name="20MnCr5"):
    """
    Calculate mass for all components including tolerance variations
    
    Args:
        components: List of component dictionaries from volume calculation
        material_name: Name of the material
        
    Returns:
        Dictionary with detailed mass calculations
    """
    result = {
        'material_used': material_name,
        'density_g_per_mm3': get_material_density(material_name),
        'components': [],
        'summary': {}
    }
    
    # Calculate mass for each component
    for component in components:
        comp_mass = {
            'name': component['name'],
            'is_subtracted': component['is_subtracted'],
            'nominal_mass': calculate_mass_from_volume(
                component['calculated_volume_mm3'], 
                material_name
            ),
            'tolerance_mass': calculate_mass_from_volume(
                component.get('volume_with_tolerance_mm3', component['calculated_volume_mm3']), 
                material_name
            )
        }
        
        # Calculate mass change due to tolerance
        comp_mass['mass_change'] = {
            'mass_change_grams': round(
                comp_mass['tolerance_mass']['mass_grams'] - comp_mass['nominal_mass']['mass_grams'], 
                3
            ),
            'mass_change_kg': round(
                comp_mass['tolerance_mass']['mass_kg'] - comp_mass['nominal_mass']['mass_kg'], 
                6
            )
        }
        
        result['components'].append(comp_mass)
    
    # Calculate summary masses
    base_components = [c for c in result['components'] if not c['is_subtracted']]
    subtracted_components = [c for c in result['components'] if c['is_subtracted']]
    
    # Nominal masses
    base_mass_nominal = sum(c['nominal_mass']['mass_grams'] for c in base_components)
    subtracted_mass_nominal = sum(c['nominal_mass']['mass_grams'] for c in subtracted_components)
    net_mass_nominal = base_mass_nominal - subtracted_mass_nominal
    
    # Tolerance masses
    base_mass_tolerance = sum(c['tolerance_mass']['mass_grams'] for c in base_components)
    subtracted_mass_tolerance = sum(c['tolerance_mass']['mass_grams'] for c in subtracted_components)
    net_mass_tolerance = base_mass_tolerance - subtracted_mass_tolerance
    
    result['summary'] = {
        'nominal_masses': {
            'base_mass_grams': round(base_mass_nominal, 3),
            'base_mass_kg': round(base_mass_nominal / 1000, 6),
            'subtracted_mass_grams': round(subtracted_mass_nominal, 3),
            'subtracted_mass_kg': round(subtracted_mass_nominal / 1000, 6),
            'net_mass_grams': round(net_mass_nominal, 3),
            'net_mass_kg': round(net_mass_nominal / 1000, 6)
        },
        'tolerance_masses': {
            'base_mass_grams': round(base_mass_tolerance, 3),
            'base_mass_kg': round(base_mass_tolerance / 1000, 6),
            'subtracted_mass_grams': round(subtracted_mass_tolerance, 3),
            'subtracted_mass_kg': round(subtracted_mass_tolerance / 1000, 6),
            'net_mass_grams': round(net_mass_tolerance, 3),
            'net_mass_kg': round(net_mass_tolerance / 1000, 6)
        },
        'mass_changes': {
            'base_mass_change_grams': round(base_mass_tolerance - base_mass_nominal, 3),
            'base_mass_change_kg': round((base_mass_tolerance - base_mass_nominal) / 1000, 6),
            'subtracted_mass_change_grams': round(subtracted_mass_tolerance - subtracted_mass_nominal, 3),
            'subtracted_mass_change_kg': round((subtracted_mass_tolerance - subtracted_mass_nominal) / 1000, 6),
            'net_mass_change_grams': round(net_mass_tolerance - net_mass_nominal, 3),
            'net_mass_change_kg': round((net_mass_tolerance - net_mass_nominal) / 1000, 6)
        }
    }
    
    return result

def calculate_simple_mass(components, material_name="20MnCr5"):
    """
    Calculate simple mass with tolerance - returns just the final mass value
    
    Args:
        components: List of component dictionaries from volume calculation
        material_name: Name of the material
        
    Returns:
        Simple dictionary with just the total mass
    """
    density = get_material_density(material_name)
    
    # Calculate net volume with tolerance
    base_volume_tolerance = sum(
        comp.get('volume_with_tolerance_mm3', comp['calculated_volume_mm3']) 
        for comp in components if not comp['is_subtracted']
    )
    subtracted_volume_tolerance = sum(
        comp.get('volume_with_tolerance_mm3', comp['calculated_volume_mm3']) 
        for comp in components if comp['is_subtracted']
    )
    
    net_volume_tolerance = base_volume_tolerance - subtracted_volume_tolerance
    # Ensure mass and volume are always positive
    total_mass_grams = abs(net_volume_tolerance * density)
    net_volume_tolerance = abs(net_volume_tolerance)
    return {
        "message": f"The total mass of material is {round(total_mass_grams, 3)} grams",
        "total_mass_grams": round(total_mass_grams, 3),
        "total_mass_kg": round(total_mass_grams / 1000, 6),
        "material": material_name,
        "net_volume_with_tolerance_mm3": round(net_volume_tolerance, 2)
    }

def get_available_materials():
    """
    Get list of available materials and their densities
    
    Returns:
        Dictionary of available materials and their properties
    """
    return {
        material: {
            'density_g_per_mm3': density,
            'density_g_per_cm3': density * 1000,
            'density_kg_per_m3': density * 1000000
        }
        for material, density in MATERIAL_DENSITIES.items()
    }