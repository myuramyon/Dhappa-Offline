from pathlib import Path
import json
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
v34=json.loads((R/'error_specific_weight_calibration_v3_4.json').read_text())
resc=json.loads((R/'candidate_rank6_12_rescue_v3_2.json').read_text())
cf=json.loads((R/'route_counterfactual_election_lab_v2_6.json').read_text())
rb={(x['date'],x['house']):x for x in resc}

# v3.5 is intentionally a controller over v3.4, not a new generator.
# Every condition below is observable before the current target outcome.
def live_families(rec):
    return [d['family'] for d in rec.get('family_diagnostics',[]) if d.get('stage')=='LIVE']

def static_precision_gate(rec):
    if not rec.get('chosen_family'):
        return False, ['NO_V3_4_LIVE_FAMILY']
    x=rb[(rec['date'],rec['house'])]
    f=rec['features']; ie=x['incumbent_evidence']; ce=x['challenger_evidence']
    checks={
        'TWO_LIVE_FAMILIES': len(live_families(rec))>=2,
        'BOUNDARY_RANK_6_9': 6 <= f['challenger_primary_rank'] <= 9,
        'NEAR_BOUNDARY_MARGIN': 0.08 <= f['margin'] <= 0.30,
        'STRONG_RELIABILITY_ADVANTAGE': f['weighted_rr_delta'] >= 0.50,
        'WEAK_INCUMBENT_SUPPORT': ie.get('support10',0) <= 2 and ie.get('family_support',0) <= 2 and ie.get('weighted_rr',0) <= 0.60,
        'MIN_CHALLENGER_DIVERSITY': ce.get('support10',0) >= 2 and ce.get('family_support',0) >= 2,
    }
    return all(checks.values()), [k for k,v in checks.items() if not v]

def outcome(base,rescue):
    return {
        'net5': int(rescue<=5)-int(base<=5),
        'net10': int(rescue<=10)-int(base<=10),
        'mrr': (1/rescue)-(1/base),
        'rescued': int(base>5 and rescue<=5),
        'damaged': int(base<=5 and rescue>5),
    }

def summarize(xs):
    if not xs: return {'n':0,'net5':0,'net10':0,'mrr':0.0,'rescued':0,'damaged':0,'precision_when_material':None}
    os=[outcome(x['v3_3_rank'],x['rescue_rank']) for x in xs]
    material=sum(o['rescued']+o['damaged'] for o in os)
    return {
        'n':len(xs),
        'net5':sum(o['net5'] for o in os),
        'net10':sum(o['net10'] for o in os),
        'mrr':round(sum(o['mrr'] for o in os)/len(os),8),
        'rescued':sum(o['rescued'] for o in os),
        'damaged':sum(o['damaged'] for o in os),
        'precision_when_material': round(sum(o['rescued'] for o in os)/material,4) if material else None,
    }

history=defaultdict(list)
records=[]
activations=Counter(); rescues=Counter(); damages=Counter(); suspensions=Counter()

for rec in sorted(v34,key=lambda z:(z['date'],z['house'])):
    house=rec['house']; gate_ok, failed=static_precision_gate(rec)
    prior=history[house]
    recent=summarize(prior[-20:]); expanding=summarize(prior)
    # Circuit breaker is prior-only. Neutral history does not block first tests; evidence of damage does.
    controller_ok=True; controller_reason='PASS'
    if recent['n']>=8 and (recent['net5']<0 or recent['net10']<0 or recent['mrr']<0 or recent['damaged']>0):
        controller_ok=False; controller_reason='RECENT_PRECISION_BREAKER'
    if expanding['n']>=12 and expanding['damaged']>expanding['rescued']:
        controller_ok=False; controller_reason='EXPANDING_DAMAGE_BREAKER'
    active=bool(gate_ok and controller_ok)
    final_rank=rec['rescue_rank'] if active else rec['v3_3_rank']
    if gate_ok and not controller_ok: suspensions[house]+=1
    if active:
        activations[house]+=1
        if rec['v3_3_rank']>5 and final_rank<=5: rescues[house]+=1
        if rec['v3_3_rank']<=5 and final_rank>5: damages[house]+=1
    records.append({
        'date':rec['date'],'house':house,'source_cutoff':rb[(rec['date'],house)].get('source_cutoff'),
        'v3_3_rank':rec['v3_3_rank'],'v3_4_rank':rec['v3_4_rank'],'v3_5_rank':final_rank,'rescue_rank':rec['rescue_rank'],
        'incumbent':rec.get('incumbent'),'challenger':rec.get('challenger'),'chosen_family_v3_4':rec.get('chosen_family'),
        'live_families':live_families(rec),'features':rec['features'],'static_gate_pass':gate_ok,'failed_conditions':failed,
        'controller_pass':controller_ok,'controller_reason':controller_reason,'active':active,
        'prior_precision_expanding':expanding,'prior_precision_recent20':recent,
    })
    # Reveal outcome only after current decision is frozen. Only static-gate opportunities are precision observations.
    if gate_ok:
        history[house].append(rec)

rec_by={(x['date'],x['house']):x for x in records}
metrics={}
for h in ('Deshawar','Faridabad','Ghaziabad','Gali'):
    rows=[e for e in cf if e['house']==h]
    ranks=[]; allr=[]
    for e in rows:
        if e.get('selected_rank') is None:
            allr.append(None); continue
        z=rec_by.get((e['date'],h)); r=z['v3_5_rank'] if z else e['selected_rank']
        ranks.append(r); allr.append(r)
    def pct(k): return round(100*sum(r<=k for r in ranks)/len(ranks),2) if ranks else 0
    def pctall(k): return round(100*sum(r is not None and r<=k for r in allr)/len(allr),2) if allr else 0
    metrics[h]={
        'targets':len(rows),'elected_targets':len(ranks),'top5_pct_elected':pct(5),'top10_pct_elected':pct(10),
        'top21_pct_elected':pct(21),'top36_pct_elected':pct(36),'top5_pct_all_targets':pctall(5),
        'mrr_elected':round(sum(1/r for r in ranks)/len(ranks),4) if ranks else 0,
        'v3_5_live_activations':activations[h],'v3_5_realized_top5_rescues':rescues[h],
        'v3_5_damaged_top5':damages[h],'v3_5_suspensions':suspensions[h],
        'precision_history':summarize(history[h]),
    }

v34m=json.loads((R/'dynamic_primary_engine_backtest_v3_4.json').read_text())['house_metrics']
comp={}
for h,m in metrics.items():
    old=v34m[h]
    comp[h]={
      'v3_4':{'top5':old['top5_pct_elected'],'top10':old['top10_pct_elected'],'mrr':old['mrr_elected'],'activations':old['v3_4_live_activations']},
      'v3_5':{'top5':m['top5_pct_elected'],'top10':m['top10_pct_elected'],'mrr':m['mrr_elected'],'activations':m['v3_5_live_activations']},
      'activation_reduction':old['v3_4_live_activations']-m['v3_5_live_activations'],
      'activation_reduction_pct':round(100*(old['v3_4_live_activations']-m['v3_5_live_activations'])/old['v3_4_live_activations'],2) if old['v3_4_live_activations'] else 0,
      'delta_top5_pp':round(m['top5_pct_elected']-old['top5_pct_elected'],2)
    }

(R/'activation_precision_controller_v3_5.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(R/'dynamic_primary_engine_backtest_v3_5.json').write_text(json.dumps({'model':'v3.5 Activation Precision Controller','house_metrics':metrics},indent=2),encoding='utf-8')
(R/'V3_4_V3_5_COMPARISON.json').write_text(json.dumps(comp,indent=2),encoding='utf-8')

md=['# DHAPPA v3.5 — Activation Precision Controller','',
'v3.5 does not add a new generator or a new ranking family. It controls when the already validated v3.4 error-specific correction is allowed to intervene. All gate inputs are frozen pre-target evidence.','',
'## Precision gate','',
'A v3.4 correction may intervene only when all of the following hold: at least two correction families are already LIVE; challenger primary rank is 6–9; evidence margin is near-boundary (0.08–0.30); weighted reciprocal-rank advantage is at least 0.50; incumbent support is weak; challenger has at least two Top-10 and two independent-family supports. A prior-only rolling circuit breaker suspends intervention after damage or negative recent utility.','',
'## Results','',
'| House | Top-5 | Top-10 | MRR | v3.4 activations | v3.5 activations | reduction | extra rescues | damaged Top-5 |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for h,m in metrics.items():
    c=comp[h]
    md.append(f"| {h} | {m['top5_pct_elected']:.2f}% | {m['top10_pct_elected']:.2f}% | {m['mrr_elected']:.4f} | {c['v3_4']['activations']} | {m['v3_5_live_activations']} | {c['activation_reduction_pct']:.2f}% | {m['v3_5_realized_top5_rescues']} | {m['v3_5_damaged_top5']} |")
md += ['', '## Interpretation','',
'v3.5 is a precision controller, so success is defined as preserving validated ranking benefit while materially reducing unnecessary interventions. A lower activation count with the same Top-5 outcome is preferable to broad intervention because it reduces exposure to future damage and makes each live correction more auditable.','',
'## Temporal integrity','',
'- Current target outcome is not used by the static gate or circuit breaker.',
'- Precision history is updated only after the current decision is frozen and the target is revealed.',
'- The controller can only suppress a v3.4 correction; it cannot invent a candidate or create a new route.',
'- If rolling precision deteriorates, live intervention is suspended automatically.']
(R/'DHAPPA_ACTIVATION_PRECISION_CONTROLLER_V3_5_REPORT.md').write_text('\n'.join(md),encoding='utf-8')

cmpmd=['# DHAPPA v3.4 vs v3.5','',
'| House | v3.4 Top-5 | v3.5 Top-5 | v3.4 activations | v3.5 activations | activation reduction |',
'|---|---:|---:|---:|---:|---:|']
for h,c in comp.items():
    cmpmd.append(f"| {h} | {c['v3_4']['top5']:.2f}% | {c['v3_5']['top5']:.2f}% | {c['v3_4']['activations']} | {c['v3_5']['activations']} | {c['activation_reduction_pct']:.2f}% |")
(R/'DHAPPA_V3_4_V3_5_COMPARISON.md').write_text('\n'.join(cmpmd),encoding='utf-8')

issues=[]
for z in records:
    if z['active'] and not z['static_gate_pass']: issues.append({'date':z['date'],'house':z['house'],'issue':'active without static gate'})
    if z['active'] and not z['controller_pass']: issues.append({'date':z['date'],'house':z['house'],'issue':'active despite circuit breaker'})
    if z['active'] and z['v3_5_rank']!=z['rescue_rank']: issues.append({'date':z['date'],'house':z['house'],'issue':'active did not apply frozen rescue rank'})
    if (not z['active']) and z['v3_5_rank']!=z['v3_3_rank']: issues.append({'date':z['date'],'house':z['house'],'issue':'inactive changed baseline rank'})
integ={'records_checked':len(records),'active_records':sum(1 for z in records if z['active']),'issues':issues,'status':'PASS' if not issues else 'FAIL'}
(R/'activation_precision_integrity_v3_5.json').write_text(json.dumps(integ,indent=2),encoding='utf-8')
print(json.dumps({'metrics':metrics,'comparison':comp,'integrity':integ,'active_cases':[z for z in records if z['active']]},indent=2))
