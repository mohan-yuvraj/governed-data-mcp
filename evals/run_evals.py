"""Eval harness: answer golden questions via the same tool functions the
MCP server exposes, score them, write evals/results.json.

Scoring: numeric answers within tolerance (default exact), keyword answers
must contain every expected keyword (case-insensitive), boolean/value_field
answers compare the named field. A question that raises (e.g. ungoverned
metric) scores 0 — the harness never crashes on a bad answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from governed_data_mcp.server import (  # noqa: E402
    check_data_quality_impl,
    explain_metric_impl,
    get_lineage_impl,
    get_metric_impl,
)

TOOLS = {
    "get_metric": get_metric_impl,
    "explain_metric": explain_metric_impl,
    "get_lineage": get_lineage_impl,
    "check_data_quality": check_data_quality_impl,
}


def score(item: dict, raw: str) -> tuple[bool, str]:
    data = json.loads(raw) if raw.strip().startswith("{") else raw
    if "expected_keywords" in item:
        text = raw.lower()
        missing = [k for k in item["expected_keywords"] if k.lower() not in text]
        return (not missing, f"missing keywords: {missing}" if missing else "all keywords present")
    if "value_field" in item:
        got = data[item["value_field"]] if isinstance(data, dict) else None
        return (got == item["expected_value"], f"got {got}, expected {item['expected_value']}")
    got = data["value"] if isinstance(data, dict) else data
    tol = item.get("tolerance", 0)
    ok = abs(float(got) - float(item["expected_value"])) <= tol
    return (ok, f"got {got}, expected {item['expected_value']} (tol {tol})")


def main() -> int:
    with open(BASE / "evals" / "golden_questions.json") as f:
        questions = json.load(f)
    results = []
    for item in questions:
        try:
            raw = TOOLS[item["tool"]](**item["args"])
            passed, detail = score(item, raw)
        except Exception as exc:  # noqa: BLE001 - a failed tool call is a failed eval
            passed, detail, raw = False, f"raised: {exc}", ""
        results.append({"id": item["id"], "question": item["question"], "passed": passed, "detail": detail})
        print(f"{'PASS' if passed else 'FAIL'}  {item['id']}: {detail}")
    passed_n = sum(r["passed"] for r in results)
    summary = {
        "total": len(results),
        "passed": passed_n,
        "score_pct": round(100 * passed_n / len(results), 1) if results else 0,
        "results": results,
    }
    with open(BASE / "evals" / "results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n{passed_n}/{len(results)} passed ({summary['score_pct']}%) -> evals/results.json")
    return 0 if passed_n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
