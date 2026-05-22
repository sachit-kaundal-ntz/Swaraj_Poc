"""
materials.py
Material catalogue — density (g/cm³) + rate ($/kg) for 15 materials.
Location: app/service/materials.py

Used by cost_service.match_material() via:  from .materials import MATERIAL_PROPERTIES
"""

MATERIAL_PROPERTIES = {
    "alloy-steel": {
        "density": 7.85,
        "rate": 4.50,
        "patterns": [
            "20mncr", "16mncr", "4140", "4340", "en36",
            "scm", "8620", "alloy steel", "alloy-steel",
            "en353", "527m20", "18crnimo",
        ],
    },
    "carbon-steel": {
        "density": 7.85,
        "rate": 3.00,
        "patterns": [
            "c45", "c35", "en8", "1045", "s45c",
            "mild steel", "carbon steel", "en9", "c60",
            "s50c", "ck45",
        ],
    },
    "stainless-steel": {
        "density": 8.00,
        "rate": 8.50,
        "patterns": [
            "stainless", "ss304", "ss316", "aisi 316", "aisi 304",
            "304l", "316l", "17-4", "ph17", "en58",
        ],
    },
    "cast-iron": {
        "density": 7.20,
        "rate": 2.50,
        "patterns": [
            "cast iron", "gg25", "ggg40", "fc25", "sg iron",
            "grey iron", "ductile iron", "nodular iron",
            "gci", "en-gjl",
        ],
    },
    "aluminium": {
        "density": 2.70,
        "rate": 6.50,
        "patterns": [
            "aluminium", "aluminum", "6061", "7075",
            "al6061", "al7075", "2024", "5052",
            "a380", "lm6",
        ],
    },
    "bronze": {
        "density": 8.80,
        "rate": 14.00,
        "patterns": [
            "bronze", "phos bronze", "phosphor bronze",
            "cusn", "c93200", "pb2", "tin bronze", "gunmetal",
        ],
    },
    "brass": {
        "density": 8.50,
        "rate": 11.00,
        "patterns": [
            "brass", "cuzn", "c36000", "free cutting brass",
            "c26000", "cartridge brass", "naval brass",
        ],
    },
    "nylon": {
        "density": 1.14,
        "rate": 6.00,
        "patterns": [
            "nylon", "pa6", "pa66", "polyamide",
            "pa12", "nylon 6", "nylon 66",
        ],
    },
    "peek": {
        "density": 1.31,
        "rate": 110.00,
        "patterns": [
            "peek", "polyetheretherketone",
            "poly ether ether ketone",
        ],
    },
    "sintered-steel": {
        "density": 6.80,
        "rate": 5.50,
        "patterns": [
            "sintered steel", "powder metal", "pm steel",
            "sintered iron", "metal powder", "p/m",
        ],
    },
    "tool-steel": {
        "density": 7.85,
        "rate": 12.00,
        "patterns": [
            "d2", "h13", "m2", "tool steel", "hss",
            "high speed steel", "d3", "o1", "a2",
        ],
    },
    "titanium": {
        "density": 4.51,
        "rate": 35.00,
        "patterns": [
            "titanium", "ti-6al-4v", "grade 5", "ti64",
            "grade 2", "astm b265",
        ],
    },
    "copper": {
        "density": 8.96,
        "rate": 9.50,
        "patterns": [
            "copper", "pure copper", "cu-ehc", "c10100",
            "electrolytic copper",
        ],
    },
    "inconel": {
        "density": 8.44,
        "rate": 55.00,
        "patterns": [
            "inconel", "625", "718", "nickel alloy",
            "nimonic", "hastelloy",
        ],
    },
    "default-steel": {
        "density": 7.85,
        "rate": 4.00,
        "patterns": [],   # fallback — matched last
    },
}