"use client";

import { AlertTriangle, Beaker, Droplets } from "lucide-react";
import React, { useMemo, useState } from "react";
import Badge from "./Badge";
import { PlateLayoutResult } from "../lib/types";

const ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"];
const COLS = Array.from({ length: 12 }, (_, i) => i + 1);

export default function PlateLayout({ plate }: { plate: PlateLayoutResult }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const wellMap = useMemo(
    () => new Map(plate.wells.map((w) => [w.well_id, w])),
    [plate.wells]
  );

  const maxVolume = useMemo(
    () => Math.max(1, ...plate.wells.map((w) => w.total_volume_ul)),
    [plate.wells]
  );

  const nonPlateWells = plate.wells.filter(
    (w) => !ROWS.includes(w.well_id[0]) || w.well_id === "POOL"
  );

  if (plate.manual_layout_required) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 border-b border-forge-border/60 px-4 py-3">
          <Badge tone="warn" icon={AlertTriangle}>
            Manual Layout Required
          </Badge>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
          <PlateGrid wellMap={new Map()} maxVolume={1} hovered={null} setHovered={() => {}} muted />
          <p className="max-w-xs text-xs text-slate-500">{plate.message}</p>
        </div>
      </div>
    );
  }

  const hoveredWell = hovered ? wellMap.get(hovered) : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-forge-border/60 px-4 py-3">
        <Badge tone="accent" icon={Droplets}>
          {plate.wells.length} wells assigned
        </Badge>
        {plate.wells.some((w) => w.hazardous) && (
          <Badge tone="warn" icon={AlertTriangle}>
            hazardous reagents present
          </Badge>
        )}
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-4 overflow-auto p-4">
        <PlateGrid
          wellMap={wellMap}
          maxVolume={maxVolume}
          hovered={hovered}
          setHovered={setHovered}
        />

        {nonPlateWells.length > 0 && (
          <div className="w-full space-y-1.5 border-t border-forge-border/50 pt-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">
              Off-plate vessels
            </p>
            {nonPlateWells.map((w) => (
              <div
                key={w.well_id}
                className="flex items-center justify-between rounded-md border border-forge-border/60 bg-forge-panel px-2.5 py-1.5 text-xs"
              >
                <span className="flex items-center gap-1.5 text-slate-300">
                  <Beaker size={12} className="text-slate-500" />
                  {w.well_id}
                </span>
                <span className="text-slate-500">{w.reagent_summary}</span>
                {w.hazardous && (
                  <Badge tone="warn" icon={AlertTriangle}>
                    hazard
                  </Badge>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="min-h-[3.25rem] w-full rounded-md border border-forge-border/60 bg-forge-panel px-3 py-2 text-xs">
          {hoveredWell ? (
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2 font-semibold text-slate-100">
                <span>{hoveredWell.well_id}</span>
                {hoveredWell.hazardous && (
                  <Badge tone="warn" icon={AlertTriangle}>
                    hazardous
                  </Badge>
                )}
              </div>
              <span className="text-slate-400">{hoveredWell.reagent_summary}</span>
              <span className="text-slate-500">
                {hoveredWell.total_volume_ul > 0
                  ? `${hoveredWell.total_volume_ul} uL total`
                  : "volume not specified"}
              </span>
            </div>
          ) : (
            <span className="text-slate-500">Hover a well to inspect its contents.</span>
          )}
        </div>
      </div>
    </div>
  );
}

function PlateGrid({
  wellMap,
  maxVolume,
  hovered,
  setHovered,
  muted = false,
}: {
  wellMap: Map<string, PlateLayoutResult["wells"][number]>;
  maxVolume: number;
  hovered: string | null;
  setHovered: (id: string | null) => void;
  muted?: boolean;
}) {
  return (
    <div className="inline-grid gap-1" style={{ gridTemplateColumns: `24px repeat(12, 1fr)` }}>
      <div />
      {COLS.map((c) => (
        <div key={c} className="text-center text-[10px] text-slate-500">
          {c}
        </div>
      ))}
      {ROWS.map((r) => (
        <React.Fragment key={r}>
          <div className="flex items-center justify-center text-[10px] text-slate-500">
            {r}
          </div>
          {COLS.map((c) => {
            const id = `${r}${c}`;
            const well = wellMap.get(id);
            const intensity = well ? Math.min(1, well.total_volume_ul / maxVolume) : 0;
            return (
              <div
                key={id}
                onMouseEnter={() => !muted && setHovered(id)}
                onMouseLeave={() => !muted && setHovered(null)}
                className={`relative aspect-square w-full rounded-full border transition-all ${
                  muted
                    ? "border-slate-700/50 bg-slate-800/30"
                    : well
                    ? "cursor-pointer border-cyan-500/40 hover:scale-110 hover:border-cyan-400"
                    : "border-slate-700/40 bg-slate-800/20"
                } ${hovered === id ? "scale-110 ring-2 ring-cyan-400" : ""}`}
                style={
                  well
                    ? {
                        backgroundColor: `rgba(34, 211, 238, ${0.12 + intensity * 0.55})`,
                      }
                    : undefined
                }
                title={well ? `${id}: ${well.reagent_summary}` : id}
              >
                {well?.hazardous && (
                  <AlertTriangle
                    size={9}
                    className="absolute -right-0.5 -top-0.5 text-amber-400"
                    fill="#78350f"
                  />
                )}
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}
