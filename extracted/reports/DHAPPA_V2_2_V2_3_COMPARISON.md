# DHAPPA v2.2 vs v2.3 — House-Specific Policy Comparison

v2.3 learns the switching policy separately for each house from **completed prior challenger events only**. No current target is used to choose its policy. The calibration utility combines Top-5 rescue, Top-10 quality, reciprocal-rank/rank improvement, damaged-hit avoidance, and switching cost.

| House | Top5 v2.2 | Top5 v2.3 | Δ Top5 | Top10 v2.2 | Top10 v2.3 | Δ Top10 | Top36 v2.2 | Top36 v2.3 | Switches 2.2→2.3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 7.6% | 7.56% | -0.04 pp | 11.7% | 10.47% | -1.23 pp | 41.52% | 38.95% | 6→8 |
| Faridabad | 5.65% | 4.52% | -1.13 pp | 11.86% | 12.43% | +0.57 pp | 37.29% | 37.29% | 9→11 |
| Ghaziabad | 5.11% | 5.68% | +0.57 pp | 11.36% | 11.93% | +0.57 pp | 46.59% | 47.73% | 8→8 |
| Gali | 4.0% | 4.57% | +0.57 pp | 8.0% | 8.57% | +0.57 pp | 30.29% | 31.43% | 10→12 |

## Interpretation
DS is broadly stable on Top-5, GB improves across Top-5/Top-10/Top-36, and GL improves modestly on Top-5/Top-10 versus v2.2. Faridabad deteriorates on Top-5 despite a Top-10 improvement, showing that the current policy calibration objective can still trade away scarce Top-5 hits too aggressively.

Therefore v2.3 is a research branch, not an automatic replacement for every house. The next refinement should calibrate **damage aversion itself** per house and require out-of-sample policy survival before a learned policy is allowed to replace BALANCED.