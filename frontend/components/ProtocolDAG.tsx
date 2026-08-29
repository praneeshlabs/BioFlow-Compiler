"use client";

import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  FlaskConical,
  ShieldAlert,
  Timer,
  XCircle,
  Zap,
} from "lucide-react";
import React, { useMemo } from "react";
import Badge from "./Badge";
import { DAGValidationResult, HazardFlag, ProtocolStep, UnitCheckResult } from "../lib/types";

const NODE_W = 216;
const NODE_H = 108;
const COL_GAP = 76;
const ROW_GAP = 26;

const STEP_TYPE_COLOR: Record<string, string> = {
  prep: "#94a3b8",
  dilution: "#a78bfa",
  incubation: "#fbbf24",
  wash: "#38bdf8",
  addition: "#22d3ee",
  detection: "#f472b6",
  purification: "#4ade80",
  qc: "#fb923c",
  other: "#94a3b8",
};

export default function ProtocolDAG({
  steps,
  dag,
  unitChecks,
  hazards,
  selectedStepId,
  onSelectStep,
}: {
  steps: ProtocolStep[];
  dag: DAGValidationResult;
  unitChecks: UnitCheckResult[];
  hazards: HazardFlag[];
  selectedStepId: string | null;
  onSelectStep: (id: string | null) => void;
}) {
  const stepById = useMemo(
    () => Object.fromEntries(steps.map((s) => [s.id, s])),
    [steps]
  );

  const layout = useMemo(() => {
    const byLayer = new Map<number, string[]>();
    for (const n of dag.nodes) {
      const arr = byLayer.get(n.layer) || [];
      arr.push(n.id);
      byLayer.set(n.layer, arr);
    }
    const positions: Record<string, { x: number; y: number }> = {};
    const maxLayer = Math.max(0, ...Array.from(byLayer.keys()));
    let maxRows = 1;
    for (let layer = 0; layer <= maxLayer; layer++) {
      const ids = byLayer.get(layer) || [];
      maxRows = Math.max(maxRows, ids.length);
      ids.forEach((id, row) => {
        positions[id] = {
          x: layer * (NODE_W + COL_GAP) + 24,
          y: row * (NODE_H + ROW_GAP) + 24,
        };
      });
    }
    return {
      positions,
      width: (maxLayer + 1) * (NODE_W + COL_GAP) + 48,
      height: maxRows * (NODE_H + ROW_GAP) + 48,
    };
  }, [dag.nodes]);

  const checksByStep = useMemo(() => {
    const m = new Map<string, UnitCheckResult[]>();
    for (const c of unitChecks) {
      const arr = m.get(c.step_id) || [];
      arr.push(c);
      m.set(c.step_id, arr);
    }
    return m;
  }, [unitChecks]);

  const hazardByReagent = useMemo(
    () => new Map(hazards.map((h) => [h.reagent.toLowerCase(), h])),
    [hazards]
  );

  if (!dag.is_acyclic) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <AlertOctagon className="text-forge-danger" size={40} />
        <h3 className="text-lg font-semibold text-red-400">
          Circular Dependency Detected
        </h3>
        <p className="max-w-md text-sm text-slate-400">{dag.message}</p>
        <div className="flex flex-wrap justify-center gap-2">
          {dag.cycle_nodes.map((id) => (
            <Badge key={id} tone="danger" icon={XCircle}>
              {stepById[id]?.name || id}
            </Badge>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-forge-border/60 px-4 py-3">
        <Badge tone="accent" icon={Timer}>
          Total runtime: {dag.total_runtime_minutes} min
        </Badge>
        <Badge tone="success" icon={CheckCircle2}>
          DAG verified acyclic
        </Badge>
        {dag.bottleneck_step_id && (
          <Badge tone="warn" icon={Zap}>
            Bottleneck: {stepById[dag.bottleneck_step_id]?.name || dag.bottleneck_step_id}
          </Badge>
        )}
        <span className="ml-auto text-xs text-slate-500">
          {dag.nodes.length} steps · {dag.edges.length} dependencies
        </span>
      </div>

      <div className="relative flex-1 overflow-auto p-4">
        <div
          className="relative"
          style={{ width: layout.width, height: layout.height, minWidth: "100%" }}
        >
          <svg
            className="pointer-events-none absolute inset-0"
            width={layout.width}
            height={layout.height}
          >
            {dag.edges.map((e, i) => {
              const s = layout.positions[e.source];
              const t = layout.positions[e.target];
              if (!s || !t) return null;
              const x1 = s.x + NODE_W;
              const y1 = s.y + NODE_H / 2;
              const x2 = t.x;
              const y2 = t.y + NODE_H / 2;
              const midX = (x1 + x2) / 2;
              const onCritical =
                dag.critical_path.includes(e.source) &&
                dag.critical_path.includes(e.target) &&
                dag.critical_path.indexOf(e.target) ===
                  dag.critical_path.indexOf(e.source) + 1;
              return (
                <path
                  key={`${e.source}-${e.target}-${i}`}
                  d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke={onCritical ? "#22d3ee" : "#334155"}
                  strokeWidth={onCritical ? 2.5 : 1.5}
                  markerEnd="url(#arrow)"
                  opacity={onCritical ? 1 : 0.6}
                />
              );
            })}
            <defs>
              <marker
                id="arrow"
                markerWidth="8"
                markerHeight="8"
                refX="7"
                refY="4"
                orient="auto"
              >
                <path d="M0,0 L8,4 L0,8 Z" fill="#475569" />
              </marker>
            </defs>
          </svg>

          {dag.nodes.map((n) => {
            const pos = layout.positions[n.id];
            const step = stepById[n.id];
            if (!pos || !step) return null;
            const checks = checksByStep.get(n.id) || [];
            const hasFailedCheck = checks.some((c) => !c.valid);
            const hasCheck = checks.length > 0;
            const hasHazard = step.reagents.some((r) =>
              hazardByReagent.get(r.reagent.toLowerCase())?.is_hazardous
            );
            const selected = selectedStepId === n.id;

            return (
              <button
                key={n.id}
                onClick={() => onSelectStep(selected ? null : n.id)}
                style={{
                  left: pos.x,
                  top: pos.y,
                  width: NODE_W,
                  height: NODE_H,
                  borderColor: n.on_critical_path ? "#22d3ee" : "#1f2937",
                }}
                className={`absolute flex flex-col justify-between rounded-lg border bg-forge-panel p-3 text-left shadow-lg transition-all hover:-translate-y-0.5 hover:shadow-cyan-500/10 ${
                  selected ? "ring-2 ring-cyan-400" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: STEP_TYPE_COLOR[n.step_type] }}
                  />
                  <p className="flex-1 text-[12.5px] font-semibold leading-tight text-slate-100">
                    {n.name}
                  </p>
                  {n.is_bottleneck && (
                    <Zap size={13} className="shrink-0 text-amber-400" />
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="neutral" icon={Clock}>
                    {n.duration_minutes}m
                  </Badge>
                  {hasCheck && !hasFailedCheck && (
                    <Badge tone="success" icon={CheckCircle2}>
                      verified
                    </Badge>
                  )}
                  {hasFailedCheck && (
                    <Badge tone="danger" icon={XCircle}>
                      unit error
                    </Badge>
                  )}
                  {hasHazard && (
                    <Badge tone="warn" icon={ShieldAlert}>
                      hazard
                    </Badge>
                  )}
                  {step.reagents.length > 0 && !hasCheck && !hasHazard && (
                    <Badge tone="neutral" icon={FlaskConical}>
                      {step.reagents.length} reagent
                      {step.reagents.length > 1 ? "s" : ""}
                    </Badge>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selectedStepId && stepById[selectedStepId] && (
        <StepDetail
          step={stepById[selectedStepId]}
          checks={checksByStep.get(selectedStepId) || []}
          hazardByReagent={hazardByReagent}
          onClose={() => onSelectStep(null)}
        />
      )}
    </div>
  );
}

function StepDetail({
  step,
  checks,
  hazardByReagent,
  onClose,
}: {
  step: ProtocolStep;
  checks: UnitCheckResult[];
  hazardByReagent: Map<string, HazardFlag>;
  onClose: () => void;
}) {
  return (
    <div className="max-h-52 overflow-y-auto border-t border-forge-border/60 bg-forge-panel/80 p-4 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="font-semibold text-slate-100">{step.name}</h4>
        <button
          onClick={onClose}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          close
        </button>
      </div>
      <p className="mb-3 text-slate-400">{step.description}</p>

      {step.reagents.length > 0 && (
        <div className="mb-3 space-y-1">
          {step.reagents.map((r, i) => {
            const hz = hazardByReagent.get(r.reagent.toLowerCase());
            return (
              <div key={i} className="flex items-center gap-2 text-xs text-slate-300">
                <FlaskConical size={12} className="text-slate-500" />
                <span>{r.reagent}</span>
                {r.volume && <span className="text-slate-500">{r.volume}</span>}
                {r.concentration && (
                  <span className="text-slate-500">@ {r.concentration}</span>
                )}
                {hz?.is_hazardous && (
                  <Badge tone="warn" icon={ShieldAlert}>
                    {hz.hazard_statements[0] || "hazardous (GHS)"}
                  </Badge>
                )}
              </div>
            );
          })}
        </div>
      )}

      {checks.map((c, i) => (
        <div
          key={i}
          className={`rounded-md border p-2 text-xs ${
            c.valid
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
              : "border-red-500/30 bg-red-500/5 text-red-300"
          }`}
        >
          {c.message}
        </div>
      ))}
    </div>
  );
}
