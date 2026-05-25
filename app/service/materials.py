

"""
materials.py
Material catalogue: density (g/cm³) + rate (INR/kg) for 11 materials.
All USD rates from spec converted at USD_TO_INR = 84.
Location: app/service/materials.py
"""

USD_TO_INR: float = 84.0          # keep in sync with gear_rule.py


def _inr(usd: float) -> float:
    """Convert USD rate to INR rate."""
    return round(usd * USD_TO_INR, 2)


MATERIAL_PROPERTIES: dict = {
    # ── Steels ────────────────────────────────────────────────────────────────
    "alloy-steel": {
        "density": 7.85,          # g/cm³
        "rate":    _inr(4.50),    # ₹378.00 / kg  (spec: $4.50/kg)
        "patterns": [
            "20mncr", "16mncr", "18crnimo", "42crmo",
            "4140", "4340", "en36", "scm", "8620",
            "alloy steel", "alloy-steel",
        ],
    },
    "carbon-steel": {
        "density": 7.85,
        "rate":    _inr(3.00),    # ₹252.00 / kg  (spec: $3.00/kg)
        "patterns": [
            "c45", "c35", "en8", "1045", "s45c",
            "mild steel", "carbon steel", "carbon-steel",
        ],
    },
    "stainless-steel": {
        "density": 8.00,
        "rate":    _inr(8.50),    # ₹714.00 / kg  (spec: $8.50/kg)
        "patterns": [
            "stainless", "ss304", "ss316",
            "aisi 316", "aisi316", "304", "316",
        ],
    },
    "cast-iron": {
        "density": 7.20,
        "rate":    _inr(2.50),    # ₹210.00 / kg  (spec: $2.50/kg)
        "patterns": [
            "cast iron", "gg25", "ggg40", "fc25",
            "sg iron", "cast-iron", "castiron",
        ],
    },
    # ── Non-ferrous metals ────────────────────────────────────────────────────
    "aluminium": {
        "density": 2.70,
        "rate":    _inr(6.50),    # ₹546.00 / kg  (spec: $6.50/kg)
        "patterns": [
            "aluminium", "aluminum", "6061", "7075",
            "al6061", "al7075",
        ],
    },
    "bronze": {
        "density": 8.80,
        "rate":    _inr(14.00),   # ₹1176.00 / kg (spec: $14.00/kg)
        "patterns": [
            "bronze", "phos bronze", "cusn", "c93200",
            "phosphor bronze",
        ],
    },
    "brass": {
        "density": 8.50,
        "rate":    _inr(11.00),   # ₹924.00 / kg  (spec: $11.00/kg)
        "patterns": ["brass", "cuzn", "c36000"],
    },
    # ── Plastics / polymer ────────────────────────────────────────────────────
    "nylon": {
        "density": 1.14,
        "rate":    _inr(6.00),    # ₹504.00 / kg  (spec: $6.00/kg)
        "patterns": ["nylon", "pa6", "pa66", "polyamide"],
    },
    "peek": {
        "density": 1.31,
        "rate":    _inr(110.00),  # ₹9240.00 / kg (spec: $110.00/kg)
        "patterns": ["peek", "polyetheretherketone"],
    },
    # ── Powder / sintered ─────────────────────────────────────────────────────
    "sintered-steel": {
        "density": 6.80,
        "rate":    _inr(5.50),    # ₹462.00 / kg  (spec: $5.50/kg)
        "patterns": [
            "sintered steel", "powder metal",
            "pm steel", "sintered-steel",
        ],
    },
    # ── Fallback ──────────────────────────────────────────────────────────────
    "default-steel": {
        "density": 7.85,
        "rate":    _inr(4.00),    # ₹336.00 / kg  (spec: $4.00/kg)
        "patterns": [],           # never matched by text — only used as fallback
    },
}