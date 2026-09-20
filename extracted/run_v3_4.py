from pathlib import Path
import json, math
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
resc=json.loads((R/'candidate_rank6_12_rescue_v3_2.json').read_text())
cf=json.loads((R/'route_counterfactual_election_lab_v2_6.json').read_text())
v33=json.loads((R/'causal_rank_correction_shadow_v3_3.json').read_text())
v33_by={(x['date'],x['house']):x for x in v33}

FAMILIES=(
    'PRIMARY_ROUTE_BIAS',
    'VOTE_COUNT_DISTORTION',
    'REDUNDANCY_OVERBOOST',
    'RELIABILITY_WEIGHT_ERROR',
    'PRIMARY_RANK_ANCHOR_BIAS',
)

def feats(x):
    ce=x.get('challenger_evidence') or {}; ie=x.get('incumbent_evidence') or {}
    return {
        'support10_delta': ce.get('support10',0)-ie.get('support10',0),
        'support5_delta': ce.get('support5',0)-ie.get('support5',0),
        'family_delta': ce.get('family_support',0)-ie.get('family_support',0),
        'weighted_rr_delta': ce.get('weighted_rr',0)-ie.get('weighted_rr',0),
        'margin': x.get('margin',0) or 0,
        'challenger_primary_rank': ce.get('primary_rank',99) or 99,
        'incumbent_primary_rank': ie.get('primary_rank',99) or 99,
        'challenger_support10': ce.get('support10',0),
        'challenger_family': ce.get('family_support',0),
    }

def triggers(x):
    f=feats(x); out=[]
    # Route-bias correction: challenger has broad independent confirmation despite not being primary Top-5.
    if f['challenger_support10']>=4 and f['challenger_family']>=3 and f['margin']>=0.05:
        out.append('PRIMARY_ROUTE_BIAS')
    # Vote-count correction: broad support materially exceeds incumbent support.
    if f['support10_delta']>=2:
        out.append('VOTE_COUNT_DISTORTION')
    # Redundancy correction: challenger support comes from more distinct engine families.
    if f['family_delta']>=2:
        out.append('REDUNDANCY_OVERBOOST')
    # Reliability correction: reliability-weighted reciprocal rank materially favors challenger.
    if f['weighted_rr_delta']>=0.25:
        out.append('RELIABILITY_WEIGHT_ERROR')
    # Rank-anchor correction: rank-6..9 challenger has a large evidence margin despite primary-rank disadvantage.
    if f['challenger_primary_rank']<=9 and f['margin']>=0.10:
        out.append('PRIMARY_RANK_ANCHOR_BIAS')
    return out

def outcome(q):
    b=q['baseline_rank']; r=q['rescue_rank']
    return {
        'net5': int(r<=5)-int(b<=5),
        'net10': int(r<=10)-int(b<=10),
        'mrr': (1/r)-(1/b),
        'rescued': int(b>5 and r<=5),
        'damaged': int(b<=5 and r>5),
        'rank_gain': b-r,
    }

def stats(xs):
    if not xs:
        return {'n':0,'net5':0,'net10':0,'mrr':0.0,'rescued':0,'damaged':0,'mean_rank_gain':0.0,'utility':0.0,'weight':0.0}
    os=[outcome(q) for q in xs]
    n=len(os); net5=sum(o['net5'] for o in os); net10=sum(o['net10'] for o in os)
    mrr=sum(o['mrr'] for o in os)/n; rescued=sum(o['rescued'] for o in os); damaged=sum(o['damaged'] for o in os)
    rg=sum(o['rank_gain'] for o in os)/n
    # Weight is derived only from completed prior observations and intentionally bounded.
    raw=(net5/n)*2.0 + (net10/n)*0.35 + mrr*0.75 + max(-0.1,min(0.1,rg/100))*0.25
    weight=max(0.0,min(1.0,0.5+raw))
    util=(net5*3.0)+(net10*0.5)+(mrr*n*0.5)-(damaged*2.0)
    return {'n':n,'net5':net5,'net10':net10,'mrr':round(mrr,8),'rescued':rescued,'damaged':damaged,
            'mean_rank_gain':round(rg,4),'utility':round(util,6),'weight':round(weight,6)}

# Independent lifecycle state per house/error family.
hist=defaultdict(list)
state=defaultdict(lambda:{'stage':'SHADOW','probation_start_n':None,'probation_obs':[]})
records=[]
activations=Counter(); rescues=Counter(); damages=Counter(); family_acts=Counter(); family_rescues=Counter()

for x in sorted(resc,key=lambda z:(z['date'],z['house'])):
    k=(x['date'],x['house'])
    existing=v33_by.get(k)
    base_rank=existing['corrected_rank'] if existing else x['baseline_rank']
    active_families=[]; diagnostics=[]
    for fam in triggers(x):
        key=(x['house'],fam); prior=hist[key]; st=state[key]
        ex=stats(prior); r10=stats(prior[-10:])
        # SHADOW -> PROBATION only on sustained prior-only performance.
        shadow_ok=(ex['n']>=15 and ex['rescued']>=2 and ex['net5']>=2 and ex['damaged']<=1 and ex['net10']>=0 and ex['mrr']>=0 and ex['weight']>=0.53
                   and r10['net5']>=0 and r10['net10']>=0 and r10['mrr']>=0)
        if st['stage']=='SHADOW' and shadow_ok:
            st['stage']='PROBATION'; st['probation_start_n']=ex['n']; st['probation_obs']=[]
        # Evaluate completed probation observations before current target.
        if st['stage']=='PROBATION' and len(st['probation_obs'])>=8:
            ps=stats(st['probation_obs'])
            if ps['net5']>=1 and ps['damaged']==0 and ps['net10']>=0 and ps['mrr']>=0:
                st['stage']='LIVE'
            else:
                st['stage']='SHADOW'; st['probation_start_n']=None; st['probation_obs']=[]
        # LIVE circuit-breaker uses only completed prior observations.
        if st['stage']=='LIVE':
            rr=stats(prior[-10:])
            if rr['net5']<0 or rr['net10']<0 or rr['mrr']<0 or rr['damaged']>1:
                st['stage']='SHADOW'; st['probation_start_n']=None; st['probation_obs']=[]
        if st['stage']=='LIVE':
            active_families.append((fam,ex['weight'],ex['utility']))
        diagnostics.append({'family':fam,'stage':st['stage'],'expanding':ex,'recent10':r10})

    # If multiple independent corrections survive, use the strongest prior-derived weight; no stacking.
    chosen=None
    if active_families:
        chosen=max(active_families,key=lambda z:(z[1],z[2],z[0]))[0]
    final_rank=x['rescue_rank'] if chosen else base_rank
    if chosen:
        activations[x['house']]+=1; family_acts[(x['house'],chosen)]+=1
        if base_rank>5 and final_rank<=5:
            rescues[x['house']]+=1; family_rescues[(x['house'],chosen)]+=1
        if base_rank<=5 and final_rank>5: damages[x['house']]+=1
    records.append({'date':x['date'],'house':x['house'],'baseline_rank':x['baseline_rank'],'v3_3_rank':base_rank,'v3_4_rank':final_rank,
                    'rescue_rank':x['rescue_rank'],'incumbent':x.get('incumbent'),'challenger':x.get('challenger'),
                    'features':feats(x),'triggered_families':triggers(x),'chosen_family':chosen,'family_diagnostics':diagnostics})
    # Reveal current target only now; update every triggered family's future history and probation log.
    for fam in triggers(x):
        key=(x['house'],fam); st=state[key]
        hist[key].append(x)
        if st['stage']=='PROBATION': st['probation_obs'].append(x)

# Reconstruct overall selected-rank metrics, layering v3.4 over v3.3/canonical.
rec_by={(x['date'],x['house']):x for x in records}
metrics={}
for h in ('Deshawar','Faridabad','Ghaziabad','Gali'):
    rows=[e for e in cf if e['house']==h]
    elected=[]; allr=[]
    for e in rows:
        if e.get('selected_rank') is None:
            allr.append(None); continue
        rr=rec_by.get((e['date'],h))
        r=rr['v3_4_rank'] if rr else e['selected_rank']
        elected.append(r); allr.append(r)
    def pct(k): return round(100*sum(r<=k for r in elected)/len(elected),2) if elected else 0
    def pctall(k): return round(100*sum(r is not None and r<=k for r in allr)/len(allr),2) if allr else 0
    mrr=sum(1/r for r in elected)/len(elected) if elected else 0
    metrics[h]={'targets':len(rows),'elected_targets':len(elected),'top5_pct_elected':pct(5),'top10_pct_elected':pct(10),'top21_pct_elected':pct(21),'top36_pct_elected':pct(36),
                'top5_pct_all_targets':pctall(5),'mrr_elected':round(mrr,4),'v3_4_live_activations':activations[h],
                'v3_4_realized_top5_rescues':rescues[h],'v3_4_damaged_top5':damages[h]}

family_summary=[]
for h in ('Deshawar','Faridabad','Ghaziabad','Gali'):
    for fam in FAMILIES:
        s=stats(hist[(h,fam)])
        family_summary.append({'house':h,'family':fam,**s,'final_stage':state[(h,fam)]['stage'],
                               'live_activations':family_acts[(h,fam)],'live_rescues':family_rescues[(h,fam)]})

(R/'error_specific_weight_calibration_v3_4.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'error_specific_family_summary_v3_4.json').write_text(json.dumps(family_summary,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_4.json').write_text(json.dumps({'model':'v3.4 Error-Specific Ranking Weight Calibration','house_metrics':metrics},indent=2),encoding='utf-8')

# comparison to v3.3 reconstructed from v3.3 corrected map.
v33_metrics={}
v33map={(x['date'],x['house']):x for x in v33}
for h in metrics:
    rows=[e for e in cf if e['house']==h]; ranks=[]
    for e in rows:
        if e.get('selected_rank') is None: continue
        z=v33map.get((e['date'],h)); ranks.append(z['corrected_rank'] if z else e['selected_rank'])
    v33_metrics[h]={'top5':round(100*sum(r<=5 for r in ranks)/len(ranks),2),'top10':round(100*sum(r<=10 for r in ranks)/len(ranks),2),'mrr':round(sum(1/r for r in ranks)/len(ranks),4)}

comp={h:{'v3_3':v33_metrics[h],'v3_4':{'top5':metrics[h]['top5_pct_elected'],'top10':metrics[h]['top10_pct_elected'],'mrr':metrics[h]['mrr_elected']},
         'delta_top5_pp':round(metrics[h]['top5_pct_elected']-v33_metrics[h]['top5'],2)} for h in metrics}
(R/'V3_3_V3_4_COMPARISON.json').write_text(json.dumps(comp,indent=2),encoding='utf-8')

md=['# DHAPPA v3.4 — Error-Specific Ranking Weight Calibration','',
'v3.4 replaces the generic rescue trigger with independent prior-only correction families. Each family has its own SHADOW → PROBATION → LIVE lifecycle and a circuit breaker. No family may use the current target result to activate itself.','',
'## Overall results','',
'| House | Top-5 | Top-10 | Top-21 | Top-36 | MRR | v3.4 live activations | extra Top-5 rescues | damaged Top-5 |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for h,m in metrics.items():
    md.append(f"| {h} | {m['top5_pct_elected']:.2f}% | {m['top10_pct_elected']:.2f}% | {m['top21_pct_elected']:.2f}% | {m['top36_pct_elected']:.2f}% | {m['mrr_elected']:.4f} | {m['v3_4_live_activations']} | {m['v3_4_realized_top5_rescues']} | {m['v3_4_damaged_top5']} |")
md += ['', '## Error-specific correction families','',
'- **PRIMARY_ROUTE_BIAS:** broad independent challenger confirmation despite Primary rank disadvantage.',
'- **VOTE_COUNT_DISTORTION:** challenger has materially stronger Top-10 support than incumbent.',
'- **REDUNDANCY_OVERBOOST:** challenger support spans more independent engine families.',
'- **RELIABILITY_WEIGHT_ERROR:** reliability-weighted reciprocal-rank evidence favors challenger.',
'- **PRIMARY_RANK_ANCHOR_BIAS:** strong evidence margin suggests Primary rank is over-anchoring the incumbent.',
'', '## Family lifecycle','',
'Every family is evaluated independently per house. It must accumulate at least 15 completed prior proposals, at least two rescues, positive net Top-5, bounded damage, and non-negative Top-10/MRR before entering probation. It then needs eight additional completed triggered proposals with positive Top-5 and zero Top-5 damage before LIVE. A rolling deterioration circuit breaker returns the family to SHADOW.',
'', '## Comparison to v3.3','']
for h,c in comp.items():
    md.append(f"- **{h}:** Top-5 {c['v3_3']['top5']:.2f}% → {c['v3_4']['top5']:.2f}% ({c['delta_top5_pp']:+.2f} pp).")
md += ['', '## Interpretation','',
'v3.4 treats ranking errors as separate mechanisms rather than one universal rescue rule. A correction is not promoted merely because it explains historical misses; it must demonstrate repeatable prior-only rescue performance and then survive a fresh probation period.',
'', '## Integrity','',
'- Current-target outcome is revealed only after the family stage and correction decision are frozen.',
'- Family weights are derived only from completed prior observations.',
'- Multiple surviving families do not stack; the strongest prior-derived family controls at most one Rank-6–12 replacement.',
'- Failed families remain in shadow and cannot alter the canonical ranking.']
(R/'DHAPPA_ERROR_SPECIFIC_RANKING_CALIBRATION_V3_4_REPORT.md').write_text('\n'.join(md),encoding='utf-8')

# integrity report
issues=[]
for z in records:
    if z['chosen_family'] and z['chosen_family'] not in z['triggered_families']: issues.append({'date':z['date'],'house':z['house'],'issue':'chosen family not triggered'})
    if z['chosen_family'] and z['v3_4_rank']!=z['rescue_rank']: issues.append({'date':z['date'],'house':z['house'],'issue':'active correction did not use frozen rescue rank'})
integ={'records_checked':len(records),'live_activations':sum(activations.values()),'issues':issues,'status':'PASS' if not issues else 'FAIL'}
(R/'error_specific_integrity_v3_4.json').write_text(json.dumps(integ,indent=2),encoding='utf-8')
print(json.dumps({'metrics':metrics,'comparison':comp,'integrity':integ,'active_families':[x for x in family_summary if x['live_activations']]},indent=2))
