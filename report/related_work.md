# Related work — Day-1 literature sweep (Stage 0)

Swept 2026-07-14 (arXiv/SSRN, 2024–26): LLM agents in double auctions, asset-market
experiments, and algorithmic collusion. Per paper: setup, findings, and what it lacks
relative to this project's claimed edge (ZI baselines + human-data anchoring +
deviation probes + log-and-replay reproducibility). Verdict at the bottom.

## Directly adjacent papers

### Jia & Yuan (2024) — "An Experimental Study of Competitive Market Behavior Through LLMs" (arXiv:2409.08357)

- **Setup:** Smith-style controlled market setting with LLM agents (GPT-4-class),
  testing convergence toward competitive equilibrium.
- **Findings:** LLMs *failed* to achieve market equilibrium, unlike human subjects;
  authors conclude current LLMs fall short of replicating dynamic trading behavior.
- **Lacks:** no ZI-C baseline (so "failed to converge" has no institution-only
  anchor — Gode–Sunder says the *market* converges even with random traders, which
  makes non-convergence a strong and surprising claim needing exactly that control);
  no Smith's α against published human numbers; no pre-registration; no
  log-and-replay artifact. **Directly relevant to H1 — cite and test against.**

### Henning, Ojha, Spoon, Han & Camerer (2025) — "LLM Agents Do Not Replicate Human Market Traders" (arXiv:2502.15800)

- **Setup:** established experimental-finance design (risky asset, known fundamental
  value — SSW-family), single-model and mixed "battle royale" LLM markets.
- **Findings:** LLMs price near fundamental value ("textbook-rational"), show *muted*
  bubble formation and far less strategy variance than humans.
- **Lacks (from abstract; verify in full text before Stage 5):** ZI baseline,
  experience treatment, contamination protocol, pre-registered primaries,
  replayable logs. **Directly relevant to H2 — predicts H2 fails.**

### Ouyang & Sui (2026) — "Dissecting AI Trading: Behavioral Finance and Market Bubbles" (arXiv:2604.18373)

- **Setup:** simulated multi-period *open-call* auction (not a CDA) of LLM agents,
  in the Smith et al. (1988) framework.
- **Findings:** LLM agents show disposition effects and extrapolative beliefs that
  aggregate into SSW-like dynamics; prompt interventions causally amplify/suppress
  bubbles.
- **Lacks:** continuous double auction (open call ≠ CDA — price formation differs);
  ZI anchor; experience treatment; pre-registration; contamination protocol.
  **Directly relevant to H2 — predicts H2 holds.**

> Henning et al. and Ouyang & Sui **disagree** on whether LLM markets bubble. That
> converts H2 from "does a known human result replicate?" into **adjudicating a live
> disagreement** with a cleaner design (CDA, ZI-C anchor, experience treatment,
> contamination probe, pre-registered shape criterion). This strengthens, not
> weakens, the case for Stage 5.

### Fish, Gonczarowski & Shorrer (2024) — "Algorithmic Collusion by Large Language Models" (arXiv:2404.00806)

- **Setup:** LLM-based *pricing* agents in repeated Bertrand oligopoly (and auction
  extensions).
- **Findings:** agents quickly and autonomously reach supracompetitive prices;
  seemingly innocuous prompt phrasing substantially modulates collusion; behavioral
  analysis surfaces "price-war concern" as a mechanism.
- **Lacks:** market-*making* setting (no inventory risk, no spread-setting against
  stochastic order flow); no Calvano-style deviation–punishment probes as the
  identification strategy; no validated Nash-vs-zero-profit benchmark distinction.
  **The canonical citation for H3; our duopoly is the microstructure analog with an
  interventionist identification.** Their prompt-sensitivity result independently
  motivates our profit-neutral vs. profit-emphasized cells and paraphrase pairs.

### Agrawal, Teo, Vazquez, Kunnavakkam, Srikanth & Liu (2025) — "Evaluating LLM Agent Collusion in Double Auctions" (arXiv:2507.01413)

- **Setup:** CDA with LLM *sellers*; manipulates seller-to-seller communication,
  model choice, oversight/urgency pressure.
- **Findings:** direct communication increases collusion; propensity varies by model
  and environmental pressure.
- **Lacks:** their headline channel is *explicit communication* — our design bans it
  (agents see only market data), targeting *tacit* collusion; no deviation probes,
  no competitive/Nash benchmark validation, no replay artifact.

## Second-ring papers

- **Lopez-Lira (2025) — "Can Large Language Models Trade?" (arXiv:2504.10789):**
  general LLM market-simulation framework (heterogeneous agent archetypes, realistic
  microstructure). A framework paper — no pre-registered hypothesis tests against
  human-lab numbers, no ZI anchoring. Useful for design comparisons.
- **"Strategic Collusion of LLM Agents: Market Division in Multi-Commodity
  Competitions" (arXiv:2410.00031):** Cournot variant; LLM agents divide markets.
  Different institution (quantity competition), same theme as H3.
- **"Prompt Optimization Enables Stable Algorithmic Collusion in LLM Agents"
  (arXiv:2604.17774):** optimization discovers collusive strategies (anchor
  tracking, cliff detection). Adjacent to H3's prompt-framing moderator.

## Scope verdict (gate item: confirmed / amended)

**Confirmed, with one repositioning.** No paper combines (a) a provably correct CDA
engine with a Gode–Sunder ZI calibration gate, (b) pre-registered hypotheses anchored
to published human-lab numbers, (c) a contamination protocol, (d) deviation–punishment
probes against a *validated* Nash benchmark in a market-making duopoly, and
(e) log-and-replay reproducibility verifiable without an API key. The claimed edge
survives contact with the literature.

Repositioning: **H2 is now framed as adjudicating the Henning-et-al. vs. Ouyang–Sui
disagreement** (muted bubbles vs. prompt-modulated bubbles) rather than as a first
demonstration — both directions of the H2 verdict are publishable-quality headlines.
H1 must engage Jia & Yuan's non-convergence claim, which lacks the ZI-C control that
our design makes central. Action for Stage 5 prep: read Henning et al. and
Ouyang & Sui in full to confirm neither runs a ZI-anchored CDA experience treatment.
