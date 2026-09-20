# DHAPPA v3.0 — Candidate-Level Cross-Route Fusion Intelligence

## Objective

Fuse candidate evidence across multiple prior-qualified routes so a useful number is not lost merely because one route won the Primary election. Same-target outcomes are never used to construct or activate that target’s fusion ranking.

## Safety architecture

1. Generate the canonical v2.9 Primary and all eligible route rankings from information available before the target.  2. Build a candidate-level reciprocal-rank fusion from up to five non-duplicate routes, weighted only by prior reliability/agreement and redundancy.  3. Run fusion in shadow mode.  4. Require historical shadow superiority.  5. After first qualification, require a separate 12-target prospective probation window.  6. Require continuing recent-15 non-inferiority.  7. Only then may fusion control the final ranking.

## Final bounded replay

| House | Top5 elected | Top10 elected | Top21 | Top36 | MRR | Fusion live activations |
|---|---:|---:|---:|---:|---:|---:|
| Deshawar | 8.14% | 11.05% | 23.26% | 39.53% | 0.0598 | 0 |
| Faridabad | 5.65% | 12.99% | 26.55% | 38.42% | 0.0599 | 0 |
| Ghaziabad | 5.68% | 11.93% | 26.14% | 47.73% | 0.0505 | 0 |
| Gali | 4.6% | 8.62% | 20.11% | 31.61% | 0.0426 | 0 |

## Result

No house passed the final shadow + prospective probation survival requirement. Therefore v3.0 did not replace the canonical v2.9 ranking on any target. This is intentional: the first experimental fusion pass showed temporary GB/GL shadow gains that reversed after live activation, so the final gate rejected those unstable signals.

## Integrity

Fusion records checked: **699**. Live activations: **0**. Integrity status: **PASS**.

## Conclusion

Candidate-level fusion is technically implemented and auditable, but current route-level evidence is not stable enough to justify live fusion. The correct action from this replay is to retain v2.9 output rather than manufacture improvement by weakening the gate.