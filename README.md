# Market Experiments with LLM Agents (Multi-Agent Systems, Experimental Economics)

*a.k.a. Agentic Trading*

Do markets of LLM traders converge, bubble, and collude? This project rebuilds the
canonical human-subject market experiments — Smith's (1962) continuous double
auction, the Smith–Suchanek–Williams (1988) bubble design, and market-maker duopoly
competition — with LLM agents as the traders. Every result is anchored to a
Gode–Sunder zero-intelligence baseline and to published human-lab numbers, under a
pre-registered protocol ([HYPOTHESES.md](HYPOTHESES.md)).

## Headline numbers

> Filled in as stage gates pass; every number in this table has a matching row in
> [CLAIMS.md](CLAIMS.md) and a green assert in a committed notebook.

| # | Question | LLM | ZI-C baseline | Human-lab anchor | Verdict |
| - | -------- | --- | ------------- | ---------------- | ------- |
| 1 | Smith CDA: convergence (early-period Smith's α) & efficiency | α 61.4 (A) / 51.5 (B); eff. 0.22 / 0.18 | α 36.5; eff. 0.92 | α ≈ 10 (Smith 1962, periods 1–2) | **H1 not supported — reversed.** Local 8B converges *worse* than ZI-C (conjunction p = 0.998, pre-Holm) and fails efficiency non-inferiority in both paraphrases |
| 2 | SSW: bubbles (RD, boom–crash shape) & experience effect | RD −0.59 (A) / −0.59 (B); shape 0/30 / 0/30 | RD 0.82 (unstructured) | RD > 0, boom–crash typical (SSW 1988) | **H2 not supported — inverted.** No bubbles: markets price *below* fundamentals in both paraphrases (conjunction p = 1.000); experience halves the mispricing magnitude (−0.59 → −0.38) but the registered directional test fails |
| 3 | Duopoly: spread markup over Nash & deviation-probe response | markup +27.42 (A) / +17.35 (B) francs = 4.43× / 3.17× the Nash spread of 8; probe response −1.53 / −1.99 | myopic BR: markup ≤ 0 (certified gate) | Calvano-style algorithmic collusion shows punishment; humans compete near Nash | **H3 not supported — supra-Nash without collusion.** Wide spreads persist from mutual failure to undercut; probes show *matching* (competition signature), not punishment; vs a myopic rival the markup collapses to +4.05 |

**Family verdict (Holm–Bonferroni, α = 0.05): 0/3 pre-registered hypotheses supported** —
and each negative is informative: the local 8B model neither out-converges zero
intelligence (it loses to it), nor bubbles (it *under*prices), nor colludes (its wide
spreads are passivity, not punishment). Claims are scoped to this model + prompts +
temperature; frontier cells are deferred with configs ready (HYPOTHESES A2.vi).

## How to verify

Everything is verifiable **without an API key** via log-and-replay: see
[REPRODUCING.md](REPRODUCING.md). Tier 1 (≤10 min): `uv sync --frozen`, run the
numbered notebooks — they replay committed session logs and assert every headline
number against [CLAIMS.md](CLAIMS.md).
