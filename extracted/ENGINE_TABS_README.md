# DHAPPA Engine Lab — 12 Individual Engines + 36 Consensus Pool

Run on Windows by double-clicking `START_ENGINE_TABS.bat`, or run:

```bash
python app_engine_tabs.py
```

The browser opens at `http://127.0.0.1:8765`.

## Dedicated tabs

- **36 CONSENSUS POOL** — separate legacy weighted-Borda Top-36 consensus tab adapted to the current 12-engine registry.
- DATE_TRIAD
- PREVIOUS_DAY
- DELTA_MATRIX
- G_SQUARE
- G_SQUARE_HARMONICS
- HARUF_PYRAMID
- LOOKBACK_5
- ECHO_7
- HOT_RECENCY
- RASHI_FAMILY
- TRANSITION_MARKOV
- MODEL_F

## 36 Consensus Pool tab

For each DS / FB / GB / GL house it shows:
- ranked Top-5 / Top-10 / Top-21 / Top-36 tiers;
- actual historical result and exact consensus rank when a historical date is selected;
- 15 / 30 / 60 / expanding H@5, H@10, H@21, H@36, MRR and mean actual rank;
- each Top-36 candidate's weighted consensus score;
- engine support count;
- exact list of contributing engines.

The pool follows the earlier **weighted Borda** idea: only each engine's frozen Top-36 contributes, with position decay and an engine weight. The current 12 canonical engine registry is used, so the pool stays aligned with the individual engine tabs.

Historical evaluation is strict: the selected target date is excluded from generation, the ranking is reconstructed using only prior rows, and the actual result is displayed afterward for audit. `NEXT TARGET` uses the latest available history and does not fabricate an outcome.

## Bulk Data Import tab

A first-class **BULK DATA IMPORT** tab has been added. It supports CSV upload, multi-line row paste, and one-row-at-a-time entry with validation, merge/replace modes, backups, normalized export, and automatic metric rebuild. See `BULK_IMPORT_README.md`.
