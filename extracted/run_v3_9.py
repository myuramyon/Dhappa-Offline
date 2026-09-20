from pathlib import Path
import json, math
from collections import defaultdict, Counter
from itertools import combinations
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from dhappa import model_v2_5 as base

ROOT=Path(__file__).resolve().parent; R=ROOT/'reports'; R.mkdir(exist_ok=True)
HOUSES=base.HOUSES; rows=base.load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
decisions=json.loads((R/'dynamic_election_decisions_v2_9.json').read_text())
dec_by={(x['date'],x['house']):x for x in decisions}
fam={e.name:e.family for e in base.ENGINES}
profiles=defaultdict(lambda:defaultdict(list)); records=[]

def route_ranking(name, rankings, rel, indep):
    if not name or name=='NO_QUALIFIED_PRIMARY': return None
    mem=tuple(name.split('+'))
    if len(mem)==1:return rankings.get(mem[0])
    if all(m in rankings for m in mem):return base.fuse(rankings,mem,rel,indep)

def cand_ev(num, rank, rankings, rel):
    s5=s10=0; rr=wrr=0.; fs=set(); engines=[]
    for en,rk in rankings.items():
        rp=rk.index(num)+1
        if rp<=5:s5+=1
        if rp<=10: s10+=1; fs.add(fam.get(en,en)); engines.append(en)
        rr+=1/rp; wrr+=max(.001,rel.get(en,.001))/rp
    return {'number':num,'rank':rank,'support5':s5,'support10':s10,'family_support':len(fs),'rr':rr,'weighted_rr':wrr,'supporters':engines}

def last_gap(hist,house,num,cap=90):
    vals=[r.get(house) for r in hist if r.get(house)]
    for i,q in enumerate(reversed(vals[-cap:]),1):
        if q==num:return i
    return cap+1

def recent_count(hist,house,num,n=30):
    vals=[r.get(house) for r in hist if r.get(house)][-n:]
    return sum(q==num for q in vals)

def cross_house_count(hist,num,n=14):
    c=0
    for r in hist[-n:]:
        c+=sum(r.get(h)==num for h in HOUSES)
    return c

def identity_features(num, hist, house, target_date):
    a,b=map(int,num); d=base.parse_date(target_date)
    vals=[r.get(house) for r in hist if r.get(house)]
    prev=vals[-1] if vals else None
    prev_a,prev_b=(map(int,prev) if prev else (0,0))
    palti=base.rev(num); mir=base.mirror(num)
    return {
      'd1':a/9,'d2':b/9,'digit_sum':(a+b)/18,'digit_diff':abs(a-b)/9,'is_double':int(a==b),'has_zero':int(a==0 or b==0),
      'root':int(base.root(num))/9,'weekday':d.weekday()/6,'gap':min(last_gap(hist,house,num),91)/91,
      'recent30':recent_count(hist,house,num,30)/5,'recent60':recent_count(hist,house,num,60)/8,
      'palti_recent':recent_count(hist,house,palti,30)/5,'mirror_recent':recent_count(hist,house,mir,30)/5,
      'cross_house14':min(cross_house_count(hist,num,14),8)/8,
      'prev_same_first':int(prev is not None and num[0]==prev[0]),'prev_same_second':int(prev is not None and num[1]==prev[1]),
      'prev_palti':int(prev==palti),'prev_mirror':int(prev==mir),
      'delta1':((a-prev_a)%10)/9 if prev else 0,'delta2':((b-prev_b)%10)/9 if prev else 0,
    }

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
        if pr:
            actual_rank=pr.index(actual)+1; inc=pr[4]; inc_ev=cand_ev(inc,5,rankings,rel); inc_id=identity_features(inc,hist,house,target['date'])
            for cr in (6,7,8):
                ch=pr[cr-1]; ce=cand_ev(ch,cr,rankings,rel); cid=identity_features(ch,hist,house,target['date'])
                out='RESCUE' if actual==ch else 'DAMAGE' if actual==inc else 'NEUTRAL'
                f={
                 'challenger_rank':cr,'support5_adv':ce['support5']-inc_ev['support5'],'support10_adv':ce['support10']-inc_ev['support10'],
                 'family_adv':ce['family_support']-inc_ev['family_support'],'weighted_rr_adv':ce['weighted_rr']-inc_ev['weighted_rr'],'rr_adv':ce['rr']-inc_ev['rr'],
                 'inc_support10':inc_ev['support10'],'inc_family':inc_ev['family_support'],'inc_weighted_rr':inc_ev['weighted_rr'],
                 'primary_members':len(selected.split('+')) if selected else 0,
                }
                f.update({f'ch_{k}':v for k,v in cid.items()}); f.update({f'inc_{k}':v for k,v in inc_id.items()})
                records.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':selected,'incumbent':inc,'challenger':ch,'challenger_rank':cr,'actual':actual,'actual_rank':actual_rank,'outcome':out,'features':f})
        for name,rk in rankings.items():
            rank=rk.index(actual)+1; profiles[house][name].append(base.Eval(target['date'],cutoff,house,name,actual,rank,rank<=5,rank<=10,rank<=21,rank<=36,1/rank,''))

feature_names=['challenger_rank','support5_adv','support10_adv','family_adv','weighted_rr_adv','rr_adv','inc_support10','inc_family','inc_weighted_rr','primary_members',
'ch_d1','ch_d2','ch_digit_sum','ch_digit_diff','ch_is_double','ch_has_zero','ch_root','ch_weekday','ch_gap','ch_recent30','ch_recent60','ch_palti_recent','ch_mirror_recent','ch_cross_house14','ch_prev_same_first','ch_prev_same_second','ch_prev_palti','ch_prev_mirror','ch_delta1','ch_delta2',
'inc_d1','inc_d2','inc_digit_sum','inc_digit_diff','inc_is_double','inc_has_zero','inc_root','inc_gap','inc_recent30','inc_recent60','inc_cross_house14']
def vec(r):return [float(r['features'].get(k,0)) for k in feature_names]

# chronological pooled house-aware model. Add one-hot house manually.
house_idx={h:j for j,h in enumerate(HOUSES)}
def xvec(r):return vec(r)+[1.0 if house_idx[r['house']]==j else 0.0 for j in range(len(HOUSES))]
by_date=defaultdict(list)
for r in records:by_date[r['date']].append(r)
train=[]; oos=[]
for date in sorted(by_date):
    cur=by_date[date]
    # Train only on prior dates. Event floor ensures sparse labels aren't overclaimed.
    rn=sum(x['outcome']=='RESCUE' for x in train); dn=sum(x['outcome']=='DAMAGE' for x in train)
    model_ok=len(train)>=750 and rn>=10 and dn>=6
    mr=md=None
    if model_ok:
        X=np.asarray([xvec(x) for x in train],float); yr=np.asarray([x['outcome']=='RESCUE' for x in train],int); yd=np.asarray([x['outcome']=='DAMAGE' for x in train],int)
        mr=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',C=.18,max_iter=700,solver='liblinear')).fit(X,yr)
        md=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',C=.18,max_iter=700,solver='liblinear')).fit(X,yd)
    for house in HOUSES:
        opts=[x for x in cur if x['house']==house]
        if not opts:continue
        baseline=opts[0]['actual_rank']; chosen=None; scores=[]; mode='INSUFFICIENT_HISTORY'
        if model_ok:
            XX=np.asarray([xvec(x) for x in opts],float); pr=mr.predict_proba(XX)[:,1]; pd=md.predict_proba(XX)[:,1]
            for j,x in enumerate(opts):
                # Identity tournament utility. Damage cost > rescue value.
                u=float(pr[j]-1.5*pd[j]); scores.append({'rank':x['challenger_rank'],'candidate':x['challenger'],'p_rescue':float(pr[j]),'p_damage':float(pd[j]),'utility':u})
            best=max(range(len(opts)),key=lambda j:scores[j]['utility']); bx=opts[best]; bs=scores[best]
            f=bx['features']
            # Rank-5 vulnerability remains separate admission gate; candidate identity must also separate from runner-up.
            sorted_u=sorted([s['utility'] for s in scores],reverse=True); sep=sorted_u[0]-sorted_u[1]
            vulnerable=(f['inc_support10']<=1 and f['inc_family']<=1 and f['inc_weighted_rr']<0.55)
            strong_ch=(f['support10_adv']>=1 and f['family_adv']>=1 and f['weighted_rr_adv']>0.10)
            if vulnerable and strong_ch and bs['utility']>=0.08 and sep>=0.025 and bs['p_rescue']>=0.48 and bs['p_damage']<=0.38:
                chosen=bx; mode='IDENTITY_TOURNAMENT_INTERVENE'
            else:mode='IDENTITY_TOURNAMENT_RETAIN'
        final=baseline
        if chosen:
            if chosen['outcome']=='RESCUE':final=5
            elif chosen['outcome']=='DAMAGE':final=chosen['challenger_rank']
        oos.append({'date':date,'house':house,'source_cutoff':opts[0]['source_cutoff'],'mode':mode,'history_n':len(train),'prior_rescues':rn,'prior_damages':dn,'baseline_rank':baseline,'final_rank':final,'chosen':chosen['challenger'] if chosen else None,'chosen_rank':chosen['challenger_rank'] if chosen else None,'chosen_outcome':chosen['outcome'] if chosen else None,'scores':scores})
    train.extend(cur)

metrics={}
for h in HOUSES:
    ds=[d for d in oos if d['house']==h]; b=[d['baseline_rank'] for d in ds]; f=[d['final_rank'] for d in ds]; act=[d for d in ds if d['mode']=='IDENTITY_TOURNAMENT_INTERVENE']
    pct=lambda a,k:round(100*sum(x<=k for x in a)/len(a),2) if a else 0
    metrics[h]={'targets':len(ds),'baseline_top5_pct':pct(b,5),'v3_9_top5_pct':pct(f,5),'baseline_top10_pct':pct(b,10),'v3_9_top10_pct':pct(f,10),'baseline_mrr':round(sum(1/x for x in b)/len(b),4),'v3_9_mrr':round(sum(1/x for x in f)/len(f),4),'interventions':len(act),'rescues':sum(d['baseline_rank']>5 and d['final_rank']<=5 for d in act),'damages':sum(d['baseline_rank']<=5 and d['final_rank']>5 for d in act)}

# diagnostic: which rank carries rescue identity historically
rank_rescue=defaultdict(Counter)
for r in records: rank_rescue[r['house']][r['challenger_rank']]+= (r['outcome']=='RESCUE')
rank_counts=defaultdict(Counter)
for r in records: rank_counts[r['house']][r['challenger_rank']]+=1
rank_diag={h:{str(k):{'rescues':rank_rescue[h][k],'n':rank_counts[h][k],'rate_pct':round(100*rank_rescue[h][k]/rank_counts[h][k],2)} for k in (6,7,8)} for h in HOUSES}

integrity={'records':len(records),'oos_decisions':len(oos),'issues':[]}
for r in records:
    if not r['source_cutoff'] < r['date']:integrity['issues'].append({'date':r['date'],'house':r['house'],'issue':'cutoff_not_prior'})
integrity['pass']=not integrity['issues']

(R/'challenger_identity_transition_dataset_v3_9.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'challenger_identity_oos_replay_v3_9.json').write_text(json.dumps(oos,indent=2),encoding='utf-8')
(R/'challenger_identity_rank_diagnostics_v3_9.json').write_text(json.dumps(rank_diag,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_9.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
(R/'challenger_identity_integrity_v3_9.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')

lines=['# DHAPPA v3.9 — Challenger Identity & Transition Intelligence','',
'v3.9 expands Rank-6/7/8 discrimination with candidate identity and transition features. Rank-5 vulnerability remains a separate admission gate. All model fits use only earlier dates; current-date labels are appended after the frozen decision.','',
'## Expanded tournament dataset',f'- Frozen boundary comparisons: **{len(records)}**',f'- OOS house-target decisions: **{len(oos)}**',f"- Integrity: **{'PASS' if integrity['pass'] else 'FAIL'}**",'',
'## Rank identity diagnostics','']
for h in HOUSES:
    lines.append(f"- **{h}**: R6 {rank_diag[h]['6']['rescues']}/{rank_diag[h]['6']['n']}, R7 {rank_diag[h]['7']['rescues']}/{rank_diag[h]['7']['n']}, R8 {rank_diag[h]['8']['rescues']}/{rank_diag[h]['8']['n']} rescues")
lines += ['', '## Strict chronological OOS replay','', '| House | Baseline Top5 | v3.9 Top5 | Baseline Top10 | v3.9 Top10 | Interventions | Rescues | Damages |','|---|---:|---:|---:|---:|---:|---:|---:|']
for h in HOUSES:
    m=metrics[h]; lines.append(f"| {h} | {m['baseline_top5_pct']:.2f}% | {m['v3_9_top5_pct']:.2f}% | {m['baseline_top10_pct']:.2f}% | {m['v3_9_top10_pct']:.2f}% | {m['interventions']} | {m['rescues']} | {m['damages']} |")
lines += ['', '## Evidence conclusion','', 'The identity/transition tournament is promoted only if its strict prior-only gate actually intervenes. Zero or neutral intervention is retained as evidence rather than forcing a positive result. Candidate structure alone is not interpreted as causal or probabilistic certainty.']
(R/'DHAPPA_CHALLENGER_IDENTITY_TRANSITION_V3_9_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
cmp=['# DHAPPA v3.8 vs v3.9','', '| House | v3.8 Baseline Top5 | v3.9 Top5 | Δ pp | Interventions | Rescues | Damages |','|---|---:|---:|---:|---:|---:|---:|']
for h in HOUSES:
    m=metrics[h]; cmp.append(f"| {h} | {m['baseline_top5_pct']:.2f}% | {m['v3_9_top5_pct']:.2f}% | {m['v3_9_top5_pct']-m['baseline_top5_pct']:+.2f} | {m['interventions']} | {m['rescues']} | {m['damages']} |")
(R/'DHAPPA_V3_8_V3_9_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')

with open(ROOT/'README.md','a',encoding='utf-8') as f:
    f.write('\n\n## v3.9 — Challenger Identity & Transition Intelligence\nRun `python run_v3_9.py`. Builds a candidate-specific Rank-6/7/8 tournament using digit structure, recency/gap, palti/mirror, previous-draw transition, cross-house recurrence and engine-support composition. Rank-5 vulnerability remains a separate admission gate.\n')
print(json.dumps({'metrics':metrics,'rank_diag':rank_diag,'integrity':integrity},indent=2))
