# DHAPPA v3.8 — Rank-5 Boundary Dataset Expansion + Out-of-Sample Replay

v3.8 expands the learning population beyond intervention-triggered cases. Every elected historical target contributes three frozen comparisons: canonical Rank-5 vs Rank-6, Rank-7 and Rank-8. Candidate evidence is computed before reveal; RESCUE/DAMAGE/NEUTRAL labels are appended only after the target result is known.

## Expanded boundary dataset

| House | Boundary comparisons | Elected target states | Rescue events | Damage events | Neutral events |
|---|---:|---:|---:|---:|---:|
| Deshawar | 516 | 172 | 2 | 3 | 511 |
| Faridabad | 531 | 177 | 7 | 3 | 521 |
| Ghaziabad | 528 | 176 | 6 | 3 | 519 |
| Gali | 522 | 174 | 5 | 3 | 514 |

## Strict chronological out-of-sample replay

An online pairwise utility model estimates rescue and damage separately from prior boundary observations only. A swap is permitted only after minimum class/sample support and conservative structural gates. This is a research challenger to the canonical model, not an oracle.

| House | Baseline Top-5 | OOS Top-5 | Baseline Top-10 | OOS Top-10 | Baseline MRR | OOS MRR | Interventions | Rescues | Damages |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 8.14% | 11.05% | 11.05% | 0.0598 | 0.0598 | 0 | 0 | 0 |
| Faridabad | 5.65% | 5.65% | 12.99% | 12.99% | 0.0599 | 0.0599 | 0 | 0 | 0 |
| Ghaziabad | 5.68% | 5.68% | 11.93% | 11.93% | 0.0505 | 0.0505 | 0 | 0 | 0 |
| Gali | 4.60% | 4.60% | 8.62% | 8.62% | 0.0426 | 0.0426 | 0 | 0 | 0 |

## Interpretation

The expanded dataset removes the strongest sampling weakness of v3.7: survival learning is no longer restricted to the tiny set of previously approved interventions. The OOS replay remains deliberately conservative. A useful result requires realized rescue lift without offsetting Rank-5 damage; otherwise the expanded dataset should be used for diagnosis rather than promoted into the canonical ranking path.

## Integrity

- Boundary records: **2097**
- OOS target decisions: **699**
- Status: **PASS**
- Same-target outcome is never used to train its own boundary decision.
- All engine reliability features are based on profiles completed before the target.