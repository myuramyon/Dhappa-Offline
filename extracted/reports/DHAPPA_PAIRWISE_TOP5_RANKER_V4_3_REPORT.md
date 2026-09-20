# DHAPPA v4.3 — Pairwise Candidate Ordering / Top-5 Objective Ranker

v4.3 replaces the generic one-vs-rest learning objective with online pairwise ordering. After a target is revealed, the actual candidate is trained to outrank canonical hard negatives. Canonical ranks 4–8 receive the highest training weight, ranks 1–3 and 9–10 receive secondary weight, and ranks 11–20 receive lighter weight. The current target never trains its own prediction.

- Frozen elected-target decisions: **699**
- Live pairwise activations: **37**
- Integrity: **PASS**

## House results

| House | Canonical Top5 | Pairwise shadow Top5 | Final Top5 | Canonical Top10 | Final Top10 | Final MRR | Live activations | Rescues | Damages | Final state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 8.14% | 4.07% | 8.14% | 11.05% | 11.05% | 0.0598 | 0 | 0 | 0 | SHADOW |
| Faridabad | 5.65% | 7.34% | 5.65% | 12.99% | 12.99% | 0.0597 | 2 | 0 | 0 | SHADOW |
| Ghaziabad | 5.68% | 3.41% | 5.68% | 11.93% | 11.93% | 0.0505 | 0 | 0 | 0 | SHADOW |
| Gali | 4.60% | 6.90% | 4.60% | 8.62% | 10.34% | 0.0476 | 35 | 3 | 3 | LIVE |

## Interpretation

The pairwise learner is evaluated in shadow mode first. It enters probation only when prior completed targets show positive Top-5 lift with non-inferior Top-10 and MRR, and becomes live only after an additional prospective probation window. A rolling circuit breaker returns it to shadow if recent live-eligible evidence deteriorates. This prevents a boundary-focused objective from being promoted merely because it fits earlier history.