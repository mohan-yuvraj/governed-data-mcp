"""MCP server over a governed synthetic claims dataset.

Governance is enforced in the tool layer, not left to the model:
- Only metrics listed in data/governed_metrics.yaml can be queried.
- Denied (PII) columns are rejected even if present in the CSV.
- Data-quality checks run before any metric is returned; a failed check
  blocks the answer instead of returning a number from bad data.

Core logic lives in plain functions (list_governed_metrics_impl, etc.) so
the eval harness can call them directly without an MCP transport.
The @mcp.tool wrappers are thin adapters over the same functions.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data" / "claims_daily.csv"
REGISTRY = BASE / "data" / "governed_metrics.yaml"

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("governed-data")
except Exception:  # mcp not installed (e.g. running evals in a bare env)
    mcp = None


def _tool(fn):
    """Register fn as an MCP tool when the SDK is available; else no-op."""
    if mcp is None:
        return fn
    return mcp.tool()(fn)


def _registry() -> dict:
    with open(REGISTRY) as f:
        return yaml.safe_load(f)


def _rows() -> list[dict]:
    with open(DATA, newline="") as f:
        return list(csv.DictReader(f))


def _in_range(row: dict, start: str, end: str) -> bool:
    return start <= row["date"] <= end


# --- core logic (used by both MCP tools and the eval harness) ---


def list_governed_metrics_impl() -> str:
    reg = _registry()
    out = [
        {
            "metric": name,
            "definition": m["definition"],
            "unit": m["unit"],
            "owner": m["owner"],
            "sla_hours": m["sla_hours"],
            "lineage": m["lineage"],
        }
        for name, m in reg["metrics"].items()
    ]
    return json.dumps(out, indent=2)


def check_data_quality_impl() -> str:
    rows = _rows()
    reg = _registry()
    checks: dict[str, object] = {}
    checks["row_count"] = len(rows)
    checks["null_cells"] = sum(1 for r in rows for v in r.values() if v in ("", None))
    keys = [(r["date"], r["market"]) for r in rows]
    checks["duplicate_date_market"] = len(keys) - len(set(keys))
    checks["freshness_latest_date"] = max(r["date"] for r in rows)
    checks["negative_values"] = sum(
        1
        for r in rows
        for col in ("claims_filed", "claims_resolved")
        if int(r[col]) < 0
    )
    passed = (
        checks["null_cells"] == 0
        and checks["duplicate_date_market"] == 0
        and checks["negative_values"] == 0
    )
    checks["passed"] = passed
    checks["sla_freshness_hours"] = reg["sla"]["freshness_hours"]
    return json.dumps(checks, indent=2)


def get_metric_impl(metric: str, market: str = "ALL", start_date: str = "2026-10-26", end_date: str = "2026-11-08") -> str:
    reg = _registry()
    if metric in reg.get("denied_columns", []):
        raise ValueError(f"Column '{metric}' is denied (PII / not governed).")
    if metric not in reg["metrics"]:
        raise ValueError(
            f"Metric '{metric}' is not governed. "
            f"Governed metrics: {sorted(reg['metrics'])}"
        )
    dq = json.loads(check_data_quality_impl())
    if not dq["passed"]:
        raise ValueError(f"Data-quality checks failed, refusing to answer: {dq}")
    rows = [r for r in _rows() if _in_range(r, start_date, end_date)]
    if market != "ALL":
        rows = [r for r in rows if r["market"] == market]
    if not rows:
        raise ValueError("No rows for that market / date range.")
    if metric == "resolution_rate":
        filed = sum(int(r["claims_filed"]) for r in rows)
        resolved = sum(int(r["claims_resolved"]) for r in rows)
        value = round(100 * resolved / filed, 2) if filed else 0.0
    elif metric == "avg_resolution_days":
        filed = sum(int(r["claims_filed"]) for r in rows)
        weighted = sum(int(r["claims_filed"]) * float(r["avg_resolution_days"]) for r in rows)
        value = round(weighted / filed, 2) if filed else 0.0
    else:
        value = sum(int(r[metric]) for r in rows)
    return json.dumps(
        {
            "metric": metric,
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "value": value,
            "unit": reg["metrics"][metric]["unit"],
            "owner": reg["metrics"][metric]["owner"],
        },
        indent=2,
    )


def get_lineage_impl(metric: str) -> str:
    reg = _registry()
    if metric not in reg["metrics"]:
        raise ValueError(f"Metric '{metric}' is not governed.")
    m = reg["metrics"][metric]
    return json.dumps(
        {
            "metric": metric,
            "lineage": m["lineage"],
            "owner": m["owner"],
            "sla_hours": m["sla_hours"],
            "definition": m["definition"],
        },
        indent=2,
    )


def explain_metric_impl(metric: str) -> str:
    reg = _registry()
    if metric not in reg["metrics"]:
        raise ValueError(f"Metric '{metric}' is not governed.")
    return reg["metrics"][metric]["definition"]


# --- MCP tool wrappers ---


@_tool
def list_governed_metrics() -> str:
    """List every governed metric with its definition, owner, SLA and lineage."""
    return list_governed_metrics_impl()


@_tool
def check_data_quality() -> str:
    """Run data-quality checks on the governed dataset (nulls, duplicates, freshness)."""
    return check_data_quality_impl()


@_tool
def get_metric(metric: str, market: str = "ALL", start_date: str = "2026-10-26", end_date: str = "2026-11-08") -> str:
    """Compute a governed metric for a market and date range. Rejects ungoverned metrics."""
    return get_metric_impl(metric, market, start_date, end_date)


@_tool
def get_lineage(metric: str) -> str:
    """Return the lineage, owner and SLA for a governed metric."""
    return get_lineage_impl(metric)


@_tool
def explain_metric(metric: str) -> str:
    """Return the plain-English governed definition of a metric."""
    return explain_metric_impl(metric)


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit("mcp package not installed — run: pip install -e .")
    mcp.run()
