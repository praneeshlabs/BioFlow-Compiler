export type StepType =
  | "prep"
  | "dilution"
  | "incubation"
  | "wash"
  | "addition"
  | "detection"
  | "purification"
  | "qc"
  | "other";

export interface ReagentVolume {
  reagent: string;
  volume?: string | null;
  concentration?: string | null;
}

export interface ProtocolStep {
  id: string;
  name: string;
  description: string;
  step_type: StepType;
  duration_minutes: number;
  depends_on: string[];
  reagents: ReagentVolume[];
  well_targets: string[];
  stock_conc?: string | null;
  target_conc?: string | null;
  final_volume?: string | null;
}

export interface UnitCheckResult {
  step_id: string;
  reagent: string;
  stock_conc?: string | null;
  target_conc?: string | null;
  final_volume?: string | null;
  stock_volume_needed?: string | null;
  diluent_volume_needed?: string | null;
  dilution_factor?: number | null;
  valid: boolean;
  message: string;
}

export interface DAGNodeOut {
  id: string;
  name: string;
  step_type: StepType;
  duration_minutes: number;
  on_critical_path: boolean;
  is_bottleneck: boolean;
  layer: number;
}

export interface DAGEdgeOut {
  source: string;
  target: string;
}

export interface DAGValidationResult {
  nodes: DAGNodeOut[];
  edges: DAGEdgeOut[];
  is_acyclic: boolean;
  total_runtime_minutes: number;
  critical_path: string[];
  bottleneck_step_id?: string | null;
  cycle_nodes: string[];
  message: string;
}

export interface HazardFlag {
  reagent: string;
  cid?: number | null;
  ghs_pictograms: string[];
  hazard_statements: string[];
  is_hazardous: boolean;
  source: string;
  lookup_status: "ok" | "not_found" | "error";
}

export interface WellAssignment {
  well_id: string;
  reagent_summary: string;
  total_volume_ul: number;
  hazardous: boolean;
  step_ids: string[];
}

export interface PlateLayoutResult {
  plate_size: number;
  rows: number;
  cols: number;
  wells: WellAssignment[];
  manual_layout_required: boolean;
  message: string;
}

export interface ProtocolState {
  protocol_name: string;
  golden_path_matched?: string | null;
  raw_text: string;
  steps: ProtocolStep[];
  dag: DAGValidationResult;
  unit_checks: UnitCheckResult[];
  hazards: HazardFlag[];
  plate: PlateLayoutResult;
  warnings: string[];
}

export interface GoldenPathPreview {
  key: string;
  name: string;
  description: string;
  preview_text: string;
}
