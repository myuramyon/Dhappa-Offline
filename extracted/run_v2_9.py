from pathlib import Path
from dhappa import model_v2_5 as base
from dhappa import model_v2_9 as v29
ROOT=Path(__file__).resolve().parent
rows=base.load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
res=v29.run_walkforward(rows,min_train=45,max_combo=3)
rep=v29.save_all(ROOT,rows,*res)
print('completed',rep['model'])
for h,m in rep['house_metrics'].items(): print(h,m)
