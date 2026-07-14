# Budget ledger (regenerated from logs by `runner.write_budget`)

Soft cap: **$150** for frontier-API spend (HYPOTHESES.md). Local-model
cells cost GPU rental time, not tokens — tracked as wall-clock hours of
LLM traffic; billable GPU hours are bounded below by this figure.

| Experiment | LLM calls | Prompt tokens | Completion tokens | LLM wall-clock (h) |
| --- | --- | --- | --- | --- |
| llm_smoke | 725 | 257211 | 9401 | 0.08 |

**Totals:** 725 calls, 257211 prompt + 9401 completion tokens.

Frontier-API dollar spend to date: **$0.00** (no frontier cells run yet).

## Stage 4-6 frontier projection (Stage 3 gate)

Measured on the smoke cell: 355 prompt + 13 completion tokens/call, retry factor 1.21. Projected frontier calls: Stage 4 = 104,400, Stage 6 = 32,625 (Stage 5 frontier cells: none pre-declared; model scale is exploratory, local-only).

| Frontier model | Stage 4 | Stage 6 | Total | Fits $150 cap? |
| --- | --- | --- | --- | --- |
| claude-haiku-4-5 | $44 | $14 | **$57** | yes |
| claude-sonnet-4-6 | $131 | $41 | **$172** | no — pre-registered fallback required |
| claude-opus-4-8 | $219 | $68 | **$287** | no — pre-registered fallback required |

Decision recorded here per the gate: the frontier-tier model is chosen at Stage 4 kickoff. If the chosen tier exceeds the cap, the pre-registered fallback applies (paraphrase robustness on the local model; frontier runs paraphrase A only; claims scoped accordingly).
