# CLAIMS.md — claim ledger

One row per resume/README claim. **A claim without a verifying artifact may not
appear in the README.** Values must match the notebook assert values exactly.

| Claim ID | Claim (verbatim from README) | Value | Verifying notebook cell | Pytest test | Log source (`results/<experiment_id>`) |
| -------- | ---------------------------- | ----- | ----------------------- | ----------- | -------------------------------------- |
| GS-1 | ZI-C mean allocative efficiency (Smith CDA, 50 sessions) | 0.928 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_efficiency_gate | zi_baseline |
| GS-2 | ZI-U mean allocative efficiency (same markets, 50 sessions) | -0.214 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
| GS-3 | ZI-C > ZI-U efficiency, Mann-Whitney one-sided p | <0.001 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
| GS-4 | ZI-C vs ZI-U rank-biserial effect size | 1.000 | 01_exchange_and_zi.ipynb, gate-assertions cell | test_gate_stage2.py::test_zic_beats_ziu | zi_baseline |
