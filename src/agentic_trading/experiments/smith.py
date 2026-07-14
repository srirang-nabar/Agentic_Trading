"""Smith (1962) induced-value CDA market generation (Stages 2 & 4).

Markets are drawn from a seeded generator with a known competitive
equilibrium: each buyer gets `units_per_trader` redemption values and each
seller the same number of unit costs, uniform on [price_low, price_high].
Degenerate draws (fewer than `min_equilibrium_quantity` equilibrium trades,
so thin that efficiency is meaningless) are re-drawn deterministically from
the same RNG stream.

Buyer cash endowment comes from the config; the Stage 2 baseline uses
units x max price so the engine's cash-feasibility constraint never binds —
required for ZI-U to be genuinely "unconstrained" in the Gode–Sunder sense.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentic_trading.exchange import TraderConfig
from agentic_trading.metrics import Equilibrium, equilibrium


@dataclass(frozen=True)
class SmithMarketSpec:
    n_buyers: int = 4
    n_sellers: int = 4
    units_per_trader: int = 3
    price_low: int = 1
    price_high: int = 200
    cash_endowment: int = 600  # units_per_trader * price_high
    min_equilibrium_quantity: int = 3


def generate_smith_market(
    rng: random.Random, spec: SmithMarketSpec
) -> tuple[list[TraderConfig], Equilibrium]:
    """Draw one market with a well-defined competitive equilibrium."""
    max_supply = spec.n_sellers * spec.units_per_trader
    max_demand = spec.n_buyers * spec.units_per_trader
    if spec.min_equilibrium_quantity > min(max_supply, max_demand):
        raise ValueError(
            f"min_equilibrium_quantity={spec.min_equilibrium_quantity} is impossible: "
            f"the market has at most {min(max_supply, max_demand)} tradeable units"
        )
    for _ in range(100_000):
        buyers = [
            TraderConfig(
                trader_id=f"B{i + 1}",
                cash=spec.cash_endowment,
                values=tuple(
                    sorted(
                        (rng.randint(spec.price_low, spec.price_high)
                         for _ in range(spec.units_per_trader)),
                        reverse=True,
                    )
                ),
            )
            for i in range(spec.n_buyers)
        ]
        sellers = [
            TraderConfig(
                trader_id=f"S{i + 1}",
                costs=tuple(
                    sorted(
                        rng.randint(spec.price_low, spec.price_high)
                        for _ in range(spec.units_per_trader)
                    )
                ),
            )
            for i in range(spec.n_sellers)
        ]
        eq = equilibrium(
            [v for b in buyers for v in b.values],
            [c for s in sellers for c in s.costs],
        )
        if eq.quantity >= spec.min_equilibrium_quantity and eq.price_low <= eq.price_high:
            return buyers + sellers, eq
    raise RuntimeError("could not draw a non-degenerate market in 100k attempts")
