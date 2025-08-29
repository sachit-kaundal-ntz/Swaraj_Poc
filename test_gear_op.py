import json
from app.service.gear_rule_engine import classify_and_plan

with open(r"C:\Users\50013525\Documents\sbc_phase_1\outputs\drawings\66aefc3e-01ed-495b-b57c-9103c7b93522\66aefc3e-01ed-495b-b57c-9103c7b93522.json","r",encoding="utf-8") as f:
    j = json.load(f)

result = classify_and_plan(j)
print(result["gear_family"])
print(result["operations_sequence"])
# For audit:
for op, why in result["operations_evidence"].items():
    print(f"{op}: {why}")
