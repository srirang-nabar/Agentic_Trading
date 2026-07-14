"""Stage 1 gate: seeded random-polling runner — determinism and replayability."""

import random

import pytest

from agentic_trading.exchange import Side, TraderConfig
from agentic_trading.replay import session_log_to_json, verify_session_log
from agentic_trading.runner import AgentView, CancelAction, SubmitAction, run_session

pytestmark = pytest.mark.gate_stage1

ROSTER = (
    TraderConfig("B1", cash=80, values=(30, 22)),
    TraderConfig("B2", cash=80, values=(26,)),
    TraderConfig("S1", costs=(4, 9)),
    TraderConfig("S2", costs=(7,)),
)


class SeededRandomAgent:
    """Test-only agent: random but fully determined by its seed and views.

    Deliberately sloppy — it submits unaffordable prices, wrong sides, and
    bogus cancels sometimes, exercising the rejection paths through the
    runner exactly as a misbehaving LLM would in Stage 3.
    """

    def __init__(self, trader_id: str, seed: int):
        self.trader_id = trader_id
        self.rng = random.Random(seed)

    def act(self, view: AgentView):
        roll = self.rng.random()
        if roll < 0.15:
            return None
        if roll < 0.25 and view.open_orders:
            return CancelAction(order_id=self.rng.choice(view.open_orders)[0])
        if roll < 0.30:
            return CancelAction(order_id=self.rng.randrange(50))  # often bogus
        side = self.rng.choice([Side.BUY, Side.SELL])
        return SubmitAction(side=side, price=self.rng.randint(1, 35))


def make_agents(seed_base: int) -> dict[str, SeededRandomAgent]:
    return {
        t.trader_id: SeededRandomAgent(t.trader_id, seed_base + i)
        for i, t in enumerate(ROSTER)
    }


def run(seed_base: int = 7, poll_seed: int = 42) -> dict:
    return run_session(
        ROSTER,
        make_agents(seed_base),
        n_periods=3,
        steps_per_period=40,
        poll_seed=poll_seed,
    )


def test_same_seeds_give_bit_identical_sessions():
    assert session_log_to_json(run()) == session_log_to_json(run())


def test_different_poll_seed_changes_the_session():
    assert session_log_to_json(run(poll_seed=42)) != session_log_to_json(run(poll_seed=43))


def test_runner_session_replays_from_its_log():
    log = run()
    assert verify_session_log(log) == []
    # Replay must not strip provenance: byte-identical including "config".
    from agentic_trading.replay import replay_session_log

    assert session_log_to_json(replay_session_log(log)) == session_log_to_json(log)


def test_session_is_nontrivial_and_logs_all_polls():
    log = run()
    # 3 periods * (open + 40 polls + close) events, every poll logged.
    assert len(log["events"]) == 3 * 42
    statuses = {o["status"] for o in log["outcomes"]}
    assert "traded" in statuses, "random agents should find some trades"
    assert "rejected" in statuses, "sloppy agents should hit rejections"
    assert "passed" in statuses, "polled agents may pass, and passes are logged"
    assert log["config"]["activation"] == "uniform_random_polling"


def test_agents_must_match_roster():
    agents = make_agents(0)
    agents.pop("S2")
    with pytest.raises(ValueError):
        run_session(ROSTER, agents, n_periods=1, steps_per_period=5, poll_seed=1)
