import requests
import json
import csv
import threading
import time
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURE THESE BEFORE RUNNING
# ─────────────────────────────────────────────
SEED_FILE_PATH = "/home/sushmetha/aditya/seed_ids/medicine_seed_ids.txt"          # Path to text file with one seed_id per row
DOMAIN = "Medicine"                    # Domain name for this run
CONCURRENCY = 32                        # Number of concurrent threads
SLEEP_BETWEEN_REQUESTS = 120           # Seconds to sleep between batches
OUTPUT_CSV = f"/home/sushmetha/aditya/concept_extraction_csvs/old_mehul_chunks/{DOMAIN}_output.csv"         # Output CSV file path
"""
OUTPUT COLS ARE  : run_id,seed_id,domain,target_concepts_range,status,timestamp
"""
# ─────────────────────────────────────────────

BASE_URL = "http://34.14.214.233:8000/api/v1"
PROMPT_TEMPLATE_ID = "0e1ff9aa-22a1-4134-bb30-03a4f62ce873"

DOMAIN_RANGE_MAP = {
    "Medicine":        "1-20",
    "Law":             "1-20",
    "Mental Health":   "1-20",
    "Diets":           "1-15",
    "Indian_Cooking":  "1-15",
    "Cooking":         "1-15",
    "Astrology":       "1-15",
    "Household":       "1-20",
    "first_aid":       "1-20",
    "Humour":          "1-15",
}

csv_lock = threading.Lock()


def get_target_range(domain):
    if domain not in DOMAIN_RANGE_MAP:
        raise ValueError(f"Domain '{domain}' not found in DOMAIN_RANGE_MAP. Please add it.")
    return DOMAIN_RANGE_MAP[domain]


def create_run(seed_id, domain, target_range):
    """Creates a run and returns run_id, or None on failure."""
    payload = {
        "seed_data_id": seed_id,
        "task_type": "concept_extraction",
        "is_thinking": False,
        "prompt_template_ids": [
            {"type": "teacher_a", "prompt_id": PROMPT_TEMPLATE_ID, "model": "deepseek-ai/DeepSeek-V3.1"},
            {"type": "auditor", "model": "Qwen/Qwen3-32B"},
            {"type": "dean", "model": "Qwen/Qwen3.5-122B-A10B"},
            {"type": "tool_verifier", "model": "Qwen/Qwen3-32B"},
            {"type": "final_guardrail", "model": "Qwen/Qwen3Guard-Gen-8B"}
        ],
        "custom_vars": {
            "request": {
                "domain": domain,
                "target_concepts_range": target_range
            }
        }
    }

    try:
        response = requests.post(
            f"{BASE_URL}/runs",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=30
        )
        print(f"[DEBUG] Create run response [{response.status_code}]: {response.text}")
        response.raise_for_status()
        data = response.json()
        run_id = data.get("run_id")
        if not run_id:
            print(f"[WARN] No run_id in response for seed {seed_id}: {data}")
        return run_id
    except Exception as e:
        print(f"[ERROR] Failed to create run for seed {seed_id}: {e}")
        return None


def start_run(run_id):
    """Starts a run. Returns True if successful."""
    try:
        response = requests.post(
            f"{BASE_URL}/runs/{run_id}/start",
            timeout=30
        )
        print(f"[DEBUG] Start run response [{response.status_code}]: {response.text}")
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to start run {run_id}: {e}")
        return False


def write_csv_row(row):
    """Thread-safe CSV row writer."""
    with csv_lock:
        with open(OUTPUT_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "run_id", "seed_id", "domain", "target_concepts_range", "status", "timestamp"
            ])
            writer.writerow(row)


def process_seed(seed_id, domain, target_range):
    """Full pipeline for one seed: create run -> start run -> log result."""
    print(f"[INFO] Processing seed: {seed_id}")

    run_id = create_run(seed_id, domain, target_range)

    if not run_id:
        write_csv_row({
            "run_id": "N/A",
            "seed_id": seed_id,
            "domain": domain,
            "target_concepts_range": target_range,
            "status": "FAILED_CREATE",
            "timestamp": datetime.now().isoformat()
        })
        return

    success = start_run(run_id)
    status = "STARTED" if success else "FAILED_START"

    write_csv_row({
        "run_id": run_id,
        "seed_id": seed_id,
        "domain": domain,
        "target_concepts_range": target_range,
        "status": status,
        "timestamp": datetime.now().isoformat()
    })

    print(f"[INFO] seed={seed_id} run_id={run_id} status={status}")


def init_csv():
    """Create CSV with headers."""
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "run_id", "seed_id", "domain", "target_concepts_range", "status", "timestamp"
        ])
        writer.writeheader()


def load_seeds(filepath):
    with open(filepath, "r") as f:
        seeds = [line.strip() for line in f if line.strip()]
    return seeds


def process_batch(batch, domain, target_range, batch_num):
    """Spawn one thread per seed in the batch, wait for all to finish."""
    print(f"[INFO] Batch {batch_num} — processing {len(batch)} seeds concurrently")
    threads = []
    for seed_id in batch:
        t = threading.Thread(
            target=process_seed,
            args=(seed_id, domain, target_range),
            name=f"batch{batch_num}-{seed_id}"
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"[INFO] Batch {batch_num} — all threads finished")


def main():
    target_range = get_target_range(DOMAIN)

    print(f"[INFO] Domain        : {DOMAIN}")
    print(f"[INFO] Target range  : {target_range}")
    print(f"[INFO] Concurrency   : {CONCURRENCY}")
    print(f"[INFO] Sleep between : {SLEEP_BETWEEN_REQUESTS}s")
    print(f"[INFO] Output CSV    : {OUTPUT_CSV}")

    seeds = load_seeds(SEED_FILE_PATH)
    print(f"[INFO] Total seeds   : {len(seeds)}")

    init_csv()

    batches = [seeds[i:i + CONCURRENCY] for i in range(0, len(seeds), CONCURRENCY)]
    total_batches = len(batches)
    print(f"[INFO] Total batches : {total_batches}")

    for batch_num, batch in enumerate(batches, start=1):
        process_batch(batch, DOMAIN, target_range, batch_num)

        if batch_num < total_batches:
            print(f"[INFO] Sleeping {SLEEP_BETWEEN_REQUESTS}s before next batch...")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"[INFO] All done. Results saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()