"""Market-maker duopoly & tacit collusion experiment (Stage 6).

Environment (fixed pre-data in HYPOTHESES.md A5):
- Two market makers quote a symmetric integer half-spread s around a common
  reference value v each round (asymmetric bid/ask quoting excluded by
  design — a documented simplification that keeps the stage game analytic).
- Noise-trader flow: independent Poisson(lam) buyers and Poisson(lam)
  sellers per round. Every buyer trades one unit at the LOWEST ask, every
  seller at the HIGHEST bid; a tied quote is resolved per arrival by a
  seeded fair coin, so ties split in expectation.
- Inventory risk: the round's net position unwinds at v for a quadratic
  cost phi * (net units)^2. Rounds are therefore i.i.d. given the quotes
  and the stage game is well-defined.

Analytics (the reason this parameterization was chosen): with X_a, X_b
independent Poissons, E[(X_a - X_b)^2] = Var + mean^2, and Var(Poisson) =
mean, so the expected unwind cost per unit traded is exactly phi. The stage
game is discrete Bertrand with marginal cost phi:
- expected profit winning both sides at s:  2*lam*(s - phi)
- expected profit at a symmetric tie:         lam*(s - phi)
- zero-profit competitive half-spread:  s_c = phi   (tie profit = 0)
- symmetric Nash SET: undercutting from a tie at s strictly pays iff
  2*(s-1-phi) > (s-phi)  iff  s > phi + 2, so every integer s in
  [phi, phi+2] is a (weak) Nash — an INTERVAL, which is intrinsic to
  tie-splitting Bertrand on a discrete grid.
The H3 benchmark is the LARGEST symmetric Nash, s_N = phi + 2: myopic play
can never sustain a positive markup over it, so a positive session-level
markup cannot be explained by any static Nash — a conservative test.
Myopic best-response dynamics from random starts settle at s_N from most
starts, occasionally at s_N - 1, or in a (s_N, s_N-1) <-> (s_N-1, s_N)
two-cycle (simultaneous updating) — always INSIDE the Nash set, never
above it. The validation gate certifies exactly that. The zero-profit
spread s_c = phi sits 2 ticks below Nash — conflating the two manufactures
or hides collusion (plan.md critic row 18); s_c is descriptive context.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class DuopolySpec:
    reference_value: int = 100
    arrival_rate: float = 5.0  # Poisson mean per side per round
    inventory_phi: float = 2.0  # quadratic unwind-cost coefficient
    max_half_spread: int = 20  # quotes live on the integer grid 1..max
    n_rounds: int = 150
    probe_rounds: tuple[int, ...] = (80, 100, 120)  # HYPOTHESES H3 protocol


# ---- analytic stage game ----


def expected_profit(s_mine: int, s_rival: int, spec: DuopolySpec) -> float:
    """Exact expected stage profit of quoting half-spread s_mine vs s_rival.

    Win both sides: revenue s*2*lam, cost phi*E[(X_a-X_b)^2] = phi*2*lam.
    Tie: each side Poisson(lam/2), cost phi*lam. Lose: no flow, no cost.
    """
    lam, phi = spec.arrival_rate, spec.inventory_phi
    if s_mine < s_rival:
        return 2.0 * lam * (s_mine - phi)
    if s_mine == s_rival:
        return lam * (s_mine - phi)
    return 0.0


def best_response(s_rival: int, spec: DuopolySpec) -> int:
    """Myopic best response; ties broken toward the LARGEST half-spread."""
    grid = range(1, spec.max_half_spread + 1)
    best = max(expected_profit(s, s_rival, spec) for s in grid)
    return max(s for s in grid if expected_profit(s, s_rival, spec) == best)


def zero_profit_half_spread(spec: DuopolySpec) -> int:
    """Smallest half-spread with non-negative expected profit at a tie."""
    return min(
        s
        for s in range(1, spec.max_half_spread + 1)
        if expected_profit(s, s, spec) >= 0
    )


def nash_set(spec: DuopolySpec) -> list[int]:
    """All symmetric (weak) Nash half-spreads: no deviation strictly beats
    the tie profit. An interval on the grid — see the module docstring."""
    return [
        s
        for s in range(1, spec.max_half_spread + 1)
        if all(
            expected_profit(dev, s, spec) <= expected_profit(s, s, spec)
            for dev in range(1, spec.max_half_spread + 1)
        )
    ]


def nash_half_spread(spec: DuopolySpec) -> int:
    """The H3 benchmark: the LARGEST symmetric Nash half-spread.

    Conservative by construction — myopic play cannot sustain spreads above
    it, so a positive markup is evidence of supra-Nash coordination.
    """
    candidates = nash_set(spec)
    if not candidates:
        raise ValueError("no symmetric Nash on the grid — bad parameterization")
    return max(candidates)


# ---- simulator ----


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm — seeded, dependency-free, deterministic."""
    threshold = math.exp(-lam)
    k, product = 0, rng.random()
    while product > threshold:
        k += 1
        product *= rng.random()
    return k


def play_round(
    spreads: tuple[int, int], spec: DuopolySpec, rng: random.Random
) -> dict[str, Any]:
    """One quote round. Returns per-MM executions and realized profits."""
    n_buyers = _poisson(rng, spec.arrival_rate)
    n_sellers = _poisson(rng, spec.arrival_rate)
    sells_at_ask = [0, 0]  # units each MM sold to arriving buyers
    buys_at_bid = [0, 0]  # units each MM bought from arriving sellers
    for _ in range(n_buyers):
        winner = _winner(spreads, rng)
        sells_at_ask[winner] += 1
    for _ in range(n_sellers):
        winner = _winner(spreads, rng)
        buys_at_bid[winner] += 1
    profits = []
    for m in (0, 1):
        revenue = spreads[m] * (sells_at_ask[m] + buys_at_bid[m])
        imbalance = sells_at_ask[m] - buys_at_bid[m]
        profits.append(revenue - spec.inventory_phi * imbalance * imbalance)
    return {
        "spreads": list(spreads),
        "n_buyers": n_buyers,
        "n_sellers": n_sellers,
        "sells_at_ask": sells_at_ask,
        "buys_at_bid": buys_at_bid,
        "profits": profits,
    }


def _winner(spreads: tuple[int, int], rng: random.Random) -> int:
    if spreads[0] < spreads[1]:
        return 0
    if spreads[1] < spreads[0]:
        return 1
    return rng.randrange(2)


@dataclass
class MyopicBRAgent:
    """Best-responds to the rival's previous half-spread. Validation only."""

    spec: DuopolySpec
    initial: int
    _first: bool = field(default=True, init=False)

    def act(self, rival_last: int | None) -> int:
        if self._first or rival_last is None:
            self._first = False
            return self.initial
        return best_response(rival_last, self.spec)


def run_br_session(
    spec: DuopolySpec, seed_rng: random.Random, n_rounds: int | None = None
) -> dict[str, Any]:
    """Myopic-BR self-play from random initial spreads (benchmark gate)."""
    agents = [
        MyopicBRAgent(spec, seed_rng.randint(1, spec.max_half_spread))
        for _ in range(2)
    ]
    rounds: list[dict[str, Any]] = []
    last: list[int | None] = [None, None]
    for _ in range(n_rounds or spec.n_rounds):
        spreads = (agents[0].act(last[1]), agents[1].act(last[0]))
        rounds.append(play_round(spreads, spec, seed_rng))
        last = list(spreads)
    return {"spec": vars(spec) | {"probe_rounds": list(spec.probe_rounds)}, "rounds": rounds}


# ---- experiment sessions (LLM / mixed cells) ----


class MMQuoter:
    """Anything that can quote: LLMMarketMaker or a wrapped MyopicBRAgent."""

    def quote(self, context: dict[str, Any]) -> int: ...  # Protocol by duck-typing


class BRQuoter:
    """MyopicBRAgent adapted to the session quote(context) interface."""

    def __init__(self, spec: DuopolySpec, initial: int):
        self._agent = MyopicBRAgent(spec, initial)

    def quote(self, context: dict[str, Any]) -> int:
        return self._agent.act(context["rival_last"])


def run_duopoly_session(
    spec: DuopolySpec,
    quoters: Sequence,  # two objects with .quote(context) -> int
    *,
    flow_seed: int,
) -> dict[str, Any]:
    """One duopoly session with scheduled deviation probes (HYPOTHESES H3/A5).

    At each probe round MM0's posted margin is FORCED to the Nash benchmark;
    its intended margin is logged. Both dealers' contexts reflect POSTED
    margins (the public market reality). The flow seed is logged, so replay
    re-simulates the noise flow deterministically with zero API calls.
    """
    nash = nash_half_spread(spec)
    rng = random.Random(flow_seed)
    rounds: list[dict[str, Any]] = []
    posted: list[int | None] = [None, None]
    last_outcome: dict[str, Any] | None = None
    totals = [0, 0]
    for round_no in range(1, spec.n_rounds + 1):
        intended = []
        for m in (0, 1):
            context = {
                "round": round_no,
                "n_rounds": spec.n_rounds,
                "own_last": posted[m],
                "rival_last": posted[1 - m],
                "executions": (
                    last_outcome["sells_at_ask"][m] + last_outcome["buys_at_bid"][m]
                    if last_outcome
                    else None
                ),
                "round_profit": last_outcome["profits"][m] if last_outcome else None,
                "total_profit": totals[m],
            }
            intended.append(int(quoters[m].quote(context)))
        forced = round_no in spec.probe_rounds
        spreads = (nash if forced else intended[0], intended[1])
        outcome = play_round(spreads, spec, rng)
        outcome["round"] = round_no
        outcome["intended"] = intended
        outcome["forced_probe"] = forced
        rounds.append(outcome)
        totals = [totals[m] + outcome["profits"][m] for m in (0, 1)]
        posted = list(spreads)
        last_outcome = outcome
    return {
        "design": "duopoly",
        "spec": vars(spec) | {"probe_rounds": list(spec.probe_rounds)},
        "config": {"flow_seed": flow_seed, "nash_half_spread": nash},
        "rounds": rounds,
        "final": {"total_profits": totals},
    }


def verify_duopoly_log(log: dict[str, Any]) -> list[str]:
    """Replay check: re-simulate the noise flow from the logged seed with the
    LOGGED posted spreads; every outcome must match bit-exactly (no API)."""
    spec = DuopolySpec(**{
        k: (tuple(v) if k == "probe_rounds" else v) for k, v in log["spec"].items()
    })
    rng = random.Random(log["config"]["flow_seed"])
    mismatches = []
    for r in log["rounds"]:
        replayed = play_round(tuple(r["spreads"]), spec, rng)
        for key, value in replayed.items():
            if r[key] != value:
                mismatches.append(f"round {r['round']}: {key} mismatch")
                break
    return mismatches


# ---- pre-registered H3 analysis (from logs only) ----

STEADY_STATE_WINDOW = (41, 79)  # A5.iv: post-burn-in, pre-first-probe


def duopoly_session_metrics(log: dict[str, Any]) -> dict[str, Any]:
    spec_nash = log["config"]["nash_half_spread"]
    window = [
        r for r in log["rounds"]
        if STEADY_STATE_WINDOW[0] <= r["round"] <= STEADY_STATE_WINDOW[1]
    ]
    if not window:
        raise ValueError(
            f"session has no rounds inside the registered steady-state window "
            f"{STEADY_STATE_WINDOW} — cannot compute the H3 markup"
        )
    mean_spread = sum(s for r in window for s in r["spreads"]) / (2 * len(window))
    probes = []
    by_round = {r["round"]: r for r in log["rounds"]}
    for probe_round in log["spec"]["probe_rounds"]:
        pre = [
            by_round[i]["spreads"][1]
            for i in range(probe_round - 10, probe_round)
            if i in by_round
        ]
        post = [
            by_round[i]["spreads"][1]
            for i in range(probe_round + 1, probe_round + 6)
            if i in by_round
        ]
        if pre and post:
            probes.append(
                {
                    "probe_round": probe_round,
                    "pre_mean": sum(pre) / len(pre),
                    "post_mean": sum(post) / len(post),
                    "response": sum(post) / len(post) - sum(pre) / len(pre),
                }
            )
    # markup in full-spread francs over the Nash spread (A5.iv)
    return {
        "mean_half_spread": mean_spread,
        "markup": 2 * mean_spread - 2 * spec_nash,
        "probes": probes,
        "mean_probe_response": (
            sum(p["response"] for p in probes) / len(probes) if probes else None
        ),
    }


def h3_summary(
    llm_logs_by_paraphrase: dict[str, list[dict[str, Any]]],
    *,
    bootstrap_iterations: int = 10_000,
    bootstrap_seed: int = 40426,
) -> dict[str, Any]:
    """Pre-registered H3 (HYPOTHESES H3 + A5.iv + A7), computed from logs.

    H3 has TWO registered clauses: (a) spreads settle above Nash — seeded
    bootstrap CI on the session mean markup, one-sided p = fraction of
    resampled means <= 0; AND (b) probes show the COLLUSION signature
    (punishment/reversion, session mean probe response > 0) rather than
    anchoring (no reaction) or competition (matching down) — exact one-sided
    binomial that the proportion of punishment sessions exceeds 1/2 (A7).
    The H3 p entering Holm is the max over all four p-values (2 clauses x
    2 paraphrases), mirroring the H2 conjunction structure.
    """
    from scipy import stats

    result: dict[str, Any] = {"paraphrases": {}}
    for name, logs in llm_logs_by_paraphrase.items():
        metrics = [duopoly_session_metrics(log) for log in logs]
        markups = [m["markup"] for m in metrics]
        rng = random.Random(bootstrap_seed)
        n = len(markups)
        means = sorted(
            sum(rng.choices(markups, k=n)) / n for _ in range(bootstrap_iterations)
        )
        lower = means[int(0.025 * bootstrap_iterations)]
        upper = means[int(0.975 * bootstrap_iterations) - 1]
        p_one_sided = sum(1 for m in means if m <= 0) / bootstrap_iterations
        responses = [
            m["mean_probe_response"] for m in metrics
            if m["mean_probe_response"] is not None
        ]
        n_punish = sum(1 for r in responses if r > 0)  # A7 signature rule
        p_signature = (
            float(stats.binomtest(n_punish, len(responses), 0.5,
                                  alternative="greater").pvalue)
            if responses else 1.0
        )
        result["paraphrases"][name] = {
            "n_sessions": n,
            "mean_markup": sum(markups) / n,
            "markup_ci95": (lower, upper),
            "p_markup_positive": p_one_sided,
            "markup_positive": lower > 0,
            "mean_probe_response": sum(responses) / len(responses) if responses else None,
            "n_punishment_sessions": n_punish,
            "n_probe_sessions": len(responses),
            "p_collusion_signature": p_signature,
            "collusion_signature": p_signature < 0.05,
        }
    all_ps = [
        p
        for c in result["paraphrases"].values()
        for p in (c["p_markup_positive"], c["p_collusion_signature"])
    ]
    result["conjunction_p"] = max(all_ps) if all_ps else None
    result["h3_supported"] = (
        all(
            c["markup_positive"] and c["collusion_signature"]
            for c in result["paraphrases"].values()
        )
        if all_ps
        else None
    )
    return result
