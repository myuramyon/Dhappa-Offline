from pathlib import Path
from dhappa.model import load_csv,run_walkforward,save_all
ROOT=Path(__file__).resolve().parent
rows=load_csv(ROOT/'data'/'Merged_Workbook.csv')
# bounded validation replay for packaged smoke/backtest; remove this slice for full history
rows=rows[-240:]
evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug=run_walkforward(rows,min_train=45,max_combo=3)
rep=save_all(ROOT,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug)
print('completed',rep['model'])
for h,m in rep['house_metrics'].items(): print(h,m)
