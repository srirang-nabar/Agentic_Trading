# Exclusions log (no-discard rule, plan.md ground rules)

Every session that starts is logged and analyzed; exclusions are permitted
only for documented harness faults. This file is the complete record.

| Date | Experiment / cell | What happened | Disposition |
| --- | --- | --- | --- |
| 2026-07-14 | smith_h1 / llm_local_a (first attempt) | The runner process was killed externally ~33 min into the cell (background task stopped at ~18:17 local; not a code fault — the `zi_c` cell had completed normally). The partial gzip stream was never finalized and its sessions were never analyzed. | Whole-cell harness abort: partial file discarded, cell re-run in full from the same seeds (markets identical by construction). No session from the aborted attempt entered any analysis. |
