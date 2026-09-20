# DHAPPA v3.5 — Activation Precision Controller

v3.5 adds no new generator and no new ranking family. It controls when an already-LIVE v3.4 error-specific correction may intervene. Every gate input is frozen before the current target outcome is revealed.

## Precision gate

A correction is allowed only when: at least two independent correction families are LIVE; challenger primary rank is 6–9; score/evidence margin is near-boundary (0.08–0.30); weighted reciprocal-rank advantage is at least 0.50; incumbent support is weak; challenger has at least two Top-10 and two independent-family supports. A prior-only rolling circuit breaker can suspend the controller after damage or negative recent utility.

## Results

| House | Top-5 | Top-10 | MRR | v3.4 activations | v3.5 activations | reduction | extra rescues | damaged Top-5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 11.05% | 0.0598 | 0 | 0 | 0.00% | 0 | 0 |
| Faridabad | 5.65% | 12.99% | 0.0599 | 0 | 0 | 0.00% | 0 | 0 |
| Ghaziabad | 6.82% | 11.93% | 0.0520 | 101 | 12 | 88.12% | 1 | 0 |
| Gali | 4.60% | 8.62% | 0.0426 | 0 | 0 | 0.00% | 0 | 0 |

## Key finding

In v3.4, Ghaziabad had 101 live error-family interventions, but audit shows only one of those interventions materially changed the realized actual rank. v3.5 retains that successful 20-Aug-2026 correction and suppresses 89 other interventions, reducing live intervention exposure by 88.12% while preserving the exact v3.4 Top-5, Top-10 and MRR metrics.

## Why this matters

The controller improves intervention precision rather than claiming a new hit-rate gain. Fewer unnecessary live corrections reduce the surface area for future damage, make each intervention easier to audit, and preserve the already demonstrated Ghaziabad rescue.

## Temporal integrity

- Current target outcome is not used by the precision gate or circuit breaker.
- Controller history updates only after the current decision is frozen and the target is revealed.
- v3.5 can only suppress a v3.4 correction; it cannot invent a new candidate or route.
- Rolling damage or negative utility automatically suspends future intervention.