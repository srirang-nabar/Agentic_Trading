"""Smith–Suchanek–Williams (1988) asset-market bubble experiment (Stage 5).

Design fixed in HYPOTHESES.md (H2 + Amendment A3):
- 15-period asset market; one common dividend per period drawn i.i.d.
  equiprobable from {0, 8, 28, 60} francs per certificate (E = 24);
  fundamental value declines linearly 360 -> 24.
- 6 traders in three endowment classes of two — (225 francs, 3 certificates),
  (585, 2), (945, 1) — the SSW design-1 endowments x100, relabeled; every
  class has equal expected initial wealth 1305; 12 certificates outstanding.
- Endowments carry over across periods (no per-period reset); certificates
  are worthless after the period-15 dividend.
- Instructions follow the contamination protocol (relabeled, never named).

This module is pure data generation: trader endowments are deterministic
(class assignment round-robin by trader index), the dividend path is drawn
from the supplied seeded RNG so matched cells share it (A3.iii). Engine
integration (endowment policy, dividend accounting) lives in the runner.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SSWMarketSpec:
    n_periods: int = 15
    dividend_values: tuple[int, ...] = (0, 8, 28, 60)
    # (cash endowment in francs, certificates) per class, two traders each
    endowment_classes: tuple[tuple[int, int], ...] = ((225, 3), (585, 2), (945, 1))
    traders_per_class: int = 2
    price_low: int = 1
    price_high: int = 720

    @property
    def n_traders(self) -> int:
        return len(self.endowment_classes) * self.traders_per_class

    @property
    def shares_outstanding(self) -> int:
        return self.traders_per_class * sum(s for _, s in self.endowment_classes)

    @property
    def expected_dividend(self) -> float:
        return sum(self.dividend_values) / len(self.dividend_values)

    def fundamental_value(self, period: int) -> float:
        """FV at period t = E[dividend] x remaining periods including t."""
        return self.expected_dividend * (self.n_periods - period + 1)


@dataclass(frozen=True)
class SSWMarket:
    spec: SSWMarketSpec
    # (trader_id, cash, certificates), class assignment interleaved so
    # consecutive trader indices cycle through the classes
    traders: tuple[tuple[str, int, int], ...]
    dividends: tuple[int, ...] = field(default=())  # realized path, one per period


def generate_ssw_market(spec: SSWMarketSpec, rng: random.Random) -> SSWMarket:
    """Endowments are deterministic; only the dividend path consumes the RNG.

    Matched cells therefore share the dividend path when they share the
    market seed (HYPOTHESES A3.iii), exactly as Smith cells share schedules.
    """
    traders = tuple(
        (f"T{i + 1}", cash, shares)
        for i, (cash, shares) in enumerate(
            spec.endowment_classes[i % len(spec.endowment_classes)]
            for i in range(spec.n_traders)
        )
    )
    dividends = tuple(rng.choice(spec.dividend_values) for _ in range(spec.n_periods))
    return SSWMarket(spec=spec, traders=traders, dividends=dividends)
