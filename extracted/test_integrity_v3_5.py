from pathlib import Path
import json
from datetime import date
R=Path(__file__).resolve().parent/'reports'
rows=json.loads((R/'activation_precision_controller_v3_5.json').read_text())
issues=[]
active=[x for x in rows if x['active']]
for x in rows:
    if x.get('source_cutoff') and x['source_cutoff'] >= x['date']:
        issues.append({'date':x['date'],'house':x['house'],'issue':'source cutoff not prior to target'})
    if x['active'] and (not x['static_gate_pass'] or not x['controller_pass']):
        issues.append({'date':x['date'],'house':x['house'],'issue':'activation bypassed gate'})
    if x['active'] and x['v3_5_rank'] != x['rescue_rank']:
        issues.append({'date':x['date'],'house':x['house'],'issue':'active correction did not use frozen rescue rank'})
    if not x['active'] and x['v3_5_rank'] != x['v3_3_rank']:
        issues.append({'date':x['date'],'house':x['house'],'issue':'inactive controller altered baseline'})
material=[x for x in rows if x['v3_4_rank'] != x['v3_3_rank']]
if len(material)!=1 or not material[0]['active']:
    issues.append({'issue':'v3.5 did not preserve the sole material v3.4 correction','material_count':len(material)})
out={'records_checked':len(rows),'active_records':len(active),'material_v3_4_rank_changes':len(material),'issues':issues,'status':'PASS' if not issues else 'FAIL'}
(R/'activation_precision_integrity_v3_5.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
