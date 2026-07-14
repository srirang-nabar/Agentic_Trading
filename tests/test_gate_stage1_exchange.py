"""Stage 1 gate: exchange engine unit tests, including the hand-worked example.

Run with: uv run pytest -m gate_stage1
"""

import pytest

from agentic_trading.exchange import (
    Cancel,
    Exchange,
    Pass,
    PeriodClose,
    PeriodOpen,
    Side,
    Submit,
    TraderConfig,
    max_total_surplus,
)

pytestmark = pytest.mark.gate_stage1


def make_exchange(*traders: TraderConfig, open_period: bool = True) -> Exchange:
    exchange = Exchange(traders)
    if open_period:
        assert exchange.apply(PeriodOpen())["status"] == "period_open"
    return exchange


B1 = TraderConfig("B1", cash=100, values=(20,))
B2 = TraderConfig("B2", cash=100, values=(15,))
S1 = TraderConfig("S1", costs=(5,))


class TestHandWorkedExample:
    """3-trader session computed on paper; opens notebooks/01 in Stage 2.

    B1 values one unit at 20, B2 at 15; S1 can sell one unit at cost 5.
    S1 asks 12; B2 bids 10 (rests below the ask); B1 bids 12, which crosses
    and trades at the resting ask price 12. Surplus: B1 gets 20-12=8,
    S1 gets 12-5=7, total 15 — exactly the maximum (20-5), so efficiency 1.
    """

    def run_session(self) -> tuple[Exchange, list]:
        exchange = make_exchange(B1, B2, S1)
        outcomes = [
            exchange.apply(Submit("S1", Side.SELL, 12)),
            exchange.apply(Submit("B2", Side.BUY, 10)),
            exchange.apply(Submit("B1", Side.BUY, 12)),
        ]
        return exchange, outcomes

    def test_order_flow(self):
        exchange, (ask, low_bid, crossing_bid) = self.run_session()
        assert ask == {"status": "resting", "order_id": 0}
        assert low_bid == {"status": "resting", "order_id": 1}
        assert crossing_bid["status"] == "traded"
        assert crossing_bid["order_id"] == 2
        assert crossing_bid["trade"] == {
            "trade_id": 0,
            "period": 1,
            "price": 12,  # the resting ask's price
            "buyer_id": "B1",
            "seller_id": "S1",
            "buy_order_id": 2,
            "sell_order_id": 0,
        }

    def test_accounts_after_trade(self):
        exchange, _ = self.run_session()
        b1 = exchange.account("B1")
        assert (b1["cash"], b1["inventory"], b1["n_bought"]) == (88, 1, 1)
        assert b1["period_surplus"] == 8
        s1 = exchange.account("S1")
        assert (s1["cash"], s1["inventory"], s1["n_sold"]) == (12, 0, 1)
        assert s1["period_surplus"] == 7
        b2 = exchange.account("B2")
        assert (b2["committed_cash"], b2["n_open_bids"]) == (10, 1)

    def test_surplus_is_maximal(self):
        exchange, _ = self.run_session()
        assert exchange.period_realized_surplus() == 15
        assert max_total_surplus([B1, B2, S1]) == 15

    def test_close_voids_remaining_bid(self):
        exchange, _ = self.run_session()
        close = exchange.apply(PeriodClose())
        assert close == {"status": "period_close", "period": 1, "voided": [1]}
        b2 = exchange.account("B2")
        assert (b2["committed_cash"], b2["n_open_bids"]) == (0, 0)
        assert exchange.book_snapshot() == []


class TestPriority:
    def test_time_priority_among_equal_asks(self):
        exchange = make_exchange(
            TraderConfig("S1", costs=(5,)),
            TraderConfig("S2", costs=(5,)),
            TraderConfig("B", cash=100, values=(30,)),
        )
        exchange.apply(Submit("S1", Side.SELL, 15))  # order 0, first at 15
        exchange.apply(Submit("S2", Side.SELL, 15))  # order 1, second at 15
        outcome = exchange.apply(Submit("B", Side.BUY, 20))
        assert outcome["trade"]["seller_id"] == "S1"
        assert outcome["trade"]["sell_order_id"] == 0

    def test_price_priority_beats_time_on_asks(self):
        exchange = make_exchange(
            TraderConfig("S1", costs=(5,)),
            TraderConfig("S2", costs=(5,)),
            TraderConfig("B", cash=100, values=(30,)),
        )
        exchange.apply(Submit("S1", Side.SELL, 15))
        exchange.apply(Submit("S2", Side.SELL, 14))  # later but better
        outcome = exchange.apply(Submit("B", Side.BUY, 20))
        assert outcome["trade"]["seller_id"] == "S2"
        assert outcome["trade"]["price"] == 14

    def test_time_priority_among_equal_bids(self):
        exchange = make_exchange(
            TraderConfig("B1", cash=100, values=(30,)),
            TraderConfig("B2", cash=100, values=(30,)),
            TraderConfig("S", costs=(2,)),
        )
        exchange.apply(Submit("B1", Side.BUY, 10))  # order 0
        exchange.apply(Submit("B2", Side.BUY, 10))  # order 1
        outcome = exchange.apply(Submit("S", Side.SELL, 5))
        assert outcome["trade"]["buyer_id"] == "B1"
        assert outcome["trade"]["buy_order_id"] == 0

    def test_price_priority_beats_time_on_bids(self):
        exchange = make_exchange(
            TraderConfig("B1", cash=100, values=(30,)),
            TraderConfig("B2", cash=100, values=(30,)),
            TraderConfig("S", costs=(2,)),
        )
        exchange.apply(Submit("B1", Side.BUY, 10))
        exchange.apply(Submit("B2", Side.BUY, 11))  # later but better
        outcome = exchange.apply(Submit("S", Side.SELL, 5))
        assert outcome["trade"]["buyer_id"] == "B2"
        assert outcome["trade"]["price"] == 11


class TestCrossing:
    def test_marketable_bid_executes_at_resting_ask_price(self):
        exchange = make_exchange(S1, B1)
        exchange.apply(Submit("S1", Side.SELL, 12))
        outcome = exchange.apply(Submit("B1", Side.BUY, 18))
        assert outcome["trade"]["price"] == 12

    def test_marketable_ask_executes_at_resting_bid_price(self):
        exchange = make_exchange(S1, B1)
        exchange.apply(Submit("B1", Side.BUY, 18))
        outcome = exchange.apply(Submit("S1", Side.SELL, 9))
        assert outcome["trade"]["price"] == 18

    def test_non_crossing_orders_rest(self):
        exchange = make_exchange(S1, B1)
        exchange.apply(Submit("S1", Side.SELL, 15))
        outcome = exchange.apply(Submit("B1", Side.BUY, 14))
        assert outcome["status"] == "resting"
        assert len(exchange.book_snapshot()) == 2

    def test_self_trade_rejected(self):
        both = TraderConfig("M", cash=100, values=(30,), costs=(5,))
        exchange = make_exchange(both)
        exchange.apply(Submit("M", Side.SELL, 10))
        before = exchange.state_snapshot()
        outcome = exchange.apply(Submit("M", Side.BUY, 12))
        assert outcome == {"status": "rejected", "reason": "self_trade"}
        assert exchange.state_snapshot() == before

    def test_self_trade_policy_holds_even_with_another_seller_behind(self):
        # Documented policy: if the BEST match is your own order, the whole
        # incoming order is rejected — matching the later same-priced rival
        # instead would violate price-time priority. Cancel first, then bid.
        both = TraderConfig("M", cash=100, values=(30,), costs=(5,))
        rival = TraderConfig("S2", costs=(5,))
        exchange = make_exchange(both, rival, B1)
        exchange.apply(Submit("M", Side.SELL, 10))  # own ask, time priority
        exchange.apply(Submit("S2", Side.SELL, 10))  # rival behind at 10
        assert exchange.apply(Submit("M", Side.BUY, 12))["reason"] == "self_trade"
        # A different buyer still matches M's ask first (time priority).
        outcome = exchange.apply(Submit("B1", Side.BUY, 12))
        assert outcome["trade"]["seller_id"] == "M"


class TestBudgetAndSchedule:
    def test_bid_over_cash_rejected(self):
        exchange = make_exchange(TraderConfig("B", cash=10, values=(30,)), S1)
        assert exchange.apply(Submit("B", Side.BUY, 11))["reason"] == "insufficient_cash"

    def test_marketable_bid_needs_only_the_execution_price(self):
        # Regression (critic pass): cash 5 cannot back a resting limit of 6,
        # but CAN afford the resting ask at 3 — the trade must go through.
        exchange = make_exchange(TraderConfig("B", cash=5, values=(30,)), S1)
        exchange.apply(Submit("S1", Side.SELL, 3))
        outcome = exchange.apply(Submit("B", Side.BUY, 6))
        assert outcome["status"] == "traded"
        assert outcome["trade"]["price"] == 3
        assert exchange.account("B")["cash"] == 2

    def test_resting_bid_still_needs_its_full_limit_backed(self):
        exchange = make_exchange(TraderConfig("B", cash=5, values=(30,)), S1)
        exchange.apply(Submit("S1", Side.SELL, 9))  # not marketable vs 6
        assert exchange.apply(Submit("B", Side.BUY, 6))["reason"] == "insufficient_cash"

    def test_committed_cash_blocks_second_bid(self):
        exchange = make_exchange(TraderConfig("B", cash=20, values=(30, 30)), S1)
        assert exchange.apply(Submit("B", Side.BUY, 15))["status"] == "resting"
        assert exchange.apply(Submit("B", Side.BUY, 6))["reason"] == "insufficient_cash"
        assert exchange.apply(Submit("B", Side.BUY, 5))["status"] == "resting"

    def test_value_schedule_caps_bids(self):
        exchange = make_exchange(TraderConfig("B", cash=100, values=(30,)), S1)
        exchange.apply(Submit("B", Side.BUY, 5))
        assert exchange.apply(Submit("B", Side.BUY, 6))["reason"] == "schedule_exhausted"

    def test_cost_schedule_caps_asks(self):
        exchange = make_exchange(TraderConfig("S", costs=(5,)), B1)
        exchange.apply(Submit("S", Side.SELL, 9))
        assert exchange.apply(Submit("S", Side.SELL, 8))["reason"] == "schedule_exhausted"

    def test_buyer_cannot_sell_bought_units(self):
        exchange = make_exchange(B1, S1)
        exchange.apply(Submit("S1", Side.SELL, 10))
        exchange.apply(Submit("B1", Side.BUY, 10))
        assert exchange.account("B1")["inventory"] == 1
        assert exchange.apply(Submit("B1", Side.SELL, 12))["reason"] == "schedule_exhausted"

    def test_invalid_prices_rejected(self):
        exchange = make_exchange(B1, S1)
        for price in (0, -3, True, "10", 2.5):
            outcome = exchange.apply(Submit("B1", Side.BUY, price))
            assert outcome == {"status": "rejected", "reason": "invalid_price"}

    def test_unknown_trader_rejected(self):
        exchange = make_exchange(B1)
        assert exchange.apply(Submit("X", Side.BUY, 5))["reason"] == "unknown_trader"
        assert exchange.apply(Pass("X"))["reason"] == "unknown_trader"

    def test_loss_making_trade_is_legal(self):
        # ZI-U territory: price above the buyer's value is a bad trade, not
        # an infeasible one — surplus goes negative, budget stays intact.
        exchange = make_exchange(TraderConfig("B", cash=100, values=(10,)), S1)
        exchange.apply(Submit("S1", Side.SELL, 60))
        outcome = exchange.apply(Submit("B", Side.BUY, 60))
        assert outcome["status"] == "traded"
        assert exchange.account("B")["period_surplus"] == -50


class TestCancel:
    def test_cancel_releases_commitment(self):
        exchange = make_exchange(TraderConfig("B", cash=20, values=(30,)), S1)
        order_id = exchange.apply(Submit("B", Side.BUY, 20))["order_id"]
        assert exchange.apply(Cancel("B", order_id)) == {
            "status": "cancelled",
            "order_id": order_id,
        }
        assert exchange.account("B")["committed_cash"] == 0
        assert exchange.apply(Submit("B", Side.BUY, 20))["status"] == "resting"

    def test_cancel_not_owner(self):
        exchange = make_exchange(B1, B2)
        order_id = exchange.apply(Submit("B1", Side.BUY, 5))["order_id"]
        assert exchange.apply(Cancel("B2", order_id))["reason"] == "not_owner"

    def test_cancel_unknown_and_filled_orders(self):
        exchange = make_exchange(B1, S1)
        assert exchange.apply(Cancel("B1", 99))["reason"] == "unknown_order"
        ask_id = exchange.apply(Submit("S1", Side.SELL, 10))["order_id"]
        exchange.apply(Submit("B1", Side.BUY, 10))
        assert exchange.apply(Cancel("S1", ask_id))["reason"] == "unknown_order"

    def test_cancelled_order_cannot_trade(self):
        exchange = make_exchange(B1, S1)
        ask_id = exchange.apply(Submit("S1", Side.SELL, 10))["order_id"]
        exchange.apply(Cancel("S1", ask_id))
        assert exchange.apply(Submit("B1", Side.BUY, 15))["status"] == "resting"


class TestPeriods:
    def test_submit_outside_period_rejected(self):
        exchange = make_exchange(B1, S1, open_period=False)
        assert exchange.apply(Submit("B1", Side.BUY, 5))["reason"] == "market_closed"
        exchange.apply(PeriodOpen())
        exchange.apply(PeriodClose())
        assert exchange.apply(Submit("B1", Side.BUY, 5))["reason"] == "market_closed"

    def test_double_open_and_close_rejected(self):
        exchange = make_exchange(B1, open_period=False)
        assert exchange.apply(PeriodClose())["reason"] == "market_closed"
        exchange.apply(PeriodOpen())
        assert exchange.apply(PeriodOpen())["reason"] == "period_already_open"

    def test_reopen_re_endows_and_keeps_totals(self):
        exchange = make_exchange(B1, S1)
        exchange.apply(Submit("S1", Side.SELL, 10))
        exchange.apply(Submit("B1", Side.BUY, 10))
        exchange.apply(PeriodClose())
        assert exchange.apply(PeriodOpen())["period"] == 2

        b1 = exchange.account("B1")
        assert (b1["cash"], b1["inventory"], b1["n_bought"]) == (100, 0, 0)
        assert b1["period_surplus"] == 0
        assert b1["total_surplus"] == 10  # 20 - 10, carried across periods
        s1 = exchange.account("S1")
        assert (s1["cash"], s1["inventory"], s1["n_sold"]) == (0, 1, 0)
        assert len(exchange.trades) == 1  # trade history persists


class TestForcedEfficientAllocation:
    def test_realized_surplus_equals_theoretical_max(self):
        roster = [
            TraderConfig("B1", cash=200, values=(20, 18)),
            TraderConfig("B2", cash=200, values=(15,)),
            TraderConfig("S1", costs=(5, 7)),
            TraderConfig("S2", costs=(10,)),
        ]
        assert max_total_surplus(roster) == 31  # (20-5) + (18-7) + (15-10)

        exchange = make_exchange(*roster)
        for seller, buyer, price in (("S1", "B1", 11), ("S1", "B1", 12), ("S2", "B2", 13)):
            exchange.apply(Submit(seller, Side.SELL, price))
            outcome = exchange.apply(Submit(buyer, Side.BUY, price))
            assert outcome["status"] == "traded"
        assert exchange.period_realized_surplus() == 31

    def test_max_surplus_excludes_unprofitable_pairs(self):
        roster = [
            TraderConfig("B", cash=10, values=(10, 4)),
            TraderConfig("S", costs=(5, 6)),
        ]
        assert max_total_surplus(roster) == 5  # only 10-5; 4 < 6 never trades
