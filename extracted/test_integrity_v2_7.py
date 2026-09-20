from pathlib import Path
import json
from datetime import datetime
R=Path(__file__).resolve().parent/'reports'
dec=json.load(open(R/'dynamic_election_decisions_v2_7.json'))
log=json.load(open(R/'prospective_route_discriminator_v2_7.json'))
back=json.load(open(R/'dynamic_primary_engine_backtest_v2_7.json'))
issues=[]
# Temporal checks rely on log source cutoffs and dates.
for x in log:
    try:
        d=datetime.fromisoformat(x['date']); c=datetime.fromisoformat(x['source_cutoff'])
        if not c<d: issues.append(('TEMPORAL',x['date'],x['house']))
    except Exception as e: issues.append(('DATE_PARSE',str(e)))
for x in dec:
    dm=x.get('discriminator') or {}
    if dm.get('shadow_active'):
        if dm.get('mode')!='ONLINE_LOGIT': issues.append(('ACTIVE_WITHOUT_MODEL',x['date'],x['house']))
        if dm.get('shadow_net5',0)<2 or dm.get('recent30_net5',0)<1: issues.append(('ACTIVE_WITHOUT_TOP5_SURVIVAL',x['date'],x['house']))
        if dm.get('shadow_net10',-1)<0 or dm.get('recent30_net10',-1)<0: issues.append(('ACTIVE_WITH_TOP10_DAMAGE',x['date'],x['house']))
        if dm.get('shadow_mrr_delta',0)<=0 or dm.get('recent30_mrr_delta',0)<=0: issues.append(('ACTIVE_WITH_MRR_DAMAGE',x['date'],x['house']))
print(json.dumps({'checked_logs':len(log),'checked_decisions':len(dec),'issues':issues,'status':'PASS' if not issues else 'FAIL'},indent=2))
raise SystemExit(0 if not issues else 1)
