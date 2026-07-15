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
| H1-1 | Mean early-period Smith's α, LLM paraphrase A (finite-α sessions of 30) | 61.4 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-2 | Mean early-period Smith's α, LLM paraphrase B (30 sessions) | 51.5 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-3 | Mean early-period Smith's α, matched ZI-C control (30 sessions) | 36.5 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-4 | H1 conjunction p (one-sided MW α_LLM < α_ZI-C, max over paraphrases; pre-Holm) | 0.998 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-5 | Efficiency non-inferior to ZI-C within 5 pts (must hold in both paraphrases) | no | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-6 | Mean allocative efficiency, LLM paraphrase A | 0.22 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-7 | Mean allocative efficiency, LLM paraphrase B | 0.18 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H1-8 | Mean allocative efficiency, matched ZI-C control | 0.92 | 03_smith_convergence.ipynb, gate cell | test_gate_stage4.py::test_h1_analysis_matches_claims | smith_h1 |
| H2-1 | Mean session RD, LLM paraphrase A (30 sessions) | -0.59 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-2 | Mean session RD, LLM paraphrase B (30 sessions) | -0.59 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-3 | Mean session RD, ZI-C anchor (unstructured mispricing, 30 sessions) | 0.82 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-4 | H2 conjunction p (max of sign + shape tests across both paraphrases; pre-Holm) | 1.000 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-5 | H2 supported (RD>0 and boom-crash shape, both paraphrases) | no | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-6 | Experience reduces RD, paired Wilcoxon one-sided p (registered direction) | 0.998 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-7 | Boom-crash shape criterion passes, A / B (of 30 sessions each) | 0/30 / 0/30 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H2-8 | Mean session RD, experienced cell (paired with paraphrase A) | -0.38 | 04_ssw_bubbles.ipynb, gate cell | test_gate_stage5.py::test_h2_analysis_matches_claims | ssw_h2 |
| H3-1 | Mean steady-state markup over the Nash spread, paraphrase A (francs) | +27.42 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_h3 |
| H3-2 | Mean steady-state markup over the Nash spread, paraphrase B (francs) | +17.35 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_h3 |
| H3-3 | H3 conjunction p (markup + probe-signature clauses, both paraphrases) | 1.000 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_h3 |
| H3-4 | H3 supported (supra-Nash markup AND collusion signature on probes) | no | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_h3 |
| H3-5 | Mean rival probe response, A / B (negative = matching = competition) | -1.53 / -1.99 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_h3 |
| H3-6 | Mean markup, exploratory mixed cell (LLM vs myopic best-response) | +4.05 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | duopoly_explore |
| HOLM-1 | Holm–Bonferroni family verdict across {H1, H2, H3} at α = 0.05 | 0/3 | 05_duopoly_collusion.ipynb, gate cell | test_gate_stage6.py::test_h3_analysis_matches_claims | smith_h1, ssw_h2, duopoly_h3 |
