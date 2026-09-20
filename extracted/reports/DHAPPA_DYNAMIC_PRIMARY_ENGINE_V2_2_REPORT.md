# DHAPPA Dynamic Primary Engine v2.2 Report

Dataset: **240 rows**, 2026-01-03 → 2026-09-19

## V2.2 election architecture
Champion/challenger gating with asymmetric incumbent protection. STRONG/MODERATE/WEAK/FAILING incumbent tiers receive progressively lower replacement friction. Paired rank evidence and a Top-5 damage budget are retained, while failing incumbents may be replaced rapidly or yield `NO_QUALIFIED_PRIMARY` rather than being locked in.

## Temporal methodology
For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.

## House-wise results

| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 170 | 18 | 90.43% | 7.06% | 11.18% | 22.35% | 34.71% | 0.0474 | 51.02 | 17 | HOT_RECENCY |
| Faridabad | 192 | 177 | 15 | 92.19% | 2.82% | 6.21% | 18.64% | 31.64% | 0.0425 | 50.3 | 12 | HARUF_PYRAMID+DELTA_MATRIX+PREVIOUS_DAY |
| Ghaziabad | 192 | 176 | 16 | 91.67% | 4.55% | 10.23% | 19.89% | 41.48% | 0.0434 | 50.21 | 10 | TRANSITION_MARKOV |
| Gali | 191 | 175 | 16 | 91.62% | 6.86% | 8.57% | 18.29% | 29.71% | 0.0545 | 54.01 | 14 | DATE_TRIAD+G_SQUARE_HARMONICS |

## Interpretation
V2.2 is allowed to abstain and uses tier-dependent challenger proof rather than universal champion protection. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.

## Integrity conclusion
V2.2 preserves prior-only election ordering while making champion protection asymmetric to avoid weak-incumbent lock-in. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.