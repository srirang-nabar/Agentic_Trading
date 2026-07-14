# CLAIMS.md — claim ledger

One row per resume/README claim. **A claim without a verifying artifact may not
appear in the README.** Values must match the notebook assert values exactly.

| Claim ID | Claim (verbatim from README) | Value | Verifying notebook cell | Pytest test | Log source (`results/<experiment_id>`) |
| -------- | ---------------------------- | ----- | ----------------------- | ----------- | -------------------------------------- |
| GS-1 | ZI-C mean allocative efficiency (Smith CDA, 50 sessions) | 0.928 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_efficiency_gate | zi_baseline |
| GS-2 | ZI-U mean allocative efficiency (same markets, 50 sessions) | -0.214 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
| GS-3 | ZI-C > ZI-U efficiency, Mann-Whitney one-sided p | <0.001 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
| GS-4 | ZI-C vs ZI-U rank-biserial effect size | 1.000 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
| SM-1 | Order-validity rate, local 8B harness (10-session smoke) | 0.993 | 02_llm_harness.ipynb, gate cell | test_gate_stage3_smoke.py::test_order_validity_meets_floor | llm_smoke |
| SM-2 | Mean LLM tokens per smoke session (prompt+completion) | 26661 | 02_llm_harness.ipynb, gate cell | test_gate_stage3_smoke.py::test_cost_accounting_matches_budget_ledger | llm_smoke |
