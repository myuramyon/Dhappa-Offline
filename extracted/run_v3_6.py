from pathlib import Path
import json
from collections import Counter, defaultdict

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
v35=json.loads((R/'activation_precision_controller_v3_5.json').read_text())
resc=json.loads((R/'candidate_rank6_12_rescue_v3_2.json').read_text())
cf=json.loads((R/'route_counterfactual_election_lab_v2_6.json').read_text())
rb={(x['date'],x['house']):x for x in resc}

# v3.6 is a suppressive controller over v3.5. It never creates a candidate or activates
# a correction that v3.5 did not already approve.
def vulnerability_features(rec):
    x=rb[(rec['date'],rec['house'])]
    ie=x['incumbent_evidence']; ce=x['challenger_evidence']
    primary_only = len(ie.get('supporters',[])) <= 1
    checks={
        'TRUE_RANK5_INCUMBENT': ie.get('primary_rank') == 5,
        'LOW_TOP10_SUPPORT': ie.get('support10',0) <= 1,
        'LOW_FAMILY_DIVERSITY': ie.get('family_support',0) <= 1,
        'LOW_WEIGHTED_RELIABILITY': ie.get('weighted_rr',0.0) <= 0.40,
        'PRIMARY_ONLY_DEPENDENCE': primary_only,
        'LOW_INCUMBENT_SCORE': ie.get('score',0.0) <= 0.26,
        'CHALLENGER_MULTI_ROUTE': ce.get('support10',0) >= 2 and ce.get('family_support',0) >= 2,
        'CHALLENGER_SCORE_ADVANTAGE': (ce.get('score',0.0)-ie.get('score',0.0)) >= 0.15,
    }
    # Core vulnerability intentionally emphasizes incumbent weakness, not just challenger strength.
    incumbent_core=sum(int(checks[k]) for k in [
        'LOW_TOP10_SUPPORT','LOW_FAMILY_DIVERSITY','LOW_WEIGHTED_RELIABILITY',
        'PRIMARY_ONLY_DEPENDENCE','LOW_INCUMBENT_SCORE'])
    challenger_core=sum(int(checks[k]) for k in ['CHALLENGER_MULTI_ROUTE','CHALLENGER_SCORE_ADVANTAGE'])
    score=incumbent_core + challenger_core
    if checks['TRUE_RANK5_INCUMBENT'] and incumbent_core>=4 and challenger_core>=1:
        tier='HIGH'
    elif checks['TRUE_RANK5_INCUMBENT'] and incumbent_core>=2:
        tier='MODERATE'
    elif checks['TRUE_RANK5_INCUMBENT']:
        tier='LOW'
    else:
        tier='NOT_RANK5'
    return x, checks, score, tier

def outcome(base,rescue):
    return {
        'net5': int(rescue<=5)-int(base<=5),
        'net10': int(rescue<=10)-int(base<=10),
        'mrr': (1/rescue)-(1/base),
        'rescued': int(base>5 and rescue<=5),
        'damaged': int(base<=5 and rescue>5),
    }

def summarize(xs):
    if not xs:
        return {'n':0,'net5':0,'net10':0,'mrr':0.0,'rescued':0,'damaged':0}
    os=[outcome(x['v3_3_rank'],x['v3_6_rank']) for x in xs]
    return {
        'n':len(xs),'net5':sum(o['net5'] for o in os),'net10':sum(o['net10'] for o in os),
        'mrr':round(sum(o['mrr'] for o in os)/len(os),8),
        'rescued':sum(o['rescued'] for o in os),'damaged':sum(o['damaged'] for o in os),
    }

records=[]
history=defaultdict(list)
activations=Counter(); rescues=Counter(); damages=Counter(); suppressed=Counter(); tiers=defaultdict(Counter)
for rec in sorted(v35,key=lambda z:(z['date'],z['house'])):
    house=rec['house']; x,checks,vscore,tier=vulnerability_features(rec); tiers[house][tier]+=1
    prior=history[house]
    # Prior-only circuit breaker for the vulnerability controller itself.
    prior_recent=summarize(prior[-12:]); prior_all=summarize(prior)
    breaker=True; breaker_reason='PASS'
    if prior_recent['n']>=6 and (prior_recent['damaged']>0 or prior_recent['net5']<0 or prior_recent['net10']<0):
        breaker=False; breaker_reason='RECENT_VULNERABILITY_DAMAGE'
    if prior_all['n']>=8 and prior_all['damaged']>prior_all['rescued']:
        breaker=False; breaker_reason='EXPANDING_VULNERABILITY_DAMAGE'
    active=bool(rec.get('active') and tier=='HIGH' and breaker)
    final_rank=rec['rescue_rank'] if active else rec['v3_3_rank']
    if rec.get('active') and not active: suppressed[house]+=1
    if active:
        activations[house]+=1
        if rec['v3_3_rank']>5 and final_rank<=5: rescues[house]+=1
        if rec['v3_3_rank']<=5 and final_rank>5: damages[house]+=1
    out={
        'date':rec['date'],'house':house,'source_cutoff':rec.get('source_cutoff'),
        'incumbent':rec.get('incumbent'),'challenger':rec.get('challenger'),
        'v3_3_rank':rec['v3_3_rank'],'v3_5_rank':rec['v3_5_rank'],'v3_6_rank':final_rank,'rescue_rank':rec['rescue_rank'],
        'v3_5_active':bool(rec.get('active')),'v3_6_active':active,
        'vulnerability_tier':tier,'vulnerability_score':vscore,'vulnerability_checks':checks,
        'incumbent_evidence':x['incumbent_evidence'],'challenger_evidence':x['challenger_evidence'],
        'breaker_pass':breaker,'breaker_reason':breaker_reason,
        'prior_vulnerability_recent12':prior_recent,'prior_vulnerability_expanding':prior_all,
    }
    records.append(out)
    # Only frozen HIGH-vulnerability opportunities are learned after reveal.
    if rec.get('active') and tier=='HIGH':
        history[house].append(out)

rec_by={(x['date'],x['house']):x for x in records}
metrics={}
for h in ('Deshawar','Faridabad','Ghaziabad','Gali'):
    rows=[e for e in cf if e['house']==h]
    ranks=[]; allr=[]
    for e in rows:
        if e.get('selected_rank') is None:
            allr.append(None); continue
        z=rec_by.get((e['date'],h)); r=z['v3_6_rank'] if z else e['selected_rank']
        ranks.append(r); allr.append(r)
    def pct(k): return round(100*sum(r<=k for r in ranks)/len(ranks),2) if ranks else 0
    def pctall(k): return round(100*sum(r is not None and r<=k for r in allr)/len(allr),2) if allr else 0
    metrics[h]={
        'targets':len(rows),'elected_targets':len(ranks),'top5_pct_elected':pct(5),'top10_pct_elected':pct(10),
        'top21_pct_elected':pct(21),'top36_pct_elected':pct(36),'top5_pct_all_targets':pctall(5),
        'mrr_elected':round(sum(1/r for r in ranks)/len(ranks),4) if ranks else 0,
        'v3_6_live_activations':activations[h],'v3_6_realized_top5_rescues':rescues[h],
        'v3_6_damaged_top5':damages[h],'v3_5_interventions_suppressed':suppressed[h],
        'vulnerability_tiers':dict(tiers[h]),'vulnerability_history':summarize(history[h]),
    }

v35m=json.loads((R/'dynamic_primary_engine_backtest_v3_5.json').read_text())['house_metrics']
comp={}
for h,m in metrics.items():
    old=v35m[h]
    comp[h]={
        'v3_5':{'top5':old['top5_pct_elected'],'top10':old['top10_pct_elected'],'mrr':old['mrr_elected'],'activations':old['v3_5_live_activations']},
        'v3_6':{'top5':m['top5_pct_elected'],'top10':m['top10_pct_elected'],'mrr':m['mrr_elected'],'activations':m['v3_6_live_activations']},
        'activation_reduction':old['v3_5_live_activations']-m['v3_6_live_activations'],
        'activation_reduction_pct':round(100*(old['v3_5_live_activations']-m['v3_6_live_activations'])/old['v3_5_live_activations'],2) if old['v3_5_live_activations'] else 0,
        'delta_top5_pp':round(m['top5_pct_elected']-old['top5_pct_elected'],2),
    }

(R/'rank5_vulnerability_controller_v3_6.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_6.json').write_text(json.dumps({'model':'v3.6 Rank-5 Vulnerability Controller','house_metrics':metrics},indent=2),encoding='utf-8')
(R/'V3_5_V3_6_COMPARISON.json').write_text(json.dumps(comp,indent=2),encoding='utf-8')

md=['# DHAPPA v3.6 — Rank-5 Vulnerability Model','',
'v3.6 is a suppressive controller over v3.5. It does not generate a new candidate and cannot activate any correction that v3.5 did not already approve. The intervention is allowed only when the candidate being displaced is the actual canonical Rank-5 candidate and its frozen pre-target evidence is structurally weak.','',
'## Vulnerability definition','',
'Rank-5 vulnerability is derived from pre-target incumbent evidence: low Top-10 support, low independent-family diversity, low reliability-weighted reciprocal-rank support, dependence on a single Primary route, and low incumbent evidence score. Challenger strength is used only as a secondary confirmation. The current target outcome is never a vulnerability feature.','',
'## Results','',
'| House | Top-5 | Top-10 | MRR | v3.5 activations | v3.6 activations | reduction | rescues | damaged Top-5 |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for h,m in metrics.items():
    c=comp[h]
    md.append(f"| {h} | {m['top5_pct_elected']:.2f}% | {m['top10_pct_elected']:.2f}% | {m['mrr_elected']:.4f} | {c['v3_5']['activations']} | {m['v3_6_live_activations']} | {c['activation_reduction_pct']:.2f}% | {m['v3_6_realized_top5_rescues']} | {m['v3_6_damaged_top5']} |")
md += ['', '## Interpretation','',
'v3.6 asks a stricter question than v3.5: not only whether the challenger is strong enough, but whether Rank-5 is weak enough to justify displacement. This reduces intervention surface area while preserving any rescue that occurs inside a demonstrably vulnerable Rank-5 state.','',
'## Temporal integrity','',
'- Vulnerability uses only frozen pre-target evidence.',
'- v3.6 can only suppress a v3.5-approved correction.',
'- Current target outcome is revealed only after the v3.6 decision is frozen.',
'- Vulnerability precision history updates only after reveal.',
'- A prior-only circuit breaker suspends intervention after damage.']
(R/'DHAPPA_RANK5_VULNERABILITY_V3_6_REPORT.md').write_text('\n'.join(md),encoding='utf-8')

cmp=['# DHAPPA v3.5 vs v3.6','',
'| House | v3.5 Top-5 | v3.6 Top-5 | v3.5 activations | v3.6 activations | activation reduction |',
'|---|---:|---:|---:|---:|---:|']
for h,c in comp.items():
    cmp.append(f"| {h} | {c['v3_5']['top5']:.2f}% | {c['v3_6']['top5']:.2f}% | {c['v3_5']['activations']} | {c['v3_6']['activations']} | {c['activation_reduction_pct']:.2f}% |")
(R/'DHAPPA_V3_5_V3_6_COMPARISON.md').write_text('\n'.join(cmp),encoding='utf-8')

issues=[]
for z in records:
    if z['v3_6_active'] and not z['v3_5_active']: issues.append({'date':z['date'],'house':z['house'],'issue':'v3.6 activated without v3.5 approval'})
    if z['v3_6_active'] and z['vulnerability_tier']!='HIGH': issues.append({'date':z['date'],'house':z['house'],'issue':'active without HIGH vulnerability'})
    if z['v3_6_active'] and not z['vulnerability_checks']['TRUE_RANK5_INCUMBENT']: issues.append({'date':z['date'],'house':z['house'],'issue':'active without true Rank-5 incumbent'})
    if z['v3_6_active'] and not z['breaker_pass']: issues.append({'date':z['date'],'house':z['house'],'issue':'active despite vulnerability breaker'})
    if z['v3_6_active'] and z['v3_6_rank']!=z['rescue_rank']: issues.append({'date':z['date'],'house':z['house'],'issue':'active did not apply frozen rescue'})
    if (not z['v3_6_active']) and z['v3_6_rank']!=z['v3_3_rank']: issues.append({'date':z['date'],'house':z['house'],'issue':'inactive changed canonical rank'})
integ={'records_checked':len(records),'active_records':sum(1 for z in records if z['v3_6_active']),'issues':issues,'status':'PASS' if not issues else 'FAIL'}
(R/'rank5_vulnerability_integrity_v3_6.json').write_text(json.dumps(integ,indent=2),encoding='utf-8')

print(json.dumps({'metrics':metrics,'comparison':comp,'integrity':integ,'active_cases':[z for z in records if z['v3_6_active']]},indent=2))
