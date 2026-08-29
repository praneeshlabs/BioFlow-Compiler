"""
ProtocolForge — strictly typed schemas (Pydantic v2)

Everything the orchestrator produces and everything the frontend renders
flows through these models. Keeping the schema strict is what lets the
Protocol Studio UI render deterministically instead of defensively.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StepType(str, Enum):
    PREP = "prep"
    DILUTION = "dilution"
    INCUBATION = "incubation"
    WASH = "wash"
    ADDITION = "addition"
    DETECTION = "detection"
    PURIFICATION = "purification"
    QC = "qc"
    OTHER = "other"


class ReagentVolume(BaseModel):
    reagent: str
    volume: Optional[str] = Field(
        default=None, description="Raw volume string, e.g. '100 uL' or '5X'"
    )
    concentration: Optional[str] = Field(
        default=None, description="Raw concentration string, e.g. '1 mg/mL'"
    )


class ProtocolStep(BaseModel):
    id: str
    name: str
    description: str
    step_type: StepType = StepType.OTHER
    duration_minutes: float = Field(ge=0, default=0)
    depends_on: list[str] = Field(default_factory=list)
    reagents: list[ReagentVolume] = Field(default_factory=list)
    well_targets: list[str] = Field(
        default_factory=list,
        description="Well IDs this step touches, e.g. ['A1','A2']",
    )
    stock_conc: Optional[str] = None
    target_conc: Optional[str] = None
    final_volume: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _no_spaces(cls, v: str) -> str:
        return v.strip().replace(" ", "_")


# ---------------------------------------------------------------------------
# Tool #1 — Pint-backed dilution / unit verification
# ---------------------------------------------------------------------------
class UnitCheckResult(BaseModel):
    step_id: str
    reagent: str
    stock_conc: Optional[str] = None
    target_conc: Optional[str] = None
    final_volume: Optional[str] = None
    stock_volume_needed: Optional[str] = None
    diluent_volume_needed: Optional[str] = None
    dilution_factor: Optional[float] = None
    valid: bool
    message: str


# ---------------------------------------------------------------------------
# Tool #2 — NetworkX-backed DAG validation
# ---------------------------------------------------------------------------
class DAGNodeOut(BaseModel):
    id: str
    name: str
    step_type: StepType
    duration_minutes: float
    on_critical_path: bool = False
    is_bottleneck: bool = False
    layer: int = 0


class DAGEdgeOut(BaseModel):
    source: str
    target: str


class DAGValidationResult(BaseModel):
    nodes: list[DAGNodeOut]
    edges: list[DAGEdgeOut]
    is_acyclic: bool
    total_runtime_minutes: float
    critical_path: list[str]
    bottleneck_step_id: Optional[str] = None
    cycle_nodes: list[str] = Field(default_factory=list)
    message: str


# ---------------------------------------------------------------------------
# Tool #3 — PubChem hazard screening
# ---------------------------------------------------------------------------
class HazardFlag(BaseModel):
    reagent: str
    cid: Optional[int] = None
    ghs_pictograms: list[str] = Field(default_factory=list)
    hazard_statements: list[str] = Field(default_factory=list)
    is_hazardous: bool = False
    source: str = "PubChem"
    lookup_status: str = "ok"  # ok | not_found | error


# ---------------------------------------------------------------------------
# Plate / vessel layout
# ---------------------------------------------------------------------------
class WellAssignment(BaseModel):
    well_id: str
    reagent_summary: str
    total_volume_ul: float = 0
    hazardous: bool = False
    step_ids: list[str] = Field(default_factory=list)


class PlateLayoutResult(BaseModel):
    plate_size: int = 96
    rows: int = 8
    cols: int = 12
    wells: list[WellAssignment] = Field(default_factory=list)
    manual_layout_required: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------
class ProtocolState(BaseModel):
    protocol_name: str
    golden_path_matched: Optional[str] = None
    raw_text: str
    steps: list[ProtocolStep]
    dag: DAGValidationResult
    unit_checks: list[UnitCheckResult]
    hazards: list[HazardFlag]
    plate: PlateLayoutResult
    warnings: list[str] = Field(default_factory=list)


class CompileRequest(BaseModel):
    raw_text: str = Field(min_length=10)


class GoldenPathPreview(BaseModel):
    key: str
    name: str
    description: str
    preview_text: str
