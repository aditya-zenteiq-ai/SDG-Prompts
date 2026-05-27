
import requests
import csv
import os
import json
import logging
import itertools
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────
# CONFIGURATION — Edit these before running
# ─────────────────────────────────────────────
DOMAIN              = "medicine"  # Must be a key in DOMAIN_BUNDLES
INPUT_CSV           = "/home/sushmetha/aditya/concepts_extracted_csv/dedup_outputs/medicine/medicine/dedup_semantic_0.90.csv"
OUTPUT_DIR          = "/home/sushmetha/aditya/concepts_extracted_csv/is_valid"
RULES_PATH          = "/home/sushmetha/aditya/concepts_extracted_csv/is_valid_test/pruning_rules.json"

MAX_WORKERS         = 512    # ← Keep this at 64–128; 8192 floods the server
SAMPLES_PER_CONCEPT = 700    # How many diverse combos to sample per concept
BATCH_SIZE          = 10     # How many combos to evaluate per LLM API call

# ─────────────────────────────────────────────
# RESUME CONFIG
# ─────────────────────────────────────────────
# Set to the path of a previous output CSV to resume from it.
# Set to None to start fresh (a new timestamped file is created).
RESUME_FROM_CSV     = "/home/sushmetha/aditya/concepts_extracted_csv/is_valid/validity_medicine_batched_20260526_133925.csv"  # e.g. "/home/.../validity_medicine_batched_20260526_133925.csv"

# ─────────────────────────────────────────────
# DOMAIN BUNDLES (Medicine Only)
# ─────────────────────────────────────────────
DOMAIN_BUNDLES = {
    "medicine": {
        "formats": [
            "tutorial", "dialogue", "faq", "case_study", "commentary",
            "reference_entry", "myth_vs_fact", "narrative"
        ],
        "audiences": [
            "complete_beginner", "informed_layperson", "practitioner",
            "domain_expert", "skeptic", "student"
        ],
        "angles": [
            "mechanistic", "historical", "failure_modes", "edge_cases",
            "practical_limits", "common_misuse", "underlying_theory", "interdependencies"
        ],
        "cognitive_operations": [
            "explain", "apply", "critique", "compare",
            "troubleshoot", "predict", "synthesize"
        ],
    }
}

# ─────────────────────────────────────────────
# MODEL CONFIG & PROMPTS
# ─────────────────────────────────────────────
MODEL_URL   = "http://34.93.210.88:8080/v1/chat/completions"
AUTH_TOKEN  = "Bearer gw-idMKBlwAA6aR0dV5u-HP5M76--41UqAvZmA31EWPI8E"

# ── Dual-model routing ──────────────────────
GEMMA_MODEL_ID    = "google/gemma-4-31B-it-mm"
DEEPSEEK_MODEL_ID = "deepseek-ai/DeepSeek-V3.1"
GEMMA_WEIGHT      = 0.60   # 60 % of requests → Gemma; 40 % → DeepSeek

def _pick_model() -> str:
    """Return a model ID according to the 60/40 split."""
    return GEMMA_MODEL_ID if random.random() < GEMMA_WEIGHT else DEEPSEEK_MODEL_ID
# ────────────────────────────────────────────


SYSTEM_PROMPT = """You are an expert curriculum designer working on a large-scale domain knowledge dataset. Your task is to evaluate whether a specific combination of dimensions would produce genuinely valuable training content about a given concept.

## Why This Decision Matters
This evaluation gates downstream LLM generation calls. Each generation call costs significant compute. A false positive (marking an invalid combo as valid) wastes an expensive generation call and introduces low-quality or redundant data into the training set. A false negative (marking a valid combo as invalid) is acceptable — we prefer precision over recall. When in doubt, mark invalid.

## Concept Types Reference
The concept you will evaluate belongs to one of these types. Use the type to inform your judgment.

- principle: A fundamental truth, rule, or guideline that governs behavior or outcomes in the domain. Usually normative or descriptive at a high level. Example: "Precautionary Principle in Medicine"
- process: A sequence of steps or stages that unfolds over time to produce an outcome. Has a clear start, progression, and end state. Example: "Digestion", "Fermentation"
- technique: A specific practical method or skill applied to achieve a result. More hands-on and applied than a process. Example: "Tempering Spices", "Cross Examination"
- relationship: A meaningful connection, dependency, or interaction between two or more entities or concepts. Example: "Dose-Response Relationship", "Correlation vs Causation"
- mechanism: The underlying system or means by which something works or produces an effect. More explanatory than a process — focuses on the how and why. Example: "Maillard Reaction", "Cognitive Dissonance"
- property: A characteristic, attribute, or quality that belongs to something. Describes what something is like rather than what it does. Example: "Viscosity", "Bioavailability"
- phenomenon: An observable event or pattern that occurs in the domain, often the thing being explained rather than the explanation itself. Example: "Emotional Eating", "Compound Interest Effect"

## The Four Dimensions
Each combo you evaluate is a combination of one value from each of these four dimensions.

### Dimension 1 — Format (how the content is structured)
| Format              | Description                                      |
|---------------------|--------------------------------------------------|
| tutorial            | Step-by-step instructional                       |
| dialogue            | Two-person conversation                          |
| faq                 | Question and answer pairs                        |
| case_study          | Real scenario walkthrough                        |
| commentary          | Expert opinion and analysis                      |
| reference_entry     | Encyclopedic definition and elaboration          |
| myth_vs_fact        | Structured misconception correction              |
| analogy_explainer   | Concept explained through extended analogy       |
| troubleshooting_guide | Problem → diagnosis → solution structure       |
| narrative           | Story-driven explanation                         |

### Dimension 2 — Audience (who the content is written for)
| Audience            | Description                                              |
|---------------------|----------------------------------------------------------|
| complete_beginner   | No prior knowledge assumed                               |
| informed_layperson  | General education, no domain expertise                   |
| practitioner        | Working professional in the domain                       |
| domain_expert       | Deep technical knowledge                                 |
| skeptic             | Questioning or resistant to the concept                  |
| student             | Learning the domain formally                             |
| caregiver_or_helper | Someone supporting another person (medicine, mental health, first aid) |

### Dimension 3 — Angle (what aspect of the concept is explored)
| Angle               | Description                                         |
|---------------------|-----------------------------------------------------|
| mechanistic         | How it works internally                             |
| historical          | How it developed or was discovered                  |
| failure_modes       | When and why it goes wrong                          |
| edge_cases          | Boundary conditions and exceptions                  |
| practical_limits    | Real-world constraints and caveats                  |
| common_misuse       | How people apply it incorrectly                     |
| underlying_theory   | Foundational principles behind it                   |
| interdependencies   | What other concepts it relies on or affects         |

### Dimension 4 — Cognitive Operation (what mental task the content demands)
| Operation           | Description                                                      |
|---------------------|------------------------------------------------------------------|
| explain             | Build understanding                                              |
| apply               | Use in a specific context                                        |
| critique            | Evaluate strengths and weaknesses                                |
| compare             | Contrast with a related concept                                  |
| troubleshoot        | Diagnose a problem involving the concept                         |
| predict             | Reason about outcomes using the concept                          |
| synthesize          | Combine with other concepts to reason about something new        |

## What Makes a Combo Valid
Apply STRONG validity — not "is this nonsensical?" but "would this combination produce genuinely informative, non-redundant content that a real reader of this audience type would benefit from?"

Ask yourself all four of the following. If any fails, mark invalid:
1. FORMAT FIT — Does this format naturally accommodate this concept type? (e.g. a troubleshooting_guide for a property with no failure modes is a poor fit)
2. ANGLE FIT — Does this angle surface real, non-trivial information about this concept? (e.g. historical angle on a concept with no meaningful history produces filler)
3. AUDIENCE FIT — Would a reader of this audience level get genuine value from this content? (e.g. domain_expert audience for a very elementary concept produces shallow content)
4. OPERATION FIT — Does the cognitive operation make sense given the format and concept type? (e.g. predict operation on a reference_entry format creates a structural mismatch)

## Output Format
Respond ONLY with valid JSON. No preamble, no explanation outside the JSON.
[
  {"id": "0", "is_valid": true, "reason": "<one sentence>"},
  {"id": "1", "is_valid": false, "reason": "<one sentence>"}
]"""



USER_PROMPT_TEMPLATE = """Domain: {domain}
Concept Name: {concept_name}
Concept Type: {concept_type}
Concept Definition: {concept_definition}

Evaluate these {batch_size} combinations:
{combos_text}"""


# ─────────────────────────────────────────────
# RESUME: load already-completed combos
# ─────────────────────────────────────────────
def load_completed_combos(csv_path: str) -> set:
    """
    Reads an existing output CSV and returns a set of
    (concept_name, format, audience, angle, cognitive_operation) tuples
    that were already successfully processed.
    Only rows where is_valid is not empty are counted as done.
    """
    done = set()
    if not csv_path or not os.path.exists(csv_path):
        return done
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # A row written by a previous run always has is_valid populated.
            # Skip rows that look like partial writes (empty reason).
            if row.get("is_valid", "").strip() == "":
                continue
            key = (
                row["concept_name"],
                row["format"],
                row["audience"],
                row["angle"],
                row["cognitive_operation"],
            )
            done.add(key)
    return done

# ─────────────────────────────────────────────
# SETUP & RETRY STRATEGY
# ─────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)

# If resuming, append to the existing file; otherwise create a new one.
if RESUME_FROM_CSV and os.path.exists(RESUME_FROM_CSV):
    output_path  = RESUME_FROM_CSV
    resume_mode  = True
else:
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path  = os.path.join(OUTPUT_DIR, f"validity_{DOMAIN}_batched_{timestamp}.csv")
    resume_mode  = False

error_path = os.path.join(OUTPUT_DIR, f"{DOMAIN}_batched_error_log.log")

logger = logging.getLogger("validity_check")
logger.setLevel(logging.ERROR)
fh = logging.FileHandler(error_path)
fh.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
logger.addHandler(fh)

retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)
_adapter = HTTPAdapter(
    pool_connections=MAX_WORKERS,
    pool_maxsize=MAX_WORKERS,
    max_retries=retry_strategy
)
SESSION = requests.Session()
SESSION.mount("http://", _adapter)
SESSION.mount("https://", _adapter)

# ─────────────────────────────────────────────
# LOAD HEURISTIC PRUNING RULES
# ─────────────────────────────────────────────
try:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        _rules = json.load(f)
    BANNED_TYPE_FMT = {tuple(x) for x in _rules.get("concept_type_vs_format", [])}
    BANNED_TYPE_ANG = {tuple(x) for x in _rules.get("concept_type_vs_angle", [])}
    BANNED_TYPE_OP  = {tuple(x) for x in _rules.get("concept_type_vs_operation", [])}
    print(f"Loaded {len(BANNED_TYPE_FMT) + len(BANNED_TYPE_ANG) + len(BANNED_TYPE_OP)} heuristic pruning rules.")
except FileNotFoundError:
    print("⚠️ Pruning rules JSON not found. Proceeding without heuristic filtering.")
    BANNED_TYPE_FMT, BANNED_TYPE_ANG, BANNED_TYPE_OP = set(), set(), set()

def is_structurally_valid(concept_type, fmt, aud, ang, op):
    """Checks if a combo survives the pruning rules."""
    if (concept_type, fmt) in BANNED_TYPE_FMT: return False
    if (concept_type, ang) in BANNED_TYPE_ANG: return False
    if (concept_type, op) in BANNED_TYPE_OP:   return False
    return True

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def iter_batched_tasks(concepts, base_combos, sample_size, batch_size, completed: set):
    """
    Filters, samples, and batches combinations for execution.
    Skips any (concept_name, fmt, aud, ang, op) tuple already in `completed`.
    """
    for row in concepts:
        c_type       = row["concept_type"]
        concept_name = row["concept_name"]

        # 1. Filter out known-bad structural combos
        good_combos = [
            c for c in base_combos
            if is_structurally_valid(c_type, c[0], c[1], c[2], c[3])
        ]

        # 2. Sample from the refined pool
        diverse_combos = random.sample(good_combos, min(sample_size, len(good_combos)))

        # 3. Drop combos already written to the output CSV (resume filter)
        if completed:
            diverse_combos = [
                c for c in diverse_combos
                if (concept_name, c[0], c[1], c[2], c[3]) not in completed
            ]

        # 4. Yield in micro-batches
        for chunk in chunk_list(diverse_combos, batch_size):
            yield row, chunk

def call_model_batched(concept_row, batched_combos):
    """Sends a batch of combos to the LLM and parses the JSON response."""
    combos_text = ""
    for i, (fmt, aud, ang, op) in enumerate(batched_combos):
        combos_text += f"[{i}] Format: {fmt} | Audience: {aud} | Angle: {ang} | Operation: {op}\n"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        domain             = concept_row["domain"],
        concept_name       = concept_row["concept_name"],
        concept_type       = concept_row["concept_type"],
        concept_definition = concept_row["concept_definition"],
        batch_size         = len(batched_combos),
        combos_text        = combos_text
    )

    # ── Route to Gemma (60 %) or DeepSeek (40 %) ──
    model_id = _pick_model()

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 1000,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    try:
        response = SESSION.post(
            MODEL_URL,
            json=payload,
            headers={"authorization": AUTH_TOKEN},
            timeout=120
        )
        response.raise_for_status()
        raw_content = response.json()["choices"][0]["message"]["content"].strip()

        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1].replace("json", "").strip()

        parsed_results = json.loads(raw_content)
        final_rows = []

        for idx in range(min(len(parsed_results), len(batched_combos))):
            result = parsed_results[idx]
            fmt, aud, ang, op = batched_combos[idx]

            final_rows.append({
                "run_id":              concept_row.get("run_id", ""),
                "seed_id":             concept_row.get("seed_id", ""),
                "domain":              concept_row["domain"],
                "concept_name":        concept_row["concept_name"],
                "concept_type":        concept_row["concept_type"],
                "concept_definition":  concept_row["concept_definition"],
                "format":              fmt,
                "audience":            aud,
                "angle":               ang,
                "cognitive_operation": op,
                "is_valid":            result.get("is_valid", False),
                "reason":              result.get("reason", "Parse error fallback"),
            })
        return final_rows

    except Exception as e:
        logger.error(
            "FAILED BATCH | model=%s | concept=%s | error=%s",
            model_id, concept_row["concept_name"], str(e)
        )
        return None

# ─────────────────────────────────────────────
# MAIN EXECUTOR
# ─────────────────────────────────────────────
def main():
    bundle = DOMAIN_BUNDLES[DOMAIN]
    all_possible_combos = list(itertools.product(
        bundle["formats"], bundle["audiences"], bundle["angles"], bundle["cognitive_operations"]
    ))

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        concepts = list(csv.DictReader(f))

    # ── Resume: figure out what's already done ──
    completed = load_completed_combos(output_path if resume_mode else None)
    already_done = len(completed)

    # Estimate remaining work (approximate — sampling is random so we can't be exact)
    total_samples   = len(concepts) * SAMPLES_PER_CONCEPT
    remaining_est   = max(0, total_samples - already_done)
    total_batches   = (remaining_est + BATCH_SIZE - 1) // BATCH_SIZE

    print("=" * 65)
    print(f"  Domain              : {DOMAIN}")
    print(f"  Concepts loaded     : {len(concepts):,}")
    print(f"  Resume mode         : {'YES — appending to existing CSV' if resume_mode else 'NO  — fresh run'}")
    if resume_mode:
        print(f"  Already completed   : {already_done:,} combos (skipping these)")
    print(f"  Remaining (approx)  : {remaining_est:,} validations")
    print(f"  API calls (approx)  : ~{total_batches:,} (Batched by {BATCH_SIZE})")
    print(f"  Concurrent workers  : {MAX_WORKERS}")
    print(f"  Models              : {GEMMA_MODEL_ID} (60%) | {DEEPSEEK_MODEL_ID} (40%)")
    print(f"  Output CSV          : {output_path}")
    print("=" * 65)

    fieldnames = [
        "run_id", "seed_id", "domain", "concept_name", "concept_type",
        "concept_definition", "format", "audience", "angle", "cognitive_operation",
        "is_valid", "reason"
    ]

    success_count = 0
    failure_count = 0

    # Open in append mode when resuming (skip writing header), write mode otherwise
    file_mode = "a" if resume_mode else "w"
    with open(output_path, file_mode, newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if not resume_mode:
            writer.writeheader()
            out_f.flush()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            QUEUE_LIMIT = MAX_WORKERS * 5
            futures     = {}

            task_gen = iter_batched_tasks(
                concepts, all_possible_combos, SAMPLES_PER_CONCEPT, BATCH_SIZE, completed
            )

            def submit_next():
                try:
                    row, batched_chunk = next(task_gen)
                    f = executor.submit(call_model_batched, row, batched_chunk)
                    futures[f] = batched_chunk
                    return True
                except StopIteration:
                    return False

            for _ in range(QUEUE_LIMIT):
                submit_next()

            with tqdm(total=total_batches, unit="batch", dynamic_ncols=True) as pbar:
                while futures:
                    future = next(as_completed(futures))
                    chunk_processed = futures.pop(future)
                    submit_next()

                    results = future.result()
                    if results:
                        writer.writerows(results)
                        out_f.flush()
                        success_count += len(results)
                    else:
                        failure_count += len(chunk_processed)

                    pbar.set_postfix(success=success_count, failed=failure_count, refresh=False)
                    pbar.update(1)

    print("=" * 65)
    print(f"  Done! Saved to {output_path}")
    print(f"  Combos written this run : {success_count:,}")
    print(f"  Failed (not written)    : {failure_count:,}")
    print("=" * 65)

if __name__ == "__main__":
    main()
