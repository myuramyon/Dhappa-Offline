from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from dhappa import model_v2_5 as core

ROWS=core.load_csv(ROOT/'data'/'Merged_Workbook.csv')
WEIGHTS={
 'DATE_TRIAD':1.50,'PREVIOUS_DAY':1.10,'DELTA_MATRIX':0.90,'G_SQUARE':1.00,
 'G_SQUARE_HARMONICS':1.00,'HARUF_PYRAMID':1.20,'LOOKBACK_5':1.00,'ECHO_7':0.80,
 'HOT_RECENCY':0.70,'RASHI_FAMILY':0.90,'TRANSITION_MARKOV':1.20,'MODEL_F':1.30,
}

def consensus(history,house,target_date):
    score={f'{i:02d}':0.0 for i in range(100)}
    support={f'{i:02d}':[] for i in range(100)}
    for eng in core.ENGINES:
        out=eng.rank(history,house,target_date)
        top=out.ranking[:36]; w=WEIGHTS.get(eng.name,1.0); n=len(top)
        for idx,c in enumerate(top):
            pos=(n-idx)/max(1,n)
            score[c]+=w*pos
            support[c].append(eng.name)
    ranked=sorted(score,key=lambda c:(-score[c],-len(support[c]),c))
    return ranked,score,support

def metric(events):
    if not events:return {'n':0,'h5':0,'h10':0,'h21':0,'h36':0,'mrr':0,'median_rank':101,'mean_rank':101}
    ranks=sorted(e['rank'] for e in events); n=len(ranks)
    med=ranks[n//2] if n%2 else (ranks[n//2-1]+ranks[n//2])/2
    return {'n':n,'h5':sum(r<=5 for r in ranks)/n,'h10':sum(r<=10 for r in ranks)/n,'h21':sum(r<=21 for r in ranks)/n,'h36':sum(r<=36 for r in ranks)/n,
            'mrr':sum(1/r for r in ranks)/n,'median_rank':med,'mean_rank':sum(ranks)/n}

events={h:[] for h in core.HOUSES}
for i in range(15,len(ROWS)):
    hist=ROWS[:i]; target=ROWS[i]; td=target['date']
    for h in core.HOUSES:
        ranked,_,_=consensus(hist,h,td); actual=target.get(h)
        if not actual: continue
        r=ranked.index(actual)+1
        events[h].append({'date':td,'rank':r})
out={}
for h,ev in events.items():
    out[h]={str(w):metric(ev[-w:]) for w in (15,30,60)}
    out[h]['expanding']=metric(ev)
    out[h]['events']=ev
(ROOT/'reports'/'consensus36_performance.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
(ROOT/'reports'/'consensus36_weights.json').write_text(json.dumps(WEIGHTS,indent=2),encoding='utf-8')
print('wrote metrics', {h:out[h]['expanding']['n'] for h in core.HOUSES})
