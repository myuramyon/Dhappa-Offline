# DHAPPA Dynamic Primary Engine v2 Report

Dataset: **240 rows**, 2025-12-13 → 2026-08-29

## V2 election architecture
Champion/challenger gating, 15/30/60/expanding window agreement, minimum-tenure hysteresis, combination survival tests, bounded contextual-regime modifiers, and an explicit `NO_QUALIFIED_PRIMARY` abstention state.

## Temporal methodology
For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.

## House-wise results

| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 171 | 17 | 90.96% | 7.6% | 10.53% | 19.3% | 36.84% | 0.0607 | 49.19 | 11 | ECHO_7 |
| Faridabad | 192 | 177 | 15 | 92.19% | 6.21% | 14.69% | 27.12% | 37.29% | 0.0569 | 47.94 | 12 | MODEL_F |
| Ghaziabad | 191 | 174 | 17 | 91.1% | 5.75% | 11.49% | 25.29% | 45.4% | 0.0504 | 47.06 | 12 | TRANSITION_MARKOV |
| Gali | 190 | 175 | 15 | 92.11% | 3.43% | 7.43% | 17.71% | 30.86% | 0.0399 | 53.33 | 13 | ECHO_7 |

## Interpretation
V2 is allowed to abstain. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.

## Integrity conclusion
V2 removes the v1 append-then-strip pattern. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.