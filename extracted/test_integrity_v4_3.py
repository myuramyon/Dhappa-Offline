from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent; R=ROOT/'reports'
recs=json.loads((R/'pairwise_candidate_ordering_v4_3.json').read_text())
acts=json.loads((R/'pairwise_candidate_ordering_activations_v4_3.json').read_text())
issues=[]
for r in recs:
    if not r['source_cutoff'] < r['date']: issues.append((r['date'],r['house'],'cutoff_not_prior'))
    if len(r.get('freeze_hash','')) != 64: issues.append((r['date'],r['house'],'bad_freeze_hash'))
    if r['live'] and r['state']!='LIVE': issues.append((r['date'],r['house'],'live_state_mismatch'))
for a in acts:
    if a['rescued'] and a['damaged']: issues.append((a['date'],a['house'],'rescue_and_damage'))
out={'records_checked':len(recs),'activations_checked':len(acts),'issues':issues,'pass':not issues}
(R/'pairwise_candidate_ordering_integrity_test_v4_3.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
