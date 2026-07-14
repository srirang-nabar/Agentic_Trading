"""Continuous double auction exchange engine (Stage 1).

Correctness is the product: this module is the project's calibration
certificate, exhaustively tested and strictly deterministic.

Design decisions (all fixed, all load-bearing for determinism):

- Prices are integers >= 1 (tick size 1). Every order is for exactly one
  unit, matching the Smith/Gode–Sunder designs where traders work through
  a schedule of single units.
- Price-time priority: best ask = lowest price, best bid = highest price;
  ties broken by order_id, which is a global counter assigned in event
  order. No other tie-break exists.
- A marketable limit order executes at the RESTING order's price.
- An incoming order whose best match is the trader's own resting order is
  rejected (`self_trade`) rather than matched or skipped — skipping would
  violate price priority.
- Budget backing is enforced at acceptance: a resting bid commits its full
  price in cash until fill/cancel/period close; an ask is backed by one
  unit of inventory. Bids and asks are additionally capped by the trader's
  remaining value/cost schedule, counting open orders.
- Induced values: the k-th unit bought redeems at `values[k]`, the k-th
  unit sold costs `costs[k]`. Loss-making trades are legal (ZI-U makes
  them); infeasible trades are not.
- Sellers are endowed with `len(costs)` physical units at period open;
  bought units enter the buyer's inventory, so total cash and total
  inventory are conserved by construction — property-tested, not assumed.
- `apply()` is total: any malformed event yields a deterministic rejection
  outcome, never an exception, and a rejected event never mutates state.
- Period close voids all resting orders; period open re-endows accounts.
- The ordered event sequence is the complete input: replaying it through a
  fresh Exchange reproduces every outcome bit-exactly (see replay.py).
- This is a full limit order book. Gode & Sunder (1993) instead kept only
  the best standing quote per side under the NYSE improvement rule; their
  qualitative result is robust to this difference, but Stage 2 must note
  the deviation when comparing efficiency levels to their published paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence, Union


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class TraderConfig:
    """Per-period endowment and induced-value schedules for one trader."""

    trader_id: str
    cash: int = 0
    values: tuple[int, ...] = ()  # redemption value of k-th unit bought
    costs: tuple[int, ...] = ()  # cost of k-th unit sold; endows len(costs) units


# --- Events: the replay format. The ordered event list is the session's ---
# --- complete input; everything else is a deterministic function of it.  ---


@dataclass(frozen=True)
class PeriodOpen:
    pass


@dataclass(frozen=True)
class PeriodClose:
    pass


@dataclass(frozen=True)
class Submit:
    trader_id: str
    side: Side
    price: int


@dataclass(frozen=True)
class Cancel:
    trader_id: str
    order_id: int


@dataclass(frozen=True)
class Pass:
    trader_id: str


Event = Union[PeriodOpen, PeriodClose, Submit, Cancel, Pass]

Outcome = dict[str, Any]


@dataclass(frozen=True)
class RestingOrder:
    order_id: int
    trader_id: str
    side: Side
    price: int


@dataclass
class _Account:
    config: TraderConfig
    cash: int = 0
    committed_cash: int = 0
    inventory: int = 0
    n_open_bids: int = 0
    n_open_asks: int = 0
    n_bought: int = 0
    n_sold: int = 0
    period_surplus: int = 0
    total_surplus: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "trader_id": self.config.trader_id,
            "cash": self.cash,
            "committed_cash": self.committed_cash,
            "inventory": self.inventory,
            "n_open_bids": self.n_open_bids,
            "n_open_asks": self.n_open_asks,
            "n_bought": self.n_bought,
            "n_sold": self.n_sold,
            "period_surplus": self.period_surplus,
            "total_surplus": self.total_surplus,
        }


def max_total_surplus(traders: Sequence[TraderConfig]) -> int:
    """Maximum attainable surplus: match highest values to lowest costs."""
    values = sorted((v for t in traders for v in t.values), reverse=True)
    costs = sorted(c for t in traders for c in t.costs)
    total = 0
    for v, c in zip(values, costs):
        if v <= c:
            break
        total += v - c
    return total


class Exchange:
    """Deterministic CDA over one asset for a fixed roster of traders."""

    def __init__(self, traders: Sequence[TraderConfig]):
        ids = [t.trader_id for t in traders]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate trader_id")
        for t in traders:
            if t.cash < 0 or any(v < 0 for v in t.values) or any(c < 0 for c in t.costs):
                raise ValueError(f"negative endowment for {t.trader_id}")
        self._configs: dict[str, TraderConfig] = {t.trader_id: t for t in traders}
        self._accounts: dict[str, _Account] = {
            t.trader_id: _Account(config=t) for t in traders
        }
        self._book: dict[int, RestingOrder] = {}
        self._market_open = False
        self._period = 0
        self._next_order_id = 0
        self._next_trade_id = 0
        self.trades: list[dict[str, Any]] = []
        self.events: list[Event] = []
        self.outcomes: list[Outcome] = []

    # ---- public API ----

    def apply(self, event: Event) -> Outcome:
        """Apply one event; total (never raises on event content)."""
        if isinstance(event, PeriodOpen):
            outcome = self._apply_period_open()
        elif isinstance(event, PeriodClose):
            outcome = self._apply_period_close()
        elif isinstance(event, Submit):
            outcome = self._apply_submit(event)
        elif isinstance(event, Cancel):
            outcome = self._apply_cancel(event)
        elif isinstance(event, Pass):
            outcome = self._apply_pass(event)
        else:
            outcome = _rejected("unknown_event")
        self.events.append(event)
        self.outcomes.append(outcome)
        return outcome

    @property
    def period(self) -> int:
        return self._period

    @property
    def market_open(self) -> bool:
        return self._market_open

    def best_bid(self) -> RestingOrder | None:
        return min(
            (o for o in self._book.values() if o.side is Side.BUY),
            key=lambda o: (-o.price, o.order_id),
            default=None,
        )

    def best_ask(self) -> RestingOrder | None:
        return min(
            (o for o in self._book.values() if o.side is Side.SELL),
            key=lambda o: (o.price, o.order_id),
            default=None,
        )

    def open_orders_for(self, trader_id: str) -> list[tuple[int, str, int]]:
        """This trader's resting orders as (order_id, side, price), oldest first."""
        return [
            (o.order_id, o.side.value, o.price)
            for o in sorted(
                (o for o in self._book.values() if o.trader_id == trader_id),
                key=lambda o: o.order_id,
            )
        ]

    def account(self, trader_id: str) -> dict[str, Any]:
        return self._accounts[trader_id].snapshot()

    def config(self, trader_id: str) -> TraderConfig:
        return self._configs[trader_id]

    def trader_ids(self) -> list[str]:
        return sorted(self._configs)

    def book_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "order_id": o.order_id,
                "trader_id": o.trader_id,
                "side": o.side.value,
                "price": o.price,
            }
            for o in sorted(self._book.values(), key=lambda o: o.order_id)
        ]

    def state_snapshot(self) -> dict[str, Any]:
        return {
            "period": self._period,
            "market_open": self._market_open,
            "next_order_id": self._next_order_id,
            "next_trade_id": self._next_trade_id,
            "accounts": [self._accounts[tid].snapshot() for tid in sorted(self._accounts)],
            "book": self.book_snapshot(),
            "n_trades": len(self.trades),
        }

    def period_realized_surplus(self) -> int:
        return sum(a.period_surplus for a in self._accounts.values())

    def session_log(self) -> dict[str, Any]:
        """The primary scientific artifact: complete inputs and outputs."""
        return {
            "traders": [
                {
                    "trader_id": t.trader_id,
                    "cash": t.cash,
                    "values": list(t.values),
                    "costs": list(t.costs),
                }
                for t in (self._configs[tid] for tid in sorted(self._configs))
            ],
            "events": [event_to_dict(e) for e in self.events],
            "outcomes": self.outcomes,
            "trades": self.trades,
            "final": self.state_snapshot(),
        }

    # ---- event handlers ----

    def _apply_period_open(self) -> Outcome:
        if self._market_open:
            return _rejected("period_already_open")
        self._period += 1
        for acct in self._accounts.values():
            acct.cash = acct.config.cash
            acct.committed_cash = 0
            acct.inventory = len(acct.config.costs)
            acct.n_open_bids = 0
            acct.n_open_asks = 0
            acct.n_bought = 0
            acct.n_sold = 0
            acct.period_surplus = 0
        self._book.clear()
        self._market_open = True
        return {"status": "period_open", "period": self._period}

    def _apply_period_close(self) -> Outcome:
        if not self._market_open:
            return _rejected("market_closed")
        voided = sorted(self._book)
        for order in self._book.values():
            acct = self._accounts[order.trader_id]
            if order.side is Side.BUY:
                acct.committed_cash -= order.price
                acct.n_open_bids -= 1
            else:
                acct.n_open_asks -= 1
        self._book.clear()
        self._market_open = False
        return {"status": "period_close", "period": self._period, "voided": voided}

    def _apply_submit(self, ev: Submit) -> Outcome:
        if not self._market_open:
            return _rejected("market_closed")
        acct = self._accounts.get(ev.trader_id)
        if acct is None:
            return _rejected("unknown_trader")
        if type(ev.price) is not int or ev.price < 1:
            return _rejected("invalid_price")
        side = ev.side
        if not isinstance(side, Side):
            return _rejected("invalid_side")

        if side is Side.BUY:
            if acct.n_bought + acct.n_open_bids >= len(acct.config.values):
                return _rejected("schedule_exhausted")
            available_cash = acct.cash - acct.committed_cash
            best = self.best_ask()
            if best is not None and best.price <= ev.price:
                # Marketable: the trade costs the resting price, so that is
                # what must be affordable — not the (possibly higher) limit.
                if best.trader_id == ev.trader_id:
                    return _rejected("self_trade")
                if available_cash < best.price:
                    return _rejected("insufficient_cash")
                order_id = self._take_order_id()
                trade = self._execute(
                    buyer_id=ev.trader_id,
                    seller_id=best.trader_id,
                    price=best.price,
                    buy_order_id=order_id,
                    sell_order_id=best.order_id,
                    resting=best,
                )
                return {"status": "traded", "order_id": order_id, "trade": trade}
            # Resting: the bid commits its full limit price until it fills,
            # cancels, or the period closes — so the limit must be backed.
            if available_cash < ev.price:
                return _rejected("insufficient_cash")
            order_id = self._take_order_id()
            acct.committed_cash += ev.price
            acct.n_open_bids += 1
            self._book[order_id] = RestingOrder(order_id, ev.trader_id, side, ev.price)
            return {"status": "resting", "order_id": order_id}

        # SELL
        if acct.n_sold + acct.n_open_asks >= len(acct.config.costs):
            return _rejected("schedule_exhausted")
        # Defensive only: with inventory endowed as len(costs) and asks capped
        # by the cost schedule above, this cannot fire — kept as insurance
        # should endowment semantics change (e.g. SSW carry-over in Stage 5).
        if acct.inventory - acct.n_open_asks < 1:
            return _rejected("insufficient_inventory")
        best = self.best_bid()
        if best is not None and best.price >= ev.price:
            if best.trader_id == ev.trader_id:
                return _rejected("self_trade")
            order_id = self._take_order_id()
            trade = self._execute(
                buyer_id=best.trader_id,
                seller_id=ev.trader_id,
                price=best.price,
                buy_order_id=best.order_id,
                sell_order_id=order_id,
                resting=best,
            )
            return {"status": "traded", "order_id": order_id, "trade": trade}
        order_id = self._take_order_id()
        acct.n_open_asks += 1
        self._book[order_id] = RestingOrder(order_id, ev.trader_id, side, ev.price)
        return {"status": "resting", "order_id": order_id}

    def _apply_cancel(self, ev: Cancel) -> Outcome:
        if not self._market_open:
            return _rejected("market_closed")
        if ev.trader_id not in self._accounts:
            return _rejected("unknown_trader")
        order = self._book.get(ev.order_id)
        if order is None:
            return _rejected("unknown_order")
        if order.trader_id != ev.trader_id:
            return _rejected("not_owner")
        acct = self._accounts[ev.trader_id]
        if order.side is Side.BUY:
            acct.committed_cash -= order.price
            acct.n_open_bids -= 1
        else:
            acct.n_open_asks -= 1
        del self._book[ev.order_id]
        return {"status": "cancelled", "order_id": ev.order_id}

    def _apply_pass(self, ev: Pass) -> Outcome:
        if not self._market_open:
            return _rejected("market_closed")
        if ev.trader_id not in self._accounts:
            return _rejected("unknown_trader")
        return {"status": "passed"}

    # ---- internals ----

    def _take_order_id(self) -> int:
        order_id = self._next_order_id
        self._next_order_id += 1
        return order_id

    def _execute(
        self,
        *,
        buyer_id: str,
        seller_id: str,
        price: int,
        buy_order_id: int,
        sell_order_id: int,
        resting: RestingOrder,
    ) -> dict[str, Any]:
        buyer = self._accounts[buyer_id]
        seller = self._accounts[seller_id]

        # Release the resting side's backing; the trade executes at the
        # resting price, so a resting bid's commitment equals the charge.
        if resting.side is Side.BUY:
            buyer.committed_cash -= resting.price
            buyer.n_open_bids -= 1
        else:
            seller.n_open_asks -= 1
        del self._book[resting.order_id]

        buyer_value = buyer.config.values[buyer.n_bought]
        seller_cost = seller.config.costs[seller.n_sold]

        buyer.cash -= price
        buyer.inventory += 1
        buyer.n_bought += 1
        buyer_gain = buyer_value - price
        buyer.period_surplus += buyer_gain
        buyer.total_surplus += buyer_gain

        seller.cash += price
        seller.inventory -= 1
        seller.n_sold += 1
        seller_gain = price - seller_cost
        seller.period_surplus += seller_gain
        seller.total_surplus += seller_gain

        trade = {
            "trade_id": self._next_trade_id,
            "period": self._period,
            "price": price,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "buy_order_id": buy_order_id,
            "sell_order_id": sell_order_id,
        }
        self._next_trade_id += 1
        self.trades.append(trade)
        return trade


def _rejected(reason: str) -> Outcome:
    return {"status": "rejected", "reason": reason}


# ---- event (de)serialization: log -> objects -> log is the identity ----

def event_to_dict(event: Event) -> dict[str, Any]:
    if isinstance(event, PeriodOpen):
        return {"type": "period_open"}
    if isinstance(event, PeriodClose):
        return {"type": "period_close"}
    if isinstance(event, Submit):
        return {
            "type": "submit",
            "trader_id": event.trader_id,
            "side": event.side.value,
            "price": event.price,
        }
    if isinstance(event, Cancel):
        return {"type": "cancel", "trader_id": event.trader_id, "order_id": event.order_id}
    if isinstance(event, Pass):
        return {"type": "pass", "trader_id": event.trader_id}
    raise TypeError(f"not an event: {event!r}")


def event_from_dict(d: dict[str, Any]) -> Event:
    kind = d["type"]
    if kind == "period_open":
        return PeriodOpen()
    if kind == "period_close":
        return PeriodClose()
    if kind == "submit":
        return Submit(trader_id=d["trader_id"], side=Side(d["side"]), price=d["price"])
    if kind == "cancel":
        return Cancel(trader_id=d["trader_id"], order_id=d["order_id"])
    if kind == "pass":
        return Pass(trader_id=d["trader_id"])
    raise ValueError(f"unknown event type: {kind!r}")
