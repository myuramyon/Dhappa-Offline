from pathlib import Path
import json, math, statistics
from collections import defaultdict, Counter
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from dhappa import model_v2_5 as base

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'; R.mkdir(exist_ok=True)
HOUSES=base.HOUSES
rows=base.load_csv(ROOT/'data'/'Merged_Workbook.csv')[-240:]
decisions=json.loads((R/'dynamic_election_decisions_v2_9.json').read_text())
dec_by={(x['date'],x['house']):x for x in decisions}

fam={e.name:e.family for e in base.ENGINES}
profiles=defaultdict(lambda:defaultdict(list))
records=[]

# route ranking reconstruction from frozen selected route names.
def route_ranking(name, rankings, rel, indep):
    if not name or name=='NO_QUALIFIED_PRIMARY': return None
    mem=tuple(name.split('+'))
    if len(mem)==1:
        return rankings.get(mem[0])
    if all(m in rankings for m in mem):
        return base.fuse(rankings,mem,rel,indep)
    return None

def cand_features(num, primary_rank, rankings, rel):
    s5=s10=0; rr=0.0; wrr=0.0; fs=set(); top_support=[]
    for en, ranked in rankings.items():
        rp=ranked.index(num)+1
        if rp<=5: s5+=1
        if rp<=10:
            s10+=1; fs.add(fam.get(en,en)); top_support.append(en)
        rr += 1/rp
        wrr += max(0.001,rel.get(en,0.001))/rp
    return {'number':num,'primary_rank':primary_rank,'support5':s5,'support10':s10,
            'family_support':len(fs),'rr':rr,'weighted_rr':wrr,'supporters':top_support}

for i in range(45,len(rows)):
    target=rows[i]; history=rows[:i]; cutoff=history[-1]['date']
    outputs={e.name:e.rank(history,h,target['date']) for h in [] for e in []}  # placeholder to keep linter calm
    for house in HOUSES:
        actual=target.get(house)
        if not actual: continue
        dec=dec_by.get((target['date'],house))
        # compute all engines at identical t-1 target using history through cutoff
        outs={e.name:e.rank(history,house,target['date']) for e in base.ENGINES}
        rankings={k:v.ranking for k,v in outs.items()}
        rel={name:max(.001,base.score_metric(base.metric(profiles[house][name]))) for name in rankings}
        names=list(rankings)
        from itertools import combinations
        indep={tuple(sorted((a,b))):base.jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}
        selected=(dec or {}).get('selected')
        pranked=route_ranking(selected,rankings,rel,indep)
        if pranked is not None:
            actual_rank=pranked.index(actual)+1
            # Capture every 5-vs-6/7/8 state, not only old rescue proposals.
            incumbent=pranked[4]
            inc_ev=cand_features(incumbent,5,rankings,rel)
            for cr in (6,7,8):
                challenger=pranked[cr-1]
                ch_ev=cand_features(challenger,cr,rankings,rel)
                outcome='RESCUE' if actual==challenger else 'DAMAGE' if actual==incumbent else 'NEUTRAL'
                rec={
                    'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':selected,
                    'incumbent':incumbent,'challenger':challenger,'challenger_rank':cr,'actual':actual,
                    'actual_rank_canonical':actual_rank,'outcome':outcome,
                    'incumbent_evidence':inc_ev,'challenger_evidence':ch_ev,
                    'features':{
                        'support5_adv':ch_ev['support5']-inc_ev['support5'],
                        'support10_adv':ch_ev['support10']-inc_ev['support10'],
                        'family_adv':ch_ev['family_support']-inc_ev['family_support'],
                        'weighted_rr_adv':ch_ev['weighted_rr']-inc_ev['weighted_rr'],
                        'rr_adv':ch_ev['rr']-inc_ev['rr'],
                        'inc_primary_only':int(inc_ev['support10']<=1),
                        'inc_low_diversity':int(inc_ev['family_support']<=1),
                        'challenger_multi_support':int(ch_ev['support10']>=2),
                        'challenger_multi_family':int(ch_ev['family_support']>=2),
                        'primary_member_count':len(selected.split('+')) if selected else 0,
                    }
                }
                records.append(rec)
        # update engine profiles only after current outcome reveal
        for name,ranked in rankings.items():
            rank=ranked.index(actual)+1
            ev=base.Eval(target['date'],cutoff,house,name,actual,rank,rank<=5,rank<=10,rank<=21,rank<=36,1/rank,'')
            profiles[house][name].append(ev)

# Expanded dataset summary
summary={}
for h in HOUSES:
    rs=[x for x in records if x['house']==h]
    oc=Counter(x['outcome'] for x in rs)
    targets=len({x['date'] for x in rs})
    summary[h]={'boundary_comparisons':len(rs),'elected_targets_with_boundary':targets,
                'rescue_events':oc['RESCUE'],'damage_events':oc['DAMAGE'],'neutral_events':oc['NEUTRAL'],
                'rescue_rate_pct':round(100*oc['RESCUE']/len(rs),2) if rs else 0,
                'damage_rate_pct':round(100*oc['DAMAGE']/len(rs),2) if rs else 0}

# Strict chronological out-of-sample pairwise utility model.
# Predict P(RESCUE) and P(DAMAGE) separately. Only prior comparisons from the same house are trainable.
feature_names=['challenger_rank','support5_adv','support10_adv','family_adv','weighted_rr_adv','rr_adv',
               'inc_primary_only','inc_low_diversity','challenger_multi_support','challenger_multi_family','primary_member_count']
def vec(x):
    f=x['features']
    return [x['challenger_rank'],f['support5_adv'],f['support10_adv'],f['family_adv'],f['weighted_rr_adv'],f['rr_adv'],
            f['inc_primary_only'],f['inc_low_diversity'],f['challenger_multi_support'],f['challenger_multi_family'],f['primary_member_count']]

# process grouped by chronological target; train excludes entire current date
by_date=defaultdict(list)
for x in records: by_date[x['date']].append(x)
train=defaultdict(list); decisions_oos=[]
for date in sorted(by_date):
    cur=by_date[date]
    for house in HOUSES:
        opts=[x for x in cur if x['house']==house]
        if not opts: continue
        hist=train[house]
        mode='INSUFFICIENT_HISTORY'; chosen=None; scores=[]
        # Require both event classes enough samples; neutrals remain in binary fits as negatives.
        resc_n=sum(x['outcome']=='RESCUE' for x in hist); dmg_n=sum(x['outcome']=='DAMAGE' for x in hist)
        if len(hist)>=150 and resc_n>=12 and dmg_n>=12:
            X=np.asarray([vec(x) for x in hist],float)
            yr=np.asarray([x['outcome']=='RESCUE' for x in hist],int)
            yd=np.asarray([x['outcome']=='DAMAGE' for x in hist],int)
            try:
                mr=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',C=0.25,max_iter=500,solver='liblinear')).fit(X,yr)
                md=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',C=0.25,max_iter=500,solver='liblinear')).fit(X,yd)
                XX=np.asarray([vec(x) for x in opts],float)
                pr=mr.predict_proba(XX)[:,1]; pd=md.predict_proba(XX)[:,1]
                # Conservative net utility: damage is costlier than rescue.
                for j,x in enumerate(opts):
                    util=float(pr[j]-1.35*pd[j])
                    scores.append({'rank':x['challenger_rank'],'challenger':x['challenger'],'p_rescue':float(pr[j]),'p_damage':float(pd[j]),'utility':util})
                best=max(range(len(opts)),key=lambda j:scores[j]['utility'])
                # Frozen threshold: only positive enough utility + structural support.
                bx=opts[best]; bf=bx['features']; bu=scores[best]['utility']
                if bu>=0.10 and bf['challenger_multi_support'] and bf['challenger_multi_family'] and bf['inc_primary_only']:
                    chosen=bx; mode='OOS_MODEL_INTERVENE'
                else: mode='OOS_MODEL_RETAIN'
            except Exception as e:
                mode='MODEL_ERROR_RETAIN'
        # Evaluate selected intervention after freeze.
        baseline_actual_rank=opts[0]['actual_rank_canonical']
        if chosen:
            if chosen['outcome']=='RESCUE': final_rank=5
            elif chosen['outcome']=='DAMAGE': final_rank=chosen['challenger_rank']
            else: final_rank=baseline_actual_rank
        else: final_rank=baseline_actual_rank
        decisions_oos.append({'date':date,'source_cutoff':opts[0]['source_cutoff'],'house':house,'mode':mode,
                              'history_n':len(hist),'prior_rescues':resc_n,'prior_damages':dmg_n,
                              'chosen_rank':chosen['challenger_rank'] if chosen else None,
                              'chosen_challenger':chosen['challenger'] if chosen else None,
                              'chosen_outcome':chosen['outcome'] if chosen else None,
                              'baseline_rank':baseline_actual_rank,'final_rank':final_rank,'scores':scores})
    # append whole date only after all decisions for that date are frozen
    for x in cur: train[x['house']].append(x)

# Compare baseline vs OOS at target level.
metrics={}
for h in HOUSES:
    ds=[d for d in decisions_oos if d['house']==h]
    b=[d['baseline_rank'] for d in ds]; f=[d['final_rank'] for d in ds]
    active=[d for d in ds if d['mode']=='OOS_MODEL_INTERVENE']
    def pct(arr,k): return round(100*sum(x<=k for x in arr)/len(arr),2) if arr else 0
    metrics[h]={
        'targets':len(ds),'baseline_top5_pct':pct(b,5),'oos_top5_pct':pct(f,5),
        'baseline_top10_pct':pct(b,10),'oos_top10_pct':pct(f,10),
        'baseline_mrr':round(sum(1/x for x in b)/len(b),4) if b else 0,
        'oos_mrr':round(sum(1/x for x in f)/len(f),4) if f else 0,
        'oos_interventions':len(active),
        'realized_rescues':sum(d['baseline_rank']>5 and d['final_rank']<=5 for d in active),
        'realized_damages':sum(d['baseline_rank']<=5 and d['final_rank']>5 for d in active),
    }

# Integrity: current date cannot be in training count; source cutoff before target lexicographically works for ISO dates.
issues=[]
for d in decisions_oos:
    if not d['source_cutoff'] < d['date']: issues.append({'date':d['date'],'house':d['house'],'issue':'cutoff_not_prior'})
    if d['mode']=='OOS_MODEL_INTERVENE' and d['history_n']<150: issues.append({'date':d['date'],'house':d['house'],'issue':'activation_without_history'})
integrity={'boundary_records':len(records),'oos_decisions':len(decisions_oos),'issues':issues,'status':'PASS' if not issues else 'FAIL'}

(R/'rank5_boundary_expanded_dataset_v3_8.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'rank5_boundary_dataset_summary_v3_8.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(R/'rank5_boundary_oos_replay_v3_8.json').write_text(json.dumps(decisions_oos,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_8.json').write_text(json.dumps({'model':'v3.8 Rank-5 Boundary Dataset Expansion + OOS Replay','house_metrics':metrics},indent=2),encoding='utf-8')
(R/'rank5_boundary_integrity_v3_8.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')

md=['# DHAPPA v3.8 — Rank-5 Boundary Dataset Expansion + Out-of-Sample Replay','',
'v3.8 expands the learning population beyond intervention-triggered cases. Every elected historical target contributes three frozen comparisons: canonical Rank-5 vs Rank-6, Rank-7 and Rank-8. Candidate evidence is computed before reveal; RESCUE/DAMAGE/NEUTRAL labels are appended only after the target result is known.','',
'## Expanded boundary dataset','',
'| House | Boundary comparisons | Elected target states | Rescue events | Damage events | Neutral events |',
'|---|---:|---:|---:|---:|---:|']
for h,s in summary.items(): md.append(f"| {h} | {s['boundary_comparisons']} | {s['elected_targets_with_boundary']} | {s['rescue_events']} | {s['damage_events']} | {s['neutral_events']} |")
md += ['', '## Strict chronological out-of-sample replay','',
'An online pairwise utility model estimates rescue and damage separately from prior boundary observations only. A swap is permitted only after minimum class/sample support and conservative structural gates. This is a research challenger to the canonical model, not an oracle.','',
'| House | Baseline Top-5 | OOS Top-5 | Baseline Top-10 | OOS Top-10 | Baseline MRR | OOS MRR | Interventions | Rescues | Damages |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for h,m in metrics.items(): md.append(f"| {h} | {m['baseline_top5_pct']:.2f}% | {m['oos_top5_pct']:.2f}% | {m['baseline_top10_pct']:.2f}% | {m['oos_top10_pct']:.2f}% | {m['baseline_mrr']:.4f} | {m['oos_mrr']:.4f} | {m['oos_interventions']} | {m['realized_rescues']} | {m['realized_damages']} |")
md += ['', '## Interpretation','',
'The expanded dataset removes the strongest sampling weakness of v3.7: survival learning is no longer restricted to the tiny set of previously approved interventions. The OOS replay remains deliberately conservative. A useful result requires realized rescue lift without offsetting Rank-5 damage; otherwise the expanded dataset should be used for diagnosis rather than promoted into the canonical ranking path.','',
'## Integrity','',f"- Boundary records: **{len(records)}**",f"- OOS target decisions: **{len(decisions_oos)}**",f"- Status: **{integrity['status']}**",'- Same-target outcome is never used to train its own boundary decision.','- All engine reliability features are based on profiles completed before the target.']
(R/'DHAPPA_RANK5_BOUNDARY_EXPANSION_V3_8_REPORT.md').write_text('\n'.join(md),encoding='utf-8')

cmp=['# DHAPPA v3.7 vs v3.8 OOS Research Challenger','',
'v3.8 does not automatically replace v3.7. It expands the boundary evidence base and runs an independent chronological challenger policy.','',
'| House | v3.7 Top-5 | v3.8 OOS Top-5 | Δ pp | OOS interventions | Rescues | Damages |','|---|---:|---:|---:|---:|---:|---:|']
v37=json.loads((R/'dynamic_primary_engine_backtest_v3_7.json').read_text())['house_metrics']
for h,m in metrics.items():
    old=v37[h]['top5_pct_elected']; cmp.append(f"| {h} | {old:.2f}% | {m['oos_top5_pct']:.2f}% | {m['oos_top5_pct']-old:+.2f} | {m['oos_interventions']} | {m['realized_rescues']} | {m['realized_damages']} |")
(R/'DHAPPA_V3_7_V3_8_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')

print(json.dumps({'summary':summary,'metrics':metrics,'integrity':integrity},indent=2))
