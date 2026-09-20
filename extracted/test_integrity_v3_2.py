from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'reports'/'contextual_rescue_attribution_v3_2.json').read_text())
issues=[]
for x in rows:
    if not (x['source_cutoff'] < x['date']):
        issues.append(('cutoff',x['date'],x['house']))
    if x['active']:
        st=x.get('contextual_status',{})
        if not st.get('active'):
            issues.append(('active_without_context',x['date'],x['house']))
        sc=st.get('selected_context') or {}
        ex=sc.get('expanding') or {}
        rc=sc.get('recent') or {}
        if ex.get('rescued5',0)<2 or ex.get('net5',0)<2 or ex.get('damaged5',99)>1 or ex.get('net10',-99)<0 or ex.get('mrr_delta',-99)<0:
            issues.append(('bad_context_gate',x['date'],x['house']))
        if rc.get('net5',-99)<0 or rc.get('net10',-99)<0 or rc.get('mrr_delta',-99)<0:
            issues.append(('bad_recent_gate',x['date'],x['house']))
print({'records':len(rows),'active':sum(1 for x in rows if x['active']),'issues':issues[:20],'status':'PASS' if not issues else 'FAIL'})
