# DHAPPA Dynamic Primary Engine Report

Dataset: **240 rows**, 2025-12-13 → 2026-08-29

## Methodology
Strict walk-forward: for each target row (`t-1`), only rows ending at the immediately preceding row (`t-2`) are supplied to engines. Rankings are hashed before the target outcome is evaluated.

## Engines
- DATE_TRIAD (calendar)
- PREVIOUS_DAY (transition)
- DELTA_MATRIX (delta)
- G_SQUARE (square)
- G_SQUARE_HARMONICS (square)
- HARUF_PYRAMID (haruf)
- LOOKBACK_5 (recency)
- ECHO_7 (echo)
- HOT_RECENCY (frequency)
- RASHI_FAMILY (family)
- TRANSITION_MARKOV (transition)
- MODEL_F (composite)

## House-wise Dynamic Primary Results

| House | Targets | Top5 | Top10 | Top21 | Top36 | MRR | Mean rank | Switches | Current primary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 188 | 7.98% | 10.64% | 21.81% | 38.83% | 0.0633 | 48.62 | 28 | HOT_RECENCY |
| Faridabad | 192 | 6.25% | 15.1% | 28.65% | 38.54% | 0.0576 | 46.66 | 19 | HARUF_PYRAMID+DATE_TRIAD |
| Ghaziabad | 191 | 5.76% | 12.57% | 23.56% | 43.46% | 0.0526 | 48.22 | 27 | TRANSITION_MARKOV |
| Gali | 190 | 3.16% | 7.37% | 20.0% | 28.42% | 0.04 | 53.59 | 40 | DATE_TRIAD+G_SQUARE |

## Interpretation
This is a research backtest, not a probability claim. A large candidate tier has a correspondingly large random baseline (Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%). Selection value should therefore be judged by rank quality, stability, and forward lift rather than raw coverage alone.

## Integrity conclusion
The scratch model removes UI coupling and enforces one temporal kernel, immutable prediction hashes, house-wise election, prior-only engine/combination profiles, and explicit ranking-failure logging.