"""Usage: python -m src.explain_price YYYY-MM-DD [--json] [--agent --model MODEL]."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from .rca_evidence import EvidenceStore, ROOT, render_report


def main():
    parser = argparse.ArgumentParser(description="Explain a saved DPE recommendation, read-only")
    parser.add_argument("date", help="Departure date: YYYY-MM-DD")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository containing saved artefacts")
    parser.add_argument("--json", action="store_true", help="Print evidence and hashes as JSON")
    parser.add_argument("--agent", action="store_true", help="Make an OpenAI API call for a narrative")
    parser.add_argument("--model", help="Explicit OpenAI model available to your API project")
    args = parser.parse_args()
    try:
        report = EvidenceStore(args.root).explain(args.date)
        if args.agent:
            if not args.model:
                parser.error("--agent requires --model")
            from .rca_agent import explain_with_agent
            narrative = asyncio.run(explain_with_agent(report, args.model))
            if args.json:
                print(json.dumps({"evidence": report, "agent": narrative}, indent=2, allow_nan=False))
            else:
                print(render_report(report))
                print("\nAgent explanation (generated prose):")
                for finding in narrative["explanation"]["findings"]:
                    print("\n" + finding["explanation"])
                    print("Evidence: " + ", ".join(finding["evidence_refs"]))
                for question in narrative["explanation"]["unresolved_questions"]:
                    print("Data-team question: " + question)
                print("\nTool calls: " + ", ".join(narrative["tool_calls"]))
        else:
            print(json.dumps(report, indent=2, allow_nan=False) if args.json else render_report(report))
        return 0 if report["status"] == "ok" else 2
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Explanation unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
