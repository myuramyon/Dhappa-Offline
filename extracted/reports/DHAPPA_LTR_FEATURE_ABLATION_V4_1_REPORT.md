# DHAPPA v4.1 — Learning-to-Rank Feature Ablation & Signal Audit

Each ablation is a separate online learner trained chronologically. Current-target labels are added only after that target is ranked. The audit uses elected targets only; NO_QUALIFIED_PRIMARY dates are not replaced with an artificial baseline. Signal classification requires directional consistency across a chronological discovery/confirmation split.

- Elected records replayed: **699**
- Integrity: **PASS**

## Full-model OOS context

| House | Baseline Top5 | FULL LTR Top5 | FULL Top10 | FULL MRR |
|---|---:|---:|---:|---:|
| Deshawar | 9.09% | 6.06% | 12.12% | 0.0553 |
| Faridabad | 6.57% | 5.11% | 8.76% | 0.0486 |
| Ghaziabad | 4.41% | 3.68% | 8.82% | 0.0477 |
| Gali | 5.22% | 4.48% | 10.45% | 0.0445 |

## Leave-one-family-out signal audit

### Deshawar

| Removed family | ΔTop5 vs FULL | ΔTop10 | ΔMRR | Discovery ΔTop5 | Confirmation ΔTop5 | Classification |
|---|---:|---:|---:|---:|---:|---|
| DIGIT_STRUCTURE | +0.76 pp | +1.52 pp | +0.0095 | +1.27 pp | +0.00 pp | HARMFUL_OR_NOISY |
| PRIMARY_EVIDENCE | +0.76 pp | +0.00 pp | +0.0004 | +1.27 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| RECENCY_GAP | +0.00 pp | +0.00 pp | +0.0045 | -1.27 pp | +1.89 pp | UNSTABLE_OR_NEUTRAL |
| CROSS_HOUSE | +0.00 pp | +0.00 pp | -0.0015 | +0.00 pp | +0.00 pp | USEFUL_SIGNAL |
| PALTI_MIRROR | +0.00 pp | -3.03 pp | -0.0055 | +0.00 pp | +0.00 pp | USEFUL_SIGNAL |
| CONSENSUS_ENGINE_RANKS | -0.76 pp | -0.76 pp | +0.0082 | -1.27 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| RELIABILITY | -0.76 pp | -1.52 pp | -0.0001 | -1.27 pp | +0.00 pp | USEFUL_SIGNAL |
| WEEKDAY_CALENDAR | -0.76 pp | -1.52 pp | -0.0022 | -1.27 pp | +0.00 pp | USEFUL_SIGNAL |
| PREVIOUS_DRAW_TRANSITION | -1.52 pp | -2.27 pp | -0.0098 | -1.27 pp | -1.89 pp | USEFUL_SIGNAL |

- Consistently harmful/noisy candidates: **DIGIT_STRUCTURE**
- Consistently useful signal candidates: **RELIABILITY, WEEKDAY_CALENDAR, PALTI_MIRROR, CROSS_HOUSE, PREVIOUS_DRAW_TRANSITION**

### Faridabad

| Removed family | ΔTop5 vs FULL | ΔTop10 | ΔMRR | Discovery ΔTop5 | Confirmation ΔTop5 | Classification |
|---|---:|---:|---:|---:|---:|---|
| CROSS_HOUSE | +0.73 pp | +0.00 pp | -0.0011 | +0.00 pp | +1.82 pp | UNSTABLE_OR_NEUTRAL |
| DIGIT_STRUCTURE | +0.00 pp | +0.00 pp | +0.0086 | +1.22 pp | -1.82 pp | UNSTABLE_OR_NEUTRAL |
| RELIABILITY | +0.00 pp | +0.00 pp | -0.0001 | +0.00 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| WEEKDAY_CALENDAR | -0.73 pp | +0.00 pp | +0.0078 | +0.00 pp | -1.82 pp | UNSTABLE_OR_NEUTRAL |
| PALTI_MIRROR | -0.73 pp | +0.00 pp | +0.0030 | +0.00 pp | -1.82 pp | UNSTABLE_OR_NEUTRAL |
| RECENCY_GAP | -0.73 pp | -0.73 pp | +0.0021 | -1.22 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| PRIMARY_EVIDENCE | -1.46 pp | +0.73 pp | +0.0002 | -2.44 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| CONSENSUS_ENGINE_RANKS | -1.46 pp | +0.73 pp | -0.0020 | -1.22 pp | -1.82 pp | USEFUL_SIGNAL |
| PREVIOUS_DRAW_TRANSITION | -1.46 pp | +0.00 pp | -0.0056 | -1.22 pp | -1.82 pp | USEFUL_SIGNAL |

- Consistently harmful/noisy candidates: **none**
- Consistently useful signal candidates: **CONSENSUS_ENGINE_RANKS, PREVIOUS_DRAW_TRANSITION**

### Ghaziabad

| Removed family | ΔTop5 vs FULL | ΔTop10 | ΔMRR | Discovery ΔTop5 | Confirmation ΔTop5 | Classification |
|---|---:|---:|---:|---:|---:|---|
| CONSENSUS_ENGINE_RANKS | +2.21 pp | +2.21 pp | +0.0159 | +2.47 pp | +1.82 pp | HARMFUL_OR_NOISY |
| PRIMARY_EVIDENCE | +0.74 pp | +0.74 pp | +0.0043 | -1.23 pp | +3.64 pp | UNSTABLE_OR_NEUTRAL |
| RELIABILITY | +0.74 pp | +0.74 pp | +0.0002 | +1.23 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| CROSS_HOUSE | +0.74 pp | +0.00 pp | -0.0008 | +0.00 pp | +1.82 pp | UNSTABLE_OR_NEUTRAL |
| DIGIT_STRUCTURE | +0.74 pp | +3.68 pp | -0.0016 | +0.00 pp | +1.82 pp | UNSTABLE_OR_NEUTRAL |
| PREVIOUS_DRAW_TRANSITION | +0.74 pp | +1.47 pp | -0.0034 | +2.47 pp | -1.82 pp | UNSTABLE_OR_NEUTRAL |
| PALTI_MIRROR | +0.00 pp | +0.74 pp | -0.0018 | +0.00 pp | +0.00 pp | USEFUL_SIGNAL |
| RECENCY_GAP | +0.00 pp | -0.74 pp | -0.0058 | -1.23 pp | +1.82 pp | UNSTABLE_OR_NEUTRAL |
| WEEKDAY_CALENDAR | -0.74 pp | +1.47 pp | -0.0025 | -1.23 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |

- Consistently harmful/noisy candidates: **CONSENSUS_ENGINE_RANKS**
- Consistently useful signal candidates: **PALTI_MIRROR**

### Gali

| Removed family | ΔTop5 vs FULL | ΔTop10 | ΔMRR | Discovery ΔTop5 | Confirmation ΔTop5 | Classification |
|---|---:|---:|---:|---:|---:|---|
| PREVIOUS_DRAW_TRANSITION | +0.75 pp | -0.75 pp | +0.0017 | +1.25 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| CONSENSUS_ENGINE_RANKS | +0.00 pp | -1.49 pp | +0.0046 | -1.25 pp | +1.85 pp | UNSTABLE_OR_NEUTRAL |
| PRIMARY_EVIDENCE | +0.00 pp | +0.00 pp | +0.0024 | +1.25 pp | -1.85 pp | UNSTABLE_OR_NEUTRAL |
| RELIABILITY | +0.00 pp | -0.75 pp | +0.0001 | +0.00 pp | +0.00 pp | HARMFUL_OR_NOISY |
| PALTI_MIRROR | +0.00 pp | +0.00 pp | +0.0000 | +0.00 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| WEEKDAY_CALENDAR | +0.00 pp | -0.75 pp | -0.0003 | +0.00 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| DIGIT_STRUCTURE | +0.00 pp | -2.24 pp | -0.0029 | -1.25 pp | +1.85 pp | UNSTABLE_OR_NEUTRAL |
| CROSS_HOUSE | -0.75 pp | +0.00 pp | -0.0003 | -1.25 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |
| RECENCY_GAP | -1.49 pp | -1.49 pp | -0.0059 | -2.50 pp | +0.00 pp | UNSTABLE_OR_NEUTRAL |

- Consistently harmful/noisy candidates: **RELIABILITY**
- Consistently useful signal candidates: **none**

## Interpretation

A positive leave-one-family-out delta means the learner improved when that feature family was removed; this is evidence that the family may be noisy or badly parameterized, not proof that the underlying concept is useless. A negative delta means removing the family hurt the learner. Only directions that persist across the chronological discovery and confirmation segments are labelled useful or harmful/noisy; mixed directions are labelled unstable/neutral.

No ablation winner is automatically promoted to production. v4.1 is a signal-audit stage; any pruned feature set must be rebuilt prospectively in a later version using only choices established before its evaluation window.