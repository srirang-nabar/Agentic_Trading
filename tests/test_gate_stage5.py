"""Stage 5 gate (part 3): H2 experiment QC + pre-registered analysis
reproduction. Everything computes from the committed logs in results/ssw_h2
and results/ssw_explore — no API key needed.
"""

import pytest

from agentic_trading.bubbles import h2_summary, ssw_metrics
from agentic_trading.replay import verify_session_log
from agentic_trading.runner import load_config, load_session_logs
from pathlib import Path

pytestmark = pytest.mark.gate_stage5

ROOT = Path(__file__).resolve().parent.parent
H2_DIR = ROOT / "results" / "ssw_h2" / "sessions"
VALIDITY_FLOOR = 0.90


@pytest.fixture(scope="module")
def cells():
    return {
        name: load_session_logs(H2_DIR / f"{name}.jsonl.gz")
        for name in ("ssw_zi_c", "ssw_llm_a", "ssw_llm_b", "ssw_llm_a_exp")
    }


def test_no_discard_audit(cells):
    config = load_config(ROOT / "configs" / "ssw_h2.yaml")
    configured = {c["name"]: c["n_sessions"] for c in config["cells"]}
    assert {name: len(logs) for name, logs in cells.items()} == configured


def test_dividends_schedules_and_polling_matched(cells):
    """A3.iii: matched cells share dividends, endowments, and polling order;
    the experienced cell shares endowments and polling but NOT dividends."""
    for index in range(len(cells["ssw_zi_c"])):
        ref = cells["ssw_zi_c"][index]
        ref_polled = [e["trader_id"] for e in ref["events"] if "trader_id" in e]
        for name in ("ssw_llm_a", "ssw_llm_b", "ssw_llm_a_exp"):
            other = cells[name][index]
            assert other["traders"] == ref["traders"], f"session {index}: endowments differ in {name}"
            polled = [e["trader_id"] for e in other["events"] if "trader_id" in e]
            assert polled == ref_polled, f"session {index}: polling order differs in {name}"
            if name == "ssw_llm_a_exp":
                assert other["ssw"]["dividends"] != ref["ssw"]["dividends"], (
                    f"session {index}: experienced cell reused the dividend path"
                )
            else:
                assert other["ssw"]["dividends"] == ref["ssw"]["dividends"], (
                    f"session {index}: dividends differ in {name}"
                )


def test_order_validity_above_floor_per_cell(cells):
    for name in ("ssw_llm_a", "ssw_llm_b", "ssw_llm_a_exp"):
        rates = [log["meta"]["validity"]["validity_rate"] for log in cells[name]]
        assert sum(rates) / len(rates) >= VALIDITY_FLOOR, f"{name} below validity floor"


def test_experience_meta_recorded(cells):
    for log in cells["ssw_llm_a_exp"]:
        assert log["meta"]["llm"]["experience_from"] == "ssw_llm_a"
        # the transcript is in every trader's system prompt for this cell
        first_system = log["llm_calls"][0]["messages"][0]["content"]
        assert "you already traded one full session" in first_system


def test_every_fifth_session_replays_bit_exactly(cells):
    for logs in cells.values():
        for log in logs[::5]:
            assert verify_session_log(log) == []


def test_h2_analysis_matches_claims(cells):
    from agentic_trading.reproduce import load_claims

    summary = h2_summary(
        {"A": cells["ssw_llm_a"], "B": cells["ssw_llm_b"]},
        experienced_logs=cells["ssw_llm_a_exp"],
        paired_inexperienced_logs=cells["ssw_llm_a"],
    )
    zic_rds = [ssw_metrics(log)["rd"] for log in cells["ssw_zi_c"]]
    claims = {row["claim_id"]: row["value"] for row in load_claims()}
    conj = summary["conjunction_p"]
    exp_p = summary["experience"]["p_wilcoxon"]
    computed = {
        "H2-1": f"{summary['paraphrases']['A']['mean_rd']:.2f}",
        "H2-2": f"{summary['paraphrases']['B']['mean_rd']:.2f}",
        "H2-3": f"{sum(zic_rds) / len(zic_rds):.2f}",
        "H2-4": "<0.001" if conj < 0.001 else f"{conj:.3f}",
        "H2-5": "yes" if summary["h2_supported"] else "no",
        "H2-6": "<0.001" if exp_p < 0.001 else f"{exp_p:.3f}",
        "H2-7": (
            f"{summary['paraphrases']['A']['n_shape_ok']}/30 / "
            f"{summary['paraphrases']['B']['n_shape_ok']}/30"
        ),
        "H2-8": f"{summary['experience']['mean_rd_experienced']:.2f}",
    }
    for claim_id, value in computed.items():
        assert claims.get(claim_id) == value, (
            f"{claim_id}: CLAIMS.md says {claims.get(claim_id)!r}, logs give {value!r}"
        )


def test_exploratory_mixed_cell_recorded():
    explore = ROOT / "results" / "ssw_explore" / "sessions"
    config = load_config(ROOT / "configs" / "ssw_explore.yaml")
    (cell,) = config["cells"]
    logs = load_session_logs(explore / f"{cell['name']}.jsonl.gz")
    assert len(logs) == cell["n_sessions"]
    # 3 LLM traders (one per endowment class) + 3 ZI-C: every LLM call comes
    # from T1-T3 only
    callers = {r["trader_id"] for log in logs for r in log["llm_calls"]}
    assert callers <= {"T1", "T2", "T3"}
