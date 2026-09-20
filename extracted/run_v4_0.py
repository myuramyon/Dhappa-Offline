from pathlib import Path
import json, math, hashlib
from collections import defaultdict, Counter, deque
from itertools import combinations
import numpy as np
from sklearn.linear_model import SGDClassifier
from dhappa import model_v2_5 as base

ROOT=Path(__file__).resolve().parent; R=ROOT/'reports'; R.mkdir(exist_ok=True)
HOUSES=base.HOUSES; ALL=base.ALL
rows=base.load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
decisions=json.loads((R/'dynamic_election_decisions_v2_9.json').read_text())
dec_by={(x['date'],x['house']):x for x in decisions}
fam={e.name:e.family for e in base.ENGINES}

def route_ranking(name, rankings, rel, indep):
    if not name or name=='NO_QUALIFIED_PRIMARY': return None
    mem=tuple(name.split('+'))
    if len(mem)==1:return rankings.get(mem[0])
    if all(m in rankings for m in mem):return base.fuse(rankings,mem,rel,indep)

def gap(hist,house,num,cap=90):
    vals=[r.get(house) for r in hist if r.get(house)]
    for i,q in enumerate(reversed(vals[-cap:]),1):
        if q==num:return i
    return cap+1

def cnt(hist,house,num,n):
    return sum(r.get(house)==num for r in hist[-n:])

def crosscnt(hist,num,n=14):
    return sum(sum(r.get(h)==num for h in HOUSES) for r in hist[-n:])

def feature_vector(num, history, house, target_date, rankings, rel, selected, pr):
    # All features are frozen before target reveal.
    ranks={en: rk.index(num)+1 for en,rk in rankings.items()}
    rs=list(ranks.values())
    support5=sum(r<=5 for r in rs); support10=sum(r<=10 for r in rs); support21=sum(r<=21 for r in rs); support36=sum(r<=36 for r in rs)
    families={fam.get(en,en) for en,r in ranks.items() if r<=10}
    wrr=sum(max(.001,rel.get(en,.001))/r for en,r in ranks.items())
    rr=sum(1/r for r in rs)
    primary_rank=(pr.index(num)+1) if pr else 101
    a,b=map(int,num); d=base.parse_date(target_date)
    vals=[r.get(house) for r in history if r.get(house)]; prev=vals[-1] if vals else None
    pa,pb=(map(int,prev) if prev else (0,0))
    pal=base.rev(num); mir=base.mirror(num)
    primary_members=set((selected or '').split('+')) if selected and selected!='NO_QUALIFIED_PRIMARY' else set()
    primary_support=sum(ranks.get(en,101)<=10 for en in primary_members)
    primary_rel=sum(rel.get(en,0) for en in primary_members)/max(1,len(primary_members))
    valsf=[
      support5/12, support10/12, support21/12, support36/12, len(families)/8,
      rr/12, min(wrr,3)/3, min(rs)/100, np.median(rs)/100, np.mean(rs)/100,
      primary_rank/101, primary_support/max(1,len(primary_members)), min(primary_rel,1),
      a/9,b/9,(a+b)/18,abs(a-b)/9,int(a==b),int(a==0 or b==0),int(base.root(num))/9,
      d.weekday()/6,min(gap(history,house,num),91)/91,
      min(cnt(history,house,num,15),5)/5,min(cnt(history,house,num,30),8)/8,min(cnt(history,house,num,60),12)/12,
      min(cnt(history,house,pal,30),5)/5,min(cnt(history,house,mir,30),5)/5,min(crosscnt(history,num,14),8)/8,
      int(prev is not None and num[0]==prev[0]),int(prev is not None and num[1]==prev[1]),int(prev==pal),int(prev==mir),
      ((a-pa)%10)/9 if prev else 0,((b-pb)%10)/9 if prev else 0,
    ]
    # Engine-rank identity: preserves which engine contributed, not just aggregate support.
    valsf.extend([ranks[e.name]/100 for e in base.ENGINES])
    valsf.extend([min(rel.get(e.name,0),1) for e in base.ENGINES])
    return np.asarray(valsf,dtype=float)

profiles=defaultdict(lambda:defaultdict(list))
models={h:SGDClassifier(loss='log_loss',alpha=0.003,l1_ratio=0.0,penalty='l2',random_state=17,learning_rate='optimal') for h in HOUSES}
model_ready={h:False for h in HOUSES}; seen_targets=Counter()
shadow=defaultdict(list); probation=defaultdict(list); state={h:'SHADOW' for h in HOUSES}; probation_left={h:0 for h in HOUSES}
records=[]; audits=[]

def cmp_stats(xs):
    if not xs:return {'n':0,'net5':0,'net10':0,'mrr_delta':0.0}
    return {'n':len(xs),
      'net5':sum((x['ltr_rank']<=5)-(x['baseline_rank']<=5) for x in xs),
      'net10':sum((x['ltr_rank']<=10)-(x['baseline_rank']<=10) for x in xs),
      'mrr_delta':sum(1/x['ltr_rank']-1/x['baseline_rank'] for x in xs)/len(xs)}

def shadow_gate(h):
    s=shadow[h]; exp=cmp_stats(s); recent=cmp_stats(s[-30:])
    return exp['n']>=45 and exp['net5']>=2 and recent['net5']>=1 and exp['net10']>=0 and recent['net10']>=0 and exp['mrr_delta']>0 and recent['mrr_delta']>=0

def probation_gate(h):
    p=probation[h]; st=cmp_stats(p)
    return st['n']>=15 and st['net5']>=1 and st['net10']>=0 and st['mrr_delta']>=0

def live_survives(h):
    recent=cmp_stats(shadow[h][-30:])
    return recent['n']>=20 and recent['net5']>=0 and recent['net10']>=0 and recent['mrr_delta']>=-0.0005

for i in range(45,len(rows)):
    target=rows[i]; hist=rows[:i]; cutoff=hist[-1]['date']
    for house in HOUSES:
        actual=target.get(house)
        if not actual: continue
        dec=dec_by.get((target['date'],house)); selected=(dec or {}).get('selected')
        outs={e.name:e.rank(hist,house,target['date']) for e in base.ENGINES}; rankings={k:v.ranking for k,v in outs.items()}
        rel={name:max(.001,base.score_metric(base.metric(profiles[house][name]))) for name in rankings}
        names=list(rankings); indep={tuple(sorted((a,b))):base.jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}
        pr=route_ranking(selected,rankings,rel,indep)
        elected = pr is not None
        baseline=pr if elected else rankings.get('HOT_RECENCY',ALL)  # fallback is shadow-only on abstention dates
        baseline_rank=baseline.index(actual)+1
        X=np.vstack([feature_vector(num,hist,house,target['date'],rankings,rel,selected,pr) for num in ALL])
        if model_ready[house] and seen_targets[house]>=40:
            scores=models[house].decision_function(X)
            order=np.argsort(-scores,kind='mergesort')
            ltr=[ALL[j] for j in order]
        else:
            ltr=list(baseline)
        ltr_rank=ltr.index(actual)+1
        frozen_state=state[house]
        live=(elected and frozen_state=='LIVE' and live_survives(house))
        final=ltr if live else (baseline if elected else None)
        final_rank=(final.index(actual)+1) if final is not None else None
        rec={'date':target['date'],'source_cutoff':cutoff,'house':house,'selected_primary':selected,'state':frozen_state,'live':live,
             'elected':elected,'baseline_rank':baseline_rank if elected else None,'shadow_baseline_rank':baseline_rank,'ltr_rank':ltr_rank,'final_rank':final_rank,'baseline_top5':baseline[:5],'ltr_top5':ltr[:5],'final_top5':final[:5] if final is not None else []}
        rec['freeze_hash']=hashlib.sha256(json.dumps([rec['date'],cutoff,house,rec['final_top5']],separators=(',',':')).encode()).hexdigest()[:20]
        records.append(rec)
        if model_ready[house] and seen_targets[house]>=40:
            if elected:
                ev={'date':target['date'],'baseline_rank':baseline_rank,'ltr_rank':ltr_rank}
                shadow[house].append(ev)
            else:
                ev=None
            if elected and frozen_state=='PROBATION':
                probation[house].append(ev); probation_left[house]-=1
                if probation_left[house]<=0:
                    state[house]='LIVE' if probation_gate(house) else 'SHADOW'; probation[house]=[]
            elif elected and frozen_state=='SHADOW' and shadow_gate(house):
                state[house]='PROBATION'; probation_left[house]=15; probation[house]=[]
            elif elected and frozen_state=='LIVE' and not live_survives(house):
                state[house]='SHADOW'; probation[house]=[]
        # reveal has happened; only now update online learner and engine profiles
        y=np.asarray([1 if num==actual else 0 for num in ALL],dtype=int)
        sw=np.where(y==1,60.0,1.0)
        if not model_ready[house]:
            models[house].partial_fit(X,y,classes=np.asarray([0,1]),sample_weight=sw); model_ready[house]=True
        else:
            models[house].partial_fit(X,y,sample_weight=sw)
        seen_targets[house]+=1
        for name,rk in rankings.items():
            r=rk.index(actual)+1
            profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,''))

metrics={}
for h in HOUSES:
    all_ds=[r for r in records if r['house']==h]
    ds=[r for r in all_ds if r['elected']]
    def pct(key,k): return round(100*sum(r[key] is not None and r[key]<=k for r in ds)/len(ds),2) if ds else 0
    live=[r for r in ds if r['live']]
    metrics[h]={
      'all_targets':len(all_ds),'elected_targets':len(ds),'coverage_pct':round(100*len(ds)/len(all_ds),2) if all_ds else 0,
      'baseline_top5_pct':pct('baseline_rank',5),'v4_top5_pct':pct('final_rank',5),
      'baseline_top10_pct':pct('baseline_rank',10),'v4_top10_pct':pct('final_rank',10),
      'baseline_top21_pct':pct('baseline_rank',21),'v4_top21_pct':pct('final_rank',21),
      'baseline_top36_pct':pct('baseline_rank',36),'v4_top36_pct':pct('final_rank',36),
      'baseline_mrr':round(sum(1/r['baseline_rank'] for r in ds)/len(ds),4) if ds else 0,'v4_mrr':round(sum(1/r['final_rank'] for r in ds)/len(ds),4) if ds else 0,
      'all_target_top5_pct':round(100*sum(r['final_rank'] is not None and r['final_rank']<=5 for r in all_ds)/len(all_ds),2) if all_ds else 0,
      'live_targets':len(live),'rescues':sum(r['baseline_rank']>5 and r['final_rank']<=5 for r in live),
      'damages':sum(r['baseline_rank']<=5 and r['final_rank']>5 for r in live),
      'final_state':state[h], 'shadow_stats':cmp_stats(shadow[h]), 'recent_shadow_stats':cmp_stats(shadow[h][-30:])}

integrity={'records_checked':len(records),'issues':[]}
for r in records:
    if not r['source_cutoff'] < r['date']: integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'cutoff_not_prior'})
    hh=hashlib.sha256(json.dumps([r['date'],r['source_cutoff'],r['house'],r['final_top5']],separators=(',',':')).encode()).hexdigest()[:20]
    if hh!=r['freeze_hash']: integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'freeze_hash_mismatch'})
integrity['pass']=not integrity['issues']

(R/'full_candidate_ltr_v4_0.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v4_0.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
(R/'full_candidate_ltr_integrity_v4_0.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')

lines=['# DHAPPA v4.0 — Full Candidate Learning-to-Rank','',
'v4.0 ranks the complete 00–99 universe from frozen pre-target engine, reliability, rank, digit, recency, gap and transition evidence. The online learner is updated only after the target outcome is revealed. It cannot control the live ranking until shadow evidence and a separate prospective probation window both survive.','',
f'- Frozen house-target decisions: **{len(records)}**',f"- Integrity: **{'PASS' if integrity['pass'] else 'FAIL'}**",'',
'## Strict OOS results','', '| House | Coverage | Baseline Top5 | v4.0 Top5 | All-target Top5 | v4.0 Top10 | v4.0 MRR | Live LTR targets | Rescues | Damages | Final state |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
for h in HOUSES:
    m=metrics[h]; lines.append(f"| {h} | {m['coverage_pct']:.2f}% | {m['baseline_top5_pct']:.2f}% | {m['v4_top5_pct']:.2f}% | {m['all_target_top5_pct']:.2f}% | {m['v4_top10_pct']:.2f}% | {m['v4_mrr']:.4f} | {m['live_targets']} | {m['rescues']} | {m['damages']} | {m['final_state']} |")
lines += ['', '## Interpretation','', 'The full-candidate learner is treated as a challenger, not an automatic replacement. If its prior shadow and future probation evidence do not beat the canonical ranking, the canonical ranking remains live. This prevents a richer model from being promoted merely because it can fit historical candidate structure.']
(R/'DHAPPA_FULL_CANDIDATE_LTR_V4_0_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
cmp=['# DHAPPA v3.9 vs v4.0','', '| House | Canonical Top5 | v4.0 Top5 | Δ pp | Live targets | Rescues | Damages |','|---|---:|---:|---:|---:|---:|---:|']
for h in HOUSES:
    m=metrics[h]; cmp.append(f"| {h} | {m['baseline_top5_pct']:.2f}% | {m['v4_top5_pct']:.2f}% | {m['v4_top5_pct']-m['baseline_top5_pct']:+.2f} | {m['live_targets']} | {m['rescues']} | {m['damages']} |")
(R/'DHAPPA_V3_9_V4_0_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')
with open(ROOT/'README.md','a',encoding='utf-8') as f:
    f.write('\n\n## v4.0 — Full Candidate Learning-to-Rank\nRun `python run_v4_0.py`. Ranks all 00–99 candidates using strictly pre-target engine/rank/reliability/structure/recency/transition features. Online model updates happen only after reveal; live promotion requires shadow + prospective probation survival.\n')
print(json.dumps({'metrics':metrics,'integrity':integrity},indent=2))
