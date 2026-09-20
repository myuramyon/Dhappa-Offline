# DHAPPA Dynamic Primary Engine v2.1 Report

Dataset: **240 rows**, 2025-12-13 → 2026-08-29

## V2.1 election architecture
Champion/challenger gating, 15/30/60/expanding window agreement, minimum-tenure hysteresis, combination survival tests, bounded contextual-regime modifiers, explicit `NO_QUALIFIED_PRIMARY`, plus paired Champion Protection: a challenger must beat the incumbent on the same prior historical targets without creating more Top-5 damage than rescues.

## Temporal methodology
For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.

## House-wise results

| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 173 | 15 | 92.02% | 6.94% | 12.72% | 20.81% | 35.84% | 0.0565 | 49.4 | 4 | HOT_RECENCY |
| Faridabad | 192 | 177 | 15 | 92.19% | 7.34% | 11.3% | 22.03% | 37.85% | 0.0554 | 49.62 | 5 | G_SQUARE_HARMONICS |
| Ghaziabad | 191 | 174 | 17 | 91.1% | 3.45% | 9.2% | 22.99% | 44.83% | 0.0464 | 47.23 | 4 | HARUF_PYRAMID |
| Gali | 190 | 175 | 15 | 92.11% | 2.29% | 8.57% | 18.29% | 29.71% | 0.0386 | 54.0 | 7 | ECHO_7 |

## Interpretation
V2.1 is allowed to abstain and blocks score-only challenger switches. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.

## Integrity conclusion
V2.1 preserves the prior-only election ordering and adds paired challenger proof before incumbent replacement. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.