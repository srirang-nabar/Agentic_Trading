"""Zero-intelligence agents per Gode & Sunder (1993) (Stage 2).

Responsibilities:
- ZI-U: unconstrained uniform-random bids/asks.
- ZI-C: budget-constrained random — buyers never bid above private value,
  sellers never ask below private cost.
- Fully seeded; pure functions of (private values, RNG state, market state)
  so Stage 2 runs are bit-reproducible from config.

ZI-C is the mandatory baseline in every experiment: it separates what the
market institution does from what agent intelligence adds.
"""
