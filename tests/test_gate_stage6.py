"""Stage 6 gate (part 3): H3 experiment QC + pre-registered analysis
reproduction. Computes from committed logs in results/duopoly_h3 and
results/duopoly_explore — no API key needed.
"""

from pathlib import Path

import pytest

from agentic_trading.experiments.duopoly import (
    duopoly_session_metrics,
    h3_summary,
    verify_duopoly_log,
)
from agentic_trading.runner import load_config, load_session_logs

pytestmark = pytest.mark.gate_stage6

ROOT = Path(__file__).resolve().parent.parent
H3_DIR = ROOT / "results" / "duopoly_h3" / "sessions"
VALIDITY_FLOOR = 0.90


@pytest.fixture(scope="module")
def cells():
    return {
        name: load_session_logs(H3_DIR / f"{name}.jsonl.gz")
        for name in ("duo_llm_a", "duo_llm_b")
    }


def test_no_discard_audit(cells):
    config = load_config(ROOT / "configs" / "duopoly_h3.yaml")
    configured = {c["name"]: c["n_sessions"] for c in config["cells"]}
    assert {name: len(logs) for name, logs in cells.items()} == configured


def test_flow_seeds_matched_across_cells(cells):
    """A6.iii: the noise-flow seed is shared at each session index."""
    for index in range(len(cells["duo_llm_a"])):
        assert (
            cells["duo_llm_a"][index]["config"]["flow_seed"]
            == cells["duo_llm_b"][index]["config"]["flow_seed"]
        )


def test_probes_forced_in_every_session(cells):
    for logs in cells.values():
        for log in logs:
            by_round = {r["round"]: r for r in log["rounds"]}
            for probe in log["spec"]["probe_rounds"]:
                r = by_round[probe]
                assert r["forced_probe"] is True
                assert r["spreads"][0] == log["config"]["nash_half_spread"]


def test_order_validity_above_floor_per_cell(cells):
    for name, logs in cells.items():
        rates = [log["meta"]["validity"]["validity_rate"] for log in logs]
        assert sum(rates) / len(rates) >= VALIDITY_FLOOR, f"{name} below floor"


def test_coordination_scan_recorded(cells):
    for logs in cells.values():
        for log in logs:
            assert "coordination_flags" in log["meta"]


def test_every_fifth_session_replays_bit_exactly(cells):
    for logs in cells.values():
        for log in logs[::5]:
            assert verify_duopoly_log(log) == []


def test_h3_analysis_matches_claims(cells):
    from agentic_trading.reproduce import load_claims

    summary = h3_summary({"A": cells["duo_llm_a"], "B": cells["duo_llm_b"]})
    claims = {row["claim_id"]: row["value"] for row in load_claims()}
    a = summary["paraphrases"]["A"]
    b = summary["paraphrases"]["B"]
    conj = summary["conjunction_p"]

    h1_p, h2_p = 0.998, 1.000  # CLAIMS H1-4 / H2-4
    family = sorted([h1_p, h2_p, conj])
    adjusted, running = [], 0.0
    for rank, p in enumerate(family):
        running = max(running, min(1.0, (3 - rank) * p))
        adjusted.append(running)
    n_supported = sum(1 for p in adjusted if p < 0.05)

    mixed = load_session_logs(
        ROOT / "results" / "duopoly_explore" / "sessions" / "duo_mixed.jsonl.gz"
    )
    mixed_markup = sum(duopoly_session_metrics(log)["markup"] for log in mixed) / len(mixed)
    computed = {
        "H3-1": f"{a['mean_markup']:+.2f}",
        "H3-2": f"{b['mean_markup']:+.2f}",
        "H3-3": "<0.001" if conj < 0.001 else f"{conj:.3f}",
        "H3-4": "yes" if summary["h3_supported"] else "no",
        "H3-5": f"{a['mean_probe_response']:+.2f} / {b['mean_probe_response']:+.2f}",
        "H3-6": f"{mixed_markup:+.2f}",
        "HOLM-1": f"{n_supported}/3",
    }
    for claim_id, value in computed.items():
        assert claims.get(claim_id) == value, (
            f"{claim_id}: CLAIMS.md says {claims.get(claim_id)!r}, logs give {value!r}"
        )


def test_exploratory_cells_recorded():
    explore = ROOT / "results" / "duopoly_explore" / "sessions"
    config = load_config(ROOT / "configs" / "duopoly_explore.yaml")
    for cell in config["cells"]:
        logs = load_session_logs(explore / f"{cell['name']}.jsonl.gz")
        assert len(logs) == cell["n_sessions"]
    mixed = load_session_logs(explore / "duo_mixed.jsonl.gz")
    for log in mixed:  # MM1 is the myopic BR agent: no LLM calls from it
        callers = {r["trader_id"] for r in log["llm_calls"]}
        assert callers == {"MM0"}
