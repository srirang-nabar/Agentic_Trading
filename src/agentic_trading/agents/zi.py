"""Zero-intelligence agents per Gode & Sunder (1993) (Stage 2).

- ZI-C (constrained): a buyer bids uniform in [1, value of next unit]; a
  seller asks uniform in [cost of next unit, max_price]. Random, but never
  quotes at a loss.
- ZI-U (unconstrained): quotes uniform in [1, max_price] regardless of
  value/cost, so it happily trades at a loss. The engine still requires
  cash/inventory feasibility; experiment configs endow ZI-U traders with
  cash = units x max_price so that constraint never binds in practice —
  matching Gode & Sunder's "unconstrained" traders.

Quote protocol (fixed here, identical for both types): one standing quote
per trader. When polled with a resting order, the agent cancels it; when
polled without one, it submits a fresh random quote; with an exhausted
schedule, it passes. This cancel-then-replace adaptation is needed because
Gode & Sunder's market kept only the best standing quote per side, while
our Stage 1 engine is a persistent limit order book — without replacement,
one unlucky low bid would block a trader for the whole period.

Agents are pure functions of (own seed, polled views): fully deterministic,
so entire ZI experiments are bit-reproducible from config (Stage 2 gate).
"""

from __future__ import annotations

import random

from agentic_trading.exchange import Side, TraderConfig
from agentic_trading.runner import Action, AgentView, CancelAction, SubmitAction


class ZITrader:
    """Gode–Sunder zero-intelligence trader (constrained or unconstrained)."""

    def __init__(self, trader_id: str, seed: int, *, max_price: int, constrained: bool):
        self.trader_id = trader_id
        self.rng = random.Random(seed)
        self.max_price = max_price
        self.constrained = constrained

    def act(self, view: AgentView) -> Action:
        if view.open_orders:
            return CancelAction(order_id=view.open_orders[0][0])
        if view.remaining_values:  # buyer role
            high = view.remaining_values[0] if self.constrained else self.max_price
            high = min(high, view.cash_available)
            if high >= 1:
                return SubmitAction(side=Side.BUY, price=self.rng.randint(1, high))
            return None
        if view.remaining_costs:  # seller role
            low = view.remaining_costs[0] if self.constrained else 1
            if low <= self.max_price:
                return SubmitAction(side=Side.SELL, price=self.rng.randint(low, self.max_price))
            return None
        return None  # schedule exhausted


def build_zi_agents(
    traders: list[TraderConfig],
    *,
    kind: str,
    max_price: int,
    seed_for: "callable",
) -> dict[str, ZITrader]:
    """One seeded ZI agent per trader. kind: 'zi_c' or 'zi_u'."""
    if kind not in ("zi_c", "zi_u"):
        raise ValueError(f"unknown ZI kind: {kind!r}")
    return {
        t.trader_id: ZITrader(
            t.trader_id,
            seed_for(t.trader_id),
            max_price=max_price,
            constrained=(kind == "zi_c"),
        )
        for t in traders
    }


class SSWZITrader:
    """ZI-C adapted to the SSW carry-over market (HYPOTHESES A3.v).

    SSW induces no value/cost schedules, so "constrained" means budget- and
    holding-feasible only: when quoteless, flip a seeded fair coin between
    bid and ask; bid ~ U[1, min(available cash, max_price)]; ask ~ U[1,
    max_price] and requires a held certificate; an infeasible drawn side
    falls back to the other; both infeasible -> pass. Cancel-then-replace as
    in the Smith protocol. By construction the agent embeds no view of the
    dividend value — it is the unstructured-mispricing anchor.
    """

    def __init__(self, trader_id: str, seed: int, *, max_price: int):
        self.trader_id = trader_id
        self.rng = random.Random(seed)
        self.max_price = max_price

    def act(self, view: AgentView) -> Action:
        if view.open_orders:
            return CancelAction(order_id=view.open_orders[0][0])
        can_bid = view.cash_available >= 1
        can_ask = view.inventory_available >= 1
        want_bid = self.rng.random() < 0.5
        if want_bid and not can_bid:
            want_bid = False
        elif not want_bid and not can_ask:
            want_bid = True
        if want_bid and can_bid:
            high = min(view.cash_available, self.max_price)
            return SubmitAction(side=Side.BUY, price=self.rng.randint(1, high))
        if not want_bid and can_ask:
            return SubmitAction(side=Side.SELL, price=self.rng.randint(1, self.max_price))
        return None  # neither side feasible


def build_ssw_zi_agents(
    trader_ids: list[str], *, max_price: int, seed_for: "callable"
) -> dict[str, SSWZITrader]:
    return {
        tid: SSWZITrader(tid, seed_for(tid), max_price=max_price)
        for tid in trader_ids
    }
