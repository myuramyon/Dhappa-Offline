# DHAPPA v2.7 — Prospective Route Discriminator

v2.7 re-ranks only already-qualified routes using an online prior-only classifier. Same-target outcomes are appended as training labels only after election freeze.

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

## Leakage guard
- Route features exist before outcome reveal.
- Training labels for a target are appended only after that target election is frozen.
- Oracle-best route from v2.6 is never supplied as an input feature.
- If prior meta evidence is insufficient, v2.5 scoring is used.