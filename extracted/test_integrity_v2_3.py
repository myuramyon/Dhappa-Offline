from pathlib import Path
from dhappa.model_v2_3 import load_csv, run_walkforward
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-140:]
*_, timeline, switches, profiles, combo_profiles, decisions, calibration_events, policy_history = run_walkforward(rows,min_train=45,max_combo=2)
assert timeline
for x in timeline:
    assert x['source_cutoff'] < x['date'], (x['source_cutoff'],x['date'])
    assert x['house_policy'] in {'CONSERVATIVE','BALANCED','ADAPTIVE','FAST_RESCUE'}
    if x['primary']=='NO_QUALIFIED_PRIMARY':
        assert x['actual_rank'] is None and x['freeze_hash'] is None
    else:
        assert x['freeze_hash'] and len(x['freeze_hash'])==20
for h, evs in calibration_events.items():
    for e in evs:
        assert e['candidate_rank'] >= 1 and e['incumbent_rank'] >= 1
print('v2.3 integrity PASS',len(timeline),'targets', {h:len(v) for h,v in calibration_events.items()})
