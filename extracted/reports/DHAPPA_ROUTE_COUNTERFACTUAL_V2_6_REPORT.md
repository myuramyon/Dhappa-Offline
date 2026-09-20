# DHAPPA v2.6 — Route-Level Counterfactual Election Lab

This is a diagnostic layer over v2.5. Outcome-revealed oracle ranks are used only after the same-target election is frozen; they are not fed back into that target prediction.

## House-wise counterfactual diagnosis

| House | Targets | Selected Top5 | Eligible-route Top5 ceiling* | All-route Top5 ceiling* | Election miss | Qualification miss | Generation miss | Ranking-depth miss | Abstention opportunity | Correct protection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 188 | 7.45% | 21.28% | 38.83% | 26 | 33 | 12 | 98 | 0 | 4 |
| Faridabad | 192 | 5.21% | 29.17% | 41.67% | 46 | 24 | 16 | 88 | 0 | 1 |
| Ghaziabad | 191 | 5.24% | 27.23% | 36.13% | 42 | 17 | 9 | 105 | 0 | 3 |
| Gali | 190 | 4.21% | 22.11% | 37.37% | 34 | 29 | 18 | 93 | 0 | 3 |

*Ceilings are hindsight diagnostic upper bounds, not achievable prospective performance claims.

## Classification rules
- **ELECTION_MISS:** selected route missed Top-5 while another already-qualified route contained the actual in Top-5.
- **QUALIFICATION_MISS:** no eligible alternative rescued Top-5, but a generated single/combination rejected by qualification did.
- **GENERATION_MISS:** even the best generated route ranked the actual below Top-36.
- **RANKING_DEPTH_MISS:** a route generated the actual within Top-36, but none placed it in Top-5.
- **ABSTENTION_OPPORTUNITY_COST:** the system abstained while a qualified route had the actual in Top-5.
- **CORRECT_PROTECTION:** a proposed challenger was rejected and the retained incumbent ranked the revealed outcome better.

## Intended use
Use this report to decide whether the next engineering effort belongs in election, qualification, ranking/generation, or abstention logic. Do not train directly on the oracle-best route identity for the same target.