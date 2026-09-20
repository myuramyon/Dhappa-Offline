from pathlib import Path
import json,sys
R=Path(__file__).resolve().parent/'reports'
recs=json.loads((R/'error_specific_weight_calibration_v3_4.json').read_text())
issues=[]
for z in recs:
    if z.get('chosen_family') and z['chosen_family'] not in z.get('triggered_families',[]): issues.append((z['date'],z['house'],'chosen_not_triggered'))
    if z.get('chosen_family') and z['v3_4_rank'] != z['rescue_rank']: issues.append((z['date'],z['house'],'active_without_frozen_rescue_rank'))
print(json.dumps({'records_checked':len(recs),'issues':issues,'status':'PASS' if not issues else 'FAIL'},indent=2))
sys.exit(1 if issues else 0)
