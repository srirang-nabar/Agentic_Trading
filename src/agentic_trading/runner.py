"""Session runner: seeded random-polling activation (Stage 1).

The activation protocol is part of the engine spec, pre-registered in
HYPOTHESES.md: at each step a uniformly random trader (seeded RNG,
Gode–Sunder style) is polled and may submit an order, cancel one of its
resting orders, or pass. The protocol is identical for every agent type —
ZI, LLM, or scripted — and response latency never affects priority: an
agent acts if and only if it is polled, in poll order.

The resulting event sequence (not the RNG) is what the session log records,
so replay needs no seed. Config-driven multi-session experiments arrive in
Stage 2; this module deliberately holds only the single-session mechanics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Protocol, Sequence, Union

from agentic_trading.exchange import (
    Cancel,
    Exchange,
    Pass,
    PeriodClose,
    PeriodOpen,
    Side,
    Submit,
    TraderConfig,
)


@dataclass(frozen=True)
class SubmitAction:
    side: Side
    price: int


@dataclass(frozen=True)
class CancelAction:
    order_id: int


Action = Union[SubmitAction, CancelAction, None]


@dataclass(frozen=True)
class AgentView:
    """Everything a polled agent is allowed to see."""

    trader_id: str
    period: int
    step: int
    best_bid: int | None
    best_ask: int | None
    last_trade_price: int | None
    cash_available: int
    inventory_available: int
    remaining_values: tuple[int, ...]
    remaining_costs: tuple[int, ...]
    open_orders: tuple[tuple[int, str, int], ...]  # (order_id, side, price)


class Agent(Protocol):
    def act(self, view: AgentView) -> Action: ...


def run_session(
    traders: Sequence[TraderConfig],
    agents: dict[str, Agent],
    *,
    n_periods: int,
    steps_per_period: int,
    poll_seed: int,
) -> dict[str, Any]:
    """Run one session; returns the complete session log (see replay.py)."""
    trader_ids = sorted(t.trader_id for t in traders)
    if sorted(agents) != trader_ids:
        raise ValueError("agents must match traders exactly")

    exchange = Exchange(traders)
    rng = random.Random(poll_seed)

    for _ in range(n_periods):
        exchange.apply(PeriodOpen())
        for step in range(steps_per_period):
            trader_id = trader_ids[rng.randrange(len(trader_ids))]
            action = agents[trader_id].act(_view(exchange, trader_id, step))
            exchange.apply(_to_event(trader_id, action))
        exchange.apply(PeriodClose())

    log = exchange.session_log()
    log["config"] = {
        "n_periods": n_periods,
        "steps_per_period": steps_per_period,
        "poll_seed": poll_seed,
        "activation": "uniform_random_polling",
    }
    return log


def _view(exchange: Exchange, trader_id: str, step: int) -> AgentView:
    acct = exchange.account(trader_id)
    cfg = exchange.config(trader_id)
    bid = exchange.best_bid()
    ask = exchange.best_ask()
    last_price = exchange.trades[-1]["price"] if exchange.trades else None
    open_orders = tuple(exchange.open_orders_for(trader_id))
    return AgentView(
        trader_id=trader_id,
        period=exchange.period,
        step=step,
        best_bid=bid.price if bid else None,
        best_ask=ask.price if ask else None,
        last_trade_price=last_price,
        cash_available=acct["cash"] - acct["committed_cash"],
        inventory_available=acct["inventory"] - acct["n_open_asks"],
        remaining_values=cfg.values[acct["n_bought"] + acct["n_open_bids"]:],
        remaining_costs=cfg.costs[acct["n_sold"] + acct["n_open_asks"]:],
        open_orders=open_orders,
    )


def _to_event(trader_id: str, action: Action):
    if action is None:
        return Pass(trader_id)
    if isinstance(action, SubmitAction):
        return Submit(trader_id=trader_id, side=action.side, price=action.price)
    if isinstance(action, CancelAction):
        return Cancel(trader_id=trader_id, order_id=action.order_id)
    raise TypeError(f"not an action: {action!r}")
