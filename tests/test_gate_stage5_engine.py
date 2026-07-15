"""Stage 5 gate (part 2): carry-over engine semantics + SSW session pipeline.

The SSW institution reuses the Stage 1 matching engine unchanged (plan.md
engine note) — these tests pin the new endowment policy, dividend events,
replay determinism, and the runner/harness integration.
"""

import random

import pytest

from agentic_trading.agents.llm import (
    LLMTrader,
    LLMTraderConfig,
    ScriptedClient,
    SessionRecorder,
    validate_decision,
    parse_decision,
)
from agentic_trading.agents.zi import SSWZITrader, build_ssw_zi_agents
from agentic_trading.bubbles import ssw_metrics
from agentic_trading.exchange import (
    Dividend,
    Exchange,
    PeriodClose,
    PeriodOpen,
    Side,
    Submit,
    TraderConfig,
    event_from_dict,
    event_to_dict,
)
from agentic_trading.experiments.ssw import (
    SSWMarketSpec,
    generate_ssw_market,
    render_experience,
)
from agentic_trading.replay import verify_session_log
from agentic_trading.runner import AgentView, run_ssw_session

pytestmark = pytest.mark.gate_stage5


def carry_exchange():
    return Exchange(
        [
            TraderConfig(trader_id="T1", cash=100, endowed_units=2),
            TraderConfig(trader_id="T2", cash=50, endowed_units=1),
        ],
        carry_over=True,
    )


class TestCarryOverSemantics:
    def test_holdings_persist_across_periods(self):
        ex = carry_exchange()
        ex.apply(PeriodOpen())
        ex.apply(Submit(trader_id="T2", side=Side.SELL, price=30))
        ex.apply(Submit(trader_id="T1", side=Side.BUY, price=30))  # trades at 30
        ex.apply(PeriodClose())
        ex.apply(Dividend(amount=8))
        ex.apply(PeriodOpen())
        t1 = ex.account("T1")
        t2 = ex.account("T2")
        # T1: 100 - 30 + 8*3 = 94 francs, 3 certificates; T2: 50 + 30 + 0
        assert (t1["cash"], t1["inventory"]) == (94, 3)
        assert (t2["cash"], t2["inventory"]) == (80, 0)

    def test_dividend_pays_per_held_unit(self):
        ex = carry_exchange()
        ex.apply(PeriodOpen())
        ex.apply(PeriodClose())
        outcome = ex.apply(Dividend(amount=28))
        assert outcome["status"] == "dividend"
        assert outcome["paid"] == {"T1": 56, "T2": 28}

    def test_dividend_rejected_while_market_open(self):
        ex = carry_exchange()
        ex.apply(PeriodOpen())
        assert ex.apply(Dividend(amount=8))["status"] == "rejected"

    def test_dividend_rejected_in_per_period_institution(self):
        ex = Exchange([TraderConfig(trader_id="B", cash=10, values=(5,))])
        ex.apply(PeriodOpen())
        ex.apply(PeriodClose())
        outcome = ex.apply(Dividend(amount=8))
        assert outcome["reason"] == "no_dividends_in_per_period_institution"

    def test_carry_over_rejects_induced_schedules(self):
        with pytest.raises(ValueError, match="carry-over"):
            Exchange(
                [TraderConfig(trader_id="B", cash=10, values=(5,))], carry_over=True
            )

    def test_sell_requires_held_certificate(self):
        ex = carry_exchange()
        ex.apply(PeriodOpen())
        for _ in range(2):  # T2 sells its single certificate, then tries again
            ex.apply(Submit(trader_id="T2", side=Side.SELL, price=10))
            ex.apply(Submit(trader_id="T1", side=Side.BUY, price=10))
        outcome = ex.outcomes[-2]
        assert outcome == {"status": "rejected", "reason": "insufficient_inventory"}

    def test_buy_unbounded_by_schedule_but_bounded_by_cash(self):
        ex = carry_exchange()
        ex.apply(PeriodOpen())
        assert ex.apply(Submit(trader_id="T1", side=Side.BUY, price=90))["status"] == "resting"
        # second bid exceeds remaining uncommitted cash (100 - 90 = 10)
        assert ex.apply(Submit(trader_id="T1", side=Side.BUY, price=11))["reason"] == "insufficient_cash"

    def test_dividend_event_serialization_round_trip(self):
        event = Dividend(amount=60)
        assert event_from_dict(event_to_dict(event)) == event


def make_view(**kw):
    defaults = dict(
        trader_id="T1", period=3, step=5, best_bid=90, best_ask=110,
        last_trade_price=100, cash_available=200, inventory_available=1,
        remaining_values=(), remaining_costs=(), open_orders=(), n_periods=15,
    )
    defaults.update(kw)
    return AgentView(**defaults)


class TestSSWValidation:
    def test_bid_allowed_without_value_schedule(self):
        decision, _ = parse_decision('{"action": "bid", "price": 100}')
        assert validate_decision(decision, make_view(), max_price=720) is None

    def test_ask_requires_certificate(self):
        decision, _ = parse_decision('{"action": "ask", "price": 100}')
        assert validate_decision(decision, make_view(), max_price=720) is None
        error = validate_decision(
            decision, make_view(inventory_available=0), max_price=720
        )
        assert "certificate" in error

    def test_bid_bounded_by_cash(self):
        decision, _ = parse_decision('{"action": "bid", "price": 500}')
        error = validate_decision(decision, make_view(), max_price=720)
        assert "200 francs" in error


class TestSSWZITrader:
    def test_cancel_then_replace(self):
        agent = SSWZITrader("T1", seed=1, max_price=720)
        action = agent.act(make_view(open_orders=((7, "buy", 50),)))
        assert action.order_id == 7

    def test_bid_within_cash(self):
        agent = SSWZITrader("T1", seed=2, max_price=720)
        for _ in range(200):
            action = agent.act(make_view(cash_available=37, inventory_available=1))
            if action is not None and action.side is Side.BUY:
                assert 1 <= action.price <= 37
            else:
                assert action.side is Side.SELL

    def test_infeasible_side_falls_back(self):
        agent = SSWZITrader("T1", seed=3, max_price=720)
        for _ in range(50):  # no certificates: every quote must be a bid
            action = agent.act(make_view(inventory_available=0))
            assert action.side is Side.BUY
        agent2 = SSWZITrader("T2", seed=4, max_price=720)
        for _ in range(50):  # no cash: every quote must be an ask
            action = agent2.act(make_view(cash_available=0))
            assert action.side is Side.SELL

    def test_both_infeasible_passes(self):
        agent = SSWZITrader("T1", seed=5, max_price=720)
        assert agent.act(make_view(cash_available=0, inventory_available=0)) is None


def run_zi_ssw(seed=11, steps=40, spec=None):
    spec = spec or SSWMarketSpec(n_periods=4)
    market = generate_ssw_market(spec, random.Random(seed))
    agents = build_ssw_zi_agents(
        [tid for tid, _, _ in market.traders],
        max_price=spec.price_high,
        seed_for=lambda tid: hash_seed(seed, tid),
    )
    return market, run_ssw_session(market, agents, steps_per_period=steps, poll_seed=seed)


def hash_seed(seed, tid):
    from agentic_trading.runner import derive_seed

    return derive_seed(seed, "agent", tid)


class TestSSWSessionPipeline:
    def test_conservation_and_log_shape(self):
        market, log = run_zi_ssw()
        spec = market.spec
        assert log["carry_over"] is True
        assert log["ssw"]["shares_outstanding"] == 12
        accounts = log["final"]["accounts"]
        assert sum(a["inventory"] for a in accounts) == 12  # certificates conserved
        initial_cash = sum(cash for _, cash, _ in market.traders)
        dividends_paid = sum(d * 12 for d in market.dividends)
        assert sum(a["cash"] for a in accounts) == initial_cash + dividends_paid

    def test_replay_is_bit_exact_including_dividends(self):
        _, log = run_zi_ssw()
        assert verify_session_log(log) == []

    def test_session_is_deterministic(self):
        _, log_a = run_zi_ssw(seed=17)
        _, log_b = run_zi_ssw(seed=17)
        assert log_a == log_b

    def test_metrics_computable_from_log(self):
        _, log = run_zi_ssw()
        metrics = ssw_metrics(log)
        assert 0 <= metrics["turnover"]
        assert metrics["rad"] >= abs(metrics["rd"])


class TestRunExperimentDispatch:
    CONFIG = {
        "experiment_id": "ssw_dispatch_test",
        "design": "ssw",
        "seed": 99,
        "matched_schedules": True,
        "market": {
            "n_periods": 3,
            "dividend_values": [0, 8, 28, 60],
            "endowment_classes": [[225, 3], [585, 2], [945, 1]],
            "traders_per_class": 2,
            "price_low": 1,
            "price_high": 720,
            "steps_per_period": 24,
        },
        "cells": [
            {"name": "cell_x", "agent_type": "zi_c", "n_sessions": 2},
            {"name": "cell_y", "agent_type": "zi_c", "n_sessions": 2},
        ],
    }

    def test_ssw_experiment_runs_and_matches_dividends(self, tmp_path):
        from agentic_trading.runner import load_session_logs, run_experiment

        summary = run_experiment(self.CONFIG, results_root=tmp_path)
        assert set(summary["cells"]) == {"cell_x", "cell_y"}
        assert "mean_rd" in summary["cells"]["cell_x"]
        logs = {
            name: load_session_logs(
                tmp_path / "ssw_dispatch_test" / "sessions" / f"{name}.jsonl.gz"
            )
            for name in ("cell_x", "cell_y")
        }
        for i in range(2):
            # matched cells share the dividend path AND polling order (A3.iii)
            assert logs["cell_x"][i]["ssw"]["dividends"] == logs["cell_y"][i]["ssw"]["dividends"]
            polled_x = [e["trader_id"] for e in logs["cell_x"][i]["events"] if "trader_id" in e]
            polled_y = [e["trader_id"] for e in logs["cell_y"][i]["events"] if "trader_id" in e]
            assert polled_x == polled_y

    def test_experienced_dividend_path_is_fresh(self):
        """A3.iii: the experienced cell's transcript would leak a reused
        dividend path, so its market seed is tagged."""
        from agentic_trading.runner import derive_seed

        spec = SSWMarketSpec(n_periods=15)
        base = generate_ssw_market(
            spec, random.Random(derive_seed(99, "shared", 0, "market"))
        )
        experienced = generate_ssw_market(
            spec, random.Random(derive_seed(99, "shared", 0, "market", "experienced"))
        )
        assert base.traders == experienced.traders  # endowments deterministic
        assert base.dividends != experienced.dividends


class TestExperienceRendering:
    def test_transcript_is_mechanical_and_complete(self):
        market, log = run_zi_ssw()
        text = render_experience(log, "T1")
        for period in range(1, 5):
            assert f"- Period {period}:" in text
        assert "payout" in text and "You finished that session with" in text

    def test_llm_trader_appends_experience_to_system_prompt(self):
        client = ScriptedClient(['{"action": "pass", "price": null}'])
        config = LLMTraderConfig(
            model="m", template="ssw_a", max_price=720,
            template_vars={"n_periods": 15, "payouts": "0, 8, 28, or 60",
                           "mean_payout": "24"},
        )
        trader = LLMTrader("T1", client, SessionRecorder(), config,
                           experience="PRIOR SESSION MARKER")
        trader.act(make_view())
        system = trader.recorder.records[0]["messages"][0]["content"]
        assert "PRIOR SESSION MARKER" in system
        assert "certificates" in system and "15" in system

    def test_ssw_template_renders_without_missing_keys(self):
        client = ScriptedClient(['{"action": "bid", "price": 90}'])
        config = LLMTraderConfig(
            model="m", template="ssw_b", max_price=720,
            template_vars={"n_periods": 15, "payouts": "0, 8, 28, or 60",
                           "mean_payout": "24"},
        )
        trader = LLMTrader("T1", client, SessionRecorder(), config)
        action = trader.act(make_view())
        assert action.price == 90
        state = trader.recorder.records[0]["messages"][1]["content"]
        assert "period 3 of 15" in state
