from pathlib import Path
import json
from datetime import datetime
R=Path(__file__).resolve().parent/'reports'
fmt='%Y-%m-%d'
issues=[]
log=json.loads((R/'post_admission_challenger_tournament_v2_9.json').read_text())
for r in log:
    if datetime.strptime(r['source_cutoff'],fmt) >= datetime.strptime(r['date'],fmt):
        issues.append(('cutoff',r['date'],r['house']))
    p=r.get('proof') or {}
    if r['state']=='BOUNDARY_CHALLENGER_WINS_TOURNAMENT' and not r.get('passed'):
        issues.append(('winner_without_pass',r['date'],r['house']))
    if r.get('passed') and p.get('net_top5',0)<=0:
        issues.append(('pass_without_net_rescue',r['date'],r['house']))
print(json.dumps({'checked':len(log),'issues':issues,'status':'PASS' if not issues else 'FAIL'},indent=2))
(R/'primary_engine_integrity_report_v2_9.json').write_text(json.dumps({'checked':len(log),'issues':issues,'status':'PASS' if not issues else 'FAIL'},indent=2))
