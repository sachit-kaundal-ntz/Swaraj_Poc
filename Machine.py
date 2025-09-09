import os
import json
from langchain_groq import ChatGroq  
# ---------------------------
# Setup Groq Client
# ---------------------------
# Make sure you set your API key in environment before running:
# export GROQ_API_KEY="your_api_key_here"
GROQ_API_KEY = 
client = ChatGroq(model= "llama-3.1-8b-instant", api_key=GROQ_API_KEY)
 
# ---------------------------
# Input Data
# ---------------------------
operations_and_machines = {
    "Forging": ["Forging Complex (Stg arms)", "Forging Symmetrical (Round Gears & Shafts)"],
    "Normalising": ["Normalising Furnace"],
    "Annealing": ["Annealing Furnace"],
    "Isothermal Annealing": ["Isothermal Annealing Furnace"],
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
    "Blackodizing": ["Blackodizing Furnace"]
}
 
# Example: paste your extracted JSON from the drawing
with open("crosscheck.json", "r") as f:
    gear_json_response = json.load(f)["extracted_data"]
 
# ---------------------------
# Prompt Construction
# ---------------------------
system_prompt = """
You are an expert in gear manufacturing.
You know about machining, forging, gear hobbing, heat treatment, surface treatment, inspection, and finishing operations.
Your task is to analyze engineering drawing data and map it to manufacturing operations and machines.
"""
 
user_prompt = f"""
I will give you two inputs:
1. A list of operations and machines with their descriptions.
2. A JSON response extracted from an engineering drawing.
 
Your task:
- Identify which operations are required for this part based on the JSON.
- Map each operation to the correct machine(s).
- Provide reasoning for why this operation and machine is selected (based on keywords or dimensional/heat-treatment/surface-treatment requirements in the JSON).
- Return the output strictly in this structured JSON format:
 
{{
  "operations": [
    {{
      "operation": "<operation name>",
      "machines": ["<machine 1>", "<machine 2>"],
      "reason": "<why this operation and these machines are needed, referencing JSON values>"
    }}
  ]
}}
 
Only include relevant operations. Do not add extra ones.
 
Operations and Machines list:
{json.dumps(operations_and_machines, indent=2)}
 
Drawing JSON response:
{json.dumps(gear_json_response, indent=2)}
"""
 
# ---------------------------
# Call Groq LLM
# ---------------------------
 
# ---------------------------
# Call Groq LLM using LangChain's .invoke()
# ---------------------------
response = client.invoke([
  {"role": "system", "content": system_prompt},
  {"role": "user", "content": user_prompt}
])
output_text = response.content.strip()
 
try:
  result = json.loads(output_text)  # ensure JSON parsing
except json.JSONDecodeError:
  print("⚠️ LLM did not return valid JSON, raw output:")
  print(output_text)
  result = None
 
# ---------------------------
# Print Final Operations → Machines Mapping
# ---------------------------
print(json.dumps(result, indent=2))