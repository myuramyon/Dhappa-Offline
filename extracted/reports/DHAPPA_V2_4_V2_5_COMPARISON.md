# DHAPPA v2.4 vs v2.5 Comparison

V2.5 adds multi-baseline Pareto policy survival. A candidate house policy is tested against BALANCED, the current incumbent policy, and the recent surviving policy using only completed prior challenger events. When no policy is non-inferior across protected metrics with a strict gain, the system emits `RETAIN_CURRENT_POLICY`.

| House | Top5 v2.4 | Top5 v2.5 | Δ pp | Top10 v2.4 | Top10 v2.5 | Top36 v2.5 | MRR v2.5 | Switches v2.4→v2.5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 7.6% | 8.14% | +0.54 | 9.94% | 11.05% | 39.53% | 0.0598 | 8→8 |
| Faridabad | 5.65% | 5.65% | +0.00 | 12.99% | 12.99% | 38.42% | 0.0599 | 11→11 |
| Ghaziabad | 5.68% | 5.68% | +0.00 | 11.93% | 11.93% | 47.73% | 0.0505 | 8→8 |
| Gali | 4.02% | 4.57% | +0.55 | 8.62% | 8.57% | 31.43% | 0.0441 | 13→12 |

## Policy survival behavior

- **Deshawar** policies: {'BALANCED': 23, 'ADAPTIVE': 38, 'FAST_RESCUE': 15}; decisions: {'WARMUP_RETAIN_CURRENT_POLICY': 15, 'RETAIN_CURRENT_POLICY_NO_PARETO_DOMINANCE': 59, 'PRIOR_ONLY_PARETO_POLICY_PROMOTION': 2}
- **Faridabad** policies: {'BALANCED': 20, 'CONSERVATIVE': 12}; decisions: {'WARMUP_RETAIN_CURRENT_POLICY': 15, 'RETAIN_CURRENT_POLICY_NO_PARETO_DOMINANCE': 16, 'PRIOR_ONLY_PARETO_POLICY_PROMOTION': 1}
- **Ghaziabad** policies: {'BALANCED': 20, 'CONSERVATIVE': 33}; decisions: {'WARMUP_RETAIN_CURRENT_POLICY': 15, 'RETAIN_CURRENT_POLICY_NO_PARETO_DOMINANCE': 37, 'PRIOR_ONLY_PARETO_POLICY_PROMOTION': 1}
- **Gali** policies: {'BALANCED': 37, 'FAST_RESCUE': 5, 'ADAPTIVE': 5}; decisions: {'WARMUP_RETAIN_CURRENT_POLICY': 15, 'RETAIN_CURRENT_POLICY_NO_PARETO_DOMINANCE': 21, 'PRIOR_ONLY_PARETO_POLICY_PROMOTION': 11}

## Evidence-based interpretation
V2.5 recovers Gali from the v2.4 Top-5 regression while preserving Faridabad recovery and Ghaziabad stability. Deshawar improves on the bounded replay. These are bounded historical results, not guarantees of future outcomes; policy promotion remains prior-only and abstention remains explicit.