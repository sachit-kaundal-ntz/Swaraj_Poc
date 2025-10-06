
# Mapping of internal operation codes → human-readable operation names
OPS = {
    # Raw stock / pre-machining
    "SAWING": "Sawing",
    "FORGING": "Forging",
    "BLANKING": "Blanking/ Piercing",
    "STRAIGHTENING": "Straightening",
    # Heat treatment
    "ISOTHERMAL_ANNEAL": "Isothermal Annealing",
    "ANNEAL": "Annealing",
    "NORMALIZE": "Annealing",  # normalized under Annealing bucket
    "CARBURIZE": "Carburizing",
    "CARBON_NITRIDING": "Carbon Nitriding",
    "HARDEN_TEMPER": "Hardening and Tempering",
    "INDUCTION_HARDEN": "Induction Hardening",
    "TEMPER": "Tempering",
    # Machining
    "FACING_CENTERING": "Facing and Centering",
    "ROUGH_TURN": "Rough Turning",
    "FINISH_TURN": "Finish Turning",
    "DRILL_TAP_REAM": "Drilling/Tapping/Reaming",
    "GUN_DRILL": "Gun Drilling",
    "MILL": "Milling",
    "SLOT": "Slotting",
    "TRAUB": " Traub",
    "VTC": "Vertical Turning Centre",
    "VMC": "VMC",
    "HMC": "HMC",
    # Gear-specific
    "GEAR_ROLL": "Gear Rolling",
    "GEAR_HOB": "Gear Hobbing",
    "GEAR_SHAPE": "Gear Shaping",
    "GEAR_SHAVE": "Gear Shaving",
    "GEAR_TOOTH_CHAMFER": "Gear Tooth Chamfering",
    "GEAR_GRIND": "Gear Grinding",
    "BEVEL_CUT": "Bevel Cutting",
    # Spline / internal profile
    "BROACH": "Broaching",
    # Finishing / surface
    "GRIND": "Grinding",
    "DEBURR": "Deburring",
    "SHOT_BLAST": "Shot Blasting",
    "SHOT_PEEN": "Shot Peening",
    "BLACKODIZE": "Blackodizing",
    "CR_PLATE": "Cr Plating",
    "PHOSPHATE": "Phosphating",
    "POWDER_COAT": "Powder Coating",
    "PRIMER_COAT": "Primer Coating",
    "PRIMER_PAINT": "Primer Painting",
    "WASH_RPO": "Washing/RPO Application",
    # QC
    "INSPECTION": "Inspection",
    "MAGNAFLUX": "Magnaflux",
}

# Mapping of machine codes → human-readable machine names
MACHINES = {
    # Forging/press
    "FORGING_SYMMETRICAL": "Forging Symmetrical (Round Gears and Shafts)",
    "FORGING_MEDIUM": "Forging Medium Complexity",
    "FORGING_COMPLEX": "Forging Complex",
    "PRESS_100T": "100 T Press",
    "PRESS_150T": "150 T Press",
    "PRESS_200T": "200 T Press",
    # Heat treatment
    "ISOTHERMAL_FURNACE": "Isothermal Annealing Furnace",
    "NORMALIZING_FURNACE": "Normalizing Furnace",
    "CARB_SALT": "Carburising Salt Bath",
    "CARB_GCF": "Carburising GCF",
    "CARB_SQF": "Carburising SQF",
    "CARBON_NITRIDING_FURNACE": "Carbon Nitriding Furnace",
    "TEMPERING_FURNACE": "Tempering Furnace",
    "HARD_TEMPER_FURNACE": "Hardening & Tempering Furnace",
    "INDUCTION_MACHINE": "Induction Hardening M/c",
    # Lathes & turning
    "LATHE_CENTRE": "Lathe Centre",
    "LATHE_HEAVY": "Lathe Heavy Duty",
    "LATHE_CNC": "Lathe CNC",
    "CNC_TURN_TWIN": "CNC Turning Centre (Twin chuck)",
    "CNC_TURN_MORE": "CNC Turning Centre (More than)",
    "VTC_CNC": "Vertical Turning Centre CNC",
    # Drilling & gun drilling
    "DRILL_PILLAR": "Drilling Pillar Type",
    "DRILL_RADIAL": "Drilling Radial",
    "GUN_DRILL_CONV": "Gun Drilling Conventional",
    "GUN_DRILL_SPM": "Gun Drilling SPM",
    # Milling/slotting
    "SLOT_MACHINE": "Slotting M/c",
    "DUPLEX_MILL": "Duplex Milling",
    # Gear making
    "HOB_CONV": "Gear Hobbing Conventional",
    "HOB_CNC": "Gear Hobbing CNC",
    "SHAPER_CONV": "Gear Shaping Conventional",
    "CNC_SHAPER": "CNC Shaper",
    "SHAVE_CNC": "Gear Shaving CNC",
    "SHAVE_CONV": "Gear Shaving Conventional",
    "GEAR_ROLLING": "Gear Rolling",
    "GEAR_GRINDING": "Gear Grinding",
    "DRY_CUT_BEVEL_CNC": "Dry Cut Bevel CNC",
    "BEVEL_CONV": "Bevel Conventional",
    "GEAR_TOOTH_CHAMFER": "Gear Tooth Chamfering",
    # Grinding (general)
    "GRIND_CYL": "Grinding Cylinderical",
    "GRIND_SURF": "Grinding Surface",
    "GRIND_CENTERLESS": "Grinding Centreless",
    "CNC_GRINDING": "CNC Grinding",
    # CNC centers
    "VMC_SINGLE": "VMC Single Pallet",
    "VMC_DOUBLE": "VMC Double Pallet",
    "VMC_DOUBLE_XTRAV": "VMC Double Pallet with X trav",
    "HMC_500_IND": "HMC- 500 Indian",
    "HMC_630_IND": "HMC – 630 Indian",
    "HMC_500_IMP": "HMC –500 Imported",
    "HMC_630_IMP": "HMC – 630 Imported",
    # Broaching
    "BROACH_VERT": "Vertical Broaching",
    "BROACH_HORZ": "Horizontal Broaching",
    # Surface treatment
    "CR_PLATE_TANK_PSI": "Cr Plating Tank PSI",
    "CR_PLATE_TANK_PKG": "Cr Plating Tank PKG",
    "PHOS_TANK": "Phosphating Tank",
    "BLACKDIZING_FURNACE": "Blackdizing Furnace",
    # QC & aux
    "MAGNAFLUX": "MagnaFlux",
    "DEBURR_MACHINE": "Deburring M/c",
    "SHOT_BLAST": "Shot Blasting",
    "SHOT_PEEN": "Shot Peening",
    "STRAIGHTEN_PRESS": "Straightening Press",
    "SAW_BAND": "Sawing Bandsaw",
    "SAW_HACK": "Sawing Hacksaw",
    "TRAUB": "Traub",
}
