"""Stage 4 gate: H1 experiment QC + pre-registered analysis reproduction.

Everything computes from the committed logs in results/smith_h1 (and the
exploratory logs in results/smith_explore) — no API key needed.
"""

import math
from pathlib import Path

import pytest

from agentic_trading.metrics import early_alpha_from_log, h1_summary, session_metrics
from agentic_trading.replay import verify_session_log
from agentic_trading.runner import load_config, load_session_logs

pytestmark = pytest.mark.gate_stage4

ROOT = Path(__file__).resolve().parent.parent
H1_DIR = ROOT / "results" / "smith_h1" / "sessions"
VALIDITY_FLOOR = 0.90  # pre-registered local-model floor (HYPOTHESES.md)


# ---- unit tests (no experiment data needed) ----


class TestEarlyAlphaUnit:
    TOY = {
        "traders": [
            {"trader_id": "B", "cash": 100, "values": [20, 15], "costs": []},
            {"trader_id": "S", "cash": 0, "values": [], "costs": [5, 8]},
        ],
        # equilibrium of values [20,15] / costs [5,8]: q*=2, band [8,15], mid 11.5
        "trades": [
            {"period": 1, "price": 10, "buyer_id": "B", "seller_id": "S"},
            {"period": 2, "price": 13, "buyer_id": "B", "seller_id": "S"},
            {"period": 3, "price": 999, "buyer_id": "B", "seller_id": "S"},
        ],
    }

    def test_pools_periods_one_and_two_only(self):
        # deviations from 11.5: -1.5 and +1.5 -> rmse 1.5, alpha = 100*1.5/11.5
        alpha = early_alpha_from_log(self.TOY)
        assert alpha == pytest.approx(100 * 1.5 / 11.5)

    def test_no_early_trades_is_positive_infinity(self):
        log = dict(self.TOY, trades=[{"period": 3, "price": 10, "buyer_id": "B", "seller_id": "S"}])
        assert early_alpha_from_log(log) == math.inf

    def test_persona_and_memory_config_validated(self):
        from agentic_trading.agents.llm import LLMTraderConfig

        with pytest.raises(ValueError, match="persona"):
            LLMTraderConfig(model="m", template="smith_a", persona="bold")
        with pytest.raises(ValueError, match="memory"):
            LLMTraderConfig(model="m", template="smith_a", memory="everything")


# ---- experiment QC (committed logs) ----


@pytest.fixture(scope="module")
def cells():
    return {
        name: load_session_logs(H1_DIR / f"{name}.jsonl.gz")
        for name in ("zi_c", "llm_local_a", "llm_local_b")
    }


def test_no_discard_audit(cells):
    config = load_config(ROOT / "configs" / "smith_h1.yaml")
    configured = {c["name"]: c["n_sessions"] for c in config["cells"]}
    assert {name: len(logs) for name, logs in cells.items()} == configured


def test_schedules_and_polling_matched_across_cells(cells):
    """Pre-registered matched design: identical markets AND polling order."""
    for index in range(len(cells["zi_c"])):
        reference = cells["zi_c"][index]
        ref_polled = [e["trader_id"] for e in reference["events"]
                      if e["type"] in ("submit", "cancel", "pass")]
        for name in ("llm_local_a", "llm_local_b"):
            other = cells[name][index]
            assert other["traders"] == reference["traders"], (
                f"session {index}: schedules differ in {name}"
            )
            polled = [e["trader_id"] for e in other["events"]
                      if e["type"] in ("submit", "cancel", "pass")]
            assert polled == ref_polled, f"session {index}: polling order differs in {name}"


def test_order_validity_above_floor_per_cell(cells):
    for name in ("llm_local_a", "llm_local_b"):
        rates = [log["meta"]["validity"]["validity_rate"] for log in cells[name]]
        mean_rate = sum(rates) / len(rates)
        assert mean_rate >= VALIDITY_FLOOR, f"{name}: validity {mean_rate:.3f} below floor"


def test_every_fifth_session_replays_bit_exactly(cells):
    for logs in cells.values():
        for log in logs[::5]:
            assert verify_session_log(log) == []


def test_h1_analysis_matches_claims(cells):
    from agentic_trading.reproduce import load_claims

    summary = h1_summary(
        cells["zi_c"],
        {"A": cells["llm_local_a"], "B": cells["llm_local_b"]},
    )
    claims = {row["claim_id"]: row["value"] for row in load_claims()}

    zic_alpha = summary["zi_c"]["mean_early_alpha"]
    a = summary["paraphrases"]["A"]
    b = summary["paraphrases"]["B"]
    computed = {
        "H1-1": f"{a['mean_early_alpha']:.1f}" if a["mean_early_alpha"] else "n/a",
        "H1-2": f"{b['mean_early_alpha']:.1f}" if b["mean_early_alpha"] else "n/a",
        "H1-3": f"{zic_alpha:.1f}",
        "H1-4": (
            "<0.001" if summary["conjunction_p"] < 0.001
            else f"{summary['conjunction_p']:.3f}"
        ),
        "H1-5": (
            "yes" if a["efficiency_non_inferior"] and b["efficiency_non_inferior"]
            else "no"
        ),
    }
    for claim_id, value in computed.items():
        assert claims.get(claim_id) == value, (
            f"{claim_id}: CLAIMS.md says {claims.get(claim_id)!r}, logs give {value!r}"
        )


def test_exploratory_cells_recorded():
    explore = ROOT / "results" / "smith_explore" / "sessions"
    config = load_config(ROOT / "configs" / "smith_explore.yaml")
    for cell in config["cells"]:
        logs = load_session_logs(explore / f"{cell['name']}.jsonl.gz")
        assert len(logs) == cell["n_sessions"]
        assert logs[0]["meta"]["llm"]["persona"] == cell["llm"].get("persona", "neutral")
        assert logs[0]["meta"]["llm"]["memory"] == cell["llm"].get("memory", "none")
