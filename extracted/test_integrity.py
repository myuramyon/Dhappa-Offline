from dhappa.model import load_csv, run_walkforward
from pathlib import Path
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-90:]
_,_,timeline,_,_,_,debug=run_walkforward(rows,min_train=45,max_combo=2)
assert timeline and debug
for x in timeline:
    assert x['source_cutoff'] < x['date'], (x['source_cutoff'],x['date'])
    if x['primary'] == 'NO_QUALIFIED_PRIMARY':
        assert x['freeze_hash'] is None
        assert x['actual_rank'] is None
    else:
        assert isinstance(x['freeze_hash'],str) and len(x['freeze_hash']) == 20
        assert 1 <= x['actual_rank'] <= 100
print('integrity tests passed:', len(timeline), 'targets;', sum(x['primary']=="NO_QUALIFIED_PRIMARY" for x in timeline), 'abstentions')
