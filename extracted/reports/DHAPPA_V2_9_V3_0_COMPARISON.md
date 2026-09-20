# DHAPPA v2.9 vs v3.0 Comparison

v3.0 adds candidate-level cross-route reciprocal-rank fusion, but only permits live control after a two-stage prior-only shadow and prospective probation survival test. No house passed the final probation gate in this bounded replay, so canonical v2.9 output was preserved.

| House | v2.9 Top5 | v3.0 Top5 | Δ Top5 | v3.0 Top10 | MRR | Live fusion activations |
|---|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 8.14% | +0.00 pp | 11.05% | 0.0598 | 0 |
| Faridabad | 5.65% | 5.65% | +0.00 pp | 12.99% | 0.0599 | 0 |
| Ghaziabad | 5.68% | 5.68% | +0.00 pp | 11.93% | 0.0505 | 0 |
| Gali | 4.6% | 4.6% | +0.00 pp | 8.62% | 0.0426 | 0 |

## Interpretation

- Raw fusion briefly looked promising in GB/GL shadow history, but its advantage reversed after activation in the first experimental pass.
- The final v3.0 therefore requires a separate 12-event prospective probation after shadow qualification, plus continuing recent-15 stability.
- No house passed that gate. This is treated as a failed promotion, not as evidence that fusion improves prediction.
- The v2.9 canonical ranking remains the protected production candidate until candidate fusion demonstrates stable out-of-sample value.