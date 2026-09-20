# DHAPPA Dynamic Primary Engine v2.3 Report

Dataset: **240 rows**, 2025-12-13 → 2026-08-29

## V2.3 election architecture
Champion/challenger gating now adds prior-only house-specific policy learning. Each house selects among conservative, balanced, adaptive, and fast-rescue policies using only completed challenger events. The calibration utility jointly values Top-5 rescue, Top-10 rank quality, MRR/rank improvement, damaged-hit avoidance, and switching cost.

## Temporal methodology
For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.

## House-wise results

| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 172 | 16 | 91.49% | 7.56% | 10.47% | 22.67% | 38.95% | 0.0583 | 50.13 | 8 | HOT_RECENCY |
| Faridabad | 192 | 177 | 15 | 92.19% | 4.52% | 12.43% | 25.42% | 37.29% | 0.0557 | 47.99 | 11 | G_SQUARE_HARMONICS |
| Ghaziabad | 191 | 176 | 15 | 92.15% | 5.68% | 11.93% | 26.14% | 47.73% | 0.0505 | 47.45 | 8 | TRANSITION_MARKOV |
| Gali | 190 | 175 | 15 | 92.11% | 4.57% | 8.57% | 20.0% | 31.43% | 0.0441 | 52.57 | 12 | ECHO_7 |

## Interpretation
V2.3 is allowed to abstain and learns its switch policy separately by house from prior completed challenger events rather than hardcoding a house label. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.

## Integrity conclusion
V2.3 preserves prior-only election ordering while calibrating house-specific switching policy strictly from already revealed historical challenger events. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.