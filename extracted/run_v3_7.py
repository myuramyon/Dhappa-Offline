from pathlib import Path
import json
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
v36=json.loads((R/'rank5_vulnerability_controller_v3_6.json').read_text())
resc=json.loads((R/'candidate_rank6_12_rescue_v3_2.json').read_text())
cf=json.loads((R/'route_counterfactual_election_lab_v2_6.json').read_text())
resc_by={(x['date'],x['house']):x for x in resc}
cf_by={(x['date'],x['house']):x for x in cf}

HOUSES=('Deshawar','Faridabad','Ghaziabad','Gali')

def weak_incumbent(x):
    ie=x['incumbent_evidence']
    return (ie.get('primary_rank')==5 and ie.get('support10',0)<=1 and
            ie.get('family_support',0)<=1 and ie.get('weighted_rr',0)<=0.40 and
            ie.get('score',0)<=0.26)

def challenger_strong(x):
    ie=x['incumbent_evidence']; ce=x['challenger_evidence']
    return (6 <= ce.get('primary_rank',99) <= 9 and ce.get('support10',0)>=2 and
            ce.get('family_support',0)>=2 and
            (ce.get('score',0)-ie.get('score',0))>=0.15)

def rank_band(r):
    if 6 <= r <= 7: return 'R6_7'
    if 8 <= r <= 9: return 'R8_9'
    if 10 <= r <= 12: return 'R10_12'
    return 'OTHER'

def rr_band(v):
    if v>=1.0:return 'RR1P'
    if v>=0.75:return 'RR75P'
    if v>=0.50:return 'RR50P'
    return 'RRLOW'

def fam_band(v): return 'F3P' if v>=3 else 'F2' if v==2 else 'F1'

def state_keys(x):
    ie=x['incumbent_evidence']; ce=x['challenger_evidence']; adv=ce.get('weighted_rr',0)-ie.get('weighted_rr',0)
    # Hierarchical signatures. Current outcome is not represented in any key.
    return [
        ('EXACT', x['house'], rank_band(ce.get('primary_rank',99)), fam_band(ce.get('family_support',0)), rr_band(adv)),
        ('COARSE', x['house'], rank_band(ce.get('primary_rank',99))),
        ('HOUSE_WEAK_R5', x['house']),
    ]

def revealed_outcome(x):
    # baseline_rank/rescue_rank are outcome-derived and are used only AFTER target reveal
    b=x['baseline_rank']; rr=x['rescue_rank']
    return {
        'baseline_top5': int(b<=5),
        'rank5_state_failed': int(b>5),
        'takeover_rescue': int(b>5 and rr<=5),
        'takeover_damage': int(b<=5 and rr>5),
        'net5': int(rr<=5)-int(b<=5),
        'net10': int(rr<=10)-int(b<=10),
        'mrr_delta': (1/rr)-(1/b),
    }

def summarize(hist):
    n=len(hist)
    if not n:
        return {'n':0,'rank5_failure_rate':None,'takeover_rescues':0,'takeover_damages':0,'net5':0,'net10':0,'mrr_delta':0.0,'material_precision':None}
    outs=[revealed_outcome(x) for x in hist]
    material=sum(o['takeover_rescue']+o['takeover_damage'] for o in outs)
    return {
        'n':n,
        'rank5_failure_rate':round(sum(o['rank5_state_failed'] for o in outs)/n,4),
        'takeover_rescues':sum(o['takeover_rescue'] for o in outs),
        'takeover_damages':sum(o['takeover_damage'] for o in outs),
        'net5':sum(o['net5'] for o in outs),
        'net10':sum(o['net10'] for o in outs),
        'mrr_delta':round(sum(o['mrr_delta'] for o in outs)/n,8),
        'material_precision':round(sum(o['takeover_rescue'] for o in outs)/material,4) if material else None,
    }

# Histories are updated strictly after the current date decision has been frozen.
histories=defaultdict(list)
records=[]
activ=Counter(); rescues=Counter(); damages=Counter(); suppressed=Counter()

# We process all rescue proposals to populate the survival database, but v3.7 can only suppress v3.6.
all_keys=sorted({(x['date'],x['house']) for x in resc})
v36_by={(x['date'],x['house']):x for x in v36}
for date,house in all_keys:
    x=resc_by[(date,house)]
    rec=v36_by.get((date,house))
    keys=state_keys(x)
    prior_stats=[]
    selected=None
    # Backoff: exact >=8, coarse >=10, house vulnerable >=12.
    mins={'EXACT':8,'COARSE':10,'HOUSE_WEAK_R5':12}
    for k in keys:
        s=summarize(histories[k]); prior_stats.append({'key':list(k),'stats':s})
        if selected is None and s['n']>=mins[k[0]]:
            selected={'key':k,'stats':s}
    # Survival criterion: similar Rank-5 states must be demonstrably unreliable.
    # Takeover damage cannot exceed rescue evidence; neutral history is allowed because v3.7
    # is suppressive over already high-precision v3.6 rather than a new activation model.
    survival_pass=False; reason='NO_V3_6_RECORD'
    if rec is not None:
        if not rec.get('v3_6_active'):
            reason='V3_6_INACTIVE'
        elif selected is None:
            # Sparse-history fail-open only for an already v3.6-approved intervention.
            # This preserves prospective discovery rather than retroactively killing first evidence.
            survival_pass=True; reason='SPARSE_HISTORY_FAIL_OPEN'
        else:
            s=selected['stats']
            survival_pass=(s['rank5_failure_rate'] is not None and s['rank5_failure_rate']>=0.80 and
                           s['takeover_damages']<=s['takeover_rescues'] and s['net10']>=0 and s['mrr_delta']>=0)
            reason='SURVIVAL_PASS' if survival_pass else 'SURVIVAL_REJECT'
    active=bool(rec is not None and rec.get('v3_6_active') and survival_pass)
    if rec is not None:
        final_rank=rec['rescue_rank'] if active else rec['v3_3_rank']
        if rec.get('v3_6_active') and not active: suppressed[house]+=1
        if active:
            activ[house]+=1
            if rec['v3_3_rank']>5 and final_rank<=5: rescues[house]+=1
            if rec['v3_3_rank']<=5 and final_rank>5: damages[house]+=1
        records.append({
            'date':date,'house':house,'source_cutoff':rec.get('source_cutoff'),
            'incumbent':rec.get('incumbent'),'challenger':rec.get('challenger'),
            'v3_3_rank':rec['v3_3_rank'],'v3_6_rank':rec['v3_6_rank'],'v3_7_rank':final_rank,
            'v3_6_active':bool(rec.get('v3_6_active')),'v3_7_active':active,
            'survival_pass':survival_pass,'survival_reason':reason,
            'selected_survival_level': selected['key'][0] if selected else None,
            'selected_survival_key': list(selected['key']) if selected else None,
            'selected_survival_stats': selected['stats'] if selected else None,
            'prior_survival_backoff': prior_stats,
            'vulnerability_tier':rec.get('vulnerability_tier'),
        })
    # Reveal/update only after current decision. Only structurally relevant weak Rank-5 states enter cohorts.
    if weak_incumbent(x) and challenger_strong(x):
        for k in keys:
            histories[k].append(x)

rec_by={(z['date'],z['house']):z for z in records}
metrics={}
for h in HOUSES:
    rows=[e for e in cf if e['house']==h]
    ranks=[]; allr=[]
    for e in rows:
        if e.get('selected_rank') is None:
            allr.append(None); continue
        z=rec_by.get((e['date'],h)); r=z['v3_7_rank'] if z else e['selected_rank']
        ranks.append(r); allr.append(r)
    def pct(k):return round(100*sum(r<=k for r in ranks)/len(ranks),2) if ranks else 0
    def pctall(k):return round(100*sum(r is not None and r<=k for r in allr)/len(allr),2) if allr else 0
    metrics[h]={
        'targets':len(rows),'elected_targets':len(ranks),'top5_pct_elected':pct(5),'top10_pct_elected':pct(10),
        'top21_pct_elected':pct(21),'top36_pct_elected':pct(36),'top5_pct_all_targets':pctall(5),
        'mrr_elected':round(sum(1/r for r in ranks)/len(ranks),4) if ranks else 0,
        'v3_7_live_activations':activ[h],'v3_7_realized_top5_rescues':rescues[h],
        'v3_7_damaged_top5':damages[h],'v3_6_interventions_suppressed':suppressed[h],
    }

v36m=json.loads((R/'dynamic_primary_engine_backtest_v3_6.json').read_text())['house_metrics']
comp={}
for h,m in metrics.items():
    old=v36m[h]
    comp[h]={
        'v3_6':{'top5':old['top5_pct_elected'],'top10':old['top10_pct_elected'],'mrr':old['mrr_elected'],'activations':old['v3_6_live_activations']},
        'v3_7':{'top5':m['top5_pct_elected'],'top10':m['top10_pct_elected'],'mrr':m['mrr_elected'],'activations':m['v3_7_live_activations']},
        'delta_top5_pp':round(m['top5_pct_elected']-old['top5_pct_elected'],2),
        'activation_reduction':old['v3_6_live_activations']-m['v3_7_live_activations'],
    }

issues=[]
for z in records:
    if z['v3_7_active'] and not z['v3_6_active']:
        issues.append({'date':z['date'],'house':z['house'],'issue':'v3.7 activated without v3.6 approval'})
    if z['v3_7_active'] and not z['survival_pass']:
        issues.append({'date':z['date'],'house':z['house'],'issue':'active without survival pass'})
    if (not z['v3_7_active']) and z['v3_7_rank']!=z['v3_3_rank']:
        issues.append({'date':z['date'],'house':z['house'],'issue':'inactive changed baseline rank'})
    if z['v3_7_active'] and z['v3_7_rank']!=z['v3_6_rank']:
        issues.append({'date':z['date'],'house':z['house'],'issue':'active rank differs from v3.6 frozen correction'})
integ={'records_checked':len(records),'active_records':sum(z['v3_7_active'] for z in records),'issues':issues,'status':'PASS' if not issues else 'FAIL'}

(R/'rank5_false_positive_survival_v3_7.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_7.json').write_text(json.dumps({'model':'v3.7 Rank-5 False-Positive Survival Model','house_metrics':metrics},indent=2),encoding='utf-8')
(R/'V3_6_V3_7_COMPARISON.json').write_text(json.dumps(comp,indent=2),encoding='utf-8')
(R/'rank5_false_positive_survival_integrity_v3_7.json').write_text(json.dumps(integ,indent=2),encoding='utf-8')

md=['# DHAPPA v3.7 — Rank-5 False-Positive Survival Model','',
'v3.7 adds a prior-only historical survival layer above v3.6. It is suppressive only: it cannot invent a challenger and cannot activate a correction that v3.6 rejected. Similar weak Rank-5 states are tracked with hierarchical backoff (exact context → coarse challenger-rank context → house-level weak Rank-5 cohort).','',
'## Survival evidence','',
'The survival layer tracks how often comparable frozen Rank-5 states subsequently missed Top-5, how often the frozen challenger actually rescued Top-5, whether a takeover damaged an existing Top-5 hit, and Top-10/MRR deltas. Outcome fields enter these histories only after the corresponding target has been revealed.','',
'## Results','',
'| House | Top-5 | Top-10 | MRR | v3.6 activations | v3.7 activations | rescues | damaged Top-5 |',
'|---|---:|---:|---:|---:|---:|---:|---:|']
for h,m in metrics.items():
    c=comp[h]
    md.append(f"| {h} | {m['top5_pct_elected']:.2f}% | {m['top10_pct_elected']:.2f}% | {m['mrr_elected']:.4f} | {c['v3_6']['activations']} | {m['v3_7_live_activations']} | {m['v3_7_realized_top5_rescues']} | {m['v3_7_damaged_top5']} |")
md += ['', '## Interpretation','',
'This experiment tests whether historical unreliability of the Rank-5 boundary can safely add another filter after structural vulnerability. Because takeover outcomes are sparse, the model uses hierarchical minimum-sample backoff and deliberately avoids converting false-positive frequency into a probability claim. Sparse history is fail-open only for interventions already approved by the much stricter v3.6 gate; once sufficient comparable history exists, survival can suppress but never create an intervention.','',
'## Temporal integrity','',
'- All state features are frozen before the current target outcome.',
'- Similar-state outcome histories update only after reveal.',
'- v3.7 can only suppress v3.6.',
'- No hindsight-selected date rule or target-specific exception is used.']
(R/'DHAPPA_RANK5_FALSE_POSITIVE_SURVIVAL_V3_7_REPORT.md').write_text('\n'.join(md),encoding='utf-8')

cmp=['# DHAPPA v3.6 vs v3.7','',
'| House | v3.6 Top-5 | v3.7 Top-5 | v3.6 activations | v3.7 activations | Δ Top-5 |',
'|---|---:|---:|---:|---:|---:|']
for h,c in comp.items():
    cmp.append(f"| {h} | {c['v3_6']['top5']:.2f}% | {c['v3_7']['top5']:.2f}% | {c['v3_6']['activations']} | {c['v3_7']['activations']} | {c['delta_top5_pp']:+.2f} pp |")
(R/'DHAPPA_V3_6_V3_7_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')
print(json.dumps({'metrics':metrics,'comparison':comp,'integrity':integ,'active_cases':[z for z in records if z['v3_7_active']]},indent=2))
