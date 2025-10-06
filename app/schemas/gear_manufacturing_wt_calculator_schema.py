from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class CalculationStep:
    """Tracks each step in the volume calculation process"""
    operation: str  # 'add', 'subtract', 'initialize'
    component: str  # 'gear_rim', 'hub', 'bore', etc.
    volume_mm3: float
    description: str
    dimensions_used: Dict[str, float] = field(default_factory=dict)
 
@dataclass
class MaterialProperties:
    """Material properties for mass calculation"""
    name: str
    density_g_per_cm3: float
    density_g_per_mm3: float
    source: str
 
@dataclass
class WeightProgression:
    """Tracks weight progression from raw material to finished part"""
    finished_weight_kg: float = 0.0
    forged_weight_kg: float = 0.0
    gross_weight_kg: float = 0.0
    material_utilization_percent: float = 0.0
    losses_breakdown: Dict[str, float] = field(default_factory=dict)
 