# DHAPPA Dynamic Primary Engine v2.5 Report

Dataset: **240 rows**, 2025-12-13 → 2026-08-29

## V2.5 election architecture
House-specific policy learning now uses Pareto survival against BALANCED, the current incumbent policy, and the recent surviving policy. A candidate policy is promoted only when it is non-inferior on protected metrics across all references and has strict prior-only gain; otherwise RETAIN_CURRENT_POLICY is emitted.

## Temporal methodology
For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.

## House-wise results

| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 172 | 16 | 91.49% | 8.14% | 11.05% | 23.26% | 39.53% | 0.0598 | 49.77 | 8 | HOT_RECENCY |
| Faridabad | 192 | 177 | 15 | 92.19% | 5.65% | 12.99% | 26.55% | 38.42% | 0.0599 | 47.55 | 11 | G_SQUARE_HARMONICS |
| Ghaziabad | 191 | 176 | 15 | 92.15% | 5.68% | 11.93% | 26.14% | 47.73% | 0.0505 | 47.45 | 8 | TRANSITION_MARKOV |
| Gali | 190 | 175 | 15 | 92.11% | 4.57% | 8.57% | 20.0% | 31.43% | 0.0441 | 52.57 | 12 | ECHO_7 |

## Interpretation
V2.5 is allowed to abstain and learns its switch policy separately by house. Policy promotion is Pareto/damage-averse: a candidate must survive against BALANCED, current incumbent policy, and recent surviving policy on prior completed challenger events; otherwise the current policy is retained. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.

## Integrity conclusion
V2.5 preserves prior-only election ordering while adding prior-only multi-baseline Pareto survival before a learned house policy may replace the incumbent policy. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.