import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
# import json

def find_table_by_id(data, table_id):
    """
    Helper function to find a table within the extracted_data by its ID.
    
    Args:
        data (dict): The main JSON data structure.
        table_id (str): The ID of the table to find (e.g., 'tbl_gear_data').

    Returns:
        dict or None: The table dictionary if found, otherwise None.
    """
    tables = data.get('extracted_data', {}).get('tables', [])
    for table in tables:
        if table.get('id') == table_id:
            return table
    return None

def find_cell_by_label_keyword(table, keyword):
    """
    Helper function to find a cell within a table by a keyword in its 'label'.
    The search is case-insensitive.
    
    Args:
        table (dict): The table dictionary to search within.
        keyword (str): The keyword to search for in the cell labels.

    Returns:
        dict or None: The cell dictionary if a match is found, otherwise None.
    """
    if not table:
        return None
    cells = table.get('cells', [])
    for cell in cells:
        if keyword.lower() in cell.get('label', '').lower():
            return cell
    return None

def find_cell_by_value_keyword(table, keyword):
    """
    Helper function to find a cell within a table by a keyword in its 'value'.
    The search is case-insensitive.

    Args:
        table (dict): The table dictionary to search within.
        keyword (str): The keyword to search for in the cell values.

    Returns:
        dict or None: The cell dictionary if a match is found, otherwise None.
    """
    if not table:
        return None
    cells = table.get('cells', [])
    for cell in cells:
        # Ensure value is a string before checking
        cell_value = cell.get('value', '')
        if isinstance(cell_value, str) and keyword.lower() in cell_value.lower():
            return cell
    return None

def identify_manufacturing_processes(data):
    """
    Analyzes gear manufacturing data from a JSON object and identifies
    the required manufacturing processes based on a rule-based system.

    Args:
        data (dict): The input JSON data loaded as a Python dictionary.

    Returns:
        list: A list of dictionaries, where each dictionary contains a
              manufacturing process and the reason for its identification.
    """
    results = []
    identified_processes = set()

    def add_process(process, reason):
        """Adds a process to the results list if it hasn't been added already."""
        if process not in identified_processes:
            results.append({"process": process, "reason": reason})
            identified_processes.add(process)

    # --- Rule 1: Forging ---
    forging_table = find_table_by_id(data, 'tbl_forging_details')
    if forging_table:
        add_process("Forging", "Keyword found: Presence of table with id 'tbl_forging_details'.")
        
        # --- Rule 2: Normalising (dependent on Forging) ---
        normalized_cell = find_cell_by_label_keyword(forging_table, "NORMALIZED")
        if normalized_cell:
            reason = f"Keyword found in forging details: '{normalized_cell.get('label')}' with value '{normalized_cell.get('value')}' {normalized_cell.get('unit', '')}."
            add_process("Normalising", reason)

    # --- Rule 3: Turning Operations ---
    has_cylindrical_features = False
    if 'features' in data.get('extracted_data', {}):
        for feature in data['extracted_data']['features']:
            if feature.get('type', '').startswith('cylindrical'):
                has_cylindrical_features = True
                break
    if not has_cylindrical_features and 'dimensions' in data.get('extracted_data', {}):
        for dim in data['extracted_data']['dimensions']:
            if dim.get('symbol') == '⌀':
                has_cylindrical_features = True
                break
    
    if has_cylindrical_features:
        add_process("Facing & Centering", "Inferred as a necessary pre-machining step for turning operations on a forged blank.")
        add_process("Rough Turning", "Keyword found: Presence of multiple cylindrical features and diameter dimensions (symbol: '⌀').")
        add_process("Finish Turning", "Keyword found: Tight tolerances on various diameters require a finishing pass.")
        add_process("Vertical Turning Centre (VTC)", "Implied for machining gear blanks with multiple diameters and faces.")

    # --- Rule 4: Gear Tooth Cutting ---
    gear_data_table = find_table_by_id(data, 'tbl_gear_data')
    if gear_data_table:
        reason = "Keyword found: Presence of 'tbl_gear_data' with gear parameters like Module, No of Teeth, etc."
        add_process("Gear Hobbing", reason)

    # --- Rule 5: Internal Spline Cutting ---
    spline_table = find_table_by_id(data, 'tbl_spline_data')
    if spline_table:
        reason = "Keyword found: Presence of 'tbl_spline_data' indicating an internal spline feature."
        add_process("Broaching", reason)

    # --- Rule 6: Heat Treatment ---
    heat_treatment_table = find_table_by_id(data, 'tbl_heat_treatment')
    is_hardened = False
    if heat_treatment_table:
        carburized_cell = find_cell_by_label_keyword(heat_treatment_table, "CARBURIZED")
        if carburized_cell:
            reason = f"Keyword found in heat treatment: '{carburized_cell.get('label')}'"
            add_process("Carburising", reason)

        harden_cell = find_cell_by_label_keyword(heat_treatment_table, "HARDEN TO")
        if harden_cell:
            is_hardened = True
            reason = f"Keyword found in heat treatment: '{harden_cell.get('label')}' with target hardness '{harden_cell.get('value')} {harden_cell.get('unit')}'."
            add_process("Hardening & Tempering", reason)

    # --- Rule 7: Surface Treatment ---
    surface_treatment_table = find_table_by_id(data, 'tbl_surface_treatment')
    if surface_treatment_table:
        shot_blast_cell = find_cell_by_label_keyword(surface_treatment_table, "SHOT BLAST")
        if shot_blast_cell:
            reason = f"Keyword found in surface treatment: '{shot_blast_cell.get('label')}'"
            add_process("Shot Blasting", reason)

    # --- Rule 8: Deburring / Chamfering ---
    general_notes_table = find_table_by_id(data, 'tbl_general_notes')
    if general_notes_table:
        burr_cell = find_cell_by_value_keyword(general_notes_table, "FREE FROM BURRS")
        if burr_cell:
            reason = f"Keyword found in general notes: Instruction to be '{burr_cell.get('value')}'."
            add_process("Deburring", reason)
            add_process("Gear Tooth Chamfering", reason)
    
    # --- Rule 9: Gear Grinding (Hard Finishing) ---
    if is_hardened and gear_data_table:
        quality_cell = find_cell_by_label_keyword(gear_data_table, "QUALITY OF TOLERANCE ZONE")
        if quality_cell:
            reason = f"High precision gear ({quality_cell.get('label')}: {quality_cell.get('value')}) requires hard finishing after heat treatment distortion."
            add_process("Gear Grinding", reason)

    # --- Rule 10: Inspection ---
    deviations_table = find_table_by_id(data, 'tbl_permissible_deviations')
    if deviations_table:
        reason = "Keyword found: Presence of 'tbl_permissible_deviations' which lists specific geometric tolerances to be inspected."
        add_process("Inspection", reason)
        
    # --- Rule 11: Cleaning (Inferred) ---
    if is_hardened:
        add_process("Washing / RPO Application", "Inferred as a standard process to clean parts before heat treatment and for rust prevention post-manufacturing.")

    return results
app = FastAPI(title="Gear Manufacturing Process API")

@app.post("/identify_processes/")
async def identify_processes(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")

    try:
        processes = identify_manufacturing_processes(data)
        return JSONResponse(content={"processes": processes})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")
