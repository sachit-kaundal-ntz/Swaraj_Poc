import json

with open(r"F:\pocSwaraj\test6.json", "r") as f:

    data = json.load(f)
 
extracted_data = data["extracted_data"]

operation_machine_map = {

    "Forging": ["Forging Complex ( Stg arms )", "Forging Symmetrical ( Round Gears & Shafts)"],

    "Normalising": ["Normalising Furnace"],

    "Isothermal Annealing": ["Isothermal Annealing Furnace"],

    "Annealing": ["Annealing Furnace"],

    "Carburising": ["Carburising GCF", "Carburising SQF", "Carburising Salt bath"],

    "Carbonitriding": ["Carbonitriding Furnace"],

    "Tempering": ["Tempering Furnace"],

    "Hardening & Tempering": ["Hardening & Tempering Furnace"],

    "Induction Hardening": ["Induction Hardening M/c"],

    "Gear Hobbing": ["Gear Hobbing CNC", "Gear Hobbing Conventional"],

    "Gear Shaping": ["Gear Shaping Conventional"],

    "Gear Shaving": ["Gear Shaving CNC", "Gear Shaving Conventional"],

    "Gear Grinding": ["Gear Grinding", "CNC Grinding"],

    "Chamfering": ["Gear Tooth Chamfering"],

    "Grinding": ["Grinding Cylindrical", "Grinding Surface", "Grinding Centreless"],

    "Broaching": ["Horizontal Broaching", "Vertical Broaching"],

    "Drilling": ["Drilling - Pillar Type", "Drilling - Radial"],

    "Gun Drilling": ["Gun Drilling SPM (Deep Hole)", "Gun Drilling Conventional"],

    "Turning": ["CNC Turning Centre /twin chuck", "Lathe CNC", "Vertical Turning Centre CNC"],

    "Inspection": ["Magnaflux", "Manual"],

    "Shot Blasting": ["Shot Blasting"],

    "Shot Peening": ["Shot Peening"],

    "Plating": ["Cr Plating Tank PKG", "Cr Plating Tank PSI", "Zinc Passivation / Plating"],

    "Phosphating": ["Phosphating Tank"],

    "Powder Coating": ["Powder Coating"],

    "Primer Coating / Painting": ["Primer Coating", "Painting cum primer"],

    "Blackodizing": ["Blackodizing Furnace"],

}


keywords_to_operations = {

    "forging": "Forging",

    "normalized": "Normalising",

    "anneal": "Annealing",

    "isothermal": "Isothermal Annealing",

    "carburized": "Carburising",

    "carbonitriding": "Carbonitriding",

    "tempering": "Tempering",

    "hardness": "Hardening & Tempering",

    "induction": "Induction Hardening",

    "gear": "Gear Hobbing",

    "spline": "Broaching",

    "grinding": "Gear Grinding",

    "chamfer": "Chamfering",

    "drill": "Drilling",

    "blast": "Shot Blasting",

    "peen": "Shot Peening",

    "plate": "Plating",

    "phosphate": "Phosphating",

    "powder": "Powder Coating",

    "paint": "Primer Coating / Painting",

    "blackodizing": "Blackodizing",

    "inspect": "Inspection",

}

found_operations = {}
 
def scan_json(obj):

    if isinstance(obj, dict):

        for k, v in obj.items():

            scan_json(v)

    elif isinstance(obj, list):

        for v in obj:

            scan_json(v)

    elif isinstance(obj, str):

        lower_val = obj.lower()

        for key, operation in keywords_to_operations.items():

            if key in lower_val:

                found_operations[operation] = {

                    "machines": operation_machine_map.get(operation, []),

                    "reason": f"Found keyword '{key}' in JSON value: '{obj}'"

                }
 
scan_json(extracted_data)

import pprint

pprint.pprint(found_operations)

 
