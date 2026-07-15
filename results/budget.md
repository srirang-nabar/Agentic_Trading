# Budget ledger (regenerated from logs by `runner.write_budget`)

Soft cap: **$150** for frontier-API spend (HYPOTHESES.md). Local-model
cells cost GPU rental time, not tokens — tracked as wall-clock hours of
LLM traffic; billable GPU hours are bounded below by this figure.

| Experiment | LLM calls | Prompt tokens | Completion tokens | LLM wall-clock (h) |
| --- | --- | --- | --- | --- |
| duopoly_explore | 6750 | 2760078 | 51490 | 0.64 |
| duopoly_h3 | 18000 | 7003268 | 140908 | 1.73 |
| llm_smoke | 725 | 257211 | 9401 | 0.08 |
| smith_explore | 97543 | 37763626 | 1276146 | 15.20 |
| smith_h1 | 106043 | 37776003 | 1343878 | 16.41 |
| ssw_explore | 11024 | 5244691 | 154435 | 1.55 |
| ssw_h2 | 82570 | 49144400 | 1023227 | 11.30 |

**Totals:** 322655 calls, 139949277 prompt + 3999485 completion tokens.

Frontier-API dollar spend to date: **$0.00** (no frontier cells run yet).

## Stage 4-6 frontier projection (Stage 3 gate)

Measured on the smoke cell: 355 prompt + 13 completion tokens/call, retry factor 1.21. Projected frontier calls: Stage 4 = 104,400, Stage 6 = 32,625 (Stage 5 frontier cells: none pre-declared; model scale is exploratory, local-only).

| Frontier model | Stage 4 | Stage 6 | Total | Fits $150 cap? |
| --- | --- | --- | --- | --- |
| claude-haiku-4-5 | $44 | $14 | **$57** | yes |
| claude-sonnet-4-6 | $131 | $41 | **$172** | no — pre-registered fallback required |
| claude-opus-4-8 | $219 | $68 | **$287** | no — pre-registered fallback required |

Decision recorded here per the gate: the frontier-tier model is chosen at Stage 4 kickoff. If the chosen tier exceeds the cap, the pre-registered fallback applies (paraphrase robustness on the local model; frontier runs paraphrase A only; claims scoped accordingly).
