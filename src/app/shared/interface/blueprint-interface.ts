
export interface CellData {
  label: string;
  value?: string | number | null;
  unit?: string | null;
  tolerance?: string | null;
  source?: string;
}

export interface TableData {
  id: string;
  cells?: CellData[];
}

export interface DimensionData {
  id: string;
  symbol?: string;
  value?: string | number | null;
  unit?: string | null;
  tolerance?: string | null;
  view_id?: string;
}

export interface FeatureData {
  id: string;
  type?: string;
  role?: string;
  view_id?: string;
  fit_class?: string;
}

export interface ViewData {
  id: string;
  name?: string;
}

export interface ExtractedData {
  units?: string;
  tables?: TableData[];
  dimensions?: DimensionData[];
  features?: FeatureData[];
  views?: ViewData[];
  metadata?: {
    title_block?: { [key: string]: any };
  };
  assembly_order?: any[];
  token_usage?: any;
  error?: string;
}

export interface TaskResult {
  task_id: string;
  filename: string;
  file_size: number;
  status: string;
  has_errors?: boolean;
  extracted_data?: ExtractedData;
}

export interface VolumeResult {
  status: string;
  timestamp: string;
  dimensions_used: {
    gear_outer_diameter_mm: number;
    gear_face_width_mm: number;
    hub_outer_diameter_mm: number;
    hub_height_mm: number | null;
    bore_diameter_mm: number;
    bore_subtraction_applied: boolean;
  };
  volume_breakdown_mm3: {
    gear_rim_gross_mm3: number;
    hub_gross_mm3: number;
    bore_cylinder_mm3: number;
    total_net_mm3: number;
  };
  volume_summary: {
    total_volume_mm3: number;
    total_volume_cm3: number;
    total_volume_liters: number;
  };
  mass_calculation: {
    material: string;
    density_g_per_mm3: number;
    calculated_mass_g: number;
    calculated_mass_kg: number;
    drawing_specified_weight_kg: number | null;
    weight_difference_percent: number | null;
  };
  calculation_notes: string[];
}

export interface VolumeSummary {
  task_id: string;
  filename: string;
  calculated_mass_kg: number;
  calculated_mass_g: number;
  total_volume_cm3: number;
  material: string;
  key_dimensions: any;
}

export interface CostBreakdown {
  material_cost: number;
  operations_cost: number;
  overhead_pct: number;
  overhead_cost: number;
  subtotal: number;
  margin_pct: number;
  margin_cost: number;
  total_cost: number;
  currency: string;
}

export interface OperationDetail {
  step: number;
  operation: string;
  description: string;
  estimated_time_min: number;
  rate_per_hour: number;
  cost: number;
  machine_options: string[];
  source: string;
}

export interface ValidationRule {
  rule_id: string;
  layer: number;
  severity: string;
  passed: boolean;
  message: string;
}

export interface ValidationReport {
  validation_passed: boolean;
  confidence_score: number;
  confidence_level: string;
  ready_for_quote: boolean;
  error_count: number;
  warn_count: number;
  rules: ValidationRule[];
}

export interface PipelineResult {
  gear_family: string;
  cost_breakdown: CostBreakdown;
  operations_detail: OperationDetail[];
  validation_report: ValidationReport;
}
