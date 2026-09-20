from pathlib import Path
import json
from datetime import datetime
ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
log=json.loads((R/'candidate_rank6_12_rescue_v3_1.json').read_text())
issues=[]
for x in log:
    d=datetime.fromisoformat(x['date']); c=datetime.fromisoformat(x['source_cutoff'])
    if not c<d: issues.append({'type':'TEMPORAL_CUTOFF','record':x})
    if x['active']:
        st=x.get('status',{})
        if not st.get('active') or st.get('reason')!='PROBATION_SURVIVED':
            issues.append({'type':'INVALID_LIVE_ACTIVATION','record':x})
        if x['challenger']==x['incumbent']:
            issues.append({'type':'IDENTICAL_SWAP','record':x})
print(json.dumps({'checked':len(log),'live_activations':sum(bool(x['active']) for x in log),'issues':len(issues),'status':'PASS' if not issues else 'FAIL','sample_issues':issues[:5]},indent=2))
raise SystemExit(1 if issues else 0)
