# Do LLM markets converge, bubble, or collude?

**Replicating three canonical human-subject market experiments with LLM traders,
anchored to zero-intelligence baselines, under a pre-registered protocol.**

*All numbers in this report are claims in [CLAIMS.md](../CLAIMS.md), each with a
green assert in a committed notebook and a pytest test that recomputes it from the
raw session logs. Verification requires no API key ([REPRODUCING.md](../REPRODUCING.md)).*

## The question

Experimental economics spent four decades establishing three benchmark facts about
human markets: continuous double auctions converge to competitive equilibrium
(Smith 1962), asset markets with declining fundamentals bubble and crash
(Smith–Suchanek–Williams 1988), and repeated pricing games can sustain
supra-competitive outcomes. A growing literature drops LLM agents into such markets
and reports conflicting answers — non-convergence (Jia & Yuan 2024) without the
control that claim needs, muted bubbles (Henning et al. 2025) vs prompt-modulated
bubbles (Ouyang & Sui 2026). This project re-runs the three canonical designs with
LLM traders and asks each question against the control the literature has mostly
skipped: **Gode & Sunder's (1993) zero-intelligence traders**, which separate what
the *institution* produces from what *intelligence* adds.

Three hypotheses were pre-registered (HYPOTHESES.md, dated before any experimental
session ran; amendments only before the affected stage collected data, in a dated
log): **H1** — LLM traders converge faster than ZI-C in the Smith CDA; **H2** — LLM
asset markets bubble (RD > 0 plus a boom–crash shape criterion); **H3** — LLM
market-maker pairs settle above the stage-game Nash spread *and* probes show the
collusion signature. Holm–Bonferroni across the family; each primary must hold under
two independently worded instruction templates (paraphrases A and B); the session is
the unit of inference; no-discard rule with an audited exclusions log.

## The machine

- **Deterministic exchange engine** (continuous double auction, price-time priority,
  integer ticks): replaying a session's event log reproduces every trade bit-exactly
  — the property-tested backbone of a *log-and-replay* reproducibility spine. All
  statistics compute from committed JSONL logs, never from live API calls.
- **Calibration certificate:** ZI-C traders in our institution achieve 0.928 mean
  allocative efficiency vs −0.214 for unconstrained ZI-U (Mann-Whitney p < 0.001,
  rank-biserial 1.000) — the Gode–Sunder result replicates qualitatively before any
  LLM enters (notebook 01).
- **LLM harness:** strict JSON order schema, semantic validation, bounded
  retry-with-feedback, full capture (one log record per API call, sessions invalid
  by construction if a record is missing). Local model pinned by exact HF revision
  (Qwen2.5-7B-Instruct @ a09a3545…, vLLM 0.25.0, T = 0.7); order-validity 0.99+ in
  every experimental cell. Contamination protocol: paraphrased, unnamed, relabeled
  instructions; an out-of-band probe shows the model *recognizes* the double-auction
  design in 100% of probes (reported as a moderator); zero in-session recognition
  flags across all cells.
- **Matched-cell design:** market schedules, polling order, dividend paths, and
  noise flow are seed-matched across cells at each session index, so every
  comparison is within identical markets.

## Experiment 1 — Smith convergence (H1): the LLM loses to zero intelligence

30 matched sessions per cell, 4 buyers + 4 sellers, 6 periods.

| | LLM (A) | LLM (B) | ZI-C control |
|---|---|---|---|
| Early-period Smith's α | 61.4 | 51.5 | 36.5 |
| Allocative efficiency | 0.22 | 0.18 | 0.92 |
| Trades/session | 14.1 | 51.2 | 32.7 |
| Loss-making trade sides | 34.8% | 46.8% | 0% (impossible by construction) |

**H1 not supported — reversed** (one-sided MW p = 0.998; efficiency non-inferiority
fails in both paraphrases). The decomposition kills the obvious deflations: only
0.1–0.2% of the LLM's passes are harness-forced (validity 0.998/0.999), and trades
land early in periods, so neither a parsing confound nor horizon truncation explains
it. The mechanism is twofold: reluctant participation *and* poor price judgment —
paraphrase B actually out-trades ZI-C and still loses, because nearly half its trade
sides are loss-making. ZI-C cannot lose money by construction; the 7B model can, and
does. This corroborates Jia & Yuan's non-convergence claim with the control their
design lacked, and sharpens it: at this scale, *constraint beats cognition*.

## Experiment 2 — SSW bubbles (H2): no bubbles — inverted markets

30 matched sessions per cell, 6 traders, 15 periods, FV declining 360 → 24.

| | LLM (A) | LLM (B) | Experienced (A) | ZI-C anchor |
|---|---|---|---|---|
| Mean session RD | −0.59 | −0.59 | −0.38 | +0.82 |
| Boom–crash shape | 0/30 | 0/30 | 0/30 | 0/30 |
| Turnover | 3.40 | 0.14 | — | ≫ human |

**H2 not supported** (conjunction p = 1.000). Where human subjects famously
overprice, this model *under*prices by ~60% of mean fundamental value — beyond
"muted bubbles," the markets are inverted. The direction is paraphrase-robust; the
mechanism is not: paraphrase A trades at human-scale volume far below FV, while
paraphrase B barely trades and — in 7 of 30 sessions — makes exactly one trade, in
period 15, at exactly 24 francs: the terminal fundamental value. The registered
experience secondary fails *as registered* (it presupposed overpricing), but
descriptively experience halves mispricing magnitude (−0.59 → −0.38): the
calibration analogue of the human experience effect, in the opposite half-plane.
The exploratory mixed market (3 LLM + 3 ZI-C) flips to RD +0.94 — reluctant LLM
sellers thin supply against random bidders — a warning that composition, not just
cognition, sets the sign of mispricing.

## Experiment 3 — duopoly (H3): supra-Nash spreads without collusion

Two dealers quote symmetric half-spreads for 150 rounds; Poisson customer flow;
quadratic inventory unwind. The parameterization makes the stage game *exactly*
discrete Bertrand with marginal cost 2, so both benchmarks are analytic: zero-profit
spread 4 francs, largest stage-game Nash spread 8 francs. A pure-simulation gate
certifies, before any LLM session, that myopic best-response play settles inside the
Nash set and can never sustain a positive markup over the benchmark — so a positive
markup cannot be explained by any static Nash.

| | LLM pair (A) | LLM pair (B) | mixed (LLM vs myopic BR) |
|---|---|---|---|
| Markup over Nash spread | +27.42 [26.68, 28.03] | +17.35 [15.06, 19.61] | +4.05 |
| Probe response (rival) | −1.53 | −1.99 | — |
| Punishment sessions | 2/30 | 1/30 | — |

**H3 not supported.** The markup clause holds overwhelmingly — but the registered
probe clause decisively fails: when one dealer is forced to the Nash spread, the
rival *matches down* (the registered competition signature), then drifts back to its
wide habit without ever overshooting — recovery toward passivity, not a punishment
phase. Against a rival that actually undercuts, the markup collapses to +4.05. The
profit-emphasized framing changes nothing (+27.90). Zero coordination-language flags
in 60 sessions. The honest headline: **supra-competitive pricing sustained by mutual
failure to undercut, not by collusion machinery** — a distinction the deviation
probes were pre-registered to draw, and one that a markup-only analysis would have
gotten wrong.

## Family verdict

Holm-adjusted across {H1, H2, H3}: **0/3 supported.** Every negative is informative,
and together they cohere: a 7B LLM in market institutions is neither the rational
trader of H1, the exuberant human of H2, nor the strategic colluder of H3 — it is a
*passive, poorly calibrated participant* whose outcomes are dominated by what the
institution and the population composition do with its passivity.

## Limitations (named, not buried)

1. **Scope:** results are claims about *this model + prompts + temperature*
   (Qwen2.5-7B-Instruct, two paraphrases, T = 0.7) — not about "LLMs." Frontier
   cells are pre-registered, budgeted (~$57 at Haiku-tier), and deferred with
   configs ready; the pre-registered fallback scopes any budget cut.
2. **Contamination:** the model verbalizes recognition of the double-auction design
   in 100% of out-of-band probes. Instructions are paraphrased/relabeled and zero
   in-session recognition flags appeared, but training-data familiarity cannot be
   ruled out as a moderator — it is reported, not hidden.
3. **Homogeneous self-play:** 30 sessions of one model at one temperature are draws
   from one policy, not 30 independent subjects; session-to-session variance comes
   from seeds, schedules, dividends, and sampling.
4. **Institution deviations:** persistent limit-order book with finite seeded
   polling vs Gode–Sunder's best-quote market (ZI-C plateau ≈ 0.93 vs their ≈ 0.99);
   no real monetary incentives; 6 traders vs 9–12 humans in SSW; ZI-C turnover far
   exceeds human magnitude (pattern comparisons only). Each deviation is tabulated
   alongside the human anchors it qualifies.
5. **Frontier replay-only asymmetry:** local-model cells are re-runnable against the
   pinned revision; any future frontier cells are archival (providers retire
   models) — verifiable by replay, not by re-query.

## Reproducing

Tier 1 (≤10 min, no API key): `uv sync --frozen`, run the numbered notebooks — every
headline number asserts against CLAIMS.md. Tier 2 (≈1 min): `uv run python -m
agentic_trading.reproduce --tier 2` verifies the log manifest and recomputes every
statistic from raw logs via the full test suite. See REPRODUCING.md for Tier 3.
