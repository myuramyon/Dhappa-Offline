from pathlib import Path
import json, hashlib
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
    if len(mem)==1:return rankings.get(mem[0])
    if all(m in rankings for m in mem):return base.fuse(rankings,mem,rel,indep)

def gap(hist,house,num,cap=90):
    vals=[r.get(house) for r in hist if r.get(house)]
    for i,q in enumerate(reversed(vals[-cap:]),1):
        if q==num:return i
    return cap+1

def cnt(hist,house,num,n): return sum(r.get(house)==num for r in hist[-n:])
def crosscnt(hist,num,n=14): return sum(sum(r.get(h)==num for h in HOUSES) for r in hist[-n:])

def feature_vector(num, history, house, target_date, rankings, rel, selected, pr):
    ranks={en:rk.index(num)+1 for en,rk in rankings.items()}; rs=list(ranks.values())
    support5=sum(r<=5 for r in rs); support10=sum(r<=10 for r in rs); support21=sum(r<=21 for r in rs); support36=sum(r<=36 for r in rs)
    families={fam.get(en,en) for en,r in ranks.items() if r<=10}
    wrr=sum(max(.001,rel.get(en,.001))/r for en,r in ranks.items()); rr=sum(1/r for r in rs)
    primary_rank=(pr.index(num)+1) if pr else 101
    a,b=map(int,num); d=base.parse_date(target_date); vals=[r.get(house) for r in history if r.get(house)]; prev=vals[-1] if vals else None
    pa,pb=(map(int,prev) if prev else (0,0)); pal=base.rev(num); mir=base.mirror(num)
    primary_members=set((selected or '').split('+')) if selected and selected!='NO_QUALIFIED_PRIMARY' else set()
    primary_support=sum(ranks.get(en,101)<=10 for en in primary_members); primary_rel=sum(rel.get(en,0) for en in primary_members)/max(1,len(primary_members))
    valsf=[support5/12,support10/12,support21/12,support36/12,len(families)/8,rr/12,min(wrr,3)/3,min(rs)/100,np.median(rs)/100,np.mean(rs)/100,
           primary_rank/101,primary_support/max(1,len(primary_members)),min(primary_rel,1),a/9,b/9,(a+b)/18,abs(a-b)/9,int(a==b),int(a==0 or b==0),int(base.root(num))/9,
           d.weekday()/6,min(gap(history,house,num),91)/91,min(cnt(history,house,num,15),5)/5,min(cnt(history,house,num,30),8)/8,min(cnt(history,house,num,60),12)/12,
           min(cnt(history,house,pal,30),5)/5,min(cnt(history,house,mir,30),5)/5,min(crosscnt(history,num,14),8)/8,int(prev is not None and num[0]==prev[0]),int(prev is not None and num[1]==prev[1]),
           int(prev==pal),int(prev==mir),((a-pa)%10)/9 if prev else 0,((b-pb)%10)/9 if prev else 0]
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
ALLIDX=list(range(58)); variants={'FULL':ALLIDX}
for g,idxs in GROUPS.items():variants['DROP_'+g]=[i for i in ALLIDX if i not in set(idxs)]

def metric(rows,key):
    if not rows:return {'n':0,'top5':0,'top10':0,'top21':0,'top36':0,'mrr':0,'mean_rank':0}
    vs=[r[key] for r in rows]
    n=len(vs)
    return {'n':n,'top5':100*sum(x<=5 for x in vs)/n,'top10':100*sum(x<=10 for x in vs)/n,'top21':100*sum(x<=21 for x in vs)/n,
            'top36':100*sum(x<=36 for x in vs)/n,'mrr':sum(1/x for x in vs)/n,'mean_rank':sum(vs)/n}

def utility(m,baseline=None):
    # Policy selection prioritizes Top5, then Top10/MRR. Mean-rank is a light stabilizer only.
    if baseline is None:return 3.0*m['top5']+0.75*m['top10']+100*m['mrr']-0.03*m['mean_rank']
    return 3.0*(m['top5']-baseline['top5'])+0.75*(m['top10']-baseline['top10'])+100*(m['mrr']-baseline['mrr'])-0.03*(m['mean_rank']-baseline['mean_rank'])

# ---------- Build frozen feature cache once ----------
profiles=defaultdict(lambda:defaultdict(list)); cache=[]
for i in range(45,len(rows)):
    target=rows[i]; hist=rows[:i]; cutoff=hist[-1]['date']
    for house in HOUSES:
        actual=target.get(house)
        if not actual:continue
        dec=dec_by.get((target['date'],house)); selected=(dec or {}).get('selected')
        outs={e.name:e.rank(hist,house,target['date']) for e in base.ENGINES}; rankings={k:v.ranking for k,v in outs.items()}
        rel={name:max(.001,base.score_metric(base.metric(profiles[house][name]))) for name in rankings}
        names=list(rankings); indep={tuple(sorted((a,b))):base.jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}
        pr=route_ranking(selected,rankings,rel,indep)
        if pr is not None:
            X=np.vstack([feature_vector(num,hist,house,target['date'],rankings,rel,selected,pr) for num in ALL])
            cache.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'actual':actual,'baseline_rank':pr.index(actual)+1,'X':X})
        for name,rk in rankings.items():
            r=rk.index(actual)+1; profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,''))

# Split per house: first 60% = discovery, last 40% untouched outer confirmation.
# Within discovery: first 60% trains candidate policies; last 40% selects policy.
byhouse={h:[r for r in cache if r['house']==h] for h in HOUSES}
policy={}; selection_details={}; confirmation_records=[]
for h in HOUSES:
    ds=byhouse[h]; outer_cut=max(60,int(len(ds)*0.60)); discovery=ds[:outer_cut]; confirmation=ds[outer_cut:]
    inner_cut=max(35,int(len(discovery)*0.60)); inner_train=discovery[:inner_cut]; inner_val=discovery[inner_cut:]
    variant_val_records={v:[] for v in variants}
    # train each variant only on inner_train; then score inner_val prospectively and update after each target
    for v,idxs in variants.items():
        model=SGDClassifier(loss='log_loss',alpha=0.003,penalty='l2',random_state=31,learning_rate='optimal')
        ready=False
        for r in inner_train:
            X=r['X'][:,idxs]; y=np.asarray([1 if n==r['actual'] else 0 for n in ALL]); sw=np.where(y==1,60.0,1.0)
            if not ready:model.partial_fit(X,y,classes=np.asarray([0,1]),sample_weight=sw); ready=True
            else:model.partial_fit(X,y,sample_weight=sw)
        for r in inner_val:
            X=r['X'][:,idxs]
            if ready:
                scores=model.decision_function(X); rank=[ALL[j] for j in np.argsort(-scores,kind='mergesort')].index(r['actual'])+1
            else:rank=r['baseline_rank']
            variant_val_records[v].append({'rank':rank,'baseline_rank':r['baseline_rank']})
            y=np.asarray([1 if n==r['actual'] else 0 for n in ALL]); sw=np.where(y==1,60.0,1.0)
            if not ready:model.partial_fit(X,y,classes=np.asarray([0,1]),sample_weight=sw);ready=True
            else:model.partial_fit(X,y,sample_weight=sw)
    base_val=metric(variant_val_records['FULL'],'baseline_rank')
    scored=[]
    for v,recs in variant_val_records.items():
        m=metric(recs,'rank'); u=utility(m,base_val)
        # Selection eligibility: don't knowingly trade away Top10/MRR heavily during inner validation.
        eligible=(m['top10']>=base_val['top10']-1e-9 and m['mrr']>=base_val['mrr']-0.001)
        scored.append((eligible,u,m['top5'],m['mrr'],v,m))
    eligible=[x for x in scored if x[0]]
    best=max(eligible if eligible else scored,key=lambda x:(x[1],x[2],x[3]))
    chosen=best[4]
    policy[h]=chosen
    selection_details[h]={'discovery_n':len(discovery),'inner_train_n':len(inner_train),'inner_validation_n':len(inner_val),'confirmation_n':len(confirmation),
                          'baseline_inner_validation':base_val,'chosen_policy':chosen,'chosen_inner_validation':best[5],
                          'all_variants':{x[4]:{'eligible':x[0],'utility':x[1],'metrics':x[5]} for x in scored}}
    # Fresh model: train selected policy on ALL discovery, then evaluate untouched outer confirmation prospectively.
    idxs=variants[chosen]; model=SGDClassifier(loss='log_loss',alpha=0.003,penalty='l2',random_state=73,learning_rate='optimal'); ready=False
    for r in discovery:
        X=r['X'][:,idxs]; y=np.asarray([1 if n==r['actual'] else 0 for n in ALL]); sw=np.where(y==1,60.0,1.0)
        if not ready:model.partial_fit(X,y,classes=np.asarray([0,1]),sample_weight=sw);ready=True
        else:model.partial_fit(X,y,sample_weight=sw)
    for r in confirmation:
        X=r['X'][:,idxs]; scores=model.decision_function(X); ranking=[ALL[j] for j in np.argsort(-scores,kind='mergesort')]; lr=ranking.index(r['actual'])+1
        confirmation_records.append({'date':r['date'],'source_cutoff':r['source_cutoff'],'house':h,'policy':chosen,'baseline_rank':r['baseline_rank'],'ltr_rank':lr})
        y=np.asarray([1 if n==r['actual'] else 0 for n in ALL]); sw=np.where(y==1,60.0,1.0); model.partial_fit(X,y,sample_weight=sw)

# Promotion decision strictly from untouched outer confirmation.
summary={}
for h in HOUSES:
    ds=[r for r in confirmation_records if r['house']==h]
    b=metric(ds,'baseline_rank'); m=metric(ds,'ltr_rank')
    promote=(m['top5']>b['top5'] and m['top10']>=b['top10'] and m['mrr']>=b['mrr'])
    summary[h]={'policy':policy[h],'baseline_confirmation':b,'policy_confirmation':m,'promote':promote,
                'delta_top5':m['top5']-b['top5'],'delta_top10':m['top10']-b['top10'],'delta_mrr':m['mrr']-b['mrr'],
                'final_live_policy':policy[h] if promote else 'CANONICAL_DYNAMIC_PRIMARY'}

integrity={'cache_records':len(cache),'confirmation_records':len(confirmation_records),'issues':[]}
for r in confirmation_records:
    if not r['source_cutoff']<r['date']:integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'cutoff_not_prior'})
for h in HOUSES:
    if selection_details[h]['confirmation_n']<=0:integrity['issues'].append({'house':h,'issue':'empty_confirmation'})
integrity['pass']=not integrity['issues']

# JSON-safe cache metadata only; feature matrices are intentionally omitted.
(R/'house_feature_policy_v4_2.json').write_text(json.dumps({'policy':policy,'selection':selection_details,'confirmation':summary},indent=2),encoding='utf-8')
(R/'house_feature_policy_confirmation_v4_2.json').write_text(json.dumps(confirmation_records,indent=2),encoding='utf-8')
(R/'house_feature_policy_integrity_v4_2.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')

lines=['# DHAPPA v4.2 — House-Specific Feature Policy with Nested Prospective Validation','',
'Feature policies are not hardcoded from v4.1. For each house, the earlier 60% elected history is the discovery segment. Discovery is itself split into inner-train and inner-validation to select among FULL and leave-one-family-out policies. The selected policy is then frozen, freshly trained on all discovery observations, and evaluated chronologically on the untouched final 40% confirmation segment.','',
f'- Frozen elected feature records: **{len(cache)}**',f'- Untouched confirmation records: **{len(confirmation_records)}**',f"- Integrity: **{'PASS' if integrity['pass'] else 'FAIL'}**",'',
'## Frozen house-specific policies','', '| House | Chosen policy | Discovery | Inner validation | Untouched confirmation |','|---|---|---:|---:|---:|']
for h in HOUSES:
    s=selection_details[h]; lines.append(f"| {h} | {policy[h]} | {s['discovery_n']} | {s['inner_validation_n']} | {s['confirmation_n']} |")
lines += ['', '## Untouched confirmation results','', '| House | Frozen policy | Canonical Top5 | Policy Top5 | ΔTop5 | Canonical Top10 | Policy Top10 | ΔMRR | Promote? | Final live policy |','|---|---|---:|---:|---:|---:|---:|---:|---|---|']
for h in HOUSES:
    s=summary[h]; b=s['baseline_confirmation']; m=s['policy_confirmation']; lines.append(f"| {h} | {s['policy']} | {b['top5']:.2f}% | {m['top5']:.2f}% | {s['delta_top5']:+.2f} pp | {b['top10']:.2f}% | {m['top10']:.2f}% | {s['delta_mrr']:+.4f} | {'YES' if s['promote'] else 'NO'} | {s['final_live_policy']} |")
lines += ['', '## Interpretation','', 'A policy is promoted only when the untouched confirmation period shows a strict Top-5 improvement with no Top-10 or MRR degradation. Otherwise the canonical Dynamic Primary ranking remains live. This converts v4.1 ablation observations into a true nested out-of-sample test instead of turning diagnostic findings into hardcoded production rules.']
(R/'DHAPPA_HOUSE_FEATURE_POLICY_V4_2_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')

cmp=['# DHAPPA v4.1 Diagnostic Findings → v4.2 Nested Confirmation','', '| House | Frozen policy | Confirmation ΔTop5 | ΔTop10 | ΔMRR | Production promotion |','|---|---|---:|---:|---:|---|']
for h in HOUSES:
    s=summary[h];cmp.append(f"| {h} | {s['policy']} | {s['delta_top5']:+.2f} pp | {s['delta_top10']:+.2f} pp | {s['delta_mrr']:+.4f} | {'PROMOTE' if s['promote'] else 'REJECT / KEEP CANONICAL'} |")
(R/'DHAPPA_V4_1_V4_2_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')
with open(ROOT/'README.md','a',encoding='utf-8') as f:
    f.write('\n\n## v4.2 — House-Specific Feature Policy with Nested Prospective Validation\nRun `python run_v4_2.py`. Selects each house feature policy only inside an earlier nested discovery segment, freezes the choice, then tests it on an untouched later confirmation segment. Promotion requires higher Top-5 with non-inferior Top-10 and MRR.\n')
print(json.dumps({'policy':policy,'summary':summary,'integrity':integrity},indent=2))
