from pathlib import Path
import json
from collections import Counter, defaultdict

ROOT=Path(__file__).resolve().parent
R=ROOT/'reports'
cf=json.loads((R/'route_counterfactual_election_lab_v2_6.json').read_text())
resc=json.loads((R/'candidate_rank6_12_rescue_v3_2.json').read_text())
by={(x['date'],x['house']):x for x in resc}

def band(r):
    if r is None:return 'NA'
    if r<=5:return 'TOP5'
    if r<=7:return 'R6_7'
    if r<=9:return 'R8_9'
    if r<=12:return 'R10_12'
    if r<=21:return 'R13_21'
    if r<=36:return 'R22_36'
    return 'R37P'

def sig(x):
    ce=x.get('challenger_evidence') or {}; ie=x.get('incumbent_evidence') or {}
    s10d=ce.get('support10',0)-ie.get('support10',0)
    famd=ce.get('family_support',0)-ie.get('family_support',0)
    wrd=ce.get('weighted_rr',0)-ie.get('weighted_rr',0)
    m=x.get('margin',0)
    return '|'.join([
        x['house'], band(ce.get('primary_rank')),
        'S10+' if s10d>0 else ('S10=' if s10d==0 else 'S10-'),
        'FAM+' if famd>0 else ('FAM=' if famd==0 else 'FAM-'),
        'WR+' if wrd>0 else ('WR=' if abs(wrd)<1e-12 else 'WR-'),
        'MHI' if m>=.10 else ('MMID' if m>=.06 else 'MLOW')])

# Miss-cause attribution across all route-level Top5 misses; candidate evidence refines boundary cases.
causes=[]; counts=Counter(); houses=Counter()
for e in cf:
    if e.get('selected_top5'): continue
    k=(e['date'],e['house']); x=by.get(k)
    if e.get('best_any_rank') is None or e.get('best_any_rank',101)>36:
        cause='GENERATION_FAILURE'
    elif e.get('best_eligible_rank') is not None and e['best_eligible_rank']<=5:
        cause='PRIMARY_ROUTE_BIAS'
    elif e.get('best_any_rank') is not None and e['best_any_rank']<=5:
        cause='QUALIFICATION_ERROR'
    elif x and x.get('baseline_rank',101)>5 and x.get('rescue_rank',101)<=5:
        ce=x.get('challenger_evidence') or {}; ie=x.get('incumbent_evidence') or {}
        if ce.get('support10',0)>ie.get('support10',0): cause='VOTE_COUNT_DISTORTION'
        elif ce.get('family_support',0)>ie.get('family_support',0): cause='REDUNDANCY_OVERBOOST'
        elif ce.get('weighted_rr',0)>ie.get('weighted_rr',0): cause='RELIABILITY_WEIGHT_ERROR'
        else: cause='PRIMARY_RANK_ANCHOR_BIAS'
    elif e.get('best_any_rank') is not None and e['best_any_rank']<=12:
        cause='RANKING_DEPTH_ERROR'
    else:
        cause='DEEP_RANKING_ERROR'
    rec=dict(e,cause=cause)
    if x:
        rec['candidate_signature']=sig(x)
        rec['candidate_margin']=x.get('margin')
        rec['incumbent_evidence']=x.get('incumbent_evidence')
        rec['challenger_evidence']=x.get('challenger_evidence')
    causes.append(rec); counts[(e['house'],cause)]+=1; houses[e['house']]+=1

# Prior-only causal-signature correction shadow replay.
hist=defaultdict(list); corr=[]; live=Counter(); rescued=Counter(); damaged=Counter()
for x in sorted(resc,key=lambda z:(z['date'],z['house'])):
    s=sig(x); prior=hist[s]
    def stat(xs):
        return {'n':len(xs),
          'net5':sum((q['rescue_rank']<=5)-(q['baseline_rank']<=5) for q in xs),
          'net10':sum((q['rescue_rank']<=10)-(q['baseline_rank']<=10) for q in xs),
          'mrr':(sum((1/q['rescue_rank'])-(1/q['baseline_rank']) for q in xs)/len(xs)) if xs else 0,
          'rescued':sum(q['baseline_rank']>5 and q['rescue_rank']<=5 for q in xs),
          'damaged':sum(q['baseline_rank']<=5 and q['rescue_rank']>5 for q in xs)}
    ex=stat(prior); recent=stat(prior[-10:])
    # A causal signature must have repeated rescue evidence, bounded damage and recent non-inferiority.
    active=(ex['n']>=12 and ex['rescued']>=2 and ex['net5']>=2 and ex['damaged']<=1 and ex['net10']>=0 and ex['mrr']>=0
            and recent['net5']>=0 and recent['net10']>=0 and recent['mrr']>=0)
    final_rank=x['rescue_rank'] if active else x['baseline_rank']
    if active:
        live[x['house']]+=1
        rescued[x['house']]+= int(x['baseline_rank']>5 and x['rescue_rank']<=5)
        damaged[x['house']]+= int(x['baseline_rank']<=5 and x['rescue_rank']>5)
    corr.append({'date':x['date'],'house':x['house'],'signature':s,'active':active,'prior':ex,'recent10':recent,
                 'baseline_rank':x['baseline_rank'],'corrected_rank':final_rank,'rescue_rank':x['rescue_rank'],
                 'challenger':x.get('challenger'),'incumbent':x.get('incumbent')})
    hist[s].append(x)

summary={}
for h in ('Deshawar','Faridabad','Ghaziabad','Gali'):
    hc=[z for z in causes if z['house']==h]
    c=Counter(z['cause'] for z in hc)
    summary[h]={'top5_misses':len(hc),'causes':dict(c),'causal_live_activations':live[h],
                'causal_live_rescues':rescued[h],'causal_live_damages':damaged[h]}

(R/'candidate_miss_cause_attribution_v3_3.json').write_text(json.dumps(causes,indent=2),encoding='utf-8')
(R/'causal_rank_correction_shadow_v3_3.json').write_text(json.dumps(corr,indent=2),encoding='utf-8')
(R/'miss_cause_summary_v3_3.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
md=['# DHAPPA v3.3 — Miss-Cause Learning at Candidate Level','',
'v3.3 decomposes every historical Top-5 miss into an auditable cause bucket and tests a prior-only causal-signature correction layer. The current target outcome is used only after the correction decision is frozen.','',
'## Miss-cause distribution','',
'| House | Top-5 misses | Primary-route bias | Qualification error | Vote distortion | Redundancy | Reliability-weight | Rank-anchor | Ranking-depth | Deep-ranking | Generation failure |',
'|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for h in summary:
    c=summary[h]['causes']
    md.append(f"| {h} | {summary[h]['top5_misses']} | {c.get('PRIMARY_ROUTE_BIAS',0)} | {c.get('QUALIFICATION_ERROR',0)} | {c.get('VOTE_COUNT_DISTORTION',0)} | {c.get('REDUNDANCY_OVERBOOST',0)} | {c.get('RELIABILITY_WEIGHT_ERROR',0)} | {c.get('PRIMARY_RANK_ANCHOR_BIAS',0)} | {c.get('RANKING_DEPTH_ERROR',0)} | {c.get('DEEP_RANKING_ERROR',0)} | {c.get('GENERATION_FAILURE',0)} |")
md += ['', '## Prospective causal-correction survival','']
for h,s in summary.items():
    md.append(f"- **{h}:** live activations={s['causal_live_activations']}, realized Top-5 rescues={s['causal_live_rescues']}, damaged Top-5 hits={s['causal_live_damages']}")
md += ['', '## Interpretation',
'- PRIMARY_ROUTE_BIAS means a route already admitted by prior-only qualification had the actual in Top-5, but another route was selected.',
'- QUALIFICATION_ERROR means an available route could place the actual in Top-5 but was outside the eligible set.',
'- Candidate-level buckets are assigned only where a frozen Rank-6–12 proposal existed; otherwise the miss remains a route/depth/generation error.',
'- The causal correction layer does not activate from a cause label observed on the same target. It needs repeated earlier examples of the same pre-target signature.',
'', '## Safety / integrity',
'- Cause attribution is post-reveal diagnostic and is never fed back into the same target.',
'- Correction signatures contain only pre-target candidate evidence.',
'- A signature needs at least 12 prior frozen proposals, at least 2 prior Top-5 rescues, positive net Top-5, bounded damage, and non-negative Top-10/MRR before live use.',
'- No threshold is relaxed merely to create a positive result.']
(R/'DHAPPA_MISS_CAUSE_LEARNING_V3_3_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps(summary,indent=2))
