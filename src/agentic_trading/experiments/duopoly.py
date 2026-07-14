"""Market-maker duopoly & tacit collusion experiment (Stage 6).

Responsibilities:
- Two quote-setting market makers, stochastic noise-trader flow,
  inventory risk; long-horizon repeated play.
- Dual analytic benchmarks: zero-profit competitive spread AND stage-game
  Nash spread (they differ under inventory risk / discrete ticks).
  Benchmark validation gate: myopic best-response agents must converge to
  Nash before any LLM session runs. H3 markup is measured against Nash.
- Deviation–punishment probes (Calvano-style): force one agent to the Nash
  spread for one round; rival matching = competition, punishment/reversion
  above Nash = collusion signature. Probe analysis pre-registered.
"""
