# DHAPPA v2.3 vs v2.4 Comparison

V2.4 adds **Damage-Averse Policy Survival**: a learned non-BALANCED house policy must survive prior-only shadow replay against BALANCED before promotion. The test protects existing Top-5 hits and rejects policy gains bought by unacceptable damage.

| House | Top5 v2.3 | Top5 v2.4 | Δ pp | Top10 v2.3 | Top10 v2.4 | Δ pp | MRR v2.3 | MRR v2.4 | Switches |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 7.56% | 7.6% | +0.04 | 10.47% | 9.94% | -0.53 | 0.0583 | 0.0584 | 8 → 8 |
| Faridabad | 4.52% | 5.65% | +1.13 | 12.43% | 12.99% | +0.56 | 0.0557 | 0.0599 | 11 → 11 |
| Ghaziabad | 5.68% | 5.68% | +0.00 | 11.93% | 11.93% | +0.00 | 0.0505 | 0.0505 | 8 → 8 |
| Gali | 4.57% | 4.02% | -0.55 | 8.57% | 8.62% | +0.05 | 0.0441 | 0.0431 | 12 → 13 |

## Reading the result
Faridabad is the clearest recovery: Top-5 improves from 4.52% to 5.65%, Top-10 from 12.43% to 12.99%, and MRR from 0.0557 to 0.0599. This supports the hypothesis that v2.3 was accepting policy changes that improved broad rank utility while damaging scarce Top-5 hits.

Ghaziabad is unchanged, indicating its previously learned routing already survives the stricter damage test. Deshawar is effectively stable. Gali loses 0.55 percentage points of elected Top-5, showing that a single BALANCED shadow baseline is still not sufficient for every house/regime.

## Next bottleneck
V2.4 reduces one failure mode but exposes another: **baseline-policy rigidity**. The next experiment should not relax the damage budget globally. Instead, compare candidate policies against a small prior-only baseline set (BALANCED plus current incumbent policy) and require Pareto survival on Top-5 damage, Top-10, MRR, and switch cost. Gali should be treated as a separate diagnostic target rather than compensated by looser global thresholds.