# DHAPPA v3.4 — Error-Specific Ranking Weight Calibration

v3.4 splits ranking correction into independent error families. Each family is learned only from completed prior targets and must pass its own SHADOW → PROBATION → LIVE lifecycle with a rolling deterioration circuit breaker.

## House-wise results

| House | v3.3 Top-5 | v3.4 Top-5 | Δ | Top-10 v3.4 | MRR v3.4 | v3.4 live activations | additional rescues | damaged hits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 8.14% | +0.00 pp | 11.05% | 0.0598 | 0 | 0 | 0 |
| Faridabad | 5.65% | 5.65% | +0.00 pp | 12.99% | 0.0599 | 0 | 0 | 0 |
| Ghaziabad | 6.25% | 6.82% | +0.57 pp | 11.93% | 0.0520 | 101 | 1 | 0 |
| Gali | 4.60% | 4.60% | +0.00 pp | 8.62% | 0.0426 | 0 | 0 | 0 |

## Correction families

- **PRIMARY_ROUTE_BIAS** — broad independent challenger confirmation is underweighted relative to the selected Primary route.
- **VOTE_COUNT_DISTORTION** — challenger has materially stronger Top-10 support than the incumbent.
- **REDUNDANCY_OVERBOOST** — incumbent support is more correlated while challenger evidence spans more independent families.
- **RELIABILITY_WEIGHT_ERROR** — prior reliability-weighted reciprocal-rank evidence materially favors the challenger.
- **PRIMARY_RANK_ANCHOR_BIAS** — canonical Primary rank is over-anchoring the incumbent despite a large evidence margin for a nearby challenger.

## Realized v3.4 rescue

Ghaziabad produced one additional realized Top-5 rescue beyond v3.3. On 2026-08-20 the actual candidate was at canonical rank 7; the surviving PRIMARY_RANK_ANCHOR_BIAS correction promoted it to rank 5. The correction had been activated from completed prior observations only. No existing Top-5 hit was damaged by v3.4.

## Family behavior

Only Ghaziabad families reached LIVE state in this replay. DS, FB and GL remained in shadow/probation because their error-specific evidence did not meet the survival requirements. Multiple live families never stack on the same candidate; the strongest prior-derived family is allowed at most one Rank-6–12 replacement.

## Integrity

- Current-target outcome is revealed only after correction family, stage and weight are frozen.
- Family weight uses completed prior observations only.
- LIVE requires prior shadow evidence and a separate eight-observation prospective probation window.
- Rolling deterioration returns a correction family to SHADOW.
- No threshold was relaxed after viewing a target result.

## Interpretation

v3.4 adds a second prospective Top-5 rescue in Ghaziabad across the v3.3→v3.4 sequence, raising elected-target Top-5 from 6.25% to 6.82% while Top-10 remains 11.93%. This remains a small absolute sample and should be treated as evidence of a potentially useful correction mechanism, not a stable probability claim.