from pathlib import Path
import json, math
from collections import defaultdict, Counter
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
    if len(mem)==1: return rankings.get(mem[0])
    if all(m in rankings for m in mem): return base.fuse(rankings,mem,rel,indep)

def gap(hist,house,num,cap=90):
    vals=[r.get(house) for r in hist if r.get(house)]
    for i,q in enumerate(reversed(vals[-cap:]),1):
        if q==num:return i
    return cap+1

def cnt(hist,house,num,n): return sum(r.get(house)==num for r in hist[-n:])
def crosscnt(hist,num,n=14): return sum(sum(r.get(h)==num for h in HOUSES) for r in hist[-n:])

def feature_vector(num, history, house, target_date, rankings, rel, selected, pr):
    ranks={en: rk.index(num)+1 for en,rk in rankings.items()}; rs=list(ranks.values())
    support5=sum(r<=5 for r in rs); support10=sum(r<=10 for r in rs); support21=sum(r<=21 for r in rs); support36=sum(r<=36 for r in rs)
    families={fam.get(en,en) for en,r in ranks.items() if r<=10}
    wrr=sum(max(.001,rel.get(en,.001))/r for en,r in ranks.items()); rr=sum(1/r for r in rs)
    primary_rank=(pr.index(num)+1) if pr else 101
    a,b=map(int,num); d=base.parse_date(target_date); vals=[r.get(house) for r in history if r.get(house)]; prev=vals[-1] if vals else None
    pa,pb=(map(int,prev) if prev else (0,0)); pal=base.rev(num); mir=base.mirror(num)
    primary_members=set((selected or '').split('+')) if selected and selected!='NO_QUALIFIED_PRIMARY' else set()
    primary_support=sum(ranks.get(en,101)<=10 for en in primary_members); primary_rel=sum(rel.get(en,0) for en in primary_members)/max(1,len(primary_members))
    valsf=[support5/12,support10/12,support21/12,support36/12,len(families)/8,rr/12,min(wrr,3)/3,min(rs)/100,np.median(rs)/100,np.mean(rs)/100,primary_rank/101,primary_support/max(1,len(primary_members)),min(primary_rel,1),a/9,b/9,(a+b)/18,abs(a-b)/9,int(a==b),int(a==0 or b==0),int(base.root(num))/9,d.weekday()/6,min(gap(history,house,num),91)/91,min(cnt(history,house,num,15),5)/5,min(cnt(history,house,num,30),8)/8,min(cnt(history,house,num,60),12)/12,min(cnt(history,house,pal,30),5)/5,min(cnt(history,house,mir,30),5)/5,min(crosscnt(history,num,14),8)/8,int(prev is not None and num[0]==prev[0]),int(prev is not None and num[1]==prev[1]),int(prev==pal),int(prev==mir),((a-pa)%10)/9 if prev else 0,((b-pb)%10)/9 if prev else 0]
    valsf.extend([ranks[e.name]/100 for e in base.ENGINES]); valsf.extend([min(rel.get(e.name,0),1) for e in base.ENGINES])
    return np.asarray(valsf,dtype=float)

GROUPS={
 'CONSENSUS_ENGINE_RANKS': list(range(0,6))+list(range(7,10))+list(range(34,46)),
 'RELIABILITY': [6,12]+list(range(46,58)),
 'PRIMARY_EVIDENCE': [10,11],
 'DIGIT_STRUCTURE': list(range(13,20)),
 'WEEKDAY_CALENDAR': [20],
 'RECENCY_GAP': list(range(21,25)),
 'PALTI_MIRROR': [25,26,30,31],
 'CROSS_HOUSE': [27],
 'PREVIOUS_DRAW_TRANSITION': [28,29,32,33],
}
ALLIDX=list(range(58))
variants={'FULL':ALLIDX}
for g,idxs in GROUPS.items():
    variants['DROP_'+g]=[i for i in ALLIDX if i not in set(idxs)]

# state per variant-house
models={v:{h:SGDClassifier(loss='log_loss',alpha=0.003,penalty='l2',random_state=17,learning_rate='optimal') for h in HOUSES} for v in variants}
ready={v:{h:False for h in HOUSES} for v in variants}; seen={v:Counter() for v in variants}
profiles=defaultdict(lambda:defaultdict(list))
records=[]

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
        if pr is None:
            # preserve abstention: do not evaluate ablation against artificial fallback
            for name,rk in rankings.items():
                r=rk.index(actual)+1; profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,''))
            continue
        baseline_rank=pr.index(actual)+1
        Xfull=np.vstack([feature_vector(num,hist,house,target['date'],rankings,rel,selected,pr) for num in ALL])
        out={'date':target['date'],'source_cutoff':cutoff,'house':house,'baseline_rank':baseline_rank}
        y=np.asarray([1 if num==actual else 0 for num in ALL],dtype=int); sw=np.where(y==1,60.0,1.0)
        for v,idxs in variants.items():
            X=Xfull[:,idxs]
            if ready[v][house] and seen[v][house]>=40:
                scores=models[v][house].decision_function(X); order=np.argsort(-scores,kind='mergesort'); ranking=[ALL[j] for j in order]
                out[v]=ranking.index(actual)+1
            else:
                out[v]=baseline_rank
            if not ready[v][house]:
                models[v][house].partial_fit(X,y,classes=np.asarray([0,1]),sample_weight=sw); ready[v][house]=True
            else: models[v][house].partial_fit(X,y,sample_weight=sw)
            seen[v][house]+=1
        records.append(out)
        for name,rk in rankings.items():
            r=rk.index(actual)+1; profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,''))

def stats(ds,key):
    n=len(ds)
    if not n:return {'n':0,'top5':0,'top10':0,'top21':0,'top36':0,'mrr':0,'mean_rank':0}
    vals=[r[key] for r in ds]
    return {'n':n,'top5':100*sum(x<=5 for x in vals)/n,'top10':100*sum(x<=10 for x in vals)/n,
            'top21':100*sum(x<=21 for x in vals)/n,'top36':100*sum(x<=36 for x in vals)/n,
            'mrr':sum(1/x for x in vals)/n,'mean_rank':sum(vals)/n}

summary={}; audit={}
for h in HOUSES:
    ds=[r for r in records if r['house']==h]
    # Only dates after all variants have 40 prior targets contribute to signal audit.
    evalds=ds[40:]
    cut=max(1,int(len(evalds)*0.6)); discovery=evalds[:cut]; confirm=evalds[cut:]
    hs={'baseline':stats(evalds,'baseline_rank'),'FULL':stats(evalds,'FULL'),'variants':{},'discovery_n':len(discovery),'confirmation_n':len(confirm)}
    fullD=stats(discovery,'FULL'); fullC=stats(confirm,'FULL')
    for v in variants:
        if v=='FULL':continue
        a=stats(evalds,v); d=stats(discovery,v); c=stats(confirm,v)
        a['delta_vs_full_top5']=a['top5']-hs['FULL']['top5']; a['delta_vs_full_top10']=a['top10']-hs['FULL']['top10']; a['delta_vs_full_mrr']=a['mrr']-hs['FULL']['mrr']
        a['discovery_delta_top5']=d['top5']-fullD['top5']; a['confirmation_delta_top5']=c['top5']-fullC['top5']
        a['discovery_delta_mrr']=d['mrr']-fullD['mrr']; a['confirmation_delta_mrr']=c['mrr']-fullC['mrr']
        # Conservative classification: harmful if removing helps in both periods on Top5 or both MRR with no Top5 degradation.
        if (a['discovery_delta_top5']>0 and a['confirmation_delta_top5']>0) or (a['discovery_delta_top5']>=0 and a['confirmation_delta_top5']>=0 and a['discovery_delta_mrr']>0 and a['confirmation_delta_mrr']>0): cls='HARMFUL_OR_NOISY'
        elif (a['discovery_delta_top5']<0 and a['confirmation_delta_top5']<0) or (a['discovery_delta_top5']<=0 and a['confirmation_delta_top5']<=0 and a['discovery_delta_mrr']<0 and a['confirmation_delta_mrr']<0): cls='USEFUL_SIGNAL'
        else: cls='UNSTABLE_OR_NEUTRAL'
        a['classification']=cls; hs['variants'][v]=a
    summary[h]=hs

audit={'records_checked':len(records),'issues':[]}
for r in records:
    if not r['source_cutoff']<r['date']:audit['issues'].append({'date':r['date'],'house':r['house'],'issue':'cutoff_not_prior'})
audit['pass']=not audit['issues']

(R/'ltr_feature_ablation_records_v4_1.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'ltr_feature_ablation_summary_v4_1.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(R/'ltr_feature_ablation_integrity_v4_1.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

lines=['# DHAPPA v4.1 — Learning-to-Rank Feature Ablation & Signal Audit','',
'Each ablation is a separate online learner trained chronologically. Current-target labels are added only after that target is ranked. The audit uses elected targets only; NO_QUALIFIED_PRIMARY dates are not replaced with an artificial baseline. Signal classification requires directional consistency across a chronological discovery/confirmation split.','',
f'- Elected records replayed: **{len(records)}**',f"- Integrity: **{'PASS' if audit['pass'] else 'FAIL'}**",'',
'## Full-model OOS context','', '| House | Baseline Top5 | FULL LTR Top5 | FULL Top10 | FULL MRR |','|---|---:|---:|---:|---:|']
for h in HOUSES:
    s=summary[h]; lines.append(f"| {h} | {s['baseline']['top5']:.2f}% | {s['FULL']['top5']:.2f}% | {s['FULL']['top10']:.2f}% | {s['FULL']['mrr']:.4f} |")
lines += ['', '## Leave-one-family-out signal audit','']
for h in HOUSES:
    lines += [f'### {h}','', '| Removed family | ΔTop5 vs FULL | ΔTop10 | ΔMRR | Discovery ΔTop5 | Confirmation ΔTop5 | Classification |','|---|---:|---:|---:|---:|---:|---|']
    ordered=sorted(summary[h]['variants'].items(), key=lambda kv:(-kv[1]['delta_vs_full_top5'],-kv[1]['delta_vs_full_mrr']))
    for v,s in ordered:
        lines.append(f"| {v.replace('DROP_','')} | {s['delta_vs_full_top5']:+.2f} pp | {s['delta_vs_full_top10']:+.2f} pp | {s['delta_vs_full_mrr']:+.4f} | {s['discovery_delta_top5']:+.2f} pp | {s['confirmation_delta_top5']:+.2f} pp | {s['classification']} |")
    harmful=[v.replace('DROP_','') for v,s in summary[h]['variants'].items() if s['classification']=='HARMFUL_OR_NOISY']
    useful=[v.replace('DROP_','') for v,s in summary[h]['variants'].items() if s['classification']=='USEFUL_SIGNAL']
    lines += ['', f"- Consistently harmful/noisy candidates: **{', '.join(harmful) if harmful else 'none'}**", f"- Consistently useful signal candidates: **{', '.join(useful) if useful else 'none'}**",'']
lines += ['## Interpretation','',
'A positive leave-one-family-out delta means the learner improved when that feature family was removed; this is evidence that the family may be noisy or badly parameterized, not proof that the underlying concept is useless. A negative delta means removing the family hurt the learner. Only directions that persist across the chronological discovery and confirmation segments are labelled useful or harmful/noisy; mixed directions are labelled unstable/neutral.', '',
'No ablation winner is automatically promoted to production. v4.1 is a signal-audit stage; any pruned feature set must be rebuilt prospectively in a later version using only choices established before its evaluation window.']
(R/'DHAPPA_LTR_FEATURE_ABLATION_V4_1_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')

cmp=['# DHAPPA v4.0 vs v4.1 Signal Audit','', 'v4.1 does not overwrite the canonical v4.0 live ranking. It diagnoses which feature families help or hurt the online full-candidate learner under strict chronological replay.','', '| House | FULL LTR Top5 | Best leave-one-out Top5 | Removed family | Δ pp |','|---|---:|---:|---|---:|']
for h in HOUSES:
    bestv,bests=max(summary[h]['variants'].items(), key=lambda kv:(kv[1]['top5'],kv[1]['mrr']))
    cmp.append(f"| {h} | {summary[h]['FULL']['top5']:.2f}% | {bests['top5']:.2f}% | {bestv.replace('DROP_','')} | {bests['top5']-summary[h]['FULL']['top5']:+.2f} |")
(R/'DHAPPA_V4_0_V4_1_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')
print(json.dumps({'summary':summary,'integrity':audit},indent=2))
