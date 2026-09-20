# DHAPPA v4.0 — Full Candidate Learning-to-Rank

v4.0 ranks the complete 00–99 universe from frozen pre-target engine, reliability, rank, digit, recency, gap and transition evidence. The online learner is updated only after the target outcome is revealed. It cannot control the live ranking until shadow evidence and a separate prospective probation window both survive.

- Frozen house-target decisions: **761**
- Integrity: **PASS**

## Strict OOS results

| House | Coverage | Baseline Top5 | v4.0 Top5 | All-target Top5 | v4.0 Top10 | v4.0 MRR | Live LTR targets | Rescues | Damages | Final state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 91.49% | 8.14% | 8.14% | 7.45% | 11.05% | 0.0598 | 0 | 0 | 0 | SHADOW |
| Faridabad | 92.19% | 5.65% | 5.65% | 5.21% | 12.99% | 0.0599 | 0 | 0 | 0 | SHADOW |
| Ghaziabad | 92.15% | 5.68% | 5.68% | 5.24% | 11.93% | 0.0505 | 0 | 0 | 0 | SHADOW |
| Gali | 91.58% | 4.60% | 4.60% | 4.21% | 8.62% | 0.0426 | 0 | 0 | 0 | PROBATION |

## Interpretation

The full-candidate learner is treated as a challenger, not an automatic replacement. If its prior shadow and future probation evidence do not beat the canonical ranking, the canonical ranking remains live. This prevents a richer model from being promoted merely because it can fit historical candidate structure.