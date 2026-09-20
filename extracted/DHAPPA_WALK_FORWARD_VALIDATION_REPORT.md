# DHAPPA Walk-Forward Validation Report

## 1. Methodology
For every eligible target date after the 15-row warm-up, each engine receives only `ROWS[:i]`. The ranking is frozen, the freeze hash is stored, and the actual target row is evaluated afterward. Consensus reconstructs the 36-pool from the engine rankings generated for that same frozen source.

## 2. Dataset
The current canonical dataset contains 809 daily rows. The replay generated 41,288 engine and consensus house records, with 767 evaluated samples per house after excluding rows with no actual value for that house.

## 3. Temporal Integrity
All 41,288 records passed `source_cutoff < target_date`. The persisted integrity report is `reports/walkforward_integrity_report.json` and reports `pass: true`.

## 4. Engine-by-Engine Results
Each of the 12 engines has persisted per-house records and expanding, 15-target, 30-target, and 60-target summaries in `reports/engine_window_metrics.json`.

## 5. House-Wise Hit Rates
House summaries are kept independently for Deshawar, Faridabad, Ghaziabad, and Gali. No house values are merged into a single hit-rate denominator.

## 6. Consensus Results
The 36 Consensus Pool has independent per-house replay records in `reports/consensus_walkforward_validation.json` and house summaries in `reports/consensus_house_hit_rates.json`.

## 7. Window Metrics
The frontend exposes 15, 30, 60, and expanding-history metric windows. Metrics include H@5, H@10, H@21, H@36, sample count, and evidence level.

## 8. Rank Quality
Persisted summaries include MRR, mean rank, median rank, best rank, and worst rank. The replay records retain actual rank for every evaluated target.

## 9. Failure Analysis
Generation and ranking failures are classified separately in each model-house summary and in `reports/walkforward_failure_analysis.json`. Misses are not removed from the replay.

## 10. Weekday and Parity Diagnostics
Each replay record stores target weekday and actual parity so weekday and odd/even diagnostics can be added without reconstructing or contaminating the replay.

## 11. Current Model Summary
The live model views show current rankings beside historical walk-forward H@5, H@10, samples, evidence, and expandable replay history. No probability claim is made.

## 12. Weaknesses
A ranking failure means the actual value was outside the model's generated Top-36; it is not equivalent to a generation failure. Low-sample contexts are labeled `INSUFFICIENT_EVIDENCE` rather than presented as reliable performance.

## 13. Evidence-Based Conclusion
The validation is leakage-controlled at the source-history boundary and auditable through freeze hashes, target dates, source cutoffs, actual ranks, and persisted replay artifacts. Performance should be interpreted house by house and window by window rather than as a single leaderboard.
