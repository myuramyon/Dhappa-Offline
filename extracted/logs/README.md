# DHAPPA Runtime & Audit Logs

All logs are append-only JSON Lines (JSONL) written locally by the application.

- `runtime.log.jsonl` — startup/shutdown/runtime lifecycle
- `access.log.jsonl` — local API/page requests (no raw import payloads)
- `errors.log.jsonl` — caught exceptions and tracebacks
- `data_import.log.jsonl` — import preview/commit summaries, not raw CSV contents
- `engine_execution.log.jsonl` — engine execution summaries by target
- `engine_predictions.log.jsonl` — per engine/house Top-36 ranking snapshots
- `consensus36.log.jsonl` — consensus Top-36 snapshots and actual rank when known
- `metrics_rebuild.log.jsonl` — metric rebuild lifecycle and counts
- `integrity_audit.log.jsonl` — source-cutoff/freeze/integrity checks
- `change_audit.log.jsonl` — data backup/import/change events
- `security.log.jsonl` — security/integrity related events

Raw uploaded CSV bodies are intentionally not logged.
