from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parent
r=json.loads((ROOT/'reports'/'primary_engine_election_timeline_v2_5.json').read_text())
issues=[]
for x in r:
    if x['source_cutoff'] >= x['date']:
        issues.append(('cutoff',x['date'],x['house']))
    if x['primary']=='NO_QUALIFIED_PRIMARY' and x.get('actual_rank') is not None:
        issues.append(('abstention_rank',x['date'],x['house']))
    if x['primary']!='NO_QUALIFIED_PRIMARY' and not x.get('freeze_hash'):
        issues.append(('missing_hash',x['date'],x['house']))
ph=json.loads((ROOT/'reports'/'house_policy_history_v2_5.json').read_text())
for x in ph:
    if x['meta'].get('reason') not in {'WARMUP_RETAIN_CURRENT_POLICY','RETAIN_CURRENT_POLICY_NO_PARETO_DOMINANCE','PRIOR_ONLY_PARETO_POLICY_PROMOTION'}:
        issues.append(('policy_reason',x['date'],x['house'],x['meta'].get('reason')))
print(json.dumps({'checked_targets':len(r),'policy_records':len(ph),'issues':issues[:20],'pass':not issues},indent=2))
sys.exit(1 if issues else 0)
