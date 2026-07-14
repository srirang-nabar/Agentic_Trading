"""Stage 3 gate: live smoke-test acceptance + cost accounting.

Runs against the committed artifacts in results/llm_smoke (produced by
`uv run python -m agentic_trading.runner configs/llm_smoke.yaml` against a
live endpoint) — the tests themselves need no API key.
"""

from pathlib import Path

import pytest

from agentic_trading.replay import verify_session_log
from agentic_trading.runner import load_config, load_session_logs

pytestmark = pytest.mark.gate_stage3

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "results" / "llm_smoke"
VALIDITY_FLOOR = 0.90  # pre-registered (HYPOTHESES.md: local-model floor)


@pytest.fixture(scope="module")
def logs():
    return load_session_logs(SMOKE / "sessions" / "qwen_smoke.jsonl.gz")


def test_ten_consecutive_sessions_no_harness_faults(logs):
    config = load_config(ROOT / "configs" / "llm_smoke.yaml")
    assert len(logs) == config["cells"][0]["n_sessions"] == 10  # no-discard audit
    for log in logs:
        # A harness fault would have aborted the run (completeness raises);
        # a session is well-formed iff every poll has records and stats.
        assert log["meta"]["validity"]["n_llm_calls"] == len(log["llm_calls"])
        assert log["meta"]["llm"]["model"] == "Qwen/Qwen2.5-7B-Instruct"
        assert log["meta"]["llm"]["revision"], "model revision must be pinned in config"


def test_order_validity_meets_floor(logs):
    rates = [log["meta"]["validity"]["validity_rate"] for log in logs]
    overall = sum(rates) / len(rates)
    assert overall >= VALIDITY_FLOOR, f"mean order-validity {overall:.3f} below floor"


def test_every_smoke_session_replays_bit_exactly(logs):
    for log in logs:
        assert verify_session_log(log) == []


def test_llm_records_carry_full_capture_fields(logs):
    required = {
        "trader_id", "period", "step", "attempt", "model", "temperature",
        "template", "template_sha256", "messages", "raw_response",
        "prompt_tokens", "completion_tokens", "parsed", "error", "ts",
    }
    for log in logs:
        for record in log["llm_calls"]:
            assert required <= set(record)


def test_sessions_actually_traded(logs):
    assert sum(len(log["trades"]) for log in logs) > 0, "smoke market never traded"


def test_recognition_scan_recorded(logs):
    for log in logs:
        assert "recognition_flags" in log["meta"]


def test_cost_accounting_matches_budget_ledger(logs):
    """Token counts in logs must sum exactly to the budget.md entry."""
    budget = (ROOT / "results" / "budget.md").read_text()
    row = next(line for line in budget.splitlines() if line.startswith("| llm_smoke "))
    cells = [c.strip() for c in row.strip("|").split("|")]
    calls, prompt_tokens, completion_tokens = int(cells[1]), int(cells[2]), int(cells[3])
    assert calls == sum(len(log["llm_calls"]) for log in logs)
    assert prompt_tokens == sum(
        r["prompt_tokens"] for log in logs for r in log["llm_calls"]
    )
    assert completion_tokens == sum(
        r["completion_tokens"] for log in logs for r in log["llm_calls"]
    )


def test_contamination_probe_recorded():
    assert (ROOT / "results" / "contamination_probe.md").is_file()
    assert (ROOT / "results" / "contamination_probe.json").is_file()
