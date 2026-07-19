# Reviewer summary — Market Experiments with LLM Agents (Multi-Agent Systems, Experimental Economics)

**One paragraph.** Experimental economics spent 40 years establishing how *human* markets behave:
double auctions converge to equilibrium (Smith 1962), asset markets bubble (Smith–Suchanek–Williams
1988), and even budget-constrained *random* traders achieve high efficiency (Gode–Sunder 1993 — the
control recent LLM-market papers skip). This project rebuilds those three canonical experiments with
LLM agents as the traders on a property-tested, bit-exact-replayable exchange engine, under a
pre-registered protocol (Holm-corrected; ≥30 sessions/cell; no-discard rule). Every statistic computes
from committed session logs, so a reviewer can verify everything **without an API key**.

**Findings (0/3 pre-registered hypotheses supported — each negative is a specific finding):**

| Question | Result |
| -------- | ------ |
| Do LLM traders out-converge zero-intelligence? | **No — reversed.** The 8B LLM *loses* to ZI-C: efficiency 0.22 vs 0.92 in seed-matched markets, with 35–47% loss-making trades random-but-constrained agents cannot make |
| Do LLM asset markets bubble? | **No — inverted.** Markets priced ~60% *below* fundamentals (RD −0.59 vs ZI-C's +0.82) under both instruction paraphrases; experience halves the mispricing |
| Do competing LLM dealers collude? | **Supra-Nash without collusion.** Spreads sat +27 francs above the certified competitive benchmark, but deviation probes showed *matching* (competition signature), not punishment — passivity, not cartel |

**How to review quickly (~5 min):**

**Fastest path: `notebooks/00_review_walkthrough.ipynb`** — a single commented, pre-executed notebook backing every resume point, with the asserts inline.

1. Open `notebooks/03_smith_convergence.ipynb`, `04_ssw_bubbles.ipynb`, `05_duopoly_collusion.ipynb` —
   commented, pre-executed, each asserts its headline row against CLAIMS.md from committed logs.
2. Optional: `uv sync --frozen && uv run pytest -q` (194 gate tests) — runs key-less; fresh-machine log
   in `results/fresh_machine_run.log` (Tier 1 + Tier 2, no API key).

**Scope honesty:** results are for one pinned 8B open model (Qwen2.5-7B) + these prompts/temperature;
frontier-model cells are pre-registered and budgeted but deferred; the model *recognizes* the classic
experimental designs in out-of-band probes (100%) yet still shows none of the human behaviors.
