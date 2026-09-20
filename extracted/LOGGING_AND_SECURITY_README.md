# DHAPPA Logging, Audit & Package Integrity

This build contains local structured logging for the complete Engine Lab + 36 Consensus + Bulk Import workflow.

## Log files
All runtime logs are under `logs/` and use JSON Lines (`.jsonl`) so every line is an independent machine-readable event.

- `runtime.log.jsonl` — app startup and evaluation lifecycle
- `access.log.jsonl` — local HTTP/API access metadata
- `errors.log.jsonl` — caught exceptions and tracebacks
- `data_import.log.jsonl` — import preview/commit summaries
- `engine_execution.log.jsonl` — engine execution summaries
- `engine_predictions.log.jsonl` — engine/house frozen Top-36 snapshots
- `consensus36.log.jsonl` — 36 Consensus frozen snapshots
- `metrics_rebuild.log.jsonl` — metric rebuild events
- `integrity_audit.log.jsonl` — source-cutoff / temporal integrity checks
- `change_audit.log.jsonl` — data backup and saved-dataset changes
- `security.log.jsonl` — local-bind and integrity/security events

## Privacy / redaction
Raw CSV upload bodies are NOT written to logs. Import logs contain counts, dates, strategy, sizes and dataset hashes only. The server binds to `127.0.0.1` by default.

## Data safety
Every committed import creates a timestamped copy under `data/backups/` before replacing the canonical CSV. Dataset saves are atomic (`.tmp` then replace).

## Package integrity
`SHA256SUMS.txt` contains SHA-256 hashes of the packaged files (excluding the manifest/checksum files themselves). Run:

- Windows: `VERIFY_PACKAGE.bat`
- Cross-platform: `python verify_integrity.py`

A mismatch means a packaged file changed after the manifest was generated.

## Important note
The checksum manifest provides tamper/corruption detection. It is not password encryption. Store the ZIP in an access-controlled location if confidentiality is required.
