# Material density database (g/cm³)
MATERIAL_DATABASE = {
    'en353': 7.85,
    '20mncr5': 7.85,
    'is:9175': 7.85,
    'bs:970': 7.85,
    'sae8620': 7.85,
    'sae8622h': 7.85,
    '4140': 7.85,
    '4340': 7.85,
    'steel': 7.85,
    'carbon_steel': 7.85,
    'alloy_steel': 7.85,
    'default_steel': 7.85
}
  
# Manufacturing operations detection rules
OPERATION_RULES = {
    'Forging': {
        'materials': ['20MnCr5', 'EN353', '4140', '4340', '8620'],
        'geometry': ['stepped', 'hub', 'complex'],
        'keywords': ['forged', 'forging']
    },
    'Hardening and Tempering': {
        'keywords': ['normaliz', 'anneal', 'harden', 'temper'],
        'heat_treatment': True
    },
    'Rough Turning': {
        'geometry': ['cylinder', 'diameter', 'bore'],
        'always': True
    },
    'Finish Turning': {
        'tolerances': ['H7', 'H8', 'H9', '±0.1', '±0.05'],
        'follows': 'Rough Turning'
    },
    'Broaching': {
        'features': ['internal_spline', 'keyway', 'internal_gear'],
        'keywords': ['spline', 'DIN 5480']
    },
    'Hobbing': {
        'features': ['external_gear_teeth', 'helical', 'spur'],
        'keywords': ['teeth', 'module', 'helix']
    },
    'Gear Tooth Chamfering': {
        'features': ['tooth_chamfer', 'gear_tip_chamfer'],
        'keywords': ['tooth edge chamfer', 'gear tip chamfer']
    },
    'Carburising': {
        'keywords': ['carburiz', 'case harden', 'case depth'],
        'heat_treatment': ['case', 'HRC']
    },
    'Grinding': {
        'post_heat_treat': True,
        'tolerances': ['tight', 'H7', 'H6'],
        'keywords': ['grind', 'ground']
    }
}