# DHAPPA Daywise Engine Performance Report

## 1. Walk-forward methodology
Every target is evaluated from source history strictly before the target. The prediction is frozen and hashed before the actual value is inspected. Consensus is reconstructed from the engine rankings for that same cutoff.

## 2. Dataset and temporal integrity
The current replay covers 795 historical target dates after warm-up. All persisted records pass `source_cutoff < target_date`.

## 3. Day-wise validation
The day-wise API provides one row per target date, four house outcomes, hits, misses, and descriptive sweep classification. The default dashboard tier is Top-5; Top-10, Top-21, and Top-36 are selectable.

## 4. Sweep distribution
The generated sweep artifact stores the 0/4 through 4/4 distribution for every supported tier. These are historical summaries, not future certainty claims.

## 5. House-wise performance
Engine and consensus performance remains separated by Deshawar, Faridabad, Ghaziabad, and Gali. Every leaderboard row includes hit tiers, MRR, and sample count.

## 6. Best engine by house
Best-engine cards use a sample-aware composite of expanding H@5, expanding H@10, MRR, recent-30 H@5, and recent-60 H@5. Consensus is included as a comparable model. Long-term and recent leaders are retained in the persisted leaderboard data.

## 7. Recent and long-term windows
The engine window artifact stores 15, 30, 60, and expanding metrics for every engine-house pair. The dashboard exposes the expanding leaderboard and the selected tier.

## 8. Coverage and failures
Replay records retain generation failures, ranking failures, actual rank, and freeze hash. No misses are silently removed.

## 9. API surfaces
- `/api/walkforward/daywise`
- `/api/walkforward/house-leaderboard`
- `/api/walkforward/best-engine-by-house`
- `/api/walkforward/summary`

## 10. Evidence-based conclusion
The dashboard answers daily house-hit count, house-wise strongest historical model, and tier-specific hit rate from strict freeze-first replay data. It does not present hit rate as probability.
