from pathlib import Path
from dhappa.model_v2_5 import load_csv,run_walkforward
from dhappa.model_v2_6 import counterfactual_lab
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
res=run_walkforward(rows,min_train=45,max_combo=3)
timeline=res[2]; debug=res[6]
records=counterfactual_lab(rows,timeline,debug,min_train=45,max_combo=3)
assert len(records)==len(timeline)
tm={(x['date'],x['house']):x for x in timeline}
issues=[]
for r in records:
    t=tm[(r['date'],r['house'])]
    if not (r['source_cutoff'] < r['date']): issues.append(('TEMPORAL',r['date'],r['house']))
    if r['selected']!=t['primary'] or r['selected_rank']!=t['actual_rank']:
        issues.append(('MUTATED_ELECTION',r['date'],r['house']))
    if r['classification']=='ELECTION_MISS' and not (r['best_eligible_rank'] and r['best_eligible_rank']<=5):
        issues.append(('BAD_ELECTION_LABEL',r['date'],r['house']))
    if r['classification']=='QUALIFICATION_MISS' and not (r['best_any_rank']<=5):
        issues.append(('BAD_QUAL_LABEL',r['date'],r['house']))
    if r['classification']=='GENERATION_MISS' and not (r['best_any_rank']>36):
        issues.append(('BAD_GEN_LABEL',r['date'],r['house']))
assert not issues, issues[:10]
print('PASS',len(records),'counterfactual records; no election mutation; strict prior cutoff preserved')
