from pathlib import Path
import json, hashlib, math
from collections import defaultdict
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

def metrics(rs,key):
    if not rs:return {'n':0,'top5':0.0,'top10':0.0,'top21':0.0,'top36':0.0,'mrr':0.0,'mean_rank':0.0}
    vals=[r[key] for r in rs]; n=len(vals)
    return {'n':n,'top5':100*sum(x<=5 for x in vals)/n,'top10':100*sum(x<=10 for x in vals)/n,'top21':100*sum(x<=21 for x in vals)/n,'top36':100*sum(x<=36 for x in vals)/n,'mrr':sum(1/x for x in vals)/n,'mean_rank':sum(vals)/n}

def deltas(rs):
    b=metrics(rs,'baseline_rank'); p=metrics(rs,'pairwise_rank')
    return {'n':len(rs),'top5':p['top5']-b['top5'],'top10':p['top10']-b['top10'],'mrr':p['mrr']-b['mrr'],'baseline':b,'pairwise':p}

def gate(hist):
    if len(hist)<40:return False, {'reason':'MIN_HISTORY'}
    exp=deltas(hist); rec=deltas(hist[-30:])
    ok=(exp['top5']>=1.0 and rec['top5']>=0.5 and exp['top10']>=0 and rec['top10']>=0 and exp['mrr']>0 and rec['mrr']>0)
    return ok, {'expanding':exp,'recent30':rec,'reason':'PASS' if ok else 'SURVIVAL_FAIL'}

def probation_gate(hist,start_idx):
    seg=hist[start_idx:]
    if len(seg)<12:return False, {'reason':'PROBATION_NOT_COMPLETE','n':len(seg)}
    d=deltas(seg)
    ok=(d['top5']>=0 and d['top10']>=0 and d['mrr']>=0)
    return ok, {'reason':'PASS' if ok else 'FAIL','metrics':d}

def pair_training_batch(X, actual, canonical_ranking):
    ai=ALL.index(actual); xa=X[ai]
    # Hard negatives are canonical top-20, with strong emphasis on ranks 4-8.
    negs=[]
    for rank,num in enumerate(canonical_ranking[:20],1):
        if num==actual: continue
        negs.append((rank,num))
    XX=[]; yy=[]; ww=[]
    for rank,num in negs:
        j=ALL.index(num); diff=xa-X[j]
        if 4<=rank<=8: w=8.0
        elif rank<=3: w=5.0
        elif rank<=10: w=4.0
        else: w=1.5
        # positive direction and symmetric reverse direction
        XX.append(diff); yy.append(1); ww.append(w)
        XX.append(-diff); yy.append(0); ww.append(w)
    return np.asarray(XX), np.asarray(yy), np.asarray(ww)

profiles=defaultdict(lambda:defaultdict(list))
models={h:SGDClassifier(loss='log_loss',alpha=0.0025,penalty='l2',random_state=43,learning_rate='optimal') for h in HOUSES}
ready={h:False for h in HOUSES}
states={h:{'state':'SHADOW','probation_start':None,'ever_live':False} for h in HOUSES}
shadow_hist=defaultdict(list); records=[]; activation_log=[]

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
        if pr is not None:
            X=np.vstack([feature_vector(num,hist,house,target['date'],rankings,rel,selected,pr) for num in ALL])
            br=pr.index(actual)+1
            if ready[house]:
                scores=models[house].decision_function(X)
                order=np.argsort(-scores,kind='mergesort')
                pair_ranking=[ALL[j] for j in order]
                rr=pair_ranking.index(actual)+1
            else:
                pair_ranking=list(pr); rr=br

            st=states[house]
            gate_ok, gate_diag=gate(shadow_hist[house])
            if st['state']=='SHADOW' and gate_ok:
                st['state']='PROBATION'; st['probation_start']=len(shadow_hist[house])
            elif st['state']=='PROBATION':
                pg,pgdiag=probation_gate(shadow_hist[house],st['probation_start'])
                if pg:
                    st['state']='LIVE'; st['ever_live']=True
                elif pgdiag.get('reason')=='FAIL':
                    st['state']='SHADOW'; st['probation_start']=None
            elif st['state']=='LIVE':
                # rolling circuit breaker; live only while recent evidence stays non-damaging
                recent=deltas(shadow_hist[house][-30:]) if shadow_hist[house] else {'top5':0,'top10':0,'mrr':0}
                if recent['top5']<0 or recent['top10']<0 or recent['mrr']<0:
                    st['state']='SHADOW'; st['probation_start']=None

            live=(st['state']=='LIVE')
            final_rank=rr if live else br
            rec={'date':target['date'],'source_cutoff':cutoff,'house':house,'selected':selected,'baseline_rank':br,'pairwise_rank':rr,'final_rank':final_rank,
                 'state':st['state'],'live':live,'gate_diag':gate_diag,'freeze_hash':hashlib.sha256((target['date']+'|'+house+'|'+','.join(pair_ranking)).encode()).hexdigest()}
            records.append(rec)
            if live: activation_log.append({'date':target['date'],'house':house,'baseline_rank':br,'pairwise_rank':rr,'rescued':br>5 and rr<=5,'damaged':br<=5 and rr>5})
            shadow_hist[house].append({'baseline_rank':br,'pairwise_rank':rr,'date':target['date']})
            # reveal target -> only now update pairwise learner
            XX,yy,ww=pair_training_batch(X,actual,pr)
            if len(yy):
                if not ready[house]: models[house].partial_fit(XX,yy,classes=np.asarray([0,1]),sample_weight=ww); ready[house]=True
                else: models[house].partial_fit(XX,yy,sample_weight=ww)
        # update engine profiles only after target reveal
        for name,rk in rankings.items():
            r=rk.index(actual)+1; profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,''))

summary={}
for h in HOUSES:
    rs=[r for r in records if r['house']==h]
    acts=[a for a in activation_log if a['house']==h]
    b=metrics(rs,'baseline_rank'); p=metrics(rs,'pairwise_rank'); f=metrics(rs,'final_rank')
    summary[h]={'n':len(rs),'baseline':b,'pairwise_shadow':p,'final':f,'shadow_delta':deltas(shadow_hist[h]),'final_state':states[h]['state'],'ever_live':states[h]['ever_live'],
                'live_activations':len(acts),'rescues':sum(a['rescued'] for a in acts),'damages':sum(a['damaged'] for a in acts)}

integrity={'records':len(records),'activations':len(activation_log),'issues':[]}
for r in records:
    if not r['source_cutoff']<r['date']: integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'cutoff_not_prior'})
    if not r['freeze_hash']: integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'missing_freeze_hash'})
integrity['pass']=not integrity['issues']

(R/'pairwise_candidate_ordering_v4_3.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'pairwise_candidate_ordering_summary_v4_3.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(R/'pairwise_candidate_ordering_integrity_v4_3.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')
(R/'pairwise_candidate_ordering_activations_v4_3.json').write_text(json.dumps(activation_log,indent=2),encoding='utf-8')

lines=['# DHAPPA v4.3 — Pairwise Candidate Ordering / Top-5 Objective Ranker','',
'v4.3 replaces the generic one-vs-rest learning objective with online pairwise ordering. After a target is revealed, the actual candidate is trained to outrank canonical hard negatives. Canonical ranks 4–8 receive the highest training weight, ranks 1–3 and 9–10 receive secondary weight, and ranks 11–20 receive lighter weight. The current target never trains its own prediction.','',
f'- Frozen elected-target decisions: **{len(records)}**',f'- Live pairwise activations: **{len(activation_log)}**',f"- Integrity: **{'PASS' if integrity['pass'] else 'FAIL'}**",'',
'## House results','', '| House | Canonical Top5 | Pairwise shadow Top5 | Final Top5 | Canonical Top10 | Final Top10 | Final MRR | Live activations | Rescues | Damages | Final state |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
for h in HOUSES:
    s=summary[h]; lines.append(f"| {h} | {s['baseline']['top5']:.2f}% | {s['pairwise_shadow']['top5']:.2f}% | {s['final']['top5']:.2f}% | {s['baseline']['top10']:.2f}% | {s['final']['top10']:.2f}% | {s['final']['mrr']:.4f} | {s['live_activations']} | {s['rescues']} | {s['damages']} | {s['final_state']} |")
lines += ['', '## Interpretation','',
'The pairwise learner is evaluated in shadow mode first. It enters probation only when prior completed targets show positive Top-5 lift with non-inferior Top-10 and MRR, and becomes live only after an additional prospective probation window. A rolling circuit breaker returns it to shadow if recent live-eligible evidence deteriorates. This prevents a boundary-focused objective from being promoted merely because it fits earlier history.']
(R/'DHAPPA_PAIRWISE_TOP5_RANKER_V4_3_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')

cmp=['# DHAPPA v4.2 → v4.3 Comparison','', '| House | Canonical Top5 | Pairwise shadow Top5 | v4.3 final Top5 | Δ final Top5 | Live activations | Rescues | Damages |','|---|---:|---:|---:|---:|---:|---:|---:|']
for h in HOUSES:
    s=summary[h]; cmp.append(f"| {h} | {s['baseline']['top5']:.2f}% | {s['pairwise_shadow']['top5']:.2f}% | {s['final']['top5']:.2f}% | {s['final']['top5']-s['baseline']['top5']:+.2f} pp | {s['live_activations']} | {s['rescues']} | {s['damages']} |")
(R/'DHAPPA_V4_2_V4_3_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')

with open(ROOT/'README.md','a',encoding='utf-8') as f:
    f.write('\n\n## v4.3 — Pairwise Candidate Ordering / Top-5 Objective Ranker\nRun `python run_v4_3.py`. Trains an online pairwise ranker after each target reveal, emphasizing canonical ranks 4–8 as hard negatives. Shadow/probation/live survival gates prevent same-history improvement from becoming automatic production promotion.\n')

print(json.dumps({'summary':summary,'integrity':integrity},indent=2))
