# Agentic Trading — experimental economics with LLM agents

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
| 1 | Smith CDA: convergence (early-period Smith's α) & efficiency | — | — | — | — |
| 2 | SSW: bubbles (RD, boom–crash shape) & experience effect | — | — | — | — |
| 3 | Duopoly: spread markup over Nash & deviation-probe response | — | — | — | — |

## How to verify

Everything is verifiable **without an API key** via log-and-replay: see
[REPRODUCING.md](REPRODUCING.md). Tier 1 (≤10 min): `uv sync --frozen`, run the
numbered notebooks — they replay committed session logs and assert every headline
number against [CLAIMS.md](CLAIMS.md).
