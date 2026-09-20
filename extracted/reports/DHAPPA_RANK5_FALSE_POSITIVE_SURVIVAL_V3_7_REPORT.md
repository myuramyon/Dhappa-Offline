# DHAPPA v3.7 — Rank-5 False-Positive Survival Model

v3.7 adds a prior-only historical survival layer above v3.6. It is suppressive only: it cannot invent a challenger and cannot activate a correction that v3.6 rejected. Similar weak Rank-5 states are tracked with hierarchical backoff (exact context → coarse challenger-rank context → house-level weak Rank-5 cohort).

## Survival evidence

The survival layer tracks how often comparable frozen Rank-5 states subsequently missed Top-5, how often the frozen challenger actually rescued Top-5, whether a takeover damaged an existing Top-5 hit, and Top-10/MRR deltas. Outcome fields enter these histories only after the corresponding target has been revealed.

## Results

| House | Top-5 | Top-10 | MRR | v3.6 activations | v3.7 activations | rescues | damaged Top-5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 11.05% | 0.0598 | 0 | 0 | 0 | 0 |
| Faridabad | 5.65% | 12.99% | 0.0599 | 0 | 0 | 0 | 0 |
| Ghaziabad | 6.82% | 11.93% | 0.0520 | 2 | 2 | 1 | 0 |
| Gali | 4.57% | 8.57% | 0.0427 | 0 | 0 | 0 | 0 |

## Finding

v3.7 did **not** safely compress the two v3.6 Ghaziabad interventions any further. Both remain live. The first qualifying intervention occurs before enough comparable takeover outcomes exist, so it is retained under sparse-history fail-open; after it produces a rescue, the second intervention still has no evidence of historical damage sufficient to justify suppression. This is a negative but useful result: a Rank-5 false-positive survival layer adds auditability, but the available takeover sample is too sparse to improve v3.6 prospectively.

## Reporting consistency correction

The legacy v3.6 summary stored Gali as 174 elected targets / 4.60% Top-5. Replaying the frozen v3.6 records against the counterfactual timeline yields **175 elected targets and 8 Top-5 hits = 4.57%**. v3.7 uses the raw frozen-record denominator for all comparisons. This is a reporting correction, not a prediction change.

## Temporal integrity

- All state features are frozen before the current target outcome.
- Similar-state outcome histories update only after reveal.
- v3.7 can only suppress v3.6.
- No hindsight-selected date rule or target-specific exception is used.