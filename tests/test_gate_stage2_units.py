"""Stage 2 gate: unit tests for ZI agents, metrics, and market generation.

Metrics are validated on hand-computed toy schedules and cross-checked
against the engine's independent surplus accounting.
"""

import random

import pytest

from agentic_trading.agents.zi import ZITrader, build_zi_agents
from agentic_trading.exchange import Exchange, PeriodOpen, Side, Submit, TraderConfig
from agentic_trading.experiments.smith import SmithMarketSpec, generate_smith_market
from agentic_trading.metrics import (
    equilibrium,
    rank_biserial,
    rmse,
    session_metrics,
    smith_alpha,
)
from agentic_trading.runner import CancelAction, SubmitAction, run_session

pytestmark = pytest.mark.gate_stage2


class TestEquilibrium:
    def test_hand_computed_toy(self):
        # Demand 20,15,10 vs supply 5,8,18: two units trade (10 < 18);
        # price bounded below by max(8, 10)=10, above by min(15, 18)=15.
        eq = equilibrium([20, 15, 10], [5, 8, 18])
        assert (eq.quantity, eq.price_low, eq.price_high) == (2, 10, 15)
        assert eq.price_mid == 12.5
        assert eq.max_surplus == 22  # (20-5) + (15-8)

    def test_no_trade_market(self):
        eq = equilibrium([5], [10])
        assert eq.quantity == 0 and eq.max_surplus == 0

    def test_tie_collapses_interval(self):
        eq = equilibrium([10, 9], [8, 9])
        assert (eq.quantity, eq.price_low, eq.price_high) == (2, 9, 9)
        assert eq.max_surplus == 2  # (10-8) + (9-9)

    def test_matches_hand_worked_stage1_example(self):
        eq = equilibrium([20, 15], [5])
        assert eq.quantity == 1 and eq.max_surplus == 15
        assert (eq.price_low, eq.price_high) == (15, 20)


class TestPriceMetrics:
    def test_smith_alpha_hand_computed(self):
        # Prices 10 and 15 around p*=12.5: deviations +-2.5, RMSE 2.5,
        # alpha = 100*2.5/12.5 = 20.
        assert rmse([10, 15], 12.5) == 2.5
        assert smith_alpha([10, 15], 12.5) == 20.0

    def test_alpha_zero_at_equilibrium(self):
        assert smith_alpha([12, 12, 12], 12.0) == 0.0

    def test_empty_prices_raise(self):
        with pytest.raises(ValueError):
            smith_alpha([], 10.0)


class TestRankBiserial:
    def test_extremes_and_midpoint(self):
        assert rank_biserial(50 * 50, 50, 50) == 1.0
        assert rank_biserial(0, 50, 50) == -1.0
        assert rank_biserial(50 * 50 / 2, 50, 50) == 0.0


class TestSessionMetricsFromLog:
    def test_cross_checks_engine_surplus_accounting(self):
        roster = [
            TraderConfig("B1", cash=200, values=(20, 18)),
            TraderConfig("B2", cash=200, values=(15,)),
            TraderConfig("S1", costs=(5, 7)),
            TraderConfig("S2", costs=(10,)),
        ]
        exchange = Exchange(roster)
        exchange.apply(PeriodOpen())
        for seller, buyer, price in (("S1", "B1", 11), ("S1", "B1", 12), ("S2", "B2", 13)):
            exchange.apply(Submit(seller, Side.SELL, price))
            exchange.apply(Submit(buyer, Side.BUY, price))
        engine_surplus = exchange.period_realized_surplus()

        metrics = session_metrics(exchange.session_log())
        assert metrics["periods"][0]["realized_surplus"] == engine_surplus == 31
        assert metrics["efficiency"] == 1.0
        assert metrics["equilibrium"]["max_surplus"] == 31

    def test_alpha_none_when_period_has_no_trades(self):
        roster = [TraderConfig("B", cash=50, values=(20,)), TraderConfig("S", costs=(5,))]
        exchange = Exchange(roster)
        exchange.apply(PeriodOpen())
        metrics = session_metrics(exchange.session_log())
        assert metrics["periods"][0]["alpha"] is None
        assert metrics["efficiency"] == 0.0


def buyer_view(values=(30, 20), cash=600, open_orders=()):
    from agentic_trading.runner import AgentView

    return AgentView(
        trader_id="B1", period=1, step=0, best_bid=None, best_ask=None,
        last_trade_price=None, cash_available=cash, inventory_available=0,
        remaining_values=values, remaining_costs=(), open_orders=open_orders,
    )


def seller_view(costs=(40, 90), open_orders=()):
    from agentic_trading.runner import AgentView

    return AgentView(
        trader_id="S1", period=1, step=0, best_bid=None, best_ask=None,
        last_trade_price=None, cash_available=0, inventory_available=len(costs),
        remaining_values=(), remaining_costs=costs, open_orders=open_orders,
    )


class TestZITraders:
    def test_zic_buyer_never_bids_above_next_value(self):
        agent = ZITrader("B1", seed=1, max_price=200, constrained=True)
        for _ in range(300):
            action = agent.act(buyer_view(values=(30, 20)))
            assert isinstance(action, SubmitAction)
            assert action.side is Side.BUY and 1 <= action.price <= 30

    def test_zic_seller_never_asks_below_next_cost(self):
        agent = ZITrader("S1", seed=2, max_price=200, constrained=True)
        for _ in range(300):
            action = agent.act(seller_view(costs=(40, 90)))
            assert isinstance(action, SubmitAction)
            assert action.side is Side.SELL and 40 <= action.price <= 200

    def test_ziu_ignores_value_and_cost(self):
        buyer = ZITrader("B1", seed=3, max_price=200, constrained=False)
        bids = [buyer.act(buyer_view(values=(5,))).price for _ in range(300)]
        assert max(bids) > 5, "ZI-U buyer must sometimes bid above value"
        seller = ZITrader("S1", seed=4, max_price=200, constrained=False)
        asks = [seller.act(seller_view(costs=(150,))).price for _ in range(300)]
        assert min(asks) < 150, "ZI-U seller must sometimes ask below cost"

    def test_cancel_then_replace_protocol(self):
        agent = ZITrader("B1", seed=5, max_price=200, constrained=True)
        action = agent.act(buyer_view(open_orders=((7, "buy", 12),)))
        assert action == CancelAction(order_id=7)

    def test_pass_when_schedule_exhausted(self):
        agent = ZITrader("B1", seed=6, max_price=200, constrained=True)
        assert agent.act(buyer_view(values=())) is None

    def test_same_seed_same_behavior(self):
        actions_a = [
            ZITrader("B1", seed=9, max_price=200, constrained=True).act(buyer_view())
        ]
        actions_b = [
            ZITrader("B1", seed=9, max_price=200, constrained=True).act(buyer_view())
        ]
        assert actions_a == actions_b

    def test_build_rejects_unknown_kind(self):
        with pytest.raises(ValueError):
            build_zi_agents([], kind="zi_x", max_price=200, seed_for=lambda t: 0)


class TestZISessionProperties:
    def run_zi_session(self, kind: str, seed: int = 11):
        rng = random.Random(seed)
        traders, eq = generate_smith_market(rng, SmithMarketSpec())
        agents = build_zi_agents(
            traders, kind=kind, max_price=200, seed_for=lambda tid: hash_free(seed, tid)
        )
        log = run_session(traders, agents, n_periods=2, steps_per_period=120, poll_seed=seed)
        return log, traders

    def test_zic_trades_are_individually_rational(self):
        # ZI-C construction guarantees cost <= price <= value on every trade.
        log, traders = self.run_zi_session("zi_c")
        values = {t.trader_id: t.values for t in traders}
        costs = {t.trader_id: t.costs for t in traders}
        n_bought: dict = {}
        n_sold: dict = {}
        assert log["trades"], "ZI-C session should trade"
        last_period = 0
        for trade in log["trades"]:
            if trade["period"] != last_period:
                n_bought, n_sold, last_period = {}, {}, trade["period"]
            b, s = trade["buyer_id"], trade["seller_id"]
            assert trade["price"] <= values[b][n_bought.get(b, 0)]
            assert trade["price"] >= costs[s][n_sold.get(s, 0)]
            n_bought[b] = n_bought.get(b, 0) + 1
            n_sold[s] = n_sold.get(s, 0) + 1

    def test_ziu_session_runs_and_trades(self):
        log, _ = self.run_zi_session("zi_u")
        assert log["trades"], "ZI-U session should trade"


def hash_free(*parts):
    from agentic_trading.runner import derive_seed

    return derive_seed(*parts)


class TestSmithMarketGenerator:
    def test_deterministic_given_seed(self):
        a = generate_smith_market(random.Random(42), SmithMarketSpec())
        b = generate_smith_market(random.Random(42), SmithMarketSpec())
        assert a == b

    def test_market_shape_and_equilibrium(self):
        traders, eq = generate_smith_market(random.Random(7), SmithMarketSpec())
        buyers = [t for t in traders if t.values]
        sellers = [t for t in traders if t.costs]
        assert len(buyers) == 4 and len(sellers) == 4
        for b in buyers:
            assert b.cash == 600
            assert b.values == tuple(sorted(b.values, reverse=True))
        for s in sellers:
            assert s.costs == tuple(sorted(s.costs))
        assert eq.quantity >= 3
        assert eq.price_low <= eq.price_high
        assert eq.max_surplus > 0
