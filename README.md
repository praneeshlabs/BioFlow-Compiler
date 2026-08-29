# BioFlow-Compiler

**Agentic Assay Compiler & Experimental Dependency Engine**

ProtocolForge takes an unstructured, free-text scientific assay protocol and
compiles it into a verified, deterministic execution DAG plus a 96-well
plate/vessel layout. It is not a chatbot — it's a **Protocol Studio**: paste
text on the left, get a validated dependency graph in the center and a
reagent-mapped plate on the right.

The system is explicitly *not* trying to parse arbitrary protocols with
LLM vibes alone. It is tuned against three real, complex, 96-well-relevant
assay families (Sandwich ELISA, Illumina-style NGS library prep, and
qPCR standard-curve setup), and every number an LLM extracts is re-verified
by deterministic tools before it reaches the UI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PROTOCOL STUDIO (Next.js)                       │
│                                                                           │
│   ┌───────────────┐    ┌───────────────────────┐   ┌─────────────────┐  │
│   │  LEFT PANEL   │    │      CENTER PANEL      │   │   RIGHT PANEL    │  │
│   │  Raw protocol │    │   Execution DAG /       │   │  96-well plate / │  │
│   │  text input + │───▶│   Timeline viewer       │   │  reagent matrix  │  │
│   │  "Compile"    │    │   (verified badges,     │   │  (volumes +      │  │
│   │  + example    │    │   bottleneck highlight) │   │  hazard flags)   │  │
│   │  loaders      │    │                         │   │                  │  │
│   └───────────────┘    └───────────────────────┘   └─────────────────┘  │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ POST /api/compile { raw_text }
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI ORCHESTRATOR (backend)                   │
│                                                                           │
│  1. detect_golden_path(text)  ──▶  ELISA | Library Prep | qPCR | None    │
│         │ match                              │ no match                 │
│         ▼                                    ▼                          │
│  tuned hand-built step graph        extract_steps_generic() +           │
│                                      optional Claude refinement pass     │
│         │                                    │                          │
│         └───────────────┬────────────────────┘                          │
│                          ▼                                               │
│           asyncio.gather( ... )  ── fired CONCURRENTLY:                  │
│           ┌─────────────────────┬─────────────────────┬───────────────┐ │
│           │ verify_units_and_   │ screen_chemical_     │ build_and_    │ │
│           │ dilution() × N      │ hazards() × 1        │ validate_dag()│ │
│           │        (Pint)       │      (PubChem)       │  (NetworkX)   │ │
│           └─────────────────────┴─────────────────────┴───────────────┘ │
│                          │                                               │
│                          ▼                                               │
│              assemble strictly-typed ProtocolState                      │
│              (steps, DAG, unit checks, hazards, plate layout)           │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
                     FASTMCP TOOL SERVER (app/mcp_tools.py)
              same 3 functions, also exposed over MCP for
              Claude Desktop / Claude Code / any MCP client
```

### Why three separate deterministic tools?

An LLM is good at *reading* a protocol and *proposing* structure. It is
untrustworthy at arithmetic, graph theory, and remembering GHS hazard
codes. BioFlow's orchestrator treats the LLM's (or the tuned
golden-path) output as a **draft** and re-derives every hard fact with a
dedicated tool:

| Tool | Library | What it actually checks |
|---|---|---|
| `verify_units_and_dilution` | **Pint** | Parses lab-notation strings (`"10 mM"`, `"5X"`, `"1 mg/mL"`) into dimensioned quantities, converts units, and solves `C1·V1 = C2·V2`. Dimensionally incompatible dilutions (e.g. mixing `mol/L` against `mg/mL`) are rejected outright rather than silently miscalculated. |
| `build_and_validate_dag` | **NetworkX** | Builds a `DiGraph` from step `depends_on` edges, confirms `is_directed_acyclic_graph`, and — critically — computes the duration-weighted **critical path** and single **bottleneck** step, the same way a real CPM (Critical Path Method) scheduler would. |
| `screen_chemical_hazards` | **Requests + PubChem PUG REST/PUG View** | Resolves each reagent name to a PubChem CID, then pulls its GHS Classification block (hazard statements + pictograms) so hazardous reagents get flagged in the plate view without a human having to know GHS codes by heart. |

### Parallelization

The three tool categories above **do not depend on each other's output** —
a dilution check for step 5 doesn't need the hazard screen for step 2's
reagents. `orchestrator.py` fires all of them in a single
`asyncio.gather(...)` call instead of awaiting them sequentially, so a
protocol with, say, 4 dilution checks + 1 hazard screen + 1 DAG build
costs roughly `max(latencies)` instead of `sum(latencies)`.

### The "Golden Path" tuning strategy

Rather than promising to parse *any* protocol on earth (and quietly
failing on most of them), BioFlow is tuned against three protocols
chosen for real 96-well complexity and branching:

1. **Sandwich ELISA** (`elisa`) — 13 steps, 5 wash cycles, a standard
   curve, colorimetric stop/read.
2. **Illumina-style NGS Library Prep** (`library_prep`) — 9 steps,
   tagmentation, dual-sided bead size selection, pooling into an
   off-plate vessel.
3. **qPCR Standard Curve & Assay Setup** (`qpcr`) — 7 steps with **three
   independent parallel branches** (standard dilution, master mix prep,
   primer dilution) that converge into a single full-plate assembly step
   — a genuine multi-branch DAG, not a straight line.

`golden_paths.detect_golden_path()` keyword-scores incoming text against
each family. A confident match swaps in a hand-built, fully-typed step
graph for that assay. Anything else falls back to
`extract_steps_generic()` — a conservative numbered-line/regex extractor —
optionally refined by a single Claude call if `ANTHROPIC_API_KEY` is set.
The generic path is a safety net, not the headline feature.

### Fallback states

- **Circular dependency detected** → the center panel renders a dedicated
  error view naming the exact steps in the cycle, instead of a blank DAG.
- **No well-level positions extracted** → the right panel renders an
  empty 96-well grid with a **"Manual Layout Required"** badge rather than
  guessing or crashing.
- **PubChem unreachable** → hazard lookups degrade to
  `lookup_status: "error"` per-reagent; the rest of the compile still
  succeeds.

---

## Directory structure

```
BioFlow/
├── README.md
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── __init__.py
│       ├── schemas.py        # Pydantic v2 models (ProtocolState, DAG, etc.)
│       ├── mcp_tools.py       # FastMCP server: Pint / NetworkX / PubChem tools
│       ├── golden_paths.py    # 3 tuned protocols + generic fallback extractor
│       ├── orchestrator.py    # asyncio.gather orchestration → ProtocolState
│       └── server.py          # FastAPI app, CORS, /api routes
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── tsconfig.json
    ├── next-env.d.ts
    ├── .env.local.example
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx            # 3-panel Protocol Studio
    │   └── globals.css
    ├── components/
    │   ├── Badge.tsx
    │   ├── ProtocolDAG.tsx      # center panel: DAG / timeline viewer
    │   └── PlateLayout.tsx      # right panel: 96-well plate / reagent matrix
    └── lib/
        ├── api.ts               # fetch wrappers for the backend
        └── types.ts             # TS mirror of the Pydantic schemas
```

---

## Local setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # ANTHROPIC_API_KEY is optional
uvicorn app.server:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Check
`http://localhost:8000/api/health` and `http://localhost:8000/docs`
(FastAPI's auto Swagger UI) to confirm it's running.

> **Note:** `ANTHROPIC_API_KEY` is only used for the *optional* refinement
> pass on protocols that don't match one of the three golden paths. The
> app is fully functional — including all three demo protocols — without
> any API key configured.

To run the tools as a standalone MCP server (for Claude Desktop / Claude
Code) instead of embedding them in the FastAPI app:

```bash
python -m app.mcp_tools
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://localhost:8000 by default
npm run dev
```

Open `http://localhost:3000`. Click one of the three "Load a tuned
example" buttons in the left panel, then **Compile Protocol**, to see the
full pipeline run end-to-end.

### 3. CORS

The backend's `FRONTEND_ORIGIN` env var (default
`http://localhost:3000`) is added to FastAPI's `CORSMiddleware`
`allow_origins`, alongside `localhost`/`127.0.0.1` fallbacks — no manual
proxy configuration needed for local development.

---

## Tech stack

| Layer | Choice |
|---|---|
| API framework | FastAPI (async) |
| Validation | Pydantic v2 |
| Deterministic tools | FastMCP (MCP protocol), Pint (units), NetworkX (graphs) |
| External data | PubChem PUG REST / PUG View (hazard data) via `requests` |
| Frontend framework | Next.js 14 (App Router) + React 18 |
| Styling | Tailwind CSS, dark/light mode via `class` strategy |
| Icons | lucide-react |

---

## Extending BioFlow

- **Add a fourth golden path**: drop a new tuned step list + keyword set
  into `golden_paths.py`'s `GOLDEN_PATHS` / `_KEYWORDS` dicts — no
  frontend changes required, `/api/golden-paths` picks it up
  automatically.
- **Swap the hazard source**: `screen_chemical_hazards_impl` is isolated
  in `mcp_tools.py`; point it at a different chemical safety API without
  touching the orchestrator or schemas.
- **Run the tools remotely**: because they're registered on a real
  `FastMCP` instance, you can host `app/mcp_tools.py` as its own MCP
  server process and have the orchestrator call it over the wire instead
  of in-process, with no change to `schemas.py`.
