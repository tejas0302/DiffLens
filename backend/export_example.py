"""Regenerate the example review shown on the live site (frontend/lib/example-review.json).

Runs the REAL analysis (rules + LLM) on the demo PR from seed_demo.py, with no
GitHub and no database. Run it with OPENAI_API_KEY set so the example shows
real AI grouping; without a key it records the fallback output, and the
"model" field says so.

    cd backend && python export_example.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.analyzer import analyze
from app.diff_parser import diff_stats, parse_files
from app.risk import find_risks
from seed_demo import DEMO_FILES

TITLE = "Rate-limit failed logins"
BODY = "Locks an account for 15 minutes after 5 failed logins."
OUT = Path(__file__).resolve().parent.parent / "frontend" / "lib" / "example-review.json"

if __name__ == "__main__":
    files = parse_files(DEMO_FILES)
    rule_risks = find_risks(files)
    result = analyze(TITLE, BODY, files)
    risks = rule_risks + result["llm_risks"]
    review = {
        "id": 0,
        "repo": "demo/shop-api",
        "pr_number": 42,
        "title": TITLE,
        "author": "example-author",
        "status": "done",
        "stats": diff_stats(files),
        "risk_count": len(risks),
        "high_risk_count": sum(1 for r in risks if r["severity"] == "high"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "head_sha": "9f3c2ab7e1d04c55",
        "pr_url": "",
        "summary": result["summary"],
        "groups": result["groups"],
        "risks": risks,
        "files": [f.to_dict() for f in files],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "error": "",
    }
    OUT.write_text(json.dumps(review, indent=2) + "\n")
    print(f"Wrote {OUT} (model: {result['model']}, {len(result['groups'])} groups, {len(risks)} risks)")
