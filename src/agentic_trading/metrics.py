"""Market metrics (Stage 2): efficiency, equilibrium, Smith's alpha, RMSE.

Every metric computes FROM SESSION LOGS, never from live engine state —
the log is the primary artifact and metrics must be recomputable by a
volunteer with nothing else. Each function is unit-tested on hand-computed
toy sessions before any experimental use.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class Equilibrium:
    """Competitive equilibrium of step supply/demand schedules."""

    quantity: int
    price_low: int
    price_high: int
    max_surplus: int

    @property
    def price_mid(self) -> float:
        return (self.price_low + self.price_high) / 2


def equilibrium(values: Sequence[int], costs: Sequence[int]) -> Equilibrium:
    """Intersect demand (values, desc) with supply (costs, asc).

    q* = largest q with demand[q-1] >= supply[q-1]. The equilibrium price
    interval is [max(S[q*-1], D[q*]), min(D[q*-1], S[q*])] — the highest
    excluded value/lowest excluded cost bound it from each side.
    """
    demand = sorted(values, reverse=True)
    supply = sorted(costs)
    q = 0
    while q < min(len(demand), len(supply)) and demand[q] >= supply[q]:
        q += 1
    if q == 0:
        return Equilibrium(0, 0, 0, 0)
    max_surplus = sum(demand[i] - supply[i] for i in range(q))
    lows = [supply[q - 1]] + ([demand[q]] if q < len(demand) else [])
    highs = [demand[q - 1]] + ([supply[q]] if q < len(supply) else [])
    return Equilibrium(q, max(lows), min(highs), max_surplus)


def smith_alpha(prices: Sequence[int], p_star: float) -> float:
    """Smith's convergence coefficient: 100 * RMSE(prices, p*) / p*."""
    if not prices:
        raise ValueError("no trade prices")
    if p_star <= 0:
        raise ValueError("p_star must be positive")
    return 100.0 * rmse(prices, p_star) / p_star


def rmse(prices: Sequence[int], p_star: float) -> float:
    if not prices:
        raise ValueError("no trade prices")
    return math.sqrt(sum((p - p_star) ** 2 for p in prices) / len(prices))


def session_metrics(log: dict[str, Any]) -> dict[str, Any]:
    """Per-session metrics recomputed from the log alone.

    Surplus is rebuilt by walking trades in order against each trader's
    value/cost schedule — an independent path from the engine's own
    accounting, cross-checked against it in the test suite.
    """
    traders = log["traders"]
    values = {t["trader_id"]: t["values"] for t in traders}
    costs = {t["trader_id"]: t["costs"] for t in traders}
    eq = equilibrium(
        [v for t in traders for v in t["values"]],
        [c for t in traders for c in t["costs"]],
    )
    if eq.max_surplus == 0:
        raise ValueError("degenerate market: no gains from trade")

    n_periods = log["final"]["period"]
    by_period: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for trade in log["trades"]:
        by_period[trade["period"]].append(trade)

    periods = []
    total_realized = 0
    for period in range(1, n_periods + 1):
        n_bought: dict[str, int] = defaultdict(int)
        n_sold: dict[str, int] = defaultdict(int)
        realized = 0
        prices = []
        for trade in by_period[period]:  # trades are logged in event order
            buyer, seller = trade["buyer_id"], trade["seller_id"]
            realized += (
                values[buyer][n_bought[buyer]] - costs[seller][n_sold[seller]]
            )
            n_bought[buyer] += 1
            n_sold[seller] += 1
            prices.append(trade["price"])
        total_realized += realized
        periods.append(
            {
                "period": period,
                "n_trades": len(prices),
                "realized_surplus": realized,
                "efficiency": realized / eq.max_surplus,
                "alpha": smith_alpha(prices, eq.price_mid) if prices else None,
                "rmse": rmse(prices, eq.price_mid) if prices else None,
            }
        )

    return {
        "efficiency": total_realized / (eq.max_surplus * n_periods),
        "n_trades": len(log["trades"]),
        "equilibrium": {
            "quantity": eq.quantity,
            "price_low": eq.price_low,
            "price_high": eq.price_high,
            "price_mid": eq.price_mid,
            "max_surplus": eq.max_surplus,
        },
        "periods": periods,
    }


def rank_biserial(u_statistic: float, n_x: int, n_y: int) -> float:
    """Rank-biserial effect size for a Mann-Whitney U (x vs y, 'greater')."""
    return 2.0 * u_statistic / (n_x * n_y) - 1.0
