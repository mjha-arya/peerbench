"""Run every golden case on the real model + real tools and score deterministically.
Usage (from the PeerBench folder): python evals/run_golden.py [case_id ...]
Writes evals/results-<date>.jsonl and prints a pass table."""
import json
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from peerbench import config  # noqa: E402
from peerbench.graph import run  # noqa: E402


def score(case: dict, out: dict) -> list[str]:
    """Return failed checks (empty = pass)."""
    e, fails = case["expect"], []
    report = out.get("report", "")
    for k, v in e.get("metrics", {}).items():
        if k.endswith("_2024_pct"):
            k = k.replace("_2024", "")
        if out["metrics"].get(k) != v:
            fails.append(f"metric {k}={out['metrics'].get(k)} want {v}")
    for name, t in e.get("tickers", {}).items():
        got = (out.get("resolved", {}).get(name) or {}).get("ticker")
        if got != t:
            fails.append(f"ticker {name}={got} want {t}")
    for name in e.get("unresolved", []):
        if name not in out.get("unresolved", []):
            fails.append(f"{name} should be unresolved")
    for sec in e.get("report_sections", []):
        if not re.search(rf"^## {re.escape(sec)}", report, re.M):
            fails.append(f"missing section {sec}")
    if e.get("report_mentions") and e["report_mentions"].lower() not in report.lower():
        fails.append(f"report lacks {e['report_mentions']!r}")
    for s in e.get("report_must_not_contain", []):
        if s.lower() in report.lower():
            fails.append(f"report contains forbidden {s!r}")
    for name in e.get("no_numbers_for", []):
        for sent in re.split(r"(?<=[.!?])\s+|\n", report):
            if name in sent and re.search(r"\$\d|\d%", sent):
                fails.append(f"numbers given for {name}: {sent[:80]}")
    if "check_numbers_violations" in e and len(out.get("violations") or []) != e["check_numbers_violations"]:
        fails.append(f"violations {out.get('violations')}")
    if e.get("every_peer_number_has_source"):
        for name, x in out.get("peer_metrics", {}).items():
            if not x.get("url") or x["url"] not in report:
                fails.append(f"peer {name} has no source in report")
    # harness hygiene: no duplicate tool calls, bounded loop
    dupes = [q for q, n in Counter(out.get("queries", [])).items() if n > 1]
    if dupes:
        fails.append(f"duplicate search queries {dupes}")
    if out.get("revision", 0) > case["input"]["max_revisions"]:
        fails.append("revision loop exceeded max")
    return fails


def main(ids: list[str]) -> int:
    cases = [json.loads(l) for l in (ROOT / "evals" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = [c for c in cases if not ids or c["id"] in ids]
    results_path = ROOT / "evals" / f"results-{date.today()}.jsonl"
    passed = 0
    for c in cases:
        i = c["input"]
        t0 = time.time()
        try:
            out = run(i["company"], i["csv"], i["competitors"], i["max_revisions"], f"golden:{c['id']}")
            fails = score(c, out)
        except Exception as ex:
            out, fails = {}, [f"crash {type(ex).__name__}: {ex}"]
        ok = not fails
        passed += ok
        rec = {"id": c["id"], "kind": c["kind"], "pass": ok, "fails": fails, "secs": round(time.time() - t0, 1),
               "model": config.MODEL, "run_id": out.get("run_id"), "revisions": out.get("revision"),
               "score": out.get("score"), "violations": out.get("violations"), "report": out.get("report_path"),
               "queries": len(out.get("queries", []))}
        with open(results_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:<18} {rec['secs']:>6}s  rev={rec['revisions']} score={rec['score']}  {'; '.join(fails)}", flush=True)
    print(f"\n{passed}/{len(cases)} passed  (model {config.MODEL})")
    return 0 if passed >= 4 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
