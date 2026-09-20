# DHAPPA Bulk Data Import

The dashboard now includes a dedicated **BULK DATA IMPORT** tab.

## Supported import modes

1. **CSV file upload**
   - Header-based mapping; column order does not matter.
   - Accepted aliases: `Deshawar/DS/DSWR`, `Faridabad/FB/FRBD`, `Ghaziabad/GB/GZBD`, `Gali/GL`.
   - Date formats accepted by the core: `YYYY-MM-DD`, `MM/DD/YYYY`, `DD/MM/YYYY`.
   - House values: `00` to `99`, or blank/XX/NA for missing.
   - Preview/validation is available before commit.
   - Merge or replace mode is selectable.

2. **Multiple line items / paste mode**
   - One row per line, no header.
   - Fixed order: `Date, Deshawar, Faridabad, Ghaziabad, Gali`.
   - Example: `2026-09-20,35,21,07,86`

3. **Single row entry**
   - Separate Date / DS / FB / GB / GL fields.
   - Duplicate dates update only the supplied nonblank house values.

## Data integrity behavior

- Invalid rows reject the entire commit (no silent partial import).
- Duplicate dates are merged deterministically; later nonblank imported values win.
- Every commit writes a timestamped backup under `data/backups/`.
- Writes are atomic (`.tmp` then replace).
- After commit, the application reloads the dataset and rebuilds:
  - 12 individual-engine historical metrics
  - 36 Consensus Pool historical metrics
- The normalized current dataset can be exported from the Import tab.

## Current bundled dataset

The user-supplied CSV `2 year data (20260920-150917).csv` was validated and loaded as the current dataset for this build:

- 809 normalized unique dates
- 0 invalid rows
- 2024-04-01 through 2026-09-19
- next target resolves to 2026-09-20

## Start

Run `START_ENGINE_TABS.bat` on Windows, then open the **BULK DATA IMPORT** tab.
