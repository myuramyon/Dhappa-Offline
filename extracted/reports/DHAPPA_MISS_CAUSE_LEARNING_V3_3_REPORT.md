# DHAPPA v3.3 — Miss-Cause Learning at Candidate Level

v3.3 decomposes every historical Top-5 miss into an auditable cause bucket and tests a prior-only causal-signature correction layer. The current target outcome is used only after the correction decision is frozen.

## Miss-cause distribution

| House | Top-5 misses | Primary-route bias | Qualification error | Vote distortion | Redundancy | Reliability-weight | Rank-anchor | Ranking-depth | Deep-ranking | Generation failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 174 | 26 | 33 | 0 | 0 | 0 | 0 | 41 | 62 | 12 |
| Faridabad | 182 | 46 | 24 | 0 | 0 | 0 | 0 | 43 | 53 | 16 |
| Ghaziabad | 181 | 42 | 17 | 0 | 0 | 0 | 0 | 45 | 68 | 9 |
| Gali | 182 | 34 | 29 | 0 | 0 | 0 | 0 | 45 | 56 | 18 |

## Prospective causal-correction survival

- **Deshawar:** live activations=0, realized Top-5 rescues=0, damaged Top-5 hits=0
- **Faridabad:** live activations=0, realized Top-5 rescues=0, damaged Top-5 hits=0
- **Ghaziabad:** live activations=23, realized Top-5 rescues=1, damaged Top-5 hits=0
- **Gali:** live activations=0, realized Top-5 rescues=0, damaged Top-5 hits=0

## Interpretation
- PRIMARY_ROUTE_BIAS means a route already admitted by prior-only qualification had the actual in Top-5, but another route was selected.
- QUALIFICATION_ERROR means an available route could place the actual in Top-5 but was outside the eligible set.
- Candidate-level buckets are assigned only where a frozen Rank-6–12 proposal existed; otherwise the miss remains a route/depth/generation error.
- The causal correction layer does not activate from a cause label observed on the same target. It needs repeated earlier examples of the same pre-target signature.

## Safety / integrity
- Cause attribution is post-reveal diagnostic and is never fed back into the same target.
- Correction signatures contain only pre-target candidate evidence.
- A signature needs at least 12 prior frozen proposals, at least 2 prior Top-5 rescues, positive net Top-5, bounded damage, and non-negative Top-10/MRR before live use.
- No threshold is relaxed merely to create a positive result.