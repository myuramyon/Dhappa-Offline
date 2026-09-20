# DHAPPA v2.8 — Qualification Boundary Rescue Lab

v2.8 preserves the survival-gated prospective discriminator and adds a narrow prior-only rescue path for NEAR_QUALIFIED_CHALLENGER routes. Same-target outcomes never affect qualification rescue.

## House metrics

| House | Elected | Coverage | Top5 elected | Top10 elected | Top21 elected | Top36 elected | MRR | Switches | Current primary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 172 | 91.49% | 8.14% | 11.05% | 23.26% | 39.53% | 0.0598 | 8 | HOT_RECENCY |
| Faridabad | 177 | 92.19% | 5.65% | 12.99% | 26.55% | 38.42% | 0.0599 | 11 | G_SQUARE_HARMONICS |
| Ghaziabad | 176 | 92.15% | 5.68% | 11.93% | 26.14% | 47.73% | 0.0505 | 8 | TRANSITION_MARKOV |
| Gali | 174 | 91.58% | 4.6% | 8.62% | 20.11% | 31.61% | 0.0426 | 14 | ECHO_7 |

## Discriminator activation
- **Deshawar:** {'NO_ROUTES': 15, 'FALLBACK_V25_SCORE': 25, 'ONLINE_LOGIT': 148}
- **Faridabad:** {'NO_ROUTES': 15, 'FALLBACK_V25_SCORE': 49, 'ONLINE_LOGIT': 128}
- **Ghaziabad:** {'NO_ROUTES': 15, 'FALLBACK_V25_SCORE': 18, 'ONLINE_LOGIT': 158}
- **Gali:** {'NO_ROUTES': 15, 'FALLBACK_V25_SCORE': 57, 'ONLINE_LOGIT': 118}

## Boundary rescue activity
- **Deshawar:** tested=324, rescued=0, rejected=324
- **Faridabad:** tested=273, rescued=0, rejected=273
- **Ghaziabad:** tested=238, rescued=30, rejected=208
- **Gali:** tested=373, rescued=0, rejected=373

## Leakage guard
- Route features exist before outcome reveal.
- Training labels for a target are appended only after that target election is frozen.
- Oracle-best route from v2.6 is never supplied as an input feature.
- If prior meta evidence is insufficient, v2.5 scoring is used.

## Outcome
Across 1208 near-qualified tests, 30 admissions survived prior-only rescue rules. All admissions were in Ghaziabad. However, boundary admission changed the final Primary route on 0 targets. Therefore house metrics remain unchanged from v2.7. This is evidence that qualification is not the only bottleneck; admitted GB routes are subsequently dominated by the election hierarchy.
