import json
import math

def calculate_gear_mass(extracted_data_json):
    """
    Calculates the mass of a gear based on extracted JSON data from an engineering drawing.
    Uses the CORRECT method for volume calculation.

    Args:
        extracted_data_json (str/dict): The JSON string or dictionary containing the extracted data.

    Returns:
        dict: A dictionary containing the calculated mass, volume, and all intermediate steps.
    """
    
    # Load the JSON data if it's a string
    if isinstance(extracted_data_json, str):
        try:
            data = json.loads(extracted_data_json)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON string provided"}
    else:
        data = extracted_data_json
        
    # Extract key parameters with error handling
    try:
        # Material density (hardcoded for 20MnCr5 steel)
        DENSITY_G_PER_CM3 = 7.85
        DENSITY_KG_PER_CM3 = DENSITY_G_PER_CM3 / 1000  # 0.00785 kg/cm³

        # Check if we have the nested structure with extracted_data
        if 'extracted_data' in data:
            data = data['extracted_data']
        
        # Get geometric features
        geo_features = data.get('geometric_features', [])
        if not geo_features:
            return {"error": "Geometric features not found in JSON data"}
        
        # Find tip diameter (F016)
        tip_dia_feature = next((f for f in geo_features if f.get('feature_id') == 'F016_GearTeeth_OuterDiameter'), None)
        if not tip_dia_feature:
            return {"error": "Tip diameter feature (F016) not found"}
        tip_dia = float(tip_dia_feature['dimensions']['diameter']['nominal_value'])  # mm
        
        # Find overall length (F001)
        length_feature = next((f for f in geo_features if f.get('feature_id') == 'F001_MainBody_OverallLength'), None)
        if not length_feature:
            return {"error": "Overall length feature (F001) not found"}
        face_width = float(length_feature['dimensions']['length']['nominal_value'])  # mm
        
        # Find hub diameter (F012)
        hub_dia_feature = next((f for f in geo_features if f.get('feature_id') == 'F012_MainBody_Hub_Diameter'), None)
        if not hub_dia_feature:
            return {"error": "Hub diameter feature (F012) not found"}
        hub_dia = float(hub_dia_feature['dimensions']['diameter']['nominal_value'])  # mm
        
        # Get spline specifications
        if 'specialized_data' in data and 'spline_specifications' in data['specialized_data']:
            spline_specs = data['specialized_data']['spline_specifications'][0]['parameters']
        else:
            return {"error": "Spline specifications not found in JSON data"}
        
        # Get spline major diameter and parse tolerance
        spline_major_dia = float(spline_specs['major_diameter']['nominal_value'])  # mm
        tolerance_notation = spline_specs['major_diameter']['tolerance_notation']
        if '/' in tolerance_notation:
            tolerance_parts = tolerance_notation.split(' / ')
            upper_tolerance = float(tolerance_parts[0].replace('+', ''))
            spline_major_dia_max = spline_major_dia + upper_tolerance
        else:
            spline_major_dia_max = spline_major_dia
        
        # CORRECT APPROACH: Use the gear body diameter instead of calculating root diameter
        # Find gear body diameter (F013)
        gear_body_dia_feature = next((f for f in geo_features if f.get('feature_id') == 'F013_MainBody_GearBody_Diameter'), None)
        if not gear_body_dia_feature:
            return {"error": "Gear body diameter feature (F013) not found"}
        gear_body_dia = float(gear_body_dia_feature['dimensions']['diameter']['nominal_value'])  # mm
        
        # Convert all dimensions to cm for volume calculation
        tip_radius_cm = tip_dia / 20  # mm to cm
        gear_body_radius_cm = gear_body_dia / 20
        hub_radius_cm = hub_dia / 20
        spline_radius_cm = spline_major_dia_max / 20
        face_width_cm = face_width / 10
        
        print(f"Debug - Dimensions in cm:")
        print(f"Tip radius: {tip_radius_cm}")
        print(f"Gear body radius: {gear_body_radius_cm}")
        print(f"Hub radius: {hub_radius_cm}")
        print(f"Spline radius: {spline_radius_cm}")
        print(f"Face width: {face_width_cm}")
        
        # CORRECT VOLUME CALCULATION:
        # 1. Volume of gear as solid cylinder from tip to spline
        volume_solid = math.pi * face_width_cm * (tip_radius_cm**2 - spline_radius_cm**2)
        
        # 2. Volume to subtract for tooth spaces (approximation)
        # The tooth space volume is roughly 40-50% of the volume between tip and gear body
        tooth_space_volume = 0.45 * math.pi * face_width_cm * (tip_radius_cm**2 - gear_body_radius_cm**2)
        
        # 3. Final volume
        total_volume_cm3 = volume_solid - tooth_space_volume
        
        # Calculate mass
        mass_kg = total_volume_cm3 * DENSITY_KG_PER_CM3
        
        # Prepare detailed results
        results = {
            "mass_kg": round(mass_kg, 2),
            "volume_cm3": round(total_volume_cm3, 2),
            "intermediate_calculations": {
                "tip_diameter_mm": tip_dia,
                "gear_body_diameter_mm": gear_body_dia,
                "hub_diameter_mm": hub_dia,
                "spline_major_diameter_max_mm": round(spline_major_dia_max, 2),
                "face_width_mm": face_width,
                "volume_solid_cm3": round(volume_solid, 2),
                "tooth_space_volume_cm3": round(tooth_space_volume, 2),
                "density_kg_per_cm3": DENSITY_KG_PER_CM3
            },
            "calculation_method": "Solid volume minus tooth space volume approximation",
            "assumptions": [
                "Tooth space volume estimated as 45% of tip-to-body volume",
                "Used maximum spline major diameter (+0.62 tolerance)",
                "Material density: 7.85 g/cm³ for 20MnCr5 steel",
                "Based on gear body diameter instead of calculated root diameter"
            ]
        }
        
        return results
        
    except KeyError as e:
        return {"error": f"Missing required data in JSON: {str(e)}"}
    except Exception as e:
        return {"error": f"Calculation failed: {str(e)}"}

# Example usage with your JSON data
if __name__ == "__main__":
    try:
        # Load your extracted JSON data
        with open('extracted_gear_data.json', 'r') as file:
            extracted_json_data = json.load(file)
        
        # Calculate mass
        result = calculate_gear_mass(extracted_json_data)
        
        # Print results
        print("Gear Mass Calculation Results:")
        print(json.dumps(result, indent=2))
        
        # Save results to file
        with open('mass_calculation_result.json', 'w') as out_file:
            json.dump(result, out_file, indent=2)
            
    except FileNotFoundError:
        print("Error: extracted_gear_data.json file not found")
    except json.JSONDecodeError:
        print("Error: Invalid JSON in extracted_gear_data.json")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")