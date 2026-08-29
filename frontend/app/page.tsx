"use client";

import {
  AlertTriangle,
  Beaker,
  FlaskConical,
  Loader2,
  Moon,
  Play,
  Sun,
  TestTube2,
} from "lucide-react";
import { useEffect, useState } from "react";
import Badge from "../components/Badge";
import PlateLayout from "../components/PlateLayout";
import ProtocolDAG from "../components/ProtocolDAG";
import { ApiError, compileProtocol, fetchGoldenPaths } from "../lib/api";
import { GoldenPathPreview, ProtocolState } from "../lib/types";

export default function ProtocolStudio() {
  const [rawText, setRawText] = useState("");
  const [state, setState] = useState<ProtocolState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [goldenPaths, setGoldenPaths] = useState<GoldenPathPreview[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  useEffect(() => {
    fetchGoldenPaths()
      .then(setGoldenPaths)
      .catch(() => setGoldenPaths([]));
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("light", theme === "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  async function handleCompile() {
    if (rawText.trim().length < 10) {
      setError("Paste a protocol with at least a few numbered steps first.");
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedStepId(null);
    try {
      const result = await compileProtocol(rawText);
      setState(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error compiling protocol.");
      setState(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-forge-border/60 bg-forge-panel/60 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10">
            <TestTube2 className="text-cyan-400" size={18} />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-100">
              ProtocolForge
            </h1>
            <p className="text-[11px] text-slate-500">
              Agentic Assay Compiler &amp; Experimental Dependency Engine
            </p>
          </div>
        </div>
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-forge-border/60 text-slate-400 hover:text-slate-200"
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </header>

      <div className="grid flex-1 grid-cols-[340px_1fr_360px] overflow-hidden">
        {/* LEFT PANEL — input */}
        <aside className="flex flex-col border-r border-forge-border/60 bg-forge-panel/30">
          <div className="border-b border-forge-border/60 px-4 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Raw Protocol Input
            </h2>
          </div>
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="Paste an unstructured assay protocol here (numbered steps work best)…"
            className="flex-1 resize-none bg-transparent p-4 font-mono text-[12.5px] leading-relaxed text-slate-200 placeholder:text-slate-600 focus:outline-none"
          />
          <div className="border-t border-forge-border/60 p-3">
            {error && (
              <div className="mb-2 flex items-start gap-1.5 rounded-md border border-red-500/30 bg-red-500/5 p-2 text-xs text-red-300">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                {error}
              </div>
            )}
            <button
              onClick={handleCompile}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Play size={15} fill="currentColor" />
              )}
              {loading ? "Compiling…" : "Compile Protocol"}
            </button>
          </div>

          {goldenPaths.length > 0 && (
            <div className="border-t border-forge-border/60 p-3">
              <p className="mb-2 text-[11px] uppercase tracking-wide text-slate-500">
                Load a tuned example
              </p>
              <div className="space-y-1.5">
                {goldenPaths.map((gp) => (
                  <button
                    key={gp.key}
                    onClick={() => {
                      setRawText(gp.preview_text);
                      setState(null);
                      setError(null);
                    }}
                    className="w-full rounded-md border border-forge-border/60 bg-forge-panel px-2.5 py-2 text-left text-xs transition hover:border-cyan-500/40"
                  >
                    <div className="flex items-center gap-1.5 font-semibold text-slate-200">
                      <FlaskConical size={12} className="text-cyan-400" />
                      {gp.name}
                    </div>
                    <p className="mt-0.5 text-[11px] text-slate-500">{gp.description}</p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* CENTER PANEL — DAG / timeline */}
        <section className="flex flex-col overflow-hidden bg-forge-bg">
          <div className="border-b border-forge-border/60 px-4 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Execution DAG &amp; Timing
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            {state ? (
              <ProtocolDAG
                steps={state.steps}
                dag={state.dag}
                unitChecks={state.unit_checks}
                hazards={state.hazards}
                selectedStepId={selectedStepId}
                onSelectStep={setSelectedStepId}
              />
            ) : (
              <EmptyState
                icon={Beaker}
                title="No protocol compiled yet"
                subtitle="Paste a protocol on the left, or load a tuned example, then hit Compile."
              />
            )}
          </div>
          {state && (
            <div className="flex flex-wrap items-center gap-2 border-t border-forge-border/60 px-4 py-2.5">
              <span className="text-xs font-medium text-slate-300">
                {state.protocol_name}
              </span>
              {state.golden_path_matched && (
                <Badge tone="accent">golden path: {state.golden_path_matched}</Badge>
              )}
              {state.warnings.map((w, i) => (
                <Badge key={i} tone="warn" icon={AlertTriangle}>
                  {w}
                </Badge>
              ))}
            </div>
          )}
        </section>

        {/* RIGHT PANEL — plate layout */}
        <aside className="flex flex-col border-l border-forge-border/60 bg-forge-panel/30 overflow-hidden">
          <div className="border-b border-forge-border/60 px-4 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              96-Well Plate / Reagent Matrix
            </h2>
          </div>
          <div className="flex-1 overflow-hidden">
            {state ? (
              <PlateLayout plate={state.plate} />
            ) : (
              <EmptyState
                icon={FlaskConical}
                title="Plate layout pending"
                subtitle="Well assignments and hazard flags appear here after compiling."
              />
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}

function EmptyState({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: typeof Beaker;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <Icon size={32} className="text-slate-700" />
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className="max-w-xs text-xs text-slate-600">{subtitle}</p>
    </div>
  );
}
