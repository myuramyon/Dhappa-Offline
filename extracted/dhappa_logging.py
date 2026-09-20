from __future__ import annotations
import json, os, threading, traceback, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOCK = threading.RLock()

LOG_FILES = {
    'runtime': 'runtime.log.jsonl',
    'access': 'access.log.jsonl',
    'errors': 'errors.log.jsonl',
    'imports': 'data_import.log.jsonl',
    'engines': 'engine_execution.log.jsonl',
    'predictions': 'engine_predictions.log.jsonl',
    'consensus': 'consensus36.log.jsonl',
    'metrics': 'metrics_rebuild.log.jsonl',
    'integrity': 'integrity_audit.log.jsonl',
    'changes': 'change_audit.log.jsonl',
    'security': 'security.log.jsonl',
}

def _now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def _safe(value):
    if isinstance(value, Path): return str(value)
    if isinstance(value, (str,int,float,bool)) or value is None: return value
    if isinstance(value, dict): return {str(k): _safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple,set)): return [_safe(v) for v in value]
    return repr(value)

def log(kind: str, event: str, **fields):
    file_name = LOG_FILES.get(kind, f'{kind}.log.jsonl')
    rec = {'ts_utc': _now(), 'kind': kind, 'event': event, **{k:_safe(v) for k,v in fields.items()}}
    line = json.dumps(rec, ensure_ascii=False, separators=(',',':'))
    with _LOCK:
        p = LOG_DIR / file_name
        with open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.write(line+'\n')
    return rec

def log_exception(event: str, exc: BaseException, **fields):
    return log('errors', event, error_type=type(exc).__name__, error=str(exc), traceback=''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-8000:], **fields)

def sha256_file(path: Path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def initialize_log_files():
    for file_name in LOG_FILES.values():
        p=LOG_DIR/file_name
        if not p.exists(): p.touch()
    readme=LOG_DIR/'README.md'
    if not readme.exists():
        readme.write_text('''# DHAPPA Runtime & Audit Logs\n\nAll logs are append-only JSON Lines (JSONL) written locally by the application.\n\n- `runtime.log.jsonl` — startup/shutdown/runtime lifecycle\n- `access.log.jsonl` — local API/page requests (no raw import payloads)\n- `errors.log.jsonl` — caught exceptions and tracebacks\n- `data_import.log.jsonl` — import preview/commit summaries, not raw CSV contents\n- `engine_execution.log.jsonl` — engine execution summaries by target\n- `engine_predictions.log.jsonl` — per engine/house Top-36 ranking snapshots\n- `consensus36.log.jsonl` — consensus Top-36 snapshots and actual rank when known\n- `metrics_rebuild.log.jsonl` — metric rebuild lifecycle and counts\n- `integrity_audit.log.jsonl` — source-cutoff/freeze/integrity checks\n- `change_audit.log.jsonl` — data backup/import/change events\n- `security.log.jsonl` — security/integrity related events\n\nRaw uploaded CSV bodies are intentionally not logged.\n''', encoding='utf-8')
initialize_log_files()
