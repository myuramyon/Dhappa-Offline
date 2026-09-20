# DHAPPA v4.2 — House-Specific Feature Policy with Nested Prospective Validation

Feature policies are not hardcoded from v4.1. For each house, the earlier 60% elected history is the discovery segment. Discovery is itself split into inner-train and inner-validation to select among FULL and leave-one-family-out policies. The selected policy is then frozen, freshly trained on all discovery observations, and evaluated chronologically on the untouched final 40% confirmation segment.

- Frozen elected feature records: **699**
- Untouched confirmation records: **281**
- Integrity: **PASS**

## Frozen house-specific policies

| House | Chosen policy | Discovery | Inner validation | Untouched confirmation |
|---|---|---:|---:|---:|
| Deshawar | DROP_PRIMARY_EVIDENCE | 103 | 42 | 69 |
| Faridabad | DROP_PREVIOUS_DRAW_TRANSITION | 106 | 43 | 71 |
| Ghaziabad | DROP_DIGIT_STRUCTURE | 105 | 42 | 71 |
| Gali | DROP_PRIMARY_EVIDENCE | 104 | 42 | 70 |

## Untouched confirmation results

| House | Frozen policy | Canonical Top5 | Policy Top5 | ΔTop5 | Canonical Top10 | Policy Top10 | ΔMRR | Promote? | Final live policy |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Deshawar | DROP_PRIMARY_EVIDENCE | 13.04% | 7.25% | -5.80 pp | 15.94% | 10.14% | -0.0081 | NO | CANONICAL_DYNAMIC_PRIMARY |
| Faridabad | DROP_PREVIOUS_DRAW_TRANSITION | 4.23% | 7.04% | +2.82 pp | 12.68% | 11.27% | +0.0072 | NO | CANONICAL_DYNAMIC_PRIMARY |
| Ghaziabad | DROP_DIGIT_STRUCTURE | 5.63% | 4.23% | -1.41 pp | 9.86% | 9.86% | -0.0037 | NO | CANONICAL_DYNAMIC_PRIMARY |
| Gali | DROP_PRIMARY_EVIDENCE | 5.71% | 2.86% | -2.86 pp | 7.14% | 8.57% | +0.0040 | NO | CANONICAL_DYNAMIC_PRIMARY |

## Interpretation

A policy is promoted only when the untouched confirmation period shows a strict Top-5 improvement with no Top-10 or MRR degradation. Otherwise the canonical Dynamic Primary ranking remains live. This converts v4.1 ablation observations into a true nested out-of-sample test instead of turning diagnostic findings into hardcoded production rules.