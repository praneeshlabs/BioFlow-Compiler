"""
ProtocolForge deterministic MCP tools.

These three functions are the "ground truth" layer of the system — the LLM
extracts *candidate* steps, but every number and dependency claim gets
checked here, deterministically, before it is trusted in the UI.

Each tool is implemented as a plain async function (``*_impl``) so the
orchestrator can call it directly and cheaply, and is also registered on a
FastMCP server instance so ProtocolForge can be run as a standalone MCP
server (``python -m app.mcp_tools``) and driven by any MCP-compatible
client (Claude Desktop, Claude Code, etc.), not just this app's own API.
"""
from __future__ import annotations

import os
import re
from typing import Any

import networkx as nx
import requests
from fastmcp import FastMCP
from pint import UndefinedUnitError, UnitRegistry

from .schemas import (
    DAGEdgeOut,
    DAGNodeOut,
    DAGValidationResult,
    HazardFlag,
    StepType,
    UnitCheckResult,
)

# ---------------------------------------------------------------------------
# Pint setup
# ---------------------------------------------------------------------------
ureg = UnitRegistry()
Q_ = ureg.Quantity
# "Fold" concentrations (10X buffer, 1X PBS) aren't a real dimensional unit,
# so we give Pint a dimensionless custom unit for them.
ureg.define("fold = [] = X = fold_concentration")

_CONC_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z%/µu]+)\s*$"
)


def _parse_quantity(raw: str):
    """Parse a loosely-formatted lab string ('10 mM', '5X', '1 mg/mL') into
    a Pint Quantity. Raises ValueError with a human-readable reason on
    failure — callers turn that into a UnitCheckResult(valid=False)."""
    if raw is None:
        raise ValueError("missing value")
    cleaned = raw.strip().replace("µ", "u").replace("%", "percent")
    # Fold-notation, e.g. "10X" / "1x"
    fold_match = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*[xX]\s*$", cleaned)
    if fold_match:
        return float(fold_match.group(1)) * ureg.fold
    try:
        return ureg.Quantity(cleaned)
    except (UndefinedUnitError, ValueError, Exception) as exc:  # pint raises several types
        raise ValueError(f"could not parse '{raw}' as a unit-bearing quantity ({exc})")


async def verify_units_and_dilution_impl(
    stock_conc: str, target_conc: str, final_volume: str
) -> dict[str, Any]:
    """Strict C1V1 = C2V2 dimensional analysis via Pint.

    Returns stock volume needed, diluent volume needed, and the dilution
    factor — or a structured failure reason if units are incompatible.
    """
    try:
        c1 = _parse_quantity(stock_conc)
        c2 = _parse_quantity(target_conc)
        vf = _parse_quantity(final_volume)
    except ValueError as exc:
        return {
            "valid": False,
            "stock_volume_needed": None,
            "diluent_volume_needed": None,
            "dilution_factor": None,
            "message": str(exc),
        }

    try:
        # Dimensional compatibility check — this is where Pint earns its
        # keep: mixing e.g. mol/L against mg/mL would raise here.
        c1_conv = c1.to(c2.units)
    except Exception as exc:
        return {
            "valid": False,
            "stock_volume_needed": None,
            "diluent_volume_needed": None,
            "dilution_factor": None,
            "message": (
                f"Incompatible units: stock is measured in "
                f"'{c1.units}' but target is in '{c2.units}' — {exc}"
            ),
        }

    if c1_conv.magnitude <= 0:
        return {
            "valid": False,
            "stock_volume_needed": None,
            "diluent_volume_needed": None,
            "dilution_factor": None,
            "message": "Stock concentration must be greater than zero.",
        }

    if c1_conv.magnitude < c2.magnitude:
        return {
            "valid": False,
            "stock_volume_needed": None,
            "diluent_volume_needed": None,
            "dilution_factor": None,
            "message": (
                f"Target concentration ({target_conc}) exceeds stock "
                f"concentration ({stock_conc}) — dilution is impossible "
                f"in this direction; did you mean concentration instead?"
            ),
        }

    # C1 * V1 = C2 * V2  =>  V1 = (C2 * V2) / C1
    v1 = (c2 * vf / c1_conv).to(vf.units)
    diluent = (vf - v1).to(vf.units)
    dilution_factor = float(c1_conv.magnitude / c2.magnitude)

    return {
        "valid": True,
        "stock_volume_needed": f"{v1.magnitude:.4g} {v1.units:~}",
        "diluent_volume_needed": f"{diluent.magnitude:.4g} {diluent.units:~}",
        "dilution_factor": round(dilution_factor, 4),
        "message": (
            f"Add {v1.magnitude:.4g} {v1.units:~} of stock to "
            f"{diluent.magnitude:.4g} {diluent.units:~} diluent for a "
            f"{dilution_factor:.3g}x dilution into {vf.magnitude:.4g} {vf.units:~} final volume."
        ),
    }


async def build_and_validate_dag_impl(steps: list[dict]) -> dict[str, Any]:
    """Build a DiGraph from step dependencies, confirm acyclicity, and
    compute the critical path (longest duration-weighted path) plus the
    single bottleneck step on it."""
    g = nx.DiGraph()
    for s in steps:
        g.add_node(
            s["id"],
            name=s.get("name", s["id"]),
            step_type=s.get("step_type", "other"),
            duration=float(s.get("duration_minutes", 0) or 0),
        )
    for s in steps:
        for dep in s.get("depends_on", []) or []:
            if dep in g.nodes:
                g.add_edge(dep, s["id"])

    is_acyclic = nx.is_directed_acyclic_graph(g)
    cycle_nodes: list[str] = []
    if not is_acyclic:
        try:
            cycle = nx.find_cycle(g)
            cycle_nodes = sorted({n for edge in cycle for n in edge})
        except nx.NetworkXNoCycle:
            cycle_nodes = []
        return {
            "is_acyclic": False,
            "total_runtime_minutes": 0.0,
            "critical_path": [],
            "bottleneck_step_id": None,
            "cycle_nodes": cycle_nodes,
            "nodes": [],
            "edges": [{"source": u, "target": v} for u, v in g.edges()],
            "message": (
                "Circular dependency detected — the protocol as written "
                f"cannot be scheduled. Steps involved: {', '.join(cycle_nodes)}."
            ),
        }

    # Longest path by cumulative duration = critical path (standard CPM).
    topo = list(nx.topological_sort(g))
    dist: dict[str, float] = {n: g.nodes[n]["duration"] for n in g.nodes}
    prev: dict[str, str | None] = {n: None for n in g.nodes}
    for n in topo:
        for succ in g.successors(n):
            candidate = dist[n] + g.nodes[succ]["duration"]
            if candidate > dist[succ]:
                dist[succ] = candidate
                prev[succ] = n

    end_node = max(dist, key=lambda n: dist[n]) if dist else None
    critical_path: list[str] = []
    cur = end_node
    while cur is not None:
        critical_path.append(cur)
        cur = prev[cur]
    critical_path.reverse()

    total_runtime = dist[end_node] if end_node else 0.0
    bottleneck = None
    if critical_path:
        bottleneck = max(critical_path, key=lambda n: g.nodes[n]["duration"])

    # Simple longest-path layering for a left-to-right DAG layout.
    layer: dict[str, int] = {}
    for n in topo:
        preds = list(g.predecessors(n))
        layer[n] = 0 if not preds else max(layer[p] for p in preds) + 1

    nodes_out = [
        {
            "id": n,
            "name": g.nodes[n]["name"],
            "step_type": g.nodes[n]["step_type"],
            "duration_minutes": g.nodes[n]["duration"],
            "on_critical_path": n in critical_path,
            "is_bottleneck": n == bottleneck,
            "layer": layer[n],
        }
        for n in g.nodes
    ]
    edges_out = [{"source": u, "target": v} for u, v in g.edges()]

    return {
        "is_acyclic": True,
        "total_runtime_minutes": round(total_runtime, 2),
        "critical_path": critical_path,
        "bottleneck_step_id": bottleneck,
        "cycle_nodes": [],
        "nodes": nodes_out,
        "edges": edges_out,
        "message": (
            f"DAG validated: {len(g.nodes)} steps, {len(g.edges)} dependencies, "
            f"critical path runtime {round(total_runtime, 2)} min."
        ),
    }


# GHS hazard statement codes that we treat as "hazardous enough to flag" —
# anything in PubChem's GHS classification block starting with H2xx-H4xx.
_HAZARD_PREFIXES = ("H2", "H3", "H4")


async def screen_chemical_hazards_impl(reagent_names: list[str]) -> dict[str, Any]:
    """Look up each reagent on PubChem and pull GHS hazard classification.

    Network calls are best-effort: PubChem being unreachable (offline demo,
    firewall, rate limit) degrades to lookup_status='error' per-reagent
    rather than failing the whole compile.
    """
    timeout = float(os.environ.get("PUBCHEM_TIMEOUT", "6"))
    results: list[dict[str, Any]] = []

    for name in reagent_names:
        entry = {
            "reagent": name,
            "cid": None,
            "ghs_pictograms": [],
            "hazard_statements": [],
            "is_hazardous": False,
            "source": "PubChem",
            "lookup_status": "ok",
        }
        try:
            cid_resp = requests.get(
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                f"{requests.utils.quote(name)}/cids/JSON",
                timeout=timeout,
            )
            if cid_resp.status_code != 200:
                entry["lookup_status"] = "not_found"
                results.append(entry)
                continue
            cids = cid_resp.json().get("IdentifierList", {}).get("CID", [])
            if not cids:
                entry["lookup_status"] = "not_found"
                results.append(entry)
                continue
            cid = cids[0]
            entry["cid"] = cid

            view_resp = requests.get(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON",
                params={"heading": "GHS Classification"},
                timeout=timeout,
            )
            if view_resp.status_code == 200:
                statements: set[str] = set()
                pictograms: set[str] = set()
                data = view_resp.json()

                def _walk(node):
                    if isinstance(node, dict):
                        if node.get("String"):
                            s = node["String"]
                            code_match = re.match(r"(H[2-4]\d\d)", s)
                            if code_match:
                                statements.add(s)
                            if "Pictogram" in str(node.get("Name", "")):
                                pictograms.add(s)
                        for v in node.values():
                            _walk(v)
                    elif isinstance(node, list):
                        for item in node:
                            _walk(item)

                _walk(data)
                entry["hazard_statements"] = sorted(statements)
                entry["ghs_pictograms"] = sorted(pictograms)
                entry["is_hazardous"] = any(
                    s.startswith(_HAZARD_PREFIXES) for s in statements
                ) or bool(pictograms)
        except requests.RequestException as exc:
            entry["lookup_status"] = "error"
            entry["hazard_statements"] = [f"lookup failed: {exc}"]
        except Exception as exc:  # noqa: BLE001 — never let a bad reagent kill the batch
            entry["lookup_status"] = "error"
            entry["hazard_statements"] = [f"unexpected error: {exc}"]

        results.append(entry)

    return {"results": results}


# ---------------------------------------------------------------------------
# FastMCP registration — exposes the same three functions over MCP so
# ProtocolForge's tools can be driven by Claude Desktop / Claude Code too.
# ---------------------------------------------------------------------------
mcp = FastMCP("ProtocolForge Tools")


@mcp.tool()
async def verify_units_and_dilution(
    stock_conc: str, target_conc: str, final_volume: str
) -> dict[str, Any]:
    """Strict dimensional-analysis dilution check (C1V1=C2V2) using Pint."""
    return await verify_units_and_dilution_impl(stock_conc, target_conc, final_volume)


@mcp.tool()
async def build_and_validate_dag(steps: list[dict]) -> dict[str, Any]:
    """Validate a protocol's step graph with NetworkX: acyclicity, critical
    path, and total run-time."""
    return await build_and_validate_dag_impl(steps)


@mcp.tool()
async def screen_chemical_hazards(reagent_names: list[str]) -> dict[str, Any]:
    """Screen a list of reagent names against PubChem for GHS hazard
    classifications."""
    return await screen_chemical_hazards_impl(reagent_names)


if __name__ == "__main__":
    # Run as a standalone MCP server: `python -m app.mcp_tools`
    mcp.run()
