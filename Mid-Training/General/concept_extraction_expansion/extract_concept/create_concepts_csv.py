import requests
import json
import csv
import os
import threading
import time
from datetime import datetime

"""
TAKES THE OUTPUT CSV OF run_concept_extraction.py (which has one row per run, with a run_id), FETCHES THE DRAFT FOR EACH RUN_ID, 
PARSES THE CONCEPTS OUT OF THE DRAFT, AND FLATTENS + SAVES THEM TO A NEW CSV WITH ONE ROW PER CONCEPT.
OUTPUT COLS ARE : run_id, seed_id, domain, concept_name, concept_type, concept_definition
"""
# ─────────────────────────────────────────────
# CONFIGURE THESE BEFORE RUNNING
# ─────────────────────────────────────────────
INPUT_CSV_PATH = "/home/sushmetha/aditya/concept_extraction_csvs/old_mehul_chunks/Mental Health_output.csv"     # CSV produced by run_concept_extraction.py
CONCURRENCY    = 128                  # Number of concurrent worker threads
SLEEP_BETWEEN_BATCHES = 1            # Seconds to sleep between batches
# ─────────────────────────────────────────────
# Get the domain from the domain column of the input CSV
import pandas as pd
df = pd.read_csv(INPUT_CSV_PATH)
if "domain" not in df.columns:
    raise ValueError("Input CSV must have a 'domain' column")
DOMAIN = df["domain"].iloc[0]
BASE_URL       = "http://34.14.214.233:8000/api/v1"
OUTPUT_DIR     = "concepts_extracted_csv"
OUTPUT_CSV     = os.path.join(OUTPUT_DIR, f"concepts_{DOMAIN}.csv")

FIELDNAMES     = ["run_id", "seed_id", "domain", "concept_name", "concept_type", "concept_definition"]

csv_lock       = threading.Lock()


# ─────────────────────────────────────────────
# IO Helpers
# ─────────────────────────────────────────────

def load_runs(filepath):
    """Load rows from the runs CSV. Only process rows with status STARTED."""
    runs = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "").strip() == "STARTED":
                runs.append(row)
    print(f"[INFO] Loaded {len(runs)} STARTED runs from {filepath}")
    return runs


def init_output_csv():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
    print(f"[INFO] Initialised output CSV at {OUTPUT_CSV}")


def write_rows(rows):
    """Thread-safe write of multiple concept rows."""
    with csv_lock:
        with open(OUTPUT_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerows(rows)


# ─────────────────────────────────────────────
# API + Parsing
# ─────────────────────────────────────────────

def fetch_draft(run_id):
    """Fetch draft JSON for a run_id. Returns parsed JSON or None."""
    try:
        response = requests.get(
            f"{BASE_URL}/drafts",
            params={"run_id": run_id},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch draft for run_id={run_id}: {e}")
        return None


def parse_concepts(draft_json, run_id, seed_id, domain):
    """
    Extract candidate_response from draft, parse JSON inside it,
    return list of flat concept dicts.
    """
    drafts = draft_json.get("drafts", [])
    if not drafts:
        print(f"[WARN] No drafts found for run_id={run_id}")
        return []

    # Take first draft (pipeline produces one per run)
    draft = drafts[0]
    teacher_output = draft.get("teacher_output", {})
    candidate_response = teacher_output.get("candidate_response", "")

    if not candidate_response:
        print(f"[WARN] Empty candidate_response for run_id={run_id}")
        return []

    try:
        parsed = json.loads(candidate_response)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse candidate_response JSON for run_id={run_id}: {e}")
        print(f"[DEBUG] Raw candidate_response: {candidate_response[:300]}")
        return []

    # Use domain from parsed output if available, else fall back to CSV value
    parsed_domain = parsed.get("domain", domain)
    concepts      = parsed.get("concepts", [])

    if not concepts:
        print(f"[WARN] No concepts found in output for run_id={run_id}")
        return []

    rows = []
    for concept in concepts:
        rows.append({
            "run_id":              run_id,
            "seed_id":             seed_id,
            "domain":              parsed_domain,
            "concept_name":        concept.get("name", "").strip(),
            "concept_type":        concept.get("type", "").strip(),
            "concept_definition":  concept.get("definition", "").strip(),
        })

    return rows


# ─────────────────────────────────────────────
# Worker
# ─────────────────────────────────────────────

def process_run(run_row):
    run_id  = run_row["run_id"].strip()
    seed_id = run_row["seed_id"].strip()
    domain  = run_row.get("domain", "").strip()

    print(f"[INFO] Fetching run_id={run_id}")

    draft_json = fetch_draft(run_id)
    if draft_json is None:
        return

    rows = parse_concepts(draft_json, run_id, seed_id, domain)
    if rows:
        write_rows(rows)
        print(f"[INFO] run_id={run_id} → wrote {len(rows)} concept rows")
    else:
        print(f"[WARN] run_id={run_id} → no rows written")


def process_batch(batch, batch_num):
    print(f"[INFO] Batch {batch_num} — processing {len(batch)} runs concurrently")
    threads = []
    for run_row in batch:
        t = threading.Thread(
            target=process_run,
            args=(run_row,),
            name=f"batch{batch_num}-{run_row['run_id']}"
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"[INFO] Batch {batch_num} — all threads finished")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print(f"[INFO] Input CSV     : {INPUT_CSV_PATH}")
    print(f"[INFO] Output CSV    : {OUTPUT_CSV}")
    print(f"[INFO] Concurrency   : {CONCURRENCY}")
    print(f"[INFO] Sleep between : {SLEEP_BETWEEN_BATCHES}s")

    runs = load_runs(INPUT_CSV_PATH)
    if not runs:
        print("[ERROR] No STARTED runs found. Exiting.")
        return

    init_output_csv()

    batches      = [runs[i:i + CONCURRENCY] for i in range(0, len(runs), CONCURRENCY)]
    total_batches = len(batches)
    print(f"[INFO] Total batches : {total_batches}")

    for batch_num, batch in enumerate(batches, start=1):
        process_batch(batch, batch_num)

        if batch_num < total_batches:
            print(f"[INFO] Sleeping {SLEEP_BETWEEN_BATCHES}s before next batch...")
            time.sleep(SLEEP_BETWEEN_BATCHES)

    print(f"[INFO] All done. Flat concepts CSV saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()