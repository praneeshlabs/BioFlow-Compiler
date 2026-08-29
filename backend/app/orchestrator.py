"""
Orchestration layer.

Flow for a single POST /api/compile:

  1. Try to match the raw text to one of the three tuned "golden path"
     assays (ELISA / library prep / qPCR). On a confident match, use the
     hand-tuned step extraction for that assay. Otherwise fall back to the
     generic regex extractor, optionally refined by Claude if an API key
     is configured.
  2. Fire all three deterministic MCP tools *concurrently* with
     ``asyncio.gather``: dilution/unit checks (Pint), hazard screening
     (PubChem), and DAG validation (NetworkX). None of these three depend
     on each other's output, so running them sequentially would only add
     latency for no benefit.
  3. Assemble the 96-well plate layout from step well_targets + reagents +
     hazard flags. If no step carried usable well information, return an
     empty plate flagged ``manual_layout_required`` instead of guessing.
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict

from .golden_paths import detect_golden_path, extract_steps_generic, get_golden_name, get_golden_steps
from .mcp_tools import (
    build_and_validate_dag_impl,
    screen_chemical_hazards_impl,
    verify_units_and_dilution_impl,
)
from .schemas import (
    DAGValidationResult,
    HazardFlag,
    PlateLayoutResult,
    ProtocolState,
    ProtocolStep,
    UnitCheckResult,
    WellAssignment,
)


async def _maybe_refine_with_claude(raw_text: str, steps: list[dict]) -> list[dict]:
    """Optional refinement pass: if ANTHROPIC_API_KEY is set, ask Claude to
    sanity-check/augment the generic extraction (fill in missing durations,
    tighten step names). Never raises — on any failure, the original
    generic extraction is returned untouched."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not steps:
        return steps
    try:
        import json

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=api_key)
        prompt = (
            "You are refining a scientific protocol step extraction. "
            "Given the raw protocol text and a draft JSON list of steps, "
            "return ONLY a corrected JSON array (same schema: id, name, "
            "description, step_type, duration_minutes, depends_on, reagents, "
            "well_targets). Keep ids identical. Fill in missing "
            "duration_minutes with a reasonable estimate from the text. "
            "Do not add commentary, backticks, or markdown — JSON array only.\n\n"
            f"RAW TEXT:\n{raw_text}\n\nDRAFT STEPS:\n{json.dumps(steps)}"
        )
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text_out = "".join(b.text for b in resp.content if b.type == "text")
        cleaned = text_out.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        refined = json.loads(cleaned)
        if isinstance(refined, list) and refined:
            return refined
    except Exception:
        # Refinement is a nice-to-have; never let it break the compile.
        pass
    return steps


def _build_plate_layout(steps: list[dict], hazard_by_reagent: dict[str, bool]) -> PlateLayoutResult:
    well_data: dict[str, dict] = defaultdict(
        lambda: {"reagents": [], "volume_ul": 0.0, "hazardous": False, "step_ids": []}
    )

    def _to_ul(volume_str: str | None) -> float:
        if not volume_str:
            return 0.0
        try:
            parts = volume_str.strip().split()
            if len(parts) != 2:
                return 0.0
            value, unit = float(parts[0]), parts[1].lower()
            if unit in ("ul", "µl", "uL"):
                return value
            if unit == "ml":
                return value * 1000
            return 0.0
        except (ValueError, IndexError):
            return 0.0

    any_wells = False
    for step in steps:
        wells = step.get("well_targets") or []
        if not wells or wells == ["POOL"]:
            continue
        any_wells = True
        for well in wells:
            entry = well_data[well]
            entry["step_ids"].append(step["id"])
            for reagent in step.get("reagents", []):
                rname = reagent.get("reagent", "unknown")
                entry["reagents"].append(rname)
                entry["volume_ul"] += _to_ul(reagent.get("volume"))
                if hazard_by_reagent.get(rname.lower()):
                    entry["hazardous"] = True

    if not any_wells:
        return PlateLayoutResult(
            wells=[],
            manual_layout_required=True,
            message=(
                "No well-level positions could be determined from this "
                "protocol text. Showing an empty 96-well plate — assign "
                "wells manually."
            ),
        )

    wells_out = [
        WellAssignment(
            well_id=well_id,
            reagent_summary=", ".join(sorted(set(data["reagents"]))) or "—",
            total_volume_ul=round(data["volume_ul"], 2),
            hazardous=data["hazardous"],
            step_ids=data["step_ids"],
        )
        for well_id, data in well_data.items()
    ]
    return PlateLayoutResult(wells=wells_out, manual_layout_required=False)


async def compile_protocol(raw_text: str) -> ProtocolState:
    warnings: list[str] = []
    golden_key = detect_golden_path(raw_text)

    if golden_key:
        raw_steps = get_golden_steps(golden_key)
        protocol_name = get_golden_name(golden_key)
    else:
        raw_steps = extract_steps_generic(raw_text)
        raw_steps = await _maybe_refine_with_claude(raw_text, raw_steps)
        protocol_name = "Custom Protocol (generic extraction)"
        if not raw_steps:
            warnings.append(
                "No numbered steps were detected in the pasted text — "
                "try formatting the protocol as a numbered list."
            )

    # --- Collect concurrent tool tasks -----------------------------------
    # Dilution checks (per step that carries stock/target/final volume),
    # the DAG validation, and the hazard screen are mutually independent —
    # fire them all at once with asyncio.gather.
    dilution_tasks = []
    dilution_step_refs: list[dict] = []
    for step in raw_steps:
        if step.get("stock_conc") and step.get("target_conc") and step.get("final_volume"):
            dilution_tasks.append(
                verify_units_and_dilution_impl(
                    step["stock_conc"], step["target_conc"], step["final_volume"]
                )
            )
            dilution_step_refs.append(step)

    reagent_names = sorted(
        {r["reagent"] for s in raw_steps for r in s.get("reagents", []) if r.get("reagent")}
    )

    dag_task = build_and_validate_dag_impl(raw_steps)
    hazard_task = screen_chemical_hazards_impl(reagent_names) if reagent_names else None

    gather_targets = [dag_task]
    if hazard_task is not None:
        gather_targets.append(hazard_task)
    gather_targets.extend(dilution_tasks)

    gathered = await asyncio.gather(*gather_targets, return_exceptions=True)

    idx = 0
    dag_raw = gathered[idx]
    idx += 1
    if isinstance(dag_raw, Exception):
        warnings.append(f"DAG validation failed unexpectedly: {dag_raw}")
        dag_raw = {
            "is_acyclic": False, "total_runtime_minutes": 0.0, "critical_path": [],
            "bottleneck_step_id": None, "cycle_nodes": [], "nodes": [], "edges": [],
            "message": "DAG validation error.",
        }

    hazard_raw = {"results": []}
    if hazard_task is not None:
        hazard_raw = gathered[idx]
        idx += 1
        if isinstance(hazard_raw, Exception):
            warnings.append(f"Hazard screening failed unexpectedly: {hazard_raw}")
            hazard_raw = {"results": []}

    dilution_results_raw = gathered[idx:]
    unit_checks: list[UnitCheckResult] = []
    for step, result in zip(dilution_step_refs, dilution_results_raw):
        if isinstance(result, Exception):
            unit_checks.append(
                UnitCheckResult(
                    step_id=step["id"], reagent=step.get("reagents", [{}])[0].get("reagent", "?"),
                    stock_conc=step.get("stock_conc"), target_conc=step.get("target_conc"),
                    final_volume=step.get("final_volume"), valid=False,
                    message=f"Unit check failed unexpectedly: {result}",
                )
            )
            continue
        unit_checks.append(
            UnitCheckResult(
                step_id=step["id"],
                reagent=step.get("reagents", [{}])[0].get("reagent", "?") if step.get("reagents") else "?",
                stock_conc=step.get("stock_conc"),
                target_conc=step.get("target_conc"),
                final_volume=step.get("final_volume"),
                stock_volume_needed=result.get("stock_volume_needed"),
                diluent_volume_needed=result.get("diluent_volume_needed"),
                dilution_factor=result.get("dilution_factor"),
                valid=result["valid"],
                message=result["message"],
            )
        )

    hazards = [HazardFlag(**h) for h in hazard_raw.get("results", [])]
    hazard_by_reagent = {h.reagent.lower(): h.is_hazardous for h in hazards}

    dag = DAGValidationResult(**dag_raw)
    plate = _build_plate_layout(raw_steps, hazard_by_reagent)

    if not dag.is_acyclic:
        warnings.append(dag.message)
    invalid_checks = [c for c in unit_checks if not c.valid]
    if invalid_checks:
        warnings.append(
            f"{len(invalid_checks)} dilution step(s) failed unit verification — see badges."
        )

    steps_typed = [ProtocolStep(**s) for s in raw_steps]

    return ProtocolState(
        protocol_name=protocol_name,
        golden_path_matched=golden_key,
        raw_text=raw_text,
        steps=steps_typed,
        dag=dag,
        unit_checks=unit_checks,
        hazards=hazards,
        plate=plate,
        warnings=warnings,
    )
