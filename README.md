# governed-data-mcp

A small MCP server over a **governed, synthetic** claims dataset, plus an LLM eval
harness that scores answers against the governed metric definitions.

Built to close three gaps from my job-search gaps analysis (Nov 9, 2026):
- **No hands-on AI-agent stack** — MCP, tool calling, evals.
- **No developer-platform / API ownership** — a server other agents/clients build against.
- **No GitHub profile / public proof of building** — this repo is the proof.

The dataset is **synthetic** (fictional claim volumes by market/day). It mirrors the
shape of the Walmart Claim Service SSOT work — one governed source of truth,
lineage, SLAs, data-quality checks — without any real company data.

## What the server exposes

| Tool | What it does | Governance rule |
|---|---|---|
| `list_governed_metrics` | Lists approved metrics + owners + SLAs | Only metrics in `data/governed_metrics.yaml` exist |
| `get_metric` | Computes a metric for a grain + date range | Rejects ungoverned metrics/columns; date range validated |
| `check_data_quality` | Runs DQ checks (nulls, duplicates, freshness) | Fails closed: any check failing blocks the metric |
| `get_lineage` | Returns source → transform → metric lineage | Every metric must have an owner and an SLA |
| `explain_metric` | Plain-English definition of a metric | Definitions come from the governed registry, not the model |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Run the MCP server (stdio transport, for Claude Desktop / any MCP client)
python -m governed_data_mcp.server
# Run the eval harness (no MCP client needed — calls the tools directly)
python evals/run_evals.py
# Run the governance tests
pytest -q
```

## Eval harness

`evals/golden_questions.json` holds 8 questions with expected answers computed
from the governed definitions. `evals/run_evals.py` answers each one by calling
the same tool functions the MCP server exposes, scores exact-match on numbers
and keyword-match on explanations, and writes `evals/results.json`.

Run it and check the score before claiming the artefact works — the harness is
the point, not the server alone. Verified Nov 9, 2026: **8/8 golden questions
pass (100%)** — see `evals/results.json`.

## Repo map

```
src/governed_data_mcp/server.py   # MCP tools + governance guardrails
data/claims_daily.csv             # synthetic governed dataset
data/governed_metrics.yaml        # metric registry: definitions, owners, SLAs, lineage
evals/golden_questions.json       # scored Q&A pairs
evals/run_evals.py                # harness: answers, scores, writes results.json
tests/test_governance.py          # guardrail tests (ungoverned metric, PII, DQ)
```

## Roadmap (next steps after first push)

1. Add a second dataset (forecast reporting: 15 days → 3 days story, synthetic).
2. Add an agent trace: log tool calls + eval scores per model version.
3. Add a `semantic layer` view: one metric, many grains, one definition.
4. Publish eval results in this README after each change.
