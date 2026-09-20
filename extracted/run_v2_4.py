from pathlib import Path
from dhappa.model_v2_4 import load_csv,run_walkforward,save_all
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
res=run_walkforward(rows,min_train=45,max_combo=3)
evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history=res
rep=save_all(ROOT,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history)
print('completed',rep['model'])
for h,m in rep['house_metrics'].items(): print(h,m)
