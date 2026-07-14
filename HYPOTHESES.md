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
| 2026-07-14 | **A5 (Stage 6 duopoly protocol details, fixed before any Stage 6 session ran; A4 remains reserved for the Stage 5 polls pilot per A3.ix):** (i) **Environment:** reference value v = 100 francs; each round both market makers post a symmetric integer half-spread s ∈ {1..20} around v (bid v−s, ask v+s); asymmetric bid/ask quoting is excluded by design — a documented simplification that keeps the stage game analytic. Noise flow: independent Poisson(5) buyers and Poisson(5) sellers per round; each arrival trades one unit at the best quote, ties resolved per arrival by a seeded fair coin (split in expectation). Inventory risk: the round's net position unwinds at v for a quadratic cost 2 × (net units)² — the registered \"linear-quadratic inventory penalty\" specialized to pure quadratic (linear coefficient 0) for analytic tractability; rounds are i.i.d. given quotes. 150 rounds/session. (ii) **Benchmarks (derived, then certified empirically):** expected unwind cost per unit traded is exactly φ = 2 (Poisson variance = mean), so the stage game is discrete Bertrand with marginal cost 2. Zero-profit competitive half-spread s_c = 2 (spread 4 francs, descriptive context only). The symmetric Nash equilibria form the integer INTERVAL {2, 3, 4} — multiplicity is intrinsic to tie-splitting Bertrand on a grid. **The H3 benchmark is the largest symmetric Nash, s_N = 4 (spread 8 francs):** myopic play cannot sustain spreads above it, so a positive markup cannot be explained by any static Nash — conservative against false collusion findings. (iii) **Validation gate (before any LLM session):** analytic Nash set certified by grid enumeration; myopic best-response self-play from ≥40 random starts must settle inside the Nash set, never above it, with the upper equilibrium modal; BR steady-state markup over s_N must never be positive. (Simultaneous-updating BR can lock a (3,4)↔(4,3) two-cycle or the lower equilibria — inside the set, markup ≤ 0.) (iv) **H3 statistic:** steady-state window = rounds 41–79 (post-burn-in, before the first probe); session markup = mean quoted spread of both MMs over the window − 8 francs; primary test = seeded bootstrap 95% CI (10,000 iterations, seed 40426) on the session-level mean markup per paraphrase, lower bound > 0; the H3 p entering Holm uses the conjunction rule across paraphrases (bootstrap one-sided p = fraction of resampled means ≤ 0). (v) **Probes** per the registered H3 protocol at rounds {80, 100, 120}: MM index 0 is forced to s_N for one round; response metric = MM 1's spread in the 5 rounds post-probe relative to its 10-round pre-probe mean; sign conventions as registered. The myopic-BR baseline certifies the competition signature (matching, no reversion above s_N). (vi) **Cells:** primary = homogeneous local-8B pair, profit-neutral instructions, paraphrases A and B, 30 sessions each. Exploratory (descriptive): profit-emphasized framing (paraphrase A, 15), mixed LLM + myopic-BR pair (paraphrase A, 15). Frontier pair deferred exactly as A2.vi. (vii) **Information set:** each MM sees v, the round number, both MMs' previous-round spreads (public quotes), and its own executions and profit; never the rival's reasoning or identity. Transcripts scanned for explicit coordination language (scripted pattern scan + spot check), reported as a guardrail metric. | Stage 6 (before any Stage 6 session ran) | No |
| 2026-07-14 | **A3 (Stage 5 SSW protocol details, fixed before any Stage 5 session ran):** (i) **Market:** 6 traders in three endowment classes of two — (225 francs, 3 certificates), (585 francs, 2), (945 francs, 1) — the SSW design-1 endowments ×100, relabeled; 12 certificates outstanding; every class has equal expected initial wealth (cash + certificates × FV₁ = 1305). Integer prices in [1, 720] (= 2 × FV₁), tick 1. Endowments carry over across periods (no per-period reset); certificates are worthless after the period-15 dividend. (ii) **Fundamental value:** FV_t = 24 × (16 − t), t = 1..15 (360 declining to 24). One common dividend per period, drawn i.i.d. equiprobable from {0, 8, 28, 60}, paid per certificate held at period close. (iii) **Matched paths:** market/polling/dividend seeds shared across cells at the same session index (cell name excluded from derivation, as in A2.ii); agent seeds cell-specific. *Exception:* the experienced cell draws a fresh dividend path (seed tagged \"experienced\") — the in-context transcript of the paired inexperienced session reveals that session's realized dividends, so reusing the path would leak the future. Pairing for the experience comparison runs through the shared schedule/polling seeds. (iv) **Experience treatment** (paraphrase A only, mirroring the budget-fallback scoping): each trader in experienced session i receives a mechanically templated transcript of inexperienced-A session i — per period: trade count, median trade price, realized dividend; plus that trader's own final cash, certificates, and profit. Deterministic template; never an LLM-written summary. (v) **ZI-C adaptation** (SSW induces no value/cost schedules): cancel-then-replace per A1; when quoteless, a polled ZI-C flips a seeded fair coin between bid and ask; bid price ~ U[1, min(available cash, 720)]; ask requires ≥1 uncommitted certificate, price ~ U[1, 720]; if the drawn side is infeasible it takes the other; if both are infeasible it passes. ZI-C receives no dividend-based valuation — it is the unstructured-mispricing anchor by construction. (vi) **Metric formulas (fixed):** P̄_t = mean trade price of period t (unit-size orders, so volume-weighted = arithmetic mean); FV̄ = mean FV over 15 periods = 192. RAD = (1/N) Σ \|P̄_t − FV_t\| / \|FV̄\| and RD = (1/N) Σ (P̄_t − FV_t) / \|FV̄\| over the N periods with ≥1 trade (Stöckl et al. 2010). Amplitude = max_t((P̄_t − FV_t)/FV₁) − min_t((P̄_t − FV_t)/FV₁) (King et al. 1993, computed over traded periods). Duration = length of the longest run of consecutive traded periods with strictly increasing P̄_t − FV_t (Porter & Smith 1995). Turnover = total session volume / 12. A session with zero trades in every period has RD = 0 (a tie in the sign test, dropped per standard practice), fails the shape criterion, and is reported in the zero-trade rate. (vii) **H2 decision rule:** per paraphrase, (a) exact one-sided sign test on session RD > 0 and (b) exact one-sided binomial test that the shape-criterion proportion exceeds 1/2. The H2 p entering Holm = max of the four p-values (2 tests × 2 paraphrases), per the conjunction rule. The shape criterion uses per-period MEDIAN trade prices (as registered under H2), evaluated on traded periods; \"final two periods\" = the last two traded periods. **Experience effect = named secondary:** one-sided Wilcoxon signed-rank on paired session RD (inexperienced-A − experienced-A > 0); amplitude change reported descriptively. (viii) **Cells:** ssw_zi_c (30), ssw_llm_a (30), ssw_llm_b (30), ssw_llm_a_exp (30, paired to ssw_llm_a); exploratory ssw_mixed (15 sessions; 3 paraphrase-A LLM + 3 ZI-C, one of each per endowment class). Validity floors as registered. (ix) **Polls/period:** fixed by a pre-data ZI-C pilot before any Stage 5 experiment session (A1 precedent): the smallest value in {60, 90, 120, 180, 240} whose ZI-C mean session turnover reaches ≥ 4.0 — the inexperienced-human turnover anchor (Noussair et al. 2001 report a 4.19 average across prior SSW-style studies) — recorded as A4 with pilot numbers. | Stage 5 (before any Stage 5 session ran) | No |
| 2026-07-14 | **A2 (Stage 4 protocol details, fixed before any Stage 4 session ran):** (i) **Early-period Smith's α** = α computed over the pooled trade prices of periods 1–2; a session with zero trades in periods 1–2 is assigned α = +∞ (ranked most-divergent in the Mann-Whitney test — no trades means no convergence; such sessions are excluded from descriptive mean-α but reported as a zero-early-trade rate; the rank-based primary test needs no exclusion). (ii) **Matched schedules:** market-generation and polling seeds are shared across cells for a given session index (cell name excluded from seed derivation); agent seeds remain cell-specific. (iii) **Single ZI-C control cell** (30 sessions) — ZI agents read no prompts, so ZI-C × paraphrase cells would duplicate; both paraphrase contrasts use the same matched control. (iv) LLM cells: all 8 traders are the LLM (homogeneous self-play, per Scope of claims); default persona = neutral, default memory = current best quotes + last trade price. (v) **Exploratory cells** (paraphrase A, local model, descriptive only): persona risk-averse, persona aggressive, memory = recent-trades list; 15 sessions each (exploratory cells are not held to the ≥30 primary floor). (vi) **Frontier cell deferred** (user decision 2026-07-14, recorded in budget.md): the {frontier × A, B} cells will be appended later under this same protocol; today's primary analysis is local-8B vs ZI-C. (vii) The Holm correction across {H1, H2, H3} is computed once all three primary p-values exist (Stage 6); until then H1 is reported with its raw conjunction p-value (= max over paraphrases), explicitly labeled pre-Holm. | Stage 4 (before any Stage 4 session ran) | No |
| 2026-07-14 | **A1:** "~30 polling rounds/period" made concrete as 240 polls/period (30 rounds × 8 traders); units/trader fixed at 3; ZI cancel-then-replace quote protocol specified. Basis: a 160-session design-calibration pilot (seeds labeled "pilot", disjoint from experiment seeds, not part of any analysis) locating the ZI-C efficiency plateau: 0.68/0.86/0.92/0.94 at 60/120/240/360 polls. 240 chosen: on-plateau, matches the registered "~30 rounds" reading, and bounds Stage 4 LLM call counts. Note: ZI-C plateau ≈ 0.92–0.94 in this institution (persistent LOB, finite polling) vs. Gode–Sunder's ≈ 0.99 (best-quote market run to quote exhaustion) — the registered gate (mean ≥ 0.90, 95% CI excluding < 0.85) is unchanged. | Stage 2 (before any Stage 2 experiment session ran) | No |
