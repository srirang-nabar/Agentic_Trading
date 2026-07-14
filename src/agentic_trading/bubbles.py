"""Bubble metrics for the SSW asset market (Stage 5).

Every metric computes FROM SESSION LOGS, never from live engine state.
Formulas are fixed in HYPOTHESES.md Amendment A3.vi and restated here so the
module is self-contained:

- P_bar_t  = mean trade price of period t (unit-size orders, so the
  volume-weighted mean of Stöckl et al. 2010 equals the arithmetic mean).
- FV_t     = E[dividend] * (periods remaining including t); FV_bar = mean FV.
- RAD      = (1/N) * sum_t |P_bar_t - FV_t| / |FV_bar|   (Stöckl et al. 2010)
- RD       = (1/N) * sum_t (P_bar_t - FV_t) / |FV_bar|   (Stöckl et al. 2010)
  with N = number of periods with at least one trade.
- Amplitude = max_t((P_bar_t - FV_t)/FV_1) - min_t((P_bar_t - FV_t)/FV_1)
  (King et al. 1993), over traded periods.
- Duration  = length of the longest run of CONSECUTIVE traded periods with
  strictly increasing P_bar_t - FV_t (Porter & Smith 1995).
- Turnover  = total session volume / shares outstanding.
- Shape criterion (H2b, per-period MEDIAN prices): peak deviation positive,
  peak (earliest argmax) inside the registered window, and the mean deviation
  over the last two traded periods below 50% of the peak.

SSW session logs carry an "ssw" section:
    {"dividend_values": [0, 8, 28, 60], "dividends": [d_1..d_T],
     "shares_outstanding": 12}
A session with zero trades in every period: RD = RAD = 0.0 (sign-test tie),
amplitude/duration undefined (None), turnover 0, shape criterion failed.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

SHAPE_WINDOW = (3, 12)  # registered peak window for the 15-period design


def fundamental_values(n_periods: int, dividend_values: list[int]) -> tuple[float, ...]:
    """FV_t = E[dividend] x (remaining periods including t), t = 1..n_periods."""
    expected = sum(dividend_values) / len(dividend_values)
    return tuple(expected * (n_periods - t + 1) for t in range(1, n_periods + 1))


def period_prices(log: dict[str, Any], stat: str = "mean") -> dict[int, float]:
    """Per-period trade-price aggregate over TRADED periods only."""
    if stat not in ("mean", "median"):
        raise ValueError(f"unknown stat {stat!r}")
    by_period: dict[int, list[int]] = defaultdict(list)
    for trade in log["trades"]:
        by_period[trade["period"]].append(trade["price"])
    agg = statistics.mean if stat == "mean" else statistics.median
    return {period: float(agg(prices)) for period, prices in sorted(by_period.items())}


def _deviations(log: dict[str, Any], stat: str) -> tuple[dict[int, float], tuple[float, ...]]:
    n_periods = log["final"]["period"]
    fv = fundamental_values(n_periods, log["ssw"]["dividend_values"])
    prices = period_prices(log, stat)
    return {t: p - fv[t - 1] for t, p in prices.items()}, fv


def ssw_metrics(log: dict[str, Any]) -> dict[str, Any]:
    """All Stage 5 session metrics, from the log alone."""
    deviations, fv = _deviations(log, "mean")
    fv_bar = sum(fv) / len(fv)
    n_traded = len(deviations)
    turnover = len(log["trades"]) / log["ssw"]["shares_outstanding"]

    if n_traded == 0:
        return {
            "rad": 0.0,
            "rd": 0.0,
            "amplitude": None,
            "duration": None,
            "turnover": 0.0,
            "shape_ok": False,
            "zero_trade_session": True,
            "n_traded_periods": 0,
        }

    rad = sum(abs(d) for d in deviations.values()) / n_traded / abs(fv_bar)
    rd = sum(deviations.values()) / n_traded / abs(fv_bar)
    normalized = [d / fv[0] for d in deviations.values()]
    amplitude = max(normalized) - min(normalized)

    return {
        "rad": rad,
        "rd": rd,
        "amplitude": amplitude,
        "duration": _duration(deviations),
        "turnover": turnover,
        "shape_ok": shape_criterion(log),
        "zero_trade_session": False,
        "n_traded_periods": n_traded,
    }


def _duration(deviations: dict[int, float]) -> int:
    """Longest run of consecutive traded periods with strictly rising deviation."""
    best = run = 1
    periods = sorted(deviations)
    for prev, cur in zip(periods, periods[1:]):
        if cur == prev + 1 and deviations[cur] > deviations[prev]:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def shape_criterion(
    log: dict[str, Any], window: tuple[int, int] = SHAPE_WINDOW
) -> bool:
    """H2b boom-crash shape on MEDIAN period prices (HYPOTHESES H2 + A3.vii).

    Peak deviation positive, earliest peak period inside `window`, and the
    mean deviation over the last two traded periods < 50% of the peak.
    Fewer than two traded periods fails by construction.
    """
    deviations, _ = _deviations(log, "median")
    if len(deviations) < 2:
        return False
    peak = max(deviations.values())
    if peak <= 0:
        return False
    peak_period = min(t for t, d in deviations.items() if d == peak)
    if not window[0] <= peak_period <= window[1]:
        return False
    tail = [deviations[t] for t in sorted(deviations)[-2:]]
    return sum(tail) / 2 < 0.5 * peak


def h2_summary(
    llm_logs_by_paraphrase: dict[str, list[dict[str, Any]]],
    *,
    experienced_logs: list[dict[str, Any]] | None = None,
    paired_inexperienced_logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pre-registered H2 analysis (HYPOTHESES H2 + A3.vii), from logs.

    Per paraphrase: (a) exact one-sided sign test on session RD > 0 (ties at
    RD == 0 dropped) and (b) exact one-sided binomial test that the
    shape-criterion proportion exceeds 1/2. The conjunction p is the max of
    all four p-values. The experience effect (named secondary) is a one-sided
    Wilcoxon signed-rank on paired session RD (inexperienced - experienced).
    """
    from scipy import stats

    result: dict[str, Any] = {"paraphrases": {}}
    for name, logs in llm_logs_by_paraphrase.items():
        metrics = [ssw_metrics(log) for log in logs]
        rds = [m["rd"] for m in metrics]
        nonzero = [r for r in rds if r != 0.0]
        n_pos = sum(1 for r in nonzero if r > 0)
        p_sign = (
            float(stats.binomtest(n_pos, len(nonzero), 0.5, alternative="greater").pvalue)
            if nonzero
            else 1.0
        )
        n_shape = sum(1 for m in metrics if m["shape_ok"])
        p_shape = float(
            stats.binomtest(n_shape, len(metrics), 0.5, alternative="greater").pvalue
        )
        finite_amp = [m["amplitude"] for m in metrics if m["amplitude"] is not None]
        result["paraphrases"][name] = {
            "n_sessions": len(logs),
            "mean_rd": sum(rds) / len(rds),
            "mean_rad": sum(m["rad"] for m in metrics) / len(metrics),
            "mean_amplitude": sum(finite_amp) / len(finite_amp) if finite_amp else None,
            "mean_turnover": sum(m["turnover"] for m in metrics) / len(metrics),
            "n_rd_positive": n_pos,
            "n_rd_nonzero": len(nonzero),
            "p_rd_sign": p_sign,
            "n_shape_ok": n_shape,
            "shape_proportion": n_shape / len(metrics),
            "p_shape": p_shape,
            "zero_trade_sessions": sum(1 for m in metrics if m["zero_trade_session"]),
        }

    all_ps = [
        p
        for cell in result["paraphrases"].values()
        for p in (cell["p_rd_sign"], cell["p_shape"])
    ]
    result["conjunction_p"] = max(all_ps) if all_ps else None
    result["h2_supported"] = all(p < 0.05 for p in all_ps) if all_ps else None

    if experienced_logs is not None and paired_inexperienced_logs is not None:
        if len(experienced_logs) != len(paired_inexperienced_logs):
            raise ValueError("experience comparison requires paired sessions")
        rd_inexp = [ssw_metrics(log)["rd"] for log in paired_inexperienced_logs]
        rd_exp = [ssw_metrics(log)["rd"] for log in experienced_logs]
        diffs = [i - e for i, e in zip(rd_inexp, rd_exp)]
        wilcoxon = stats.wilcoxon(diffs, alternative="greater")
        result["experience"] = {
            "n_pairs": len(diffs),
            "mean_rd_inexperienced": sum(rd_inexp) / len(rd_inexp),
            "mean_rd_experienced": sum(rd_exp) / len(rd_exp),
            "mean_rd_reduction": sum(diffs) / len(diffs),
            "p_wilcoxon": float(wilcoxon.pvalue),
        }
    return result
