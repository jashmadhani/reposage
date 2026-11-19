"""Run the ten question eval set against RepoSage's own code.

For each case the question goes through the real agent pipeline; a case passes
if the expected file (named in the reference answer, e.g. "(backend/chunker.py)")
is among the citations whose line range exists in the index.

Needs a real key (GOOGLE_API_KEY or GEMINI_API_KEY in .env, or GROQ_API_KEY).
Run from the repository root:

    EMBEDDING_PROVIDER=local python eval/run_eval.py

Writes eval/results.json and prints a summary.
"""

import asyncio
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import citations  # noqa: E402
import keys  # noqa: E402
import repo_loader  # noqa: E402
import vector_store  # noqa: E402
from agent import pipeline  # noqa: E402

keys.activate()
REPO_URL = "https://github.com/jashmadhani/reposage"
MAX_TRIES = 4


def snapshot_files():
    """Index a clean copy of the committed files (no venv, no cloned repos)."""
    tmp = tempfile.mkdtemp(prefix="reposage-eval-")
    archive = subprocess.run(
        ["git", "archive", "HEAD"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True)
    return repo_loader.collect_files(tmp)


def retry_seconds(error: Exception):
    """Seconds to wait if this is a per-minute rate limit, None if not retryable."""
    text = " ".join(str(error).split())
    if "per day" in text.lower():
        return None
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "503" in text:
        m = re.search(r"retry in ([\d.]+)s", text)
        return (float(m.group(1)) + 2) if m else 20.0
    return None


async def run_case(question):
    for attempt in range(1, MAX_TRIES + 1):
        try:
            return await pipeline.run(question), None
        except Exception as e:  # noqa: BLE001
            wait = retry_seconds(e)
            if wait is None or attempt == MAX_TRIES:
                return None, " ".join(str(e).split())[:200]
            print(f"   rate limited, waiting {wait:.0f}s (try {attempt})", flush=True)
            await asyncio.sleep(wait)


def main():
    evalset = json.loads((ROOT / "eval" / "reposage.evalset.json").read_text())
    idx = vector_store.build("reposage", snapshot_files())
    print(f"indexed {len(idx.files)} files, {len(idx.chunks)} chunks", flush=True)

    results = []
    for case in evalset["eval_cases"]:
        inv = case["conversation"][0]
        question = inv["user_content"]["parts"][0]["text"]
        reference = inv["final_response"]["parts"][0]["text"]
        expected = re.search(r"\(([\w./-]+)\)\s*$", reference).group(1)
        print(f"- {case['eval_id']}: {question}", flush=True)
        out, err = asyncio.run(run_case(question))
        if err:
            print(f"   ERROR {err}", flush=True)
            results.append({"id": case["eval_id"], "expected": expected, "error": err, "passed": False})
            if "per day" in err.lower() or "daily" in err.lower():
                print("   daily quota reached, stopping", flush=True)
                break
            continue
        cites = citations.resolve(out["answer"], idx, REPO_URL)
        cited = sorted({c["path"] for c in cites if c["verified"]})
        passed = expected in cited
        t = out["trace"]
        print(f"   {'PASS' if passed else 'FAIL'} expected={expected} cited={cited}", flush=True)
        results.append(
            {
                "id": case["eval_id"],
                "expected": expected,
                "cited": cited,
                "passed": passed,
                "latency_ms": t["latency_ms"],
                "tokens_in": t["tokens_in"],
                "tokens_out": t["tokens_out"],
                "llm_calls": t["llm_calls"],
                "tool_calls": t["tool_calls"],
            }
        )
        time.sleep(5)  # stay under the free tier requests per minute

    done = [r for r in results if "error" not in r]
    summary = {
        "model": os.getenv("GEMINI_MODEL", pipeline.MODEL),
        "provider": pipeline.llm_provider(),
        "cases_total": len(evalset["eval_cases"]),
        "cases_run": len(done),
        "passed": sum(r["passed"] for r in done),
    }
    if done:
        summary["p50_latency_s"] = round(statistics.median(r["latency_ms"] for r in done) / 1000, 1)
        summary["median_tokens_in"] = int(statistics.median(r["tokens_in"] for r in done))
        summary["median_tokens_out"] = int(statistics.median(r["tokens_out"] for r in done))
    (ROOT / "eval" / "results.json").write_text(json.dumps({"summary": summary, "cases": results}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
