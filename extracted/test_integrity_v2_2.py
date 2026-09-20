from pathlib import Path
from dhappa.model import load_csv, run_walkforward
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-120:]
_,_,timeline,_,_,_,decisions=run_walkforward(rows,min_train=45,max_combo=2)
assert timeline
for x in timeline:
    assert x['source_cutoff'] < x['date'], (x['source_cutoff'],x['date'])
    if x['primary']=='NO_QUALIFIED_PRIMARY':
        assert x['actual_rank'] is None and x['freeze_hash'] is None
    else:
        assert x['freeze_hash'] and len(x['freeze_hash'])==20
print('v2.2 integrity PASS',len(timeline),'targets')
