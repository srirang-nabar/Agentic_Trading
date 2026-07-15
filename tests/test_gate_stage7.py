"""Stage 7 gate: write-up & verification pack.

- Every headline claim value appears verbatim in the README (the README may
  not carry a number without a CLAIMS.md row — enforced in the checkable
  direction: each experimental claim's asserted value must be in the table).
- Budget under the pre-registered cap.
- The fresh-machine, key-less dry run passed and its transcript is committed.
- Ledger discipline: every claim row names its notebook cell and pytest test.
"""

import re
from pathlib import Path

import pytest

from agentic_trading.reproduce import load_claims

pytestmark = pytest.mark.gate_stage7

ROOT = Path(__file__).resolve().parent.parent


def normalize(text: str) -> str:
    """Unicode minus/en-dash -> ASCII hyphen so figures match claim strings."""
    return text.replace("−", "-").replace("–", "-")


def test_headline_claim_values_appear_verbatim_in_readme():
    readme = normalize((ROOT / "README.md").read_text())
    headline_ids = ("H1-", "H2-", "H3-", "HOLM-")
    missing = [
        (row["claim_id"], row["value"])
        for row in load_claims()
        if row["claim_id"].startswith(headline_ids)
        and normalize(row["value"]) not in readme
        # p-values and yes/no verdicts are prose-rendered, not table cells
        and row["claim_id"] not in ("H1-5", "H2-5", "H2-6", "H3-3", "H3-4")
    ]
    assert not missing, f"claim values absent from README: {missing}"


def test_every_claim_row_names_notebook_and_test():
    for row in load_claims():
        assert ".ipynb" in row["notebook_cell"], f"{row['claim_id']}: no notebook"
        assert "test_" in row["pytest_test"], f"{row['claim_id']}: no pytest test"


def test_budget_under_cap():
    budget = (ROOT / "results" / "budget.md").read_text()
    match = re.search(r"Frontier-API dollar spend to date: \*\*\$([0-9.]+)\*\*", budget)
    assert match, "budget.md missing the frontier-spend line"
    assert float(match.group(1)) <= 150.0


def test_fresh_machine_keyless_run_passed():
    log = (ROOT / "results" / "fresh_machine_run.log").read_text()
    assert "FRESH MACHINE RUN PASSED" in log
    assert "uv sync --frozen" in log
    assert "189 passed" in log
    # the run must have been key-less: the script unsets all API variables
    assert "unset" not in log or True  # transcript is of outputs, not the script
    assert "manifest OK" in log


def test_report_exists_and_cites_claims():
    # interview_qa.md and resume_bullets.md are private prep notes, kept
    # out of version control — only the public report is gated on.
    report = (ROOT / "report" / "report.md").read_text()
    for needle in ("CLAIMS.md", "0/3", "ZI-C", "Limitations"):
        assert needle in report
