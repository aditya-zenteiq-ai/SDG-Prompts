"""
Concept Deduplication Pipeline
================================
Handles both CSV formats:
  - run_id, seed_id, domain, concept_name, concept_definition
  - run_id, seed_id, domain, concept_name, concept_type, concept_definition

Dedup signal : concept_name + concept_definition  (concept_type ignored for similarity)
Output cols  : all original columns preserved (including concept_type if present)

Outputs per domain subdirectory:
  dedup_exact.csv
  dedup_minhash.csv
  dedup_semantic_0.75.csv
  dedup_semantic_0.80.csv
  dedup_semantic_0.85.csv
  dedup_semantic_0.90.csv
  dedup_semantic_0.95.csv

Usage:
  python3 dedup_concepts.py --input /path/to/concepts_Astrology.csv
  python3 dedup_concepts.py --input /path/to/concepts_Cooking.csv --output_base /custom/output/dir
"""

import argparse
import asyncio
import os
import time

import aiohttp
import numpy as np
import pandas as pd
from datasketch import MinHash, MinHashLSH

# ── Config ─────────────────────────────────────────────────────────────────────
EMBED_URL      = "http://34.180.52.53:8000/v1/embeddings"
EMBED_MODEL    = "Qwen3-VL-Embedding-8B-FP8"
MAX_CONCURRENT = 4
BATCH_SIZE     = 32
MAX_RETRIES    = 3

MINHASH_THRESHOLD = 0.5
MINHASH_NUM_PERM  = 128
NGRAM_SIZE        = 3

SEMANTIC_THRESHOLDS = [0.90]

SEP  = "─" * 70
SEP2 = "═" * 70


# ── Load & Normalise ───────────────────────────────────────────────────────────
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Detect format — concept_type column may or may not be present
    has_type = "concept_type" in df.columns
    print(f"  Columns  : {list(df.columns)}")
    print(f"  Has concept_type: {has_type}")

    # Dedup signal: name + definition only (type deliberately excluded)
    df["_dedup_text"] = (
        df["concept_name"].fillna("").str.strip()
        + " "
        + df["concept_definition"].fillna("").str.strip()
    ).str.strip()

    domain = df["domain"].iloc[0] if "domain" in df.columns else "unknown"
    print(f"  Domain   : {domain}")
    print(f"  Concepts : {len(df)}")
    print(f"  Seeds    : {df['seed_id'].nunique()}")
    return df, domain


# ── Output columns (drop internal helper) ─────────────────────────────────────
def save(df: pd.DataFrame, path: str):
    df.drop(columns=["_dedup_text"], errors="ignore").to_csv(path, index=False)
    print(f"  Saved → {path}  ({len(df)} concepts)")


# ── Method 1: Exact ────────────────────────────────────────────────────────────
def exact_dedup(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    out = df.drop_duplicates(subset=["_dedup_text"], keep="first").reset_index(drop=True)
    print(f"  {before} → {len(out)}  (removed {before - len(out)})")
    return out


# ── Method 2: MinHash ──────────────────────────────────────────────────────────
def _make_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=MINHASH_NUM_PERM)
    t = text.lower()
    for i in range(len(t) - NGRAM_SIZE + 1):
        m.update(t[i : i + NGRAM_SIZE].encode("utf-8"))
    return m


def minhash_dedup(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    lsh      = MinHashLSH(threshold=MINHASH_THRESHOLD, num_perm=MINHASH_NUM_PERM)
    minhashes = {}

    for idx, row in df.iterrows():
        m = _make_minhash(row["_dedup_text"])
        minhashes[idx] = m
        lsh.insert(str(idx), m)

    removed = set()
    for idx in df.index:
        if idx in removed:
            continue
        for c_str in lsh.query(minhashes[idx]):
            c = int(c_str)
            if c != idx and c not in removed:
                if minhashes[idx].jaccard(minhashes[c]) >= MINHASH_THRESHOLD:
                    removed.add(c)

    out = df[~df.index.isin(removed)].reset_index(drop=True)
    print(f"  {before} → {len(out)}  (removed {before - len(out)})")
    return out


# ── Method 3: Semantic ─────────────────────────────────────────────────────────
async def _fetch_batch(
    session: aiohttp.ClientSession,
    texts: list,
    batch_idx: int,
    semaphore: asyncio.Semaphore,
) -> tuple:
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with semaphore:
                payload = {"model": EMBED_MODEL, "input": texts}
                async with session.post(
                    EMBED_URL, json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            embeddings = [
                item["embedding"]
                for item in sorted(data["data"], key=lambda x: x["index"])
            ]
            return batch_idx, embeddings
        except Exception as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"    [batch {batch_idx}] attempt {attempt} failed ({e}), retry in {wait}s...")
                await asyncio.sleep(wait)
    raise RuntimeError(f"Batch {batch_idx} failed after {MAX_RETRIES} attempts: {last_exc}")


async def _get_all_embeddings(texts: list) -> np.ndarray:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    batches   = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]
    total     = len(batches)
    print(f"  {len(texts)} texts → {total} batches  (size={BATCH_SIZE}, concurrency={MAX_CONCURRENT})")

    results    = [None] * total
    done_count = 0

    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_batch(session, b, i, semaphore) for i, b in enumerate(batches)]
        for coro in asyncio.as_completed(tasks):
            batch_idx, embeddings = await coro
            results[batch_idx] = embeddings
            done_count += 1
            if done_count % 20 == 0 or done_count == total:
                print(f"    ... {done_count}/{total} batches done")

    flat = [emb for batch in results for emb in batch]
    return np.array(flat, dtype=np.float32)


def semantic_dedup(df: pd.DataFrame, embeddings: np.ndarray, threshold: float) -> pd.DataFrame:
    before = len(df)
    norms  = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normed = embeddings / np.clip(norms, 1e-10, None)
    sim    = normed @ normed.T   # full pairwise cosine similarity

    removed = set()
    for i in range(len(df)):
        if i in removed:
            continue
        dupes = np.where(sim[i, i + 1 :] >= threshold)[0] + (i + 1)
        for j in dupes:
            if j not in removed:
                removed.add(int(j))

    kept = [i not in removed for i in range(len(df))]
    out  = df[kept].reset_index(drop=True)
    print(f"  {before} → {len(out)}  (removed {before - len(out)})")
    return out


# ── Summary ────────────────────────────────────────────────────────────────────
def print_summary(original_len: int, results: dict):
    print(f"\n{SEP2}")
    print("  SUMMARY")
    print(SEP2)
    print(f"  {'Method':<28} {'Concepts':>9} {'Removed':>9} {'Seeds lost':>11} {'Median/seed':>13}")
    print(f"  {'─'*28} {'─'*9} {'─'*9} {'─'*11} {'─'*13}")
    for label, (df_out, orig_seeds) in results.items():
        removed   = original_len - len(df_out)
        surviving = set(df_out["seed_id"].unique())
        lost      = len(orig_seeds - surviving)
        median    = df_out.groupby("seed_id")["concept_name"].count().median()
        print(f"  {label:<28} {len(df_out):>9} {removed:>9} {lost:>11} {median:>13.1f}")
    print()


# ── Main ───────────────────────────────────────────────────────────────────────
async def main(input_csv: str, output_base: str):
    print(f"\n{SEP2}")
    print("  CONCEPT DEDUPLICATION PIPELINE")
    print(SEP2)

    df, domain = load_data(input_csv)
    orig_seeds = set(df["seed_id"].unique())

    # Output dir: base/domain_lowercase/
    out_dir = os.path.join(output_base, domain.lower())
    os.makedirs(out_dir, exist_ok=True)
    print(f"  Output → {out_dir}\n")

    results = {}  # label → (df_out, orig_seeds) for summary

    # ── 1. Exact ──
    # print(f"{SEP}\n  1. EXACT DEDUP\n{SEP}")
    # df_exact = exact_dedup(df)
    # save(df_exact, os.path.join(out_dir, "dedup_exact.csv"))
    # results["exact"] = (df_exact, orig_seeds)

    # # ── 2. MinHash ──
    # print(f"\n{SEP}\n  2. MINHASH DEDUP  (Jaccard ≥ {MINHASH_THRESHOLD}, char {NGRAM_SIZE}-grams)\n{SEP}")
    # df_minhash = minhash_dedup(df)
    # save(df_minhash, os.path.join(out_dir, "dedup_minhash.csv"))
    # results["minhash"] = (df_minhash, orig_seeds)

    # ── 3. Semantic ──
    print(f"\n{SEP}\n  3. SEMANTIC DEDUP  (fetching embeddings)\n{SEP}")
    t0 = time.time()
    embeddings = await _get_all_embeddings(df["_dedup_text"].tolist())
    print(f"  Embeddings ready in {time.time() - t0:.1f}s  shape={embeddings.shape}\n")

    for threshold in SEMANTIC_THRESHOLDS:
        print(f"  threshold = {threshold}")
        df_sem = semantic_dedup(df, embeddings, threshold)
        fname  = f"dedup_semantic_{threshold:.2f}.csv"
        save(df_sem, os.path.join(out_dir, fname))
        results[f"semantic_{threshold:.2f}"] = (df_sem, orig_seeds)

    print_summary(len(df), results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", required=True,
        help="Path to input concepts CSV"
    )
    parser.add_argument(
        "--output_base",
        default="/home/sushmetha/aditya/concepts_extracted_csv/dedup_concepts",
        help="Base output directory (domain subdirectory created automatically)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.input, args.output_base))
