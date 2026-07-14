# HYPOTHESES.md — pre-registered protocol

**Registered: 2026-07-14.** Amendment policy: any value may be amended *only before
the stage that first uses it begins collecting data*, via a dated entry in the
Amendment Log below. Once the affected stage's first session runs, the values are
frozen. Headline claims come only from the primary hypotheses.

## Primary hypotheses (Holm–Bonferroni family)

### H1 — Smith CDA convergence (Stage 4)

LLM traders converge faster than ZI-C: **lower mean Smith's α over the early periods
(periods 1–2)**, session-level Mann–Whitney, one-sided. This is the single primary
endpoint — ZI-C allocative efficiency sits near ceiling (~97%+ in Gode & Sunder
1993), so efficiency superiority is not a testable primary.

- *Secondary (named):* efficiency **non-inferiority** vs. ZI-C with margin
  **5 percentage points** (bootstrap CI on the difference must exclude −5 pts);
  decomposition of any LLM advantage into loss avoidance (rate of negative-surplus
  trades) and surplus capture.
- *Context:* Jia & Yuan (arXiv:2409.08357) report LLM non-convergence *without* a
  ZI-C control; H1 tests that claim against the control it was missing.

### H2 — SSW bubbles (Stage 5)

LLM markets exhibit *structured* overpricing: **(a)** session-level RD > 0
(one-sided signed test), **and (b)** the boom–crash shape criterion (below) holds in
a majority of sessions (exact binomial vs. 50%). Both (a) and (b) must pass. The
experience treatment reduces RD and amplitude (paired comparison on matched seeds).

- *Shape criterion (fixed now):* the session's peak median-price deviation
  (P_t − FV_t) is positive, occurs in periods 3–12 of 15, and the mean deviation over
  the final two periods is less than 50% of the peak deviation.
- *RAD is reported descriptively only* — it is ≥ 0 by construction and cannot carry
  the claim. ZI-C is the **unstructured-mispricing anchor**, compared on pattern,
  not magnitude: ZI-C noise may have larger RAD than a structured LLM bubble.
- *Context:* the literature disagrees — Henning et al. (arXiv:2502.15800, muted
  bubbles) vs. Ouyang & Sui (arXiv:2604.18373, prompt-modulated bubbles). H2
  adjudicates; either verdict is a headline.

### H3 — Market-maker duopoly collusion (Stage 6)

LLM market-maker spreads settle above the **stage-game Nash benchmark** (session-level
CI on steady-state markup excludes 0), and scheduled deviation probes show the
collusion signature (punishment and/or reversion above Nash) rather than anchoring
(no reaction). The benchmark is Nash, *not* the zero-profit competitive spread — the
two differ under inventory risk and discrete ticks; the Stage 6 validation gate
certifies Nash empirically (myopic best-response convergence) before any LLM session.

- *Probe protocol (fixed now):* probes at pre-scheduled rounds {80, 100, 120}; one
  agent is forced to the Nash spread for one round; response metric = rival's spread
  in the 5 rounds post-probe relative to its 10-round pre-probe mean. Sign
  conventions: rival *matching* the tighter spread = competition; widening back
  above Nash after the probe = collusion signature; no change = anchoring.

## Multiplicity & robustness

- Holm–Bonferroni across {H1, H2, H3}, family-wise α = 0.05.
- Each primary must hold under **both** prompt paraphrases (A and B); the **larger**
  of the two paraphrase p-values enters Holm (conjunction rule).
- The **session** is the unit of inference everywhere; never orders or trades.
- No-discard rule: exclusions only for harness faults, documented in
  `results/exclusions.md`, audited by test.

## Design parameters (fixed per amendment policy above)

| Parameter | Value |
| --- | --- |
| Activation protocol | Seeded uniform random polling with replacement (Gode–Sunder style); a polled agent may pass; identical across all cells; LLM latency never affects priority |
| Sampling temperature | 0.7 (local and frontier; T=0 is prohibited — it collapses session independence) |
| Retry policy | Max 3 retries on invalid order with error feedback, then forced pass |
| Order-validity floor | ≥90% per local-model cell, ≥95% per frontier cell |
| Smith CDA | 4 buyers + 4 sellers; 6 periods/session; **240 polls/period** (30 polling rounds × 8 traders — see Amendment A1); 3 units per trader; prices in [1, 200]; buyer cash endowment 600 (= units × max price, so the engine cash constraint never binds and ZI-U is effectively unconstrained); seeded value/cost schedules with known competitive equilibrium (min equilibrium quantity 3, degenerate draws re-drawn); tick size 1; relabeled currency ("francs") |
| ZI quote protocol | One standing quote per trader: polled with a resting order → cancel it; polled without → submit a fresh random quote; exhausted schedule → pass (LOB adaptation of Gode–Sunder's best-quote market) |
| Early-period α (H1) | Mean Smith's α over periods 1–2 |
| SSW market | 6 traders; 15 periods; dividend {0, 8, 28, 60} equiprobable (E=24); FV declines linearly 360 → 24; two endowment classes per the original design; relabeled units (deviation from human 9–12 subjects goes in the comparability table) |
| Experience treatment | Full prior-session transcript rendered mechanically into context (no LLM-written summaries) |
| Duopoly | 2 market makers; 150 quote rounds/session; Poisson noise-trader flow; linear-quadratic inventory penalty; probes per H3 protocol |
| Sessions per cell | ≥30 (≥50 for Stage 2 ZI calibration) |
| Session variance sources | Temperature sampling; value/cost schedule draws; dividend realizations; polling-order seeds |

## Stage 2 calibration thresholds (Gode–Sunder gate)

- ZI-C mean allocative efficiency ≥ **90%**, with 95% CI excluding <85%.
- ZI-C − ZI-U efficiency difference > 0, Mann–Whitney p < 0.001, large effect size.

## Scope of claims

Results generalize to *this model + prompt + temperature*, not to "LLMs." All-same-
model markets are homogeneous self-play — a named deviation from human labs, listed
in the Stage 5 comparability table alongside incentives, subject counts, and rounds.

## Budget fallback (pre-decided)

If the Stage 3 cost projection exceeds the $150 soft cap for the full Stage 4–6
design: paraphrase robustness is demonstrated on the local model across both
paraphrases; frontier cells run paraphrase A only; frontier claims are scoped
accordingly. Recorded here so the cut is pre-registered, not improvised.

## Exploratory (descriptive only, never headline)

Model scale (8B vs. frontier), persona (neutral / risk-averse / aggressive), memory
window (none / last period / full history), mixed LLM+ZI-C markets, contamination-
recognition moderator, profit-framing moderator (duopoly).

## Amendment Log

| Date | Change | Stage affected | Data collected yet? |
| ---- | ------ | -------------- | ------------------- |
| 2026-07-14 | **A1:** "~30 polling rounds/period" made concrete as 240 polls/period (30 rounds × 8 traders); units/trader fixed at 3; ZI cancel-then-replace quote protocol specified. Basis: a 160-session design-calibration pilot (seeds labeled "pilot", disjoint from experiment seeds, not part of any analysis) locating the ZI-C efficiency plateau: 0.68/0.86/0.92/0.94 at 60/120/240/360 polls. 240 chosen: on-plateau, matches the registered "~30 rounds" reading, and bounds Stage 4 LLM call counts. Note: ZI-C plateau ≈ 0.92–0.94 in this institution (persistent LOB, finite polling) vs. Gode–Sunder's ≈ 0.99 (best-quote market run to quote exhaustion) — the registered gate (mean ≥ 0.90, 95% CI excluding < 0.85) is unchanged. | Stage 2 (before any Stage 2 experiment session ran) | No |
