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
from typing import Any


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
