# DHAPPA v3.1 — Candidate Evidence Attribution & Rank-6–12 Rescue

v2.9 preserves v2.8 qualification rescue and adds a dedicated prior-only head-to-head tournament between an admitted boundary challenger and the canonical Primary. The challenger does not need to beat the old route-score hierarchy; it must prove paired rescue value with bounded damage.

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

## Post-admission tournament activity
- **Deshawar:** wins=0, retained=0, no_decision=0
- **Faridabad:** wins=0, retained=0, no_decision=0
- **Ghaziabad:** wins=0, retained=30, no_decision=0
- **Gali:** wins=0, retained=0, no_decision=0

## Leakage guard
- Route features exist before outcome reveal.
- Training labels for a target are appended only after that target election is frozen.
- Oracle-best route from v2.6 is never supplied as an input feature.
- If prior meta evidence is insufficient, v2.5 scoring is used.

## Candidate-level fusion activation
- **Deshawar:** live fusion targets=0, shadow samples=172
- **Faridabad:** live fusion targets=0, shadow samples=177
- **Ghaziabad:** live fusion targets=0, shadow samples=176
- **Gali:** live fusion targets=0, shadow samples=174

Fusion is activated only from prior completed shadow evidence; current-target outcome cannot activate its own fusion ranking.

## Rank-6–12 rescue activity
- **Deshawar:** frozen proposals=134, live rescue activations=0, shadow samples=134
- **Faridabad:** frozen proposals=129, live rescue activations=0, shadow samples=129
- **Ghaziabad:** frozen proposals=146, live rescue activations=59, shadow samples=146
- **Gali:** frozen proposals=129, live rescue activations=0, shadow samples=129

The rescue decision is frozen from prior-only candidate evidence. The current target outcome is used only after freeze to score the proposal for future survival gating.