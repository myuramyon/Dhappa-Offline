from pathlib import Path
import hashlib, sys
ROOT=Path(__file__).resolve().parent
manifest=ROOT/'SHA256SUMS.txt'
if not manifest.exists():
    print('SHA256SUMS.txt not found');sys.exit(2)
failed=[];checked=0
for line in manifest.read_text(encoding='utf-8').splitlines():
    if not line.strip():continue
    expected, rel=line.split('  ',1)
    p=ROOT/rel
    if not p.exists(): failed.append((rel,'MISSING',expected));continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    actual=h.hexdigest();checked+=1
    if actual!=expected:failed.append((rel,actual,expected))
print(f'Checked {checked} files')
if failed:
    print(f'FAILED: {len(failed)} integrity issue(s)')
    for rel,actual,expected in failed[:50]: print(rel, actual, 'expected', expected)
    sys.exit(1)
print('PASS: all packaged files match SHA256SUMS.txt')
