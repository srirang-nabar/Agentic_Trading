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


def h1_summary(
    zic_logs: list[dict[str, Any]],
    llm_logs_by_paraphrase: dict[str, list[dict[str, Any]]],
    *,
    non_inferiority_margin: float = 0.05,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 40426,
) -> dict[str, Any]:
    """Pre-registered H1 analysis (HYPOTHESES H1 + A2), computed from logs.

    Primary: early-period Smith's alpha, LLM < ZI-C, one-sided Mann-Whitney
    per paraphrase; the conjunction p (max over paraphrases) is what enters
    Holm once H2/H3 exist. Secondary: efficiency non-inferiority via a seeded
    bootstrap CI on the difference in means (lower bound must clear -margin).
    """
    import random as _random

    from scipy import stats

    def cell_stats(logs: list[dict[str, Any]]) -> dict[str, Any]:
        alphas = [early_alpha_from_log(log) for log in logs]
        finite = [a for a in alphas if math.isfinite(a)]
        efficiencies = [session_metrics(log)["efficiency"] for log in logs]
        return {
            "alphas": alphas,
            "mean_early_alpha": sum(finite) / len(finite) if finite else None,
            "zero_early_trade_sessions": len(alphas) - len(finite),
            "efficiencies": efficiencies,
            "mean_efficiency": sum(efficiencies) / len(efficiencies),
        }

    def bootstrap_diff_lower(x: list[float], y: list[float]) -> float:
        rng = _random.Random(bootstrap_seed)
        diffs = sorted(
            sum(rng.choices(x, k=len(x))) / len(x) - sum(rng.choices(y, k=len(y))) / len(y)
            for _ in range(bootstrap_iterations)
        )
        return diffs[int(0.025 * bootstrap_iterations)]

    zic = cell_stats(zic_logs)
    result: dict[str, Any] = {"zi_c": zic, "paraphrases": {}}
    for name, logs in llm_logs_by_paraphrase.items():
        llm = cell_stats(logs)
        u, p = stats.mannwhitneyu(llm["alphas"], zic["alphas"], alternative="less")
        eff_lower = bootstrap_diff_lower(llm["efficiencies"], zic["efficiencies"])
        llm.update(
            {
                "mannwhitney_u": float(u),
                "p_alpha_less": float(p),
                "efficiency_diff_lower95": eff_lower,
                "efficiency_non_inferior": eff_lower > -non_inferiority_margin,
            }
        )
        result["paraphrases"][name] = llm
    ps = [c["p_alpha_less"] for c in result["paraphrases"].values()]
    result["conjunction_p"] = max(ps) if ps else None
    result["h1_direction_supported"] = all(
        c["p_alpha_less"] < 0.05 for c in result["paraphrases"].values()
    ) if ps else None
    return result


def early_alpha_from_log(log: dict[str, Any], last_period: int = 2) -> float:
    """Pre-registered H1 endpoint (HYPOTHESES A2.i).

    Smith's alpha over the pooled trade prices of periods 1..last_period.
    A session with zero trades in that window returns +inf — no trades means
    no convergence, and the rank-based primary test handles inf without
    excluding the session (the no-discard rule stays intact).
    """
    traders = log["traders"]
    eq = equilibrium(
        [v for t in traders for v in t["values"]],
        [c for t in traders for c in t["costs"]],
    )
    prices = [t["price"] for t in log["trades"] if t["period"] <= last_period]
    if not prices:
        return math.inf
    return smith_alpha(prices, eq.price_mid)
