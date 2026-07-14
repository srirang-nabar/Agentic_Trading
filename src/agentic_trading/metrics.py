"""Market metrics (Stages 2 & 5).

Responsibilities:
- Allocative efficiency (realized surplus / maximum surplus).
- Smith's α convergence coefficient; price-path RMSE vs. equilibrium.
- Bubble metrics per Stöckl et al. (2010): RAD, RD, amplitude, duration,
  turnover — unit-tested against hand-worked examples from the paper.

Every metric is unit-tested on hand-computable toy sessions before use.
All metrics compute from session logs, never from live state.
"""
