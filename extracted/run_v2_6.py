from pathlib import Path
from dhappa.model_v2_5 import load_csv, run_walkforward
from dhappa.model_v2_6 import counterfactual_lab, save_counterfactual
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
res=run_walkforward(rows,min_train=45,max_combo=3)
evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history=res
records=counterfactual_lab(rows,timeline,election_debug,min_train=45,max_combo=3)
summary=save_counterfactual(ROOT,records)
print('completed DHAPPA v2.6 Route-Level Counterfactual Election Lab')
for h,m in summary.items(): print(h,m)
