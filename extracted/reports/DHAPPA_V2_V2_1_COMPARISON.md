# DHAPPA v2 vs v2.1 — Champion Protection Comparison

V2.1 adds paired challenger proof before a qualified challenger can replace the incumbent. The comparison below uses the same bounded 240-row replay.

| House | V2 Top5 | V2.1 Top5 | Δ Top5 | V2 Top10 | V2.1 Top10 | Δ Top10 | V2 switches | V2.1 switches | V2.1 current |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Deshawar | 7.6% | 6.94% | -0.66 pp | 10.53% | 12.72% | +2.19 pp | 11 | 4 | HOT_RECENCY |
| Faridabad | 6.21% | 7.34% | +1.13 pp | 14.69% | 11.3% | -3.39 pp | 12 | 5 | G_SQUARE_HARMONICS |
| Ghaziabad | 5.75% | 3.45% | -2.30 pp | 11.49% | 9.2% | -2.29 pp | 12 | 4 | HARUF_PYRAMID |
| Gali | 3.43% | 2.29% | -1.14 pp | 7.43% | 8.57% | +1.14 pp | 13 | 7 | ECHO_7 |

## Interpretation
Champion Protection materially reduced engine switching. However, lower switching is not itself a prediction improvement. Deshawar and Faridabad show mixed changes; Ghaziabad and Gali lose Top-5 performance under the current proof gate. Therefore v2.1 should be treated as a diagnostic branch, not automatically promoted over v2.

## Next refinement
The proof gate should become asymmetric: protect a demonstrably strong incumbent, but allow faster replacement of a weak incumbent when an alternative has materially better same-date paired rank quality. A future v2.2 should use incumbent-strength tiers and damage-budgeted switching instead of one universal protection threshold.