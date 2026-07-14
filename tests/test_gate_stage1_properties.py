"""Stage 1 gate: property tests — invariants, conservation, replay determinism.

The engine must hold its invariants under *arbitrary* event streams, not just
well-behaved ones, and every session must replay bit-exactly from its log.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agentic_trading.exchange import (
    Cancel,
    Exchange,
    Pass,
    PeriodClose,
    PeriodOpen,
    Side,
    Submit,
    TraderConfig,
    event_from_dict,
    event_to_dict,
    max_total_surplus,
)
from agentic_trading.replay import (
    session_log_from_json,
    session_log_to_json,
    verify_session_log,
)

pytestmark = pytest.mark.gate_stage1

ROSTER = (
    TraderConfig("B1", cash=60, values=(30, 25)),
    TraderConfig("B2", cash=50, values=(28,)),
    TraderConfig("S1", costs=(5, 10)),
    TraderConfig("S2", costs=(8,)),
    TraderConfig("M1", cash=40, values=(20,), costs=(12,)),
)
TRADER_IDS = sorted(t.trader_id for t in ROSTER)

trader_ids = st.sampled_from(TRADER_IDS)
sides = st.sampled_from([Side.BUY, Side.SELL])

submits = st.builds(Submit, trader_id=trader_ids, side=sides, price=st.integers(1, 40))
cancels = st.builds(Cancel, trader_id=trader_ids, order_id=st.integers(0, 30))
passes = st.builds(Pass, trader_id=trader_ids)
actions = st.one_of(submits, cancels, passes)

# Arbitrary in-period action streams, split across two periods.
streams = st.tuples(
    st.lists(actions, max_size=50), st.lists(actions, max_size=50)
)


def full_event_sequence(stream: tuple) -> list:
    events: list = []
    for period_actions in stream:
        events.append(PeriodOpen())
        events.extend(period_actions)
        events.append(PeriodClose())
    return events


def check_invariants(exchange: Exchange) -> None:
    snapshot = exchange.state_snapshot()
    book = snapshot["book"]

    for account in snapshot["accounts"]:
        tid = account["trader_id"]
        cfg = exchange.config(tid)
        my_bids = [o for o in book if o["trader_id"] == tid and o["side"] == "buy"]
        my_asks = [o for o in book if o["trader_id"] == tid and o["side"] == "sell"]

        assert account["cash"] >= 0, f"{tid}: negative cash"
        assert 0 <= account["committed_cash"] <= account["cash"], f"{tid}: bad commitment"
        assert account["inventory"] >= 0, f"{tid}: negative inventory"
        assert account["n_open_asks"] <= account["inventory"], f"{tid}: naked asks"
        assert account["n_bought"] + account["n_open_bids"] <= len(cfg.values)
        assert account["n_sold"] + account["n_open_asks"] <= len(cfg.costs)
        # Book must agree with the account's own bookkeeping.
        assert len(my_bids) == account["n_open_bids"], f"{tid}: bid count drift"
        assert len(my_asks) == account["n_open_asks"], f"{tid}: ask count drift"
        assert sum(o["price"] for o in my_bids) == account["committed_cash"]

    if snapshot["period"] >= 1:
        total_cash = sum(a["cash"] for a in snapshot["accounts"])
        total_inventory = sum(a["inventory"] for a in snapshot["accounts"])
        assert total_cash == sum(t.cash for t in ROSTER), "cash not conserved"
        assert total_inventory == sum(len(t.costs) for t in ROSTER), (
            "inventory not conserved"
        )

    for trade in exchange.trades:
        assert trade["buyer_id"] != trade["seller_id"]
        assert trade["price"] >= 1

    # Realized surplus is bounded by the theoretical maximum: trades consume
    # schedule prefixes, and no selection of k values/costs beats the global
    # best-k matching that max_total_surplus computes.
    assert exchange.period_realized_surplus() <= max_total_surplus(ROSTER)


@settings(max_examples=200)
@given(streams)
def test_invariants_and_conservation_under_random_streams(stream):
    exchange = Exchange(ROSTER)
    for event in full_event_sequence(stream):
        exchange.apply(event)
        check_invariants(exchange)


@settings(max_examples=200)
@given(streams)
def test_rejected_events_never_mutate_state(stream):
    exchange = Exchange(ROSTER)
    for event in full_event_sequence(stream):
        before = json.dumps(exchange.state_snapshot(), sort_keys=True)
        outcome = exchange.apply(event)
        if outcome["status"] == "rejected":
            after = json.dumps(exchange.state_snapshot(), sort_keys=True)
            assert before == after, f"rejection mutated state: {outcome['reason']}"


@settings(max_examples=200)
@given(streams)
def test_replay_is_bit_identical(stream):
    exchange = Exchange(ROSTER)
    for event in full_event_sequence(stream):
        exchange.apply(event)
    log = exchange.session_log()

    assert verify_session_log(log) == []

    # And after a full JSON round trip — the on-disk form replays too.
    round_tripped = session_log_from_json(session_log_to_json(log))
    assert verify_session_log(round_tripped) == []
    assert session_log_to_json(round_tripped) == session_log_to_json(log)


@settings(max_examples=200)
@given(st.lists(actions, max_size=30))
def test_event_serialization_round_trip_is_identity(events):
    for event in [PeriodOpen(), PeriodClose(), *events]:
        assert event_from_dict(event_to_dict(event)) == event


@settings(max_examples=100)
@given(streams)
def test_two_fresh_runs_agree_exactly(stream):
    """Same event sequence, two fresh engines: identical logs, bit for bit."""
    logs = []
    for _ in range(2):
        exchange = Exchange(ROSTER)
        for event in full_event_sequence(stream):
            exchange.apply(event)
        logs.append(session_log_to_json(exchange.session_log()))
    assert logs[0] == logs[1]
