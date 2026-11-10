"""Guardrail tests: the server must fail closed, not guess."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from governed_data_mcp.server import (  # noqa: E402
    check_data_quality_impl,
    get_metric_impl,
)


def test_ungoverned_metric_rejected():
    with pytest.raises(ValueError, match="not governed"):
        get_metric_impl("revenue")


def test_denied_pii_column_rejected():
    with pytest.raises(ValueError, match="denied"):
        get_metric_impl("claimant_name")


def test_data_quality_passes_on_synthetic_data():
    dq = json.loads(check_data_quality_impl())
    assert dq["passed"] is True
    assert dq["null_cells"] == 0
    assert dq["duplicate_date_market"] == 0


def test_metric_sums_are_deterministic():
    us_filed = json.loads(
        get_metric_impl("claims_filed", market="US", start_date="2026-10-26", end_date="2026-11-08")
    )
    assert us_filed["value"] == 6074
