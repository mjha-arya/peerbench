"""CLI: python -m peerbench --csv financials.csv --company "Mega AI Co" --competitors "Datadog,Elastic"
Exit 0 = report written and verified; 2 = bad input or unverified numbers (needs_human)."""
import argparse
import sys
from pathlib import Path

from .metrics import BadCSV, load_csv, summarise


def main() -> int:
    ap = argparse.ArgumentParser(prog="peerbench")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--company", required=True)
    ap.add_argument("--competitors", required=True, help="comma-separated names")
    ap.add_argument("--max-revisions", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="parse the CSV and print metrics; no LLM, no web, no files")
    a = ap.parse_args()
    text = Path(a.csv).read_text(encoding="utf-8")
    try:
        if a.dry_run:
            rows, ignored = load_csv(text)
            print(summarise(rows), "| ignored columns:", ignored)
            return 0
        from .graph import run
        out = run(a.company, text, a.competitors.split(","), a.max_revisions, Path(a.csv).name)
    except BadCSV as e:
        print(f"NEEDS HUMAN: {e}", file=sys.stderr)
        return 2
    print(out["report_path"])
    print(f"revisions={out.get('revision')} score={out.get('score')} violations={out.get('violations')} unresolved={out.get('unresolved')}")
    if out.get("violations"):
        return 2
    if not out.get("peer_metrics"):
        print("NEEDS HUMAN: no competitor could be resolved", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
