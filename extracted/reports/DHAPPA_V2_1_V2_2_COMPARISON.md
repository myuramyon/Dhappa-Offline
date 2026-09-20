# DHAPPA v2.1 vs v2.2 — Asymmetric Champion Protection

| House | V2.1 Top5 | V2.2 Top5 | Δ Top5 | V2.1 Top10 | V2.2 Top10 | Δ Top10 | Switches 2.1→2.2 | Current v2.2 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 6.94% | 7.6% | +0.66 pp | 12.72% | 11.7% | -1.02 pp | 4→6 | HOT_RECENCY |
| Faridabad | 7.34% | 5.65% | -1.69 pp | 11.3% | 11.86% | +0.56 pp | 5→9 | G_SQUARE_HARMONICS |
| Ghaziabad | 3.45% | 5.11% | +1.66 pp | 9.2% | 11.36% | +2.16 pp | 4→8 | TRANSITION_MARKOV |
| Gali | 2.29% | 4.0% | +1.71 pp | 8.57% | 8.0% | -0.57 pp | 7→10 | ECHO_7 |

## Result
Asymmetric protection corrected part of the v2.1 over-stability failure: DS, GB and GL Top-5 recovered, while FB degraded. This means strength-tiered protection is useful but should not yet be treated as a universally calibrated policy.

## Next bottleneck
Calibrate the switch gate per house using only nested prior windows. FB especially needs a stricter damage budget / promotion gate, while GB and GL benefit from the faster weak/failing-incumbent path. Do not optimize thresholds on the same evaluation period.