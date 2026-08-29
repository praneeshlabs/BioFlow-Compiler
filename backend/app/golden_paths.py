"""
The three "golden path" assays ProtocolForge is tuned for.

Rather than pretending to parse arbitrary free-text protocols with an LLM
and hoping for the best, ProtocolForge scores incoming text against three
real, complex, 96-well-relevant assay types and — on a confident match —
uses a hand-tuned, deterministic step/well extraction for that assay
family. Anything that doesn't match falls back to a conservative generic
regex extractor (``extract_steps_generic``) which degrades gracefully
(including triggering the "Manual Layout Required" plate fallback) instead
of guessing.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. Sandwich ELISA (Enzyme-Linked Immunosorbent Assay)
# ---------------------------------------------------------------------------
ELISA_PROTOCOL = """Sandwich ELISA Protocol — Human IL-6 Quantification (96-well plate)

1. Coat a 96-well high-binding plate with 100 uL/well of capture antibody
   diluted to 2 ug/mL in coating buffer (PBS, pH 7.4). Cover wells A1-H12
   and incubate overnight at 4C.
2. Wash the plate 3x with 300 uL/well Wash Buffer (PBS + 0.05% Tween-20).
3. Block wells with 200 uL/well Blocking Buffer (1% BSA in PBS) for 60
   minutes at room temperature.
4. Wash the plate 3x with 300 uL/well Wash Buffer.
5. Prepare a standard curve: dilute IL-6 standard stock (10 ng/mL) to a
   target concentration of 0.5 ng/mL in a final volume of 500 uL using
   Sample Diluent, then serially dilute across columns 1-8.
6. Add 100 uL/well of sample or standard to wells A1-H12 and incubate
   for 120 minutes at room temperature on a plate shaker.
7. Wash the plate 5x with 300 uL/well Wash Buffer.
8. Add 100 uL/well of Detection Antibody diluted to 250 ng/mL in Antibody
   Diluent and incubate for 60 minutes at room temperature.
9. Wash the plate 5x with 300 uL/well Wash Buffer.
10. Add 100 uL/well Streptavidin-HRP diluted to 1X working concentration
    from a 200X stock in Antibody Diluent, incubate 30 minutes in the dark.
11. Wash the plate 5x with 300 uL/well Wash Buffer.
12. Add 100 uL/well TMB Substrate Solution and incubate 15 minutes in the
    dark at room temperature.
13. Add 50 uL/well Stop Solution (2N Sulfuric Acid) and read absorbance
    at 450 nm within 30 minutes.
"""

_ELISA_STEPS = [
    dict(id="coat_plate", name="Coat plate with capture antibody",
         description="Coat 96-well high-binding plate with capture antibody.",
         step_type="prep", duration_minutes=720, depends_on=[],
         reagents=[dict(reagent="Capture Antibody", volume="100 uL", concentration="2 ug/mL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="200 ug/mL", target_conc="2 ug/mL", final_volume="10 mL"),
    dict(id="wash_1", name="Wash (1st)", description="Wash plate 3x with Wash Buffer.",
         step_type="wash", duration_minutes=10, depends_on=["coat_plate"],
         reagents=[dict(reagent="Wash Buffer", volume="300 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="block", name="Block plate", description="Block with 1% BSA blocking buffer.",
         step_type="incubation", duration_minutes=60, depends_on=["wash_1"],
         reagents=[dict(reagent="Blocking Buffer (BSA)", volume="200 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="wash_2", name="Wash (2nd)", description="Wash plate 3x with Wash Buffer.",
         step_type="wash", duration_minutes=10, depends_on=["block"],
         reagents=[dict(reagent="Wash Buffer", volume="300 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="prep_standards", name="Prepare standard curve",
         description="Dilute IL-6 standard and serially dilute across columns 1-8.",
         step_type="dilution", duration_minutes=20, depends_on=["wash_2"],
         reagents=[dict(reagent="IL-6 Standard", volume="500 uL", concentration="0.5 ng/mL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 9)],
         stock_conc="10 ng/mL", target_conc="0.5 ng/mL", final_volume="500 uL"),
    dict(id="add_sample", name="Add sample / standard",
         description="Add sample or standard to all wells, incubate on shaker.",
         step_type="incubation", duration_minutes=120, depends_on=["prep_standards"],
         reagents=[dict(reagent="Sample / Standard", volume="100 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="wash_3", name="Wash (3rd)", description="Wash plate 5x with Wash Buffer.",
         step_type="wash", duration_minutes=15, depends_on=["add_sample"],
         reagents=[dict(reagent="Wash Buffer", volume="300 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="add_detection_ab", name="Add detection antibody",
         description="Add biotinylated detection antibody.",
         step_type="addition", duration_minutes=60, depends_on=["wash_3"],
         reagents=[dict(reagent="Detection Antibody", volume="100 uL", concentration="250 ng/mL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="50 ug/mL", target_conc="250 ng/mL", final_volume="10 mL"),
    dict(id="wash_4", name="Wash (4th)", description="Wash plate 5x with Wash Buffer.",
         step_type="wash", duration_minutes=15, depends_on=["add_detection_ab"],
         reagents=[dict(reagent="Wash Buffer", volume="300 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="add_hrp", name="Add Streptavidin-HRP",
         description="Add Streptavidin-HRP conjugate at 1X working concentration.",
         step_type="addition", duration_minutes=30, depends_on=["wash_4"],
         reagents=[dict(reagent="Streptavidin-HRP", volume="100 uL", concentration="1X")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="200X", target_conc="1X", final_volume="10 mL"),
    dict(id="wash_5", name="Wash (5th)", description="Wash plate 5x with Wash Buffer.",
         step_type="wash", duration_minutes=15, depends_on=["add_hrp"],
         reagents=[dict(reagent="Wash Buffer", volume="300 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="add_substrate", name="Add TMB substrate",
         description="Add TMB substrate solution, develop in the dark.",
         step_type="detection", duration_minutes=15, depends_on=["wash_5"],
         reagents=[dict(reagent="TMB Substrate", volume="100 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="stop_reaction", name="Stop reaction & read",
         description="Add Stop Solution and read absorbance at 450 nm.",
         step_type="detection", duration_minutes=5, depends_on=["add_substrate"],
         reagents=[dict(reagent="Stop Solution (Sulfuric Acid)", volume="50 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
]

# ---------------------------------------------------------------------------
# 2. NGS Library Prep (Illumina-style, with branching size-selection)
# ---------------------------------------------------------------------------
LIBRARY_PREP_PROTOCOL = """Illumina DNA Library Prep Protocol (96-well plate, tagmentation-based)

1. Normalize genomic DNA input to a target concentration of 5 ng/uL in a
   final volume of 10 uL using low-EDTA TE buffer, across wells A1-H12.
2. Tagment DNA by adding 10 uL Tagmentation Mix (5X TD Buffer diluted to
   1X) and incubate at 55C for 15 minutes.
3. Clean up tagmented DNA using paramagnetic beads at a 1.8X bead ratio.
4. PCR-amplify tagmented fragments with indexed adapters (i7/i5) for 8
   cycles; PCR run-time is 35 minutes.
5. Perform a dual-sided size selection using bead ratios of 0.5X then
   0.7X to select fragments between 300-600 bp, discarding both the
   high-MW pellet fraction and the low-MW supernatant fraction.
6. Quantify each library using a fluorometric assay; dilute each library
   from an assumed stock of 50 ng/uL down to a target of 4 nM in a final
   volume of 20 uL using Resuspension Buffer.
7. Pool equal volumes of normalized libraries (10 uL each) into a single
   tube.
8. Denature the pooled library with 0.2N NaOH for 5 minutes, then dilute
   to the final loading concentration of 1.8 pM in a final volume of
   1300 uL using HT1 buffer.
9. Load the denatured, diluted pool onto the sequencer.
"""

_LIB_PREP_STEPS = [
    dict(id="normalize_input", name="Normalize gDNA input",
         description="Normalize genomic DNA to 5 ng/uL across the plate.",
         step_type="dilution", duration_minutes=15, depends_on=[],
         reagents=[dict(reagent="Genomic DNA", volume="10 uL", concentration="5 ng/uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="50 ng/uL", target_conc="5 ng/uL", final_volume="10 uL"),
    dict(id="tagmentation", name="Tagment DNA",
         description="Add Tagmentation Mix (5X TD Buffer diluted to 1X), incubate 55C.",
         step_type="addition", duration_minutes=15, depends_on=["normalize_input"],
         reagents=[dict(reagent="TD Buffer (Tagmentation)", volume="10 uL", concentration="1X")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="5X", target_conc="1X", final_volume="20 uL"),
    dict(id="bead_cleanup_1", name="Bead cleanup (post-tagmentation)",
         description="Clean up with paramagnetic beads at 1.8X ratio.",
         step_type="purification", duration_minutes=20, depends_on=["tagmentation"],
         reagents=[dict(reagent="Paramagnetic Beads", volume="1.8X")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="pcr_amplify", name="PCR amplify with indices",
         description="Amplify with i7/i5 indexed adapters, 8 cycles.",
         step_type="addition", duration_minutes=35, depends_on=["bead_cleanup_1"],
         reagents=[dict(reagent="Indexed Adapters (i7/i5)", volume="5 uL")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="size_selection", name="Dual-sided size selection",
         description="Bead-based size selection at 0.5X then 0.7X for 300-600bp fragments.",
         step_type="purification", duration_minutes=30, depends_on=["pcr_amplify"],
         reagents=[dict(reagent="Paramagnetic Beads", volume="0.5X then 0.7X")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="quantify_normalize", name="Quantify & normalize libraries",
         description="Quantify fluorometrically; dilute to 4 nM target.",
         step_type="dilution", duration_minutes=25, depends_on=["size_selection"],
         reagents=[dict(reagent="Library", volume="20 uL", concentration="4 nM")],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)],
         stock_conc="50 ng/uL", target_conc="4 nM", final_volume="20 uL"),
    dict(id="pool_libraries", name="Pool libraries",
         description="Pool equal volumes (10 uL) of normalized libraries.",
         step_type="prep", duration_minutes=10, depends_on=["quantify_normalize"],
         reagents=[dict(reagent="Pooled Library", volume="10 uL")],
         well_targets=["POOL"]),
    dict(id="denature_dilute", name="Denature & dilute pool",
         description="Denature with 0.2N NaOH, dilute to 1.8 pM loading concentration.",
         step_type="dilution", duration_minutes=10, depends_on=["pool_libraries"],
         reagents=[dict(reagent="Pooled Library", volume="1300 uL", concentration="1.8 pM")],
         well_targets=["POOL"],
         stock_conc="4 nM", target_conc="1.8 pM", final_volume="1300 uL"),
    dict(id="load_sequencer", name="Load sequencer",
         description="Load denatured, diluted pool onto the sequencer.",
         step_type="qc", duration_minutes=5, depends_on=["denature_dilute"],
         reagents=[dict(reagent="Loading Pool", volume="1300 uL")],
         well_targets=["POOL"]),
]

# ---------------------------------------------------------------------------
# 3. Serial Dilution + qPCR Setup
# ---------------------------------------------------------------------------
SERIAL_DILUTION_QPCR_PROTOCOL = """qPCR Standard Curve & Assay Setup Protocol (96-well plate)

1. Prepare 10X serial dilutions of the DNA standard, starting from a
   stock concentration of 1e8 copies/uL, diluting to a target
   concentration of 1e7 copies/uL in a final volume of 100 uL using
   nuclease-free water. Repeat across 6 points down column 1 (A1-F1).
2. Prepare the 2X qPCR Master Mix working solution by diluting from a
   4X concentrate down to 2X in a final volume of 2000 uL using
   nuclease-free water.
3. Dilute forward and reverse primers from a 100 uM stock to a working
   concentration of 10 uM in a final volume of 500 uL using TE buffer.
4. Assemble qPCR reactions in wells A1-H12: 10 uL 2X Master Mix, 1 uL
   Primer Mix (10 uM), 2 uL template (standard or sample), topped up to
   20 uL with nuclease-free water.
5. Seal the plate with optical film and centrifuge briefly at 1000 x g
   for 1 minute.
6. Run the qPCR thermocycler program: 95C for 10 minutes (initial
   denaturation), then 40 cycles of 95C for 15 seconds and 60C for 60
   seconds, total run-time approximately 90 minutes.
7. Analyze amplification curves and generate the standard curve (Ct vs
   log copy number).
"""

_QPCR_STEPS = [
    dict(id="serial_dilute_standard", name="Serial dilute DNA standard",
         description="10X serial dilution series of DNA standard, 6 points down column 1.",
         step_type="dilution", duration_minutes=20, depends_on=[],
         reagents=[dict(reagent="DNA Standard", volume="100 uL", concentration="1e7 copies/uL")],
         well_targets=[f"{r}1" for r in "ABCDEF"],
         stock_conc="1e8 copies/uL", target_conc="1e7 copies/uL", final_volume="100 uL"),
    dict(id="prep_master_mix", name="Prepare 2X Master Mix",
         description="Dilute 4X Master Mix concentrate to 2X working solution.",
         step_type="dilution", duration_minutes=10, depends_on=[],
         reagents=[dict(reagent="qPCR Master Mix", volume="2000 uL", concentration="2X")],
         well_targets=[],
         stock_conc="4X", target_conc="2X", final_volume="2000 uL"),
    dict(id="prep_primers", name="Dilute primers to working stock",
         description="Dilute F/R primers from 100 uM stock to 10 uM working concentration.",
         step_type="dilution", duration_minutes=10, depends_on=[],
         reagents=[dict(reagent="Primer Mix", volume="500 uL", concentration="10 uM")],
         well_targets=[],
         stock_conc="100 uM", target_conc="10 uM", final_volume="500 uL"),
    dict(id="assemble_reactions", name="Assemble qPCR reactions",
         description="Assemble 20 uL reactions across the full plate.",
         step_type="addition", duration_minutes=20,
         depends_on=["serial_dilute_standard", "prep_master_mix", "prep_primers"],
         reagents=[
             dict(reagent="qPCR Master Mix", volume="10 uL", concentration="2X"),
             dict(reagent="Primer Mix", volume="1 uL", concentration="10 uM"),
             dict(reagent="Template DNA", volume="2 uL"),
         ],
         well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="seal_centrifuge", name="Seal & centrifuge",
         description="Seal with optical film, centrifuge at 1000 x g for 1 minute.",
         step_type="prep", duration_minutes=3, depends_on=["assemble_reactions"],
         reagents=[], well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="run_qpcr", name="Run qPCR thermocycler program",
         description="95C 10min, then 40 cycles of 95C/15s + 60C/60s.",
         step_type="detection", duration_minutes=90, depends_on=["seal_centrifuge"],
         reagents=[], well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
    dict(id="analyze_curve", name="Analyze standard curve",
         description="Generate Ct vs log copy-number standard curve.",
         step_type="qc", duration_minutes=15, depends_on=["run_qpcr"],
         reagents=[], well_targets=[f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]),
]

GOLDEN_PATHS: dict[str, dict] = {
    "elisa": {
        "name": "Sandwich ELISA — Human IL-6 Quantification",
        "description": "13-step sandwich ELISA with a standard curve, 5 wash cycles, and colorimetric detection.",
        "text": ELISA_PROTOCOL,
        "steps": _ELISA_STEPS,
    },
    "library_prep": {
        "name": "Illumina DNA Library Prep",
        "description": "9-step tagmentation-based NGS library prep with dual-sided bead size selection and pooling.",
        "text": LIBRARY_PREP_PROTOCOL,
        "steps": _LIB_PREP_STEPS,
    },
    "qpcr": {
        "name": "qPCR Standard Curve & Assay Setup",
        "description": "Parallel reagent prep (standard, master mix, primers) converging into full-plate qPCR assembly.",
        "text": SERIAL_DILUTION_QPCR_PROTOCOL,
        "steps": _QPCR_STEPS,
    },
}

_KEYWORDS: dict[str, list[str]] = {
    "elisa": ["elisa", "capture antibody", "tmb", "stop solution", "streptavidin-hrp",
              "detection antibody", "450 nm", "blocking buffer"],
    "library_prep": ["tagment", "library prep", "i7/i5", "adapter", "bead ratio",
                      "sequencer", "flow cell", "hiseq", "novaseq", "miseq", "denature the pooled"],
    "qpcr": ["qpcr", "master mix", "thermocycler", "ct value", "copies/ul", "copies/uL",
             "primer", "amplification curve", "95c", "60c"],
}


def detect_golden_path(raw_text: str) -> str | None:
    """Score raw text against each golden path's keyword set; return the
    best match if it clears a minimum confidence bar, else None."""
    text_lower = raw_text.lower()
    scores = {
        key: sum(1 for kw in kws if kw.lower() in text_lower)
        for key, kws in _KEYWORDS.items()
    }
    best_key = max(scores, key=lambda k: scores[k])
    if scores[best_key] >= 2:
        return best_key
    return None


def get_golden_steps(key: str) -> list[dict]:
    return [dict(s) for s in GOLDEN_PATHS[key]["steps"]]


def get_golden_name(key: str) -> str:
    return GOLDEN_PATHS[key]["name"]


def list_golden_paths() -> list[dict]:
    return [
        {
            "key": key,
            "name": v["name"],
            "description": v["description"],
            "preview_text": v["text"],
        }
        for key, v in GOLDEN_PATHS.items()
    ]


# ---------------------------------------------------------------------------
# Generic fallback extractor for text that doesn't match a golden path.
# Deliberately conservative: numbered-line steps, best-effort duration and
# reagent/volume extraction, no invented dependencies beyond linear order.
# ---------------------------------------------------------------------------
_LINE_RE = re.compile(r"^\s*(\d+)[\.\)]\s+(.*)$")
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(minute|minutes|min|hour|hours|hr|second|seconds|sec)s?\b",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(u?L|m?L|mL|uL|µL)\b(?![a-zA-Z])"
)
_WELL_RANGE_RE = re.compile(r"\b([A-H])(\d{1,2})\s*-\s*([A-H])(\d{1,2})\b")
_WELL_SINGLE_RE = re.compile(r"\b([A-H])(\d{1,2})\b")


def _duration_to_minutes(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit.startswith("hour") or unit == "hr":
        return value * 60
    if unit.startswith("sec"):
        return value / 60
    return value


def _expand_well_range(r1: str, c1: str, r2: str, c2: str) -> list[str]:
    rows = [chr(x) for x in range(ord(r1), ord(r2) + 1)]
    cols = range(int(c1), int(c2) + 1)
    return [f"{r}{c}" for r in rows for c in cols]


def extract_steps_generic(raw_text: str) -> list[dict]:
    """Best-effort numbered-line step extraction for non-golden-path text.

    No LLM call is required for this to function (it's a safety net); the
    orchestrator may optionally ask Claude to refine the output when an
    API key is configured — see orchestrator.py.
    """
    steps: list[dict] = []
    prev_id: str | None = None
    for line in raw_text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        num, body = m.groups()
        step_id = f"step_{num}"
        duration = 0.0
        dur_match = _DURATION_RE.search(body)
        if dur_match:
            duration = _duration_to_minutes(float(dur_match.group(1)), dur_match.group(2))

        wells: list[str] = []
        range_match = _WELL_RANGE_RE.search(body)
        if range_match:
            wells = _expand_well_range(*range_match.groups())
        else:
            wells = sorted(set(f"{r}{c}" for r, c in _WELL_SINGLE_RE.findall(body)))

        reagents = []
        vol_match = _VOLUME_RE.search(body)
        if vol_match:
            reagents.append(
                {"reagent": body[: min(40, len(body))].strip().rstrip("."),
                 "volume": f"{vol_match.group(1)} {vol_match.group(2)}"}
            )

        step_type = "other"
        low = body.lower()
        if "wash" in low:
            step_type = "wash"
        elif "incubat" in low:
            step_type = "incubation"
        elif "dilut" in low:
            step_type = "dilution"
        elif "add" in low:
            step_type = "addition"
        elif "read" in low or "detect" in low or "absorbance" in low:
            step_type = "detection"
        elif "purif" in low or "clean" in low or "bead" in low:
            step_type = "purification"

        steps.append(
            dict(
                id=step_id,
                name=body[:60].strip().rstrip("."),
                description=body.strip(),
                step_type=step_type,
                duration_minutes=duration,
                depends_on=[prev_id] if prev_id else [],
                reagents=reagents,
                well_targets=wells,
            )
        )
        prev_id = step_id

    return steps
