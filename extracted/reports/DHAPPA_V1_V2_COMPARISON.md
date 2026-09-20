# DHAPPA V1 vs V2 Bounded Replay Comparison

Same packaged 240-row bounded replay. V2 candidate generators are unchanged; only election/routing logic is different.

| House | V1 Top5 | V2 Top5 elected | V2 Top5 all targets | V1 Top10 | V2 Top10 elected | V1 switches | V2 switches | Abstain | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deshawar | 7.98% | 7.6% | 6.91% | 10.64% | 10.53% | 28 | 11 | 17 | 90.96% |
| Faridabad | 6.25% | 6.21% | 5.73% | 15.1% | 14.69% | 19 | 12 | 15 | 92.19% |
| Ghaziabad | 5.76% | 5.75% | 5.24% | 12.57% | 11.49% | 27 | 12 | 17 | 91.1% |
| Gali | 3.16% | 3.43% | 3.16% | 7.37% | 7.43% | 40 | 13 | 15 | 92.11% |

## Reading the result
V2 should not be judged only on conditional elected-target hit rate. Coverage and all-target performance are shown to prevent abstention from creating a misleading improvement. On this bounded replay, V2 improves selection discipline but does not uniformly improve predictive ranking across all houses.