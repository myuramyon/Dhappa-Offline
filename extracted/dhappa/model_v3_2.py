from __future__ import annotations
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path
import json, statistics, math
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from . import model_v2_5 as v25

HOUSES=v25.HOUSES


def _route_ranking(route, rankings, rel, indep):
    mem=route['members']
    return rankings[mem[0]] if len(mem)==1 else v25.fuse(rankings,mem,rel,indep)


def _family_diversity(members):
    fam={e.name:e.family for e in v25.ENGINES}
    if not members: return 0.0
    return len({fam.get(x,x) for x in members})/len(members)


def _feature(route, route_ranked, peer_rankings):
    w=route['window']; wm=w.get('metrics',{})
    vals=[]
    for key in ('15','30','60','expanding'):
        m=wm.get(key) or {}
        vals += [m.get('h5',0.0),m.get('h10',0.0),m.get('mrr',0.0)]
    peer_overlap=[]
    a=set(route_ranked[:10])
    for pr in peer_rankings:
        b=set(pr[:10]); peer_overlap.append(len(a&b)/max(1,len(a|b)))
    avg_overlap=sum(peer_overlap)/len(peer_overlap) if peer_overlap else 0.0
    top10_scores=[]
    for i,n in enumerate(route_ranked[:10]): top10_scores.append(1/(i+1))
    return [
        route.get('score',0.0), route.get('base_score',route.get('score',0.0)), route.get('context_mod',0.0),
        route.get('redundancy',0.0), route.get('incremental',0.0), route.get('n',0)/100.0,
        w.get('score',0.0), w.get('positive',0)/4.0, len(route['members'])/3.0, _family_diversity(route['members']),
        avg_overlap, 1-avg_overlap,
    ] + vals


def _discriminator_scores(house, routes, route_rankings, meta_x, meta_y):
    # Strict fallback until enough prior labeled route observations and enough positive cases exist.
    y=meta_y[house]
    if len(y)<120 or sum(y)<12 or (len(y)-sum(y))<30:
        return {r['name']:r['score'] for r in routes}, {'mode':'FALLBACK_V25_SCORE','samples':len(y),'positives':sum(y)}
    X=np.asarray(meta_x[house],dtype=float); Y=np.asarray(y,dtype=int)
    try:
        clf=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',C=0.35,max_iter=500,solver='liblinear'))
        clf.fit(X,Y)
        cur=[]
        for r in routes:
            peers=[route_rankings[x['name']] for x in routes if x['name']!=r['name']]
            cur.append(_feature(r,route_rankings[r['name']],peers))
        p=clf.predict_proba(np.asarray(cur,dtype=float))[:,1]
        # Tiny prior-score tie-breaker; classifier remains dominant.
        scores={r['name']:float(p[i] + 0.03*max(-1,min(1,r['score']))) for i,r in enumerate(routes)}
        return scores, {'mode':'ONLINE_LOGIT','samples':len(y),'positives':int(sum(y)),'positive_rate':round(float(np.mean(Y)),4)}
    except Exception as e:
        return {r['name']:r['score'] for r in routes}, {'mode':'FALLBACK_ERROR','samples':len(y),'error':str(e)[:120]}



def _qualification_band(route, is_combo=False):
    """Prior-only 3-way qualification band. NEAR is intentionally narrow."""
    wa=route.get('window') or {}; n=route.get('n',0)
    if wa.get('qualified'):
        return 'QUALIFIED'
    avail=wa.get('available',0) or 0; pos=wa.get('positive',0) or 0; score=wa.get('score',-9)
    agreement=(pos/max(1,avail)) if avail else 0.0
    if is_combo:
        near=(n>=20 and avail>=2 and agreement>=0.50 and score>=-0.018 and route.get('redundancy',1)<0.80 and route.get('incremental',-9)>=-0.006)
    else:
        near=(n>=15 and avail>=2 and agreement>=0.50 and score>=-0.018)
    return 'NEAR_QUALIFIED_CHALLENGER' if near else 'REJECTED'


def _boundary_rescue_proof(challenger_evs, reference_evs):
    """Prior-only proof that a near-qualified route deserves temporary admission."""
    proof=v25._paired_challenger_proof(challenger_evs, reference_evs)
    if proof.get('n',0)<20:
        return {**proof,'boundary_pass':False,'boundary_reason':'INSUFFICIENT_PAIRED_HISTORY'}
    windows=proof.get('windows',{})
    recent=[m for _,m in sorted(windows.items(), key=lambda x:int(x[0])) if m.get('n',0)>=15]
    recent_ok=any(m.get('net_top5',0)>=0 and m.get('mean_rank_delta',0)>0 and m.get('mrr_delta',0)>=0 for m in recent)
    damage_budget=max(1, int(proof['n']*0.025))
    ok=(proof.get('rescued_top5',0)>proof.get('damaged_top5',0)
        and proof.get('damaged_top5',0)<=damage_budget
        and proof.get('net_top10',0)>=0
        and proof.get('mrr_delta',0)>=0
        and proof.get('mean_rank_delta',0)>0
        and proof.get('win_rate',0)>=0.50
        and recent_ok)
    return {**proof,'boundary_pass':bool(ok),'damage_budget':damage_budget,'recent_persistence':recent_ok,
            'boundary_reason':'BOUNDARY_RESCUE_PASSED' if ok else 'BOUNDARY_RESCUE_NOT_PROVEN'}



def _post_admission_tournament(challenger, primary, profiles, combo_profiles, house, indep):
    """Prior-only head-to-head adjudication. Never uses current target outcome or route score margin.
    The boundary route has already passed admission; this tournament asks whether it has earned
    the right to override the canonical primary on paired historical evidence.
    """
    cev=v25._route_history(profiles,combo_profiles,house,challenger['name'])
    pev=v25._route_history(profiles,combo_profiles,house,primary['name'])
    proof=v25._paired_challenger_proof(cev,pev)
    n=proof.get('n',0)
    strength=v25._incumbent_strength(pev)
    # route-family independence is used only as a guard against duplicate evidence
    cm=set(challenger.get('members',())); pm=set(primary.get('members',()))
    disjoint=cm.isdisjoint(pm)
    overlap_pairs=[]
    for a in cm:
        for b in pm:
            if a!=b: overlap_pairs.append(indep.get(tuple(sorted((a,b))),0.0))
    avg_overlap=sum(overlap_pairs)/len(overlap_pairs) if overlap_pairs else (1.0 if not disjoint else 0.0)
    independent=(disjoint and avg_overlap<0.72)
    windows=proof.get('windows',{})
    recent=[m for k,m in sorted(windows.items(), key=lambda kv:int(kv[0])) if m.get('n',0)>=15]
    recent_pos=sum(1 for m in recent if m.get('net_top5',0)>=0 and m.get('net_top10',0)>=0 and m.get('mrr_delta',0)>=0 and m.get('mean_rank_delta',0)>0)
    damage_budget=max(1,int(n*0.02))
    base=(n>=20 and proof.get('net_top5',0)>0 and proof.get('damaged_top5',0)<=damage_budget
          and proof.get('net_top10',0)>=0 and proof.get('mrr_delta',0)>=0
          and proof.get('mean_rank_delta',0)>0 and proof.get('win_rate',0)>=0.50
          and recent_pos>=1 and independent)
    tier=strength.get('tier','WEAK')
    if tier=='STRONG':
        passed=base and n>=30 and proof.get('net_top5',0)>=2 and recent_pos>=2
    elif tier=='MODERATE':
        passed=base and proof.get('net_top5',0)>=1
    elif tier=='WEAK':
        passed=base
    else: # FAILING incumbent: still require positive rescue and no broad damage
        passed=(n>=15 and proof.get('net_top5',0)>0 and proof.get('net_top10',0)>=0
                and proof.get('mrr_delta',0)>=-0.001 and proof.get('mean_rank_delta',0)>0
                and proof.get('damaged_top5',0)<=damage_budget and independent)
    state='BOUNDARY_CHALLENGER_WINS_TOURNAMENT' if passed else 'CANONICAL_PRIMARY_RETAINED'
    if n<15 or not independent:
        state='NO_DECISION_RETAIN_PRIMARY'
        passed=False
    return {
        'state':state,'passed':bool(passed),'challenger':challenger['name'],'primary':primary['name'],
        'incumbent_tier':tier,'independent':independent,'avg_cross_route_overlap':round(avg_overlap,4),
        'damage_budget':damage_budget,'recent_positive_windows':recent_pos,'proof':proof
    }



def _candidate_level_fusion(routes, route_rankings, max_routes=5):
    """Fuse candidate evidence across prior-qualified routes without using target outcome.
    Route inclusion is evidence/rank based; duplicate member sets are suppressed.
    """
    if not routes:
        return [f"{i:02d}" for i in range(100)], []
    chosen=[]
    used_members=[]
    for r in sorted(routes,key=lambda x:x.get('score',-999),reverse=True):
        mem=set(r.get('members',()))
        # suppress near-duplicate routes; preserve genuinely different evidence sources
        duplicate=False
        for um in used_members:
            inter=len(mem & um); union=max(1,len(mem | um))
            if inter/union>=0.67:
                duplicate=True; break
        if duplicate and chosen:
            continue
        chosen.append(r); used_members.append(mem)
        if len(chosen)>=max_routes: break
    scores={f"{i:02d}":0.0 for i in range(100)}
    details=[]
    for r in chosen:
        ranked=route_rankings[r['name']]
        wa=r.get('window') or {}; avail=max(1,wa.get('available',0)); pos=wa.get('positive',0)
        agreement=pos/avail
        # All terms are prior-only evidence. Keep weight bounded to avoid one route dominating.
        reliability=max(0.20,min(1.0,0.35+0.45*agreement+0.20*min(1.0,r.get('n',0)/60)))
        redundancy=max(0.0,min(0.9,r.get('redundancy',0.0) or 0.0))
        weight=reliability*(1-0.45*redundancy)
        details.append({'route':r['name'],'weight':round(weight,6),'agreement':round(agreement,4),'redundancy':round(redundancy,4)})
        for idx,num in enumerate(ranked,1):
            # reciprocal-rank fusion; finite contribution throughout 00-99 universe
            scores[num]+=weight/idx
    fused=sorted(scores,key=lambda n:(scores[n],-int(n)),reverse=True)
    return fused,details

def _fusion_shadow_status(events):
    def calc(xs):
        if not xs: return {'net5':0,'net10':0,'mrr_delta':0.0,'damaged5':0,'rescued5':0}
        n=len(xs)
        return {
            'net5':sum((e['fusion_rank']<=5)-(e['baseline_rank']<=5) for e in xs),
            'net10':sum((e['fusion_rank']<=10)-(e['baseline_rank']<=10) for e in xs),
            'mrr_delta':sum((1/e['fusion_rank'])-(1/e['baseline_rank']) for e in xs)/n,
            'damaged5':sum((e['baseline_rank']<=5 and e['fusion_rank']>5) for e in xs),
            'rescued5':sum((e['baseline_rank']>5 and e['fusion_rank']<=5) for e in xs),
        }
    if len(events)<45:
        return {'active':False,'n':len(events),'stage':'SHADOW','reason':'INSUFFICIENT_SHADOW_HISTORY'}
    ex=calc(events); rc=calc(events[-30:]); r15=calc(events[-15:])
    initial=(ex['net5']>=2 and rc['net5']>=1 and ex['net10']>=0 and rc['net10']>=0
             and ex['mrr_delta']>0 and rc['mrr_delta']>0 and ex['rescued5']>ex['damaged5'])
    if not initial:
        return {'active':False,'n':len(events),'stage':'SHADOW','expanding':ex,'recent30':rc,'recent15':r15,'reason':'SHADOW_NOT_PROVEN'}
    # Two-stage guard: locate a past point where shadow first qualified, then demand >=12 later
    # outcomes (which were still shadow-only at that time) to confirm the advantage prospectively.
    probation_pass=False; probation=None; qualified_at=None
    for j in range(30, len(events)-11):
        pre=events[:j]; pex=calc(pre); pr30=calc(pre[-30:])
        q=(pex['net5']>=2 and pr30['net5']>=1 and pex['net10']>=0 and pr30['net10']>=0
           and pex['mrr_delta']>0 and pr30['mrr_delta']>0 and pex['rescued5']>pex['damaged5'])
        if not q: continue
        prob=calc(events[j:j+12])
        if prob['net5']>=1 and prob['net10']>=0 and prob['mrr_delta']>0 and prob['rescued5']>prob['damaged5']:
            probation_pass=True; probation=prob; qualified_at=j; break
    active=bool(initial and probation_pass and r15['net5']>=0 and r15['net10']>=0 and r15['mrr_delta']>=0)
    return {'active':active,'n':len(events),'stage':'LIVE_ELIGIBLE' if active else 'PROBATION',
            'expanding':ex,'recent30':rc,'recent15':r15,'qualified_at_index':qualified_at,'probation':probation,
            'reason':'PROBATION_SURVIVED' if active else 'PROBATION_NOT_PROVEN'}




def _candidate_evidence_attribution(primary_ranked, routes, route_rankings):
    """Prior-only evidence for the canonical Top-12. Outcome is not used.
    Scores reward agreement across distinct historically qualified routes while keeping
    the canonical primary rank as an anchor.
    """
    fam={e.name:e.family for e in v25.ENGINES}
    out={}
    route_weights={}
    for r in routes:
        wa=r.get('window') or {}; avail=max(1,wa.get('available',0)); pos=wa.get('positive',0)
        agreement=pos/avail
        reliability=max(0.15,min(1.0,0.30+0.45*agreement+0.25*min(1.0,r.get('n',0)/60)))
        redundancy=max(0.0,min(0.9,r.get('redundancy',0.0) or 0.0))
        route_weights[r['name']]=reliability*(1-0.40*redundancy)
    for pr,num in enumerate(primary_ranked[:12],1):
        support5=support10=0; rr_sum=0.0; weighted_rr=0.0; families=set(); supporters=[]
        for r in routes:
            ranked=route_rankings[r['name']]
            rp=ranked.index(num)+1
            w=route_weights.get(r['name'],0.2)
            if rp<=5: support5+=1
            if rp<=10: support10+=1
            rr_sum += 1/rp
            weighted_rr += w/rp
            if rp<=10:
                for m in r.get('members',()): families.add(fam.get(m,m))
                supporters.append(r['name'])
        # Primary rank remains meaningful but cannot dominate independent confirmation.
        base=1/pr
        score=(0.42*base + 0.22*weighted_rr + 0.10*rr_sum/max(1,len(routes))
               +0.11*min(1.0,support5/3) +0.10*min(1.0,support10/4)
               +0.05*min(1.0,len(families)/3))
        out[num]={'number':num,'primary_rank':pr,'score':score,'support5':support5,'support10':support10,
                  'family_support':len(families),'supporters':supporters,'weighted_rr':weighted_rr}
    return out

def _candidate_rescue_proposal(primary_ranked, routes, route_rankings):
    ev=_candidate_evidence_attribution(primary_ranked,routes,route_rankings)
    incs=[ev[n] for n in primary_ranked[:5]]
    chals=[ev[n] for n in primary_ranked[5:12]]
    if not incs or not chals: return None,ev
    weakest=min(incs,key=lambda x:(x['score'],x['support10'],x['family_support']))
    strongest=max(chals,key=lambda x:(x['score'],x['support5'],x['support10'],x['family_support']))
    margin=strongest['score']-weakest['score']
    # Narrow boundary: challenger needs multi-route corroboration and a real evidence margin.
    eligible=(strongest['support10']>=2 and strongest['family_support']>=1 and margin>=0.035)
    if not eligible: return None,ev
    swapped=list(primary_ranked)
    i=swapped.index(weakest['number']); j=swapped.index(strongest['number'])
    swapped[i],swapped[j]=swapped[j],swapped[i]
    return {'incumbent':weakest['number'],'challenger':strongest['number'],'margin':margin,
            'incumbent_evidence':weakest,'challenger_evidence':strongest,'ranking':swapped},ev

def _candidate_rescue_status(events):
    def calc(xs):
        if not xs: return {'n':0,'net5':0,'net10':0,'mrr_delta':0.0,'rescued5':0,'damaged5':0}
        return {'n':len(xs),
            'net5':sum((e['rescue_rank']<=5)-(e['baseline_rank']<=5) for e in xs),
            'net10':sum((e['rescue_rank']<=10)-(e['baseline_rank']<=10) for e in xs),
            'mrr_delta':sum((1/e['rescue_rank'])-(1/e['baseline_rank']) for e in xs)/len(xs),
            'rescued5':sum(e['baseline_rank']>5 and e['rescue_rank']<=5 for e in xs),
            'damaged5':sum(e['baseline_rank']<=5 and e['rescue_rank']>5 for e in xs)}
    if len(events)<40:
        return {'active':False,'stage':'SHADOW','reason':'INSUFFICIENT_HISTORY','n':len(events)}
    ex=calc(events); r30=calc(events[-30:]); r15=calc(events[-15:])
    shadow=(ex['net5']>=2 and r30['net5']>=1 and ex['net10']>=0 and r30['net10']>=0
            and ex['mrr_delta']>0 and r30['mrr_delta']>=0 and ex['rescued5']>ex['damaged5'])
    if not shadow:
        return {'active':False,'stage':'SHADOW','reason':'SHADOW_NOT_PROVEN','expanding':ex,'recent30':r30,'recent15':r15}
    # Historical two-stage probation: after the first prior point that qualified, require 10 later frozen proposals.
    probation=None; qidx=None
    for j in range(30,len(events)-9):
        pre=calc(events[:j]); pre30=calc(events[max(0,j-30):j])
        q=(pre['net5']>=2 and pre30['net5']>=1 and pre['net10']>=0 and pre30['net10']>=0
           and pre['mrr_delta']>0 and pre30['mrr_delta']>=0 and pre['rescued5']>pre['damaged5'])
        if not q: continue
        pr=calc(events[j:j+10])
        if pr['net5']>=1 and pr['net10']>=0 and pr['mrr_delta']>=0 and pr['rescued5']>pr['damaged5']:
            probation=pr; qidx=j; break
    active=bool(probation is not None and r15['net5']>=0 and r15['net10']>=0 and r15['mrr_delta']>=0)
    return {'active':active,'stage':'LIVE_ELIGIBLE' if active else 'PROBATION',
            'reason':'PROBATION_SURVIVED' if active else 'PROBATION_NOT_PROVEN',
            'expanding':ex,'recent30':r30,'recent15':r15,'qualified_at_index':qidx,'probation':probation}


def _rescue_context_keys(house, ctx, primary_name, proposal, incumbent_tier):
    """Hierarchical pre-target context keys. No outcome-derived fields are allowed here."""
    if not proposal:
        return []
    ce=proposal['challenger_evidence']; ie=proposal['incumbent_evidence']
    cr=ce.get('primary_rank',99); ir=ie.get('primary_rank',99)
    s10=ce.get('support10',0); s5=ce.get('support5',0); fam=ce.get('family_support',0)
    margin=proposal.get('margin',0.0)
    parts={x.split('DOW')[-1] if x.startswith('DOW') else x for x in ctx.split('|')}
    ctx_parts=ctx.split('|'); dow=ctx_parts[0] if ctx_parts else 'DOWX'; gap=ctx_parts[-1] if ctx_parts else 'GX'
    crb='R6_7' if cr<=7 else ('R8_9' if cr<=9 else 'R10_12')
    irb=f'I{ir}'
    sb='S10_4P' if s10>=4 else ('S10_2_3' if s10>=2 else 'S10_LT2')
    fmb='FAM2P' if fam>=2 else 'FAM1'
    mb='MHI' if margin>=0.10 else ('MMID' if margin>=0.06 else 'MLOW')
    tier=incumbent_tier or 'UNKNOWN'
    # Multiple hierarchical lenses reduce sparsity. All are knowable before reveal.
    return [
        f'{house}|{dow}|{crb}|{tier}',
        f'{house}|{gap}|{crb}|{sb}',
        f'{house}|{primary_name}|{crb}|{tier}',
        f'{house}|{crb}|{irb}|{sb}|{fmb}',
        f'{house}|{crb}|{sb}|{fmb}|{mb}',
    ]

def _contextual_rescue_status(context_history, keys):
    """Prior-only contextual survival. Requires both expanding and recent evidence.
    A context cannot activate from the current target because current outcome is appended later.
    """
    candidates=[]
    for key in keys:
        evs=context_history.get(key,[])
        if len(evs)<12:
            continue
        def calc(xs):
            if not xs: return {'n':0,'net5':0,'net10':0,'mrr_delta':0.0,'rescued5':0,'damaged5':0}
            return {'n':len(xs),
                'net5':sum((e['rescue_rank']<=5)-(e['baseline_rank']<=5) for e in xs),
                'net10':sum((e['rescue_rank']<=10)-(e['baseline_rank']<=10) for e in xs),
                'mrr_delta':sum((1/e['rescue_rank'])-(1/e['baseline_rank']) for e in xs)/len(xs),
                'rescued5':sum(e['baseline_rank']>5 and e['rescue_rank']<=5 for e in xs),
                'damaged5':sum(e['baseline_rank']<=5 and e['rescue_rank']>5 for e in xs)}
        ex=calc(evs); recent=calc(evs[-min(10,len(evs)):])
        # Require actual rescue history, not merely rank-neutral behavior.
        passed=(ex['rescued5']>=2 and ex['net5']>=2 and ex['damaged5']<=1 and ex['net10']>=0 and ex['mrr_delta']>=0
                and recent['net5']>=0 and recent['net10']>=0 and recent['mrr_delta']>=0)
        score=(2.0*ex['net5'] + 0.5*ex['net10'] + 8.0*ex['mrr_delta'] - 2.0*ex['damaged5'])/max(1,ex['n'])
        candidates.append({'key':key,'passed':bool(passed),'score':score,'expanding':ex,'recent':recent})
    passed=[x for x in candidates if x['passed']]
    if not passed:
        return {'active':False,'reason':'NO_CONTEXT_SURVIVED','tested':candidates}
    best=max(passed,key=lambda x:(x['score'],x['expanding']['net5'],x['expanding']['rescued5']))
    return {'active':True,'reason':'CONTEXT_SURVIVED','selected_context':best,'tested':candidates}

def run_walkforward(rows,min_train=45,max_combo=3,min_tenure=7,challenger_margin=0.010):
    evals=[]; combo_evals=[]; timeline=[]
    profiles=defaultdict(lambda:defaultdict(list)); combo_profiles=defaultdict(lambda:defaultdict(list))
    context_profiles=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    prev_primary={h:None for h in HOUSES}; tenure=Counter(); switches=Counter(); no_primary=Counter()
    election_debug=[]; calibration_events=defaultdict(list); policy_history=[]
    current_policy={h:'BALANCED' for h in HOUSES}; recent_surviving_policy={h:'BALANCED' for h in HOUSES}
    meta_x=defaultdict(list); meta_y=defaultdict(list); discriminator_log=[]; shadow_events=defaultdict(list); boundary_log=[]; boundary_counts=Counter(); boundary_shadow=defaultdict(list); tournament_log=[]; tournament_counts=Counter(); fusion_shadow=defaultdict(list); fusion_log=[]; candidate_rescue_shadow=defaultdict(list); candidate_rescue_log=[]; contextual_rescue_shadow=defaultdict(lambda:defaultdict(list)); contextual_rescue_log=[]

    for i in range(min_train,len(rows)):
        target=rows[i]; history=rows[:i]; cutoff=history[-1]['date']
        for house in HOUSES:
            actual=target.get(house)
            if not actual: continue
            ctx=v25._context_key(history,house,target['date'])
            house_policy, policy_meta=v25._select_house_policy(calibration_events[house],current_policy[house],recent_surviving_policy[house])
            prior_policy=current_policy[house]
            if house_policy!=prior_policy: recent_surviving_policy[house]=house_policy
            current_policy[house]=house_policy
            outputs={e.name:e.rank(history,house,target['date']) for e in v25.ENGINES}
            rankings={k:v.ranking for k,v in outputs.items()}
            single_hashes={name:v25.hash_prediction(target['date'],cutoff,house,name,ranked) for name,ranked in rankings.items()}
            rel={name:max(.001,v25.score_metric(v25.metric(profiles[house][name]))) for name in rankings}
            names=list(rankings); qualified_names=sorted(names,key=lambda n:rel[n],reverse=True)[:6]
            indep={tuple(sorted((a,b))):v25.jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}
            routes=[]; near_routes=[]; rejected_count=0
            for name in names:
                past=profiles[house][name]; m=v25.metric(past); sc=v25.score_metric(m)
                if sc<=-900: continue
                cs=v25._context_score(context_profiles,house,name,ctx); cmod,cn=(cs if cs else (0.0,0))
                rr=v25._route_record((name,),past,sc,context_mod=cmod,context_n=cn); rr['qualification_band']=_qualification_band(rr,False)
                if rr['qualification_band']=='QUALIFIED': routes.append(rr)
                elif rr['qualification_band']=='NEAR_QUALIFIED_CHALLENGER': near_routes.append(rr)
                else: rejected_count+=1
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem); past=combo_profiles[house][key]
                    if len(past)<20: continue
                    pm=v25.metric(past); pscore=v25.score_metric(pm)
                    if pscore<=-900: continue
                    strongest=max((v25.score_metric(v25.metric(profiles[house][x])) for x in mem),default=-999)
                    incremental=pscore-strongest
                    pairs=list(combinations(mem,2)); red=sum(indep[tuple(sorted(x))] for x in pairs)/max(1,len(pairs))
                    cs=v25._context_score(context_profiles,house,key,ctx); cmod,cn=(cs if cs else (0.0,0))
                    rr=v25._route_record(mem,past,pscore,red,incremental,cmod,cn); rr['qualification_band']=_qualification_band(rr,True)
                    if incremental>0.003 and red<0.72 and rr['window']['qualified']:
                        rr['qualification_band']='QUALIFIED'; routes.append(rr)
                    elif rr['qualification_band']=='NEAR_QUALIFIED_CHALLENGER': near_routes.append(rr)
                    else: rejected_count+=1

            routes.sort(key=lambda x:x['score'],reverse=True)
            # Boundary rescue is decided ONLY from prior completed route histories/shadow contests.
            baseline_pre=routes[0] if routes else None
            rescued=[]; shadow_candidate=max(near_routes,key=lambda x:x['score']) if near_routes else None
            bsev=boundary_shadow[house]
            if len(bsev)>=30:
                recent_b=bsev[-30:]
                bnet5=sum((e['near_rank']<=5)-(e['baseline_rank']<=5) for e in bsev)
                bnet10=sum((e['near_rank']<=10)-(e['baseline_rank']<=10) for e in bsev)
                bmrr=sum((1/e['near_rank'])-(1/e['baseline_rank']) for e in bsev)/len(bsev)
                brnet5=sum((e['near_rank']<=5)-(e['baseline_rank']<=5) for e in recent_b)
                brnet10=sum((e['near_rank']<=10)-(e['baseline_rank']<=10) for e in recent_b)
                brmrr=sum((1/e['near_rank'])-(1/e['baseline_rank']) for e in recent_b)/len(recent_b)
                shadow_ok=(bnet5>=2 and brnet5>=1 and bnet10>=0 and brnet10>=0 and bmrr>=0 and brmrr>=0)
            else:
                bnet5=bnet10=brnet5=brnet10=0; bmrr=brmrr=0.0; shadow_ok=False
            for nr in sorted(near_routes,key=lambda x:x['score'],reverse=True):
                ref=baseline_pre
                if ref is None:
                    continue
                pr=_boundary_rescue_proof(v25._route_history(profiles,combo_profiles,house,nr['name']),
                                          v25._route_history(profiles,combo_profiles,house,ref['name']))
                is_shadow_pick=(shadow_candidate is not None and nr['name']==shadow_candidate['name'])
                admitted=bool(pr.get('boundary_pass') or (is_shadow_pick and shadow_ok))
                boundary_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'route':nr['name'],
                                     'band':'NEAR_QUALIFIED_CHALLENGER','reference':ref['name'],'proof':pr,
                                     'shadow_pick':is_shadow_pick,'shadow_survival':{'n':len(bsev),'net5':bnet5,'net10':bnet10,'mrr_delta':round(bmrr,6),'recent30_net5':brnet5,'recent30_net10':brnet10,'recent30_mrr_delta':round(brmrr,6),'passed':shadow_ok},
                                     'admitted':admitted})
                boundary_counts[(house,'near_tested')]+=1
                if admitted:
                    nr['boundary_rescued']=True; nr['boundary_proof']=pr; nr['boundary_shadow_survived']=bool(is_shadow_pick and shadow_ok)
                    nr['score'] += min(0.010, 0.002 + 0.001*max(0,pr.get('net_top5',0)))
                    rescued.append(nr); boundary_counts[(house,'rescued')]+=1
                else:
                    boundary_counts[(house,'near_rejected')]+=1
            routes.extend(rescued); routes.sort(key=lambda x:x['score'],reverse=True)
            route_rankings={r['name']:_route_ranking(r,rankings,rel,indep) for r in routes}
            disc_scores,disc_meta=_discriminator_scores(house,routes,route_rankings,meta_x,meta_y) if routes else ({}, {'mode':'NO_ROUTES','samples':len(meta_y[house])})
            meta_ranked=sorted(routes,key=lambda r:(disc_scores.get(r['name'],-999),r['score']),reverse=True)
            baseline_candidate=routes[0] if routes else None
            meta_candidate=meta_ranked[0] if meta_ranked else None
            sev=shadow_events[house]
            if len(sev)>=30:
                recent=sev[-30:]
                net5=sum((e['meta_rank']<=5)-(e['baseline_rank']<=5) for e in sev)
                net10=sum((e['meta_rank']<=10)-(e['baseline_rank']<=10) for e in sev)
                mrr_delta=sum((1/e['meta_rank'])-(1/e['baseline_rank']) for e in sev)/len(sev)
                rnet5=sum((e['meta_rank']<=5)-(e['baseline_rank']<=5) for e in recent)
                rnet10=sum((e['meta_rank']<=10)-(e['baseline_rank']<=10) for e in recent)
                rmrr=sum((1/e['meta_rank'])-(1/e['baseline_rank']) for e in recent)/len(recent)
                activate=(net5>=2 and rnet5>=1 and net10>=0 and rnet10>=0 and mrr_delta>0 and rmrr>0)
            else:
                net5=net10=rnet5=rnet10=0; mrr_delta=rmrr=0.0; activate=False
            if disc_meta.get('mode')!='ONLINE_LOGIT': activate=False
            candidate=meta_candidate if activate else baseline_candidate
            ranked_routes=meta_ranked if activate else routes
            disc_meta=dict(disc_meta,shadow_active=activate,shadow_n=len(sev),shadow_net5=net5,shadow_net10=net10,shadow_mrr_delta=round(mrr_delta,6),recent30_net5=rnet5,recent30_net10=rnet10,recent30_mrr_delta=round(rmrr,6))
            incumbent_name=prev_primary[house]
            incumbent=next((r for r in routes if r['name']==incumbent_name),None) if incumbent_name else None
            decision_reason='NO_ROUTE_PASSED_QUALIFICATION'; selected=None; paired_proof=None
            if candidate and incumbent and candidate['name']!=incumbent_name:
                paired_proof=v25._paired_challenger_proof(v25._route_history(profiles,combo_profiles,house,candidate['name']),v25._route_history(profiles,combo_profiles,house,incumbent_name))
            incumbent_strength=None
            if candidate is None:
                selected=None; no_primary[house]+=1; tenure[house]=0
            elif incumbent_name is None:
                selected=candidate; decision_reason='INITIAL_QUALIFIED_CHAMPION'
            elif incumbent is None:
                if tenure[house]>=2: selected=candidate; decision_reason='INCUMBENT_FAILED_SURVIVAL_FAST_REPLACEMENT'
                else:
                    selected=None; decision_reason='INCUMBENT_FAILED_SURVIVAL_ABSTAIN'; no_primary[house]+=1
            elif candidate['name']==incumbent_name:
                incumbent_strength=v25._incumbent_strength(v25._route_history(profiles,combo_profiles,house,incumbent_name)); selected=incumbent; decision_reason='CHAMPION_RETAINED'
            else:
                incumbent_strength=v25._incumbent_strength(v25._route_history(profiles,combo_profiles,house,incumbent_name)); tier=incumbent_strength['tier']
                # Use prospective discriminator margin as candidate gap while retaining v2.5 paired-proof/policy gate.
                c2=dict(candidate); i2=dict(incumbent)
                if activate:
                    c2['score']=disc_scores.get(candidate['name'],candidate['score']); i2['score']=disc_scores.get(incumbent['name'],incumbent['score'])
                allow,reason=v25._policy_switch_gate(house_policy,tier,c2,i2,paired_proof,tenure[house])
                if allow: selected=candidate; decision_reason='DISCRIMINATOR_'+reason
                elif tier=='FAILING':
                    selected=None; decision_reason=reason; no_primary[house]+=1; prev_primary[house]=None; tenure[house]=0
                else: selected=incumbent; decision_reason=reason

            # v2.9: admitted boundary routes receive a dedicated head-to-head tournament.
            # This happens before current-target outcome reveal and does NOT require beating the old route score.
            canonical_selected=selected
            tournament_decision=None
            if canonical_selected is not None and rescued:
                contenders=[r for r in rescued if r['name']!=canonical_selected['name']]
                adjudicated=[]
                for br in contenders:
                    td=_post_admission_tournament(br,canonical_selected,profiles,combo_profiles,house,indep)
                    adjudicated.append((br,td))
                    tournament_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,**td})
                    tournament_counts[(house,td['state'])]+=1
                winners=[x for x in adjudicated if x[1]['passed']]
                if winners:
                    # Choose using prior-only paired evidence, not the canonical route score.
                    winners.sort(key=lambda x:(x[1]['proof'].get('net_top5',0),x[1]['proof'].get('mrr_delta',0),x[1]['proof'].get('mean_rank_delta',0)),reverse=True)
                    selected=winners[0][0]
                    tournament_decision=winners[0][1]
                    decision_reason='BOUNDARY_CHALLENGER_WINS_TOURNAMENT'
                elif adjudicated:
                    tournament_decision=adjudicated[0][1]

            fusion_ranked=None; fusion_details=[]; fusion_status=_fusion_shadow_status(fusion_shadow[house])
            if selected is None:
                primary_name='NO_QUALIFIED_PRIMARY'; primary_rank=None; canonical_primary_rank=None; primary_hash=None; secondary=None; rescue_proposal=None; candidate_attribution={}; rescue_status={'active':False,'stage':'NO_PRIMARY'}; contextual_status={'active':False,'reason':'NO_PRIMARY'}; rescue_context_keys=[]; rescue_active=False
                if incumbent_name and decision_reason.startswith('INCUMBENT_FAILED'): prev_primary[house]=None
            else:
                primary_name=selected['name']; primary_ranked=route_rankings[primary_name]
                canonical_primary_rank=primary_ranked.index(actual)+1
                fusion_ranked,fusion_details=_candidate_level_fusion(routes,route_rankings,max_routes=5)
                # Activation decision is prior-only; actual below is used only to score the already-frozen ranking.
                canonical_stage_ranked=fusion_ranked if fusion_status['active'] else primary_ranked
                rescue_proposal,candidate_attribution=_candidate_rescue_proposal(canonical_stage_ranked,routes,route_rankings)
                rescue_status=_candidate_rescue_status(candidate_rescue_shadow[house])
                incumbent_tier_for_rescue=(incumbent_strength or {}).get('tier') if incumbent_strength else 'UNKNOWN'
                rescue_context_keys=_rescue_context_keys(house,ctx,primary_name,rescue_proposal,incumbent_tier_for_rescue)
                contextual_status=_contextual_rescue_status(contextual_rescue_shadow[house],rescue_context_keys) if rescue_proposal else {'active':False,'reason':'NO_PROPOSAL'}
                # v3.2 requires both broad survival and a repeatable pre-target context.
                rescue_active=bool(rescue_proposal is not None and rescue_status.get('active') and contextual_status.get('active'))
                final_ranked=rescue_proposal['ranking'] if rescue_active else canonical_stage_ranked
                primary_rank=final_ranked.index(actual)+1
                hash_label=('TOP5_RESCUE:' if rescue_active else ('FUSION:' if fusion_status['active'] else 'PRIMARY:'))+primary_name
                primary_hash=v25.hash_prediction(target['date'],cutoff,house,hash_label,final_ranked)
                secondary=next((r for r in ranked_routes if r['name']!=primary_name and set(r['members']).isdisjoint(set(selected['members']))),None)
                if prev_primary[house] and prev_primary[house]!=primary_name: switches[house]+=1; tenure[house]=1
                elif prev_primary[house]==primary_name: tenure[house]+=1
                else: tenure[house]=1
                prev_primary[house]=primary_name

            election_debug.append({'date':target['date'],'house':house,'context':ctx,'decision':decision_reason,'selected':primary_name,
                'candidate':candidate['name'] if candidate else None,'incumbent':incumbent_name,'routes_considered':len(routes),
                'discriminator':disc_meta,'candidate_discriminator_score':disc_scores.get(candidate['name']) if candidate else None,
                'house_policy':house_policy,'paired_proof':paired_proof,'incumbent_strength':incumbent_strength,
                'qualification_boundary':{'qualified':sum(1 for r in routes if not r.get('boundary_rescued')),'near_tested':len(near_routes),'rescued':len(rescued),'rejected':rejected_count},'post_admission_tournament':tournament_decision})
            discriminator_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'mode':disc_meta.get('mode'),'samples':disc_meta.get('samples',0),
                'candidate':candidate['name'] if candidate else None,'selected':primary_name,'candidate_score':disc_scores.get(candidate['name']) if candidate else None})

            pending_calibration=None
            if candidate and incumbent and candidate['name']!=incumbent_name and incumbent_strength:
                cand_ranked=route_rankings[candidate['name']]; inc_ranked=route_rankings[incumbent['name']]
                effective_gap=(disc_scores.get(candidate['name'],candidate['score'])-disc_scores.get(incumbent['name'],incumbent['score'])) if activate else (candidate['score']-incumbent['score'])
                pending_calibration={'date':target['date'],'tier':incumbent_strength['tier'],'gap':effective_gap,
                    'tenure':tenure[house] if selected is None else max(1,tenure[house]),'proof':paired_proof,'candidate':candidate['name'],'incumbent':incumbent_name,
                    'candidate_rank':cand_ranked.index(actual)+1,'incumbent_rank':inc_ranked.index(actual)+1,'policy_used':house_policy}

            combo_current=[]
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem); ranked=v25.fuse(rankings,mem,rel,indep)
                    combo_current.append((key,mem,ranked,v25.hash_prediction(target['date'],cutoff,house,key,ranked)))

            # Candidate-fusion shadow is frozen before reveal; append its evaluation only after reveal.
            if selected is not None and fusion_ranked is not None:
                fusion_shadow[house].append({'date':target['date'],'fusion_rank':fusion_ranked.index(actual)+1,
                    'baseline_rank':canonical_primary_rank,'primary':primary_name})
                fusion_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':primary_name,
                    'active':fusion_status['active'],'shadow_status':fusion_status,'route_weights':fusion_details,
                    'canonical_rank':canonical_primary_rank,'fusion_rank':fusion_ranked.index(actual)+1,'final_rank':primary_rank})
            # Top-5 rescue proposal was frozen before reveal. Score it only now for FUTURE activation.
            if selected is not None and rescue_proposal is not None:
                base_rank=canonical_stage_ranked.index(actual)+1; rr=rescue_proposal['ranking'].index(actual)+1
                candidate_rescue_shadow[house].append({'date':target['date'],'baseline_rank':base_rank,'rescue_rank':rr,
                    'incumbent':rescue_proposal['incumbent'],'challenger':rescue_proposal['challenger'],'margin':rescue_proposal['margin']})
                ctx_event={'date':target['date'],'baseline_rank':base_rank,'rescue_rank':rr,
                    'incumbent':rescue_proposal['incumbent'],'challenger':rescue_proposal['challenger']}
                for ck in rescue_context_keys:
                    contextual_rescue_shadow[house][ck].append(ctx_event)
                candidate_rescue_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':primary_name,
                    'active':rescue_active,'status':rescue_status,'contextual_status':contextual_status,'context_keys':rescue_context_keys,
                    'incumbent':rescue_proposal['incumbent'],
                    'challenger':rescue_proposal['challenger'],'margin':round(rescue_proposal['margin'],6),
                    'baseline_rank':base_rank,'rescue_rank':rr,'final_rank':primary_rank,
                    'incumbent_evidence':rescue_proposal['incumbent_evidence'],'challenger_evidence':rescue_proposal['challenger_evidence']})
                contextual_rescue_log.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':primary_name,
                    'active':rescue_active,'contextual_status':contextual_status,'context_keys':rescue_context_keys,
                    'baseline_rank':base_rank,'rescue_rank':rr,'challenger':rescue_proposal['challenger'],'incumbent':rescue_proposal['incumbent']})

            # Outcome reveal. First score the pre-frozen discriminator proposal versus the v2.5 baseline for FUTURE activation only.
            if meta_candidate is not None and baseline_candidate is not None:
                shadow_events[house].append({'date':target['date'],'meta':meta_candidate['name'],'baseline':baseline_candidate['name'],
                    'meta_rank':route_rankings[meta_candidate['name']].index(actual)+1,
                    'baseline_rank':route_rankings[baseline_candidate['name']].index(actual)+1})
            # Boundary shadow contest is also frozen pre-reveal and appended only after outcome reveal.
            if shadow_candidate is not None and baseline_pre is not None:
                nranked=_route_ranking(shadow_candidate,rankings,rel,indep)
                branked=_route_ranking(baseline_pre,rankings,rel,indep)
                boundary_shadow[house].append({'date':target['date'],'near':shadow_candidate['name'],'baseline':baseline_pre['name'],
                                               'near_rank':nranked.index(actual)+1,'baseline_rank':branked.index(actual)+1})

            # Append discriminator training samples from the PRE-REVEAL qualified route snapshot.
            for r in routes:
                rr=route_rankings[r['name']]; peers=[route_rankings[x['name']] for x in routes if x['name']!=r['name']]
                meta_x[house].append(_feature(r,rr,peers)); meta_y[house].append(1 if rr.index(actual)+1<=5 else 0)

            for name,ranked in rankings.items():
                rank=ranked.index(actual)+1
                ev=v25.Eval(target['date'],cutoff,house,name,actual,rank,rank<=5,rank<=10,rank<=21,rank<=36,1/rank,single_hashes[name])
                evals.append(ev); profiles[house][name].append(ev); context_profiles[house][name][ctx].append(ev)
            for key,mem,ranked,fh in combo_current:
                rank=ranked.index(actual)+1
                ev=v25.Eval(target['date'],cutoff,house,key,actual,rank,rank<=5,rank<=10,rank<=21,rank<=36,1/rank,fh)
                combo_evals.append(ev); combo_profiles[house][key].append(ev); context_profiles[house][key][ctx].append(ev)
            if pending_calibration:
                calibration_events[house].append(pending_calibration)
                policy_history.append({'date':target['date'],'house':house,'policy':house_policy,'prior_policy':prior_policy,'meta':policy_meta,'event_count_after':len(calibration_events[house])})

            confidence='INSUFFICIENT_EVIDENCE'
            if selected:
                wn=selected['window']['available']; n=selected['n']; pos=selected['window']['positive']
                if n>=60 and wn>=4 and pos>=3: confidence='STRONG_EVIDENCE'
                elif n>=30 and wn>=3 and pos>=2: confidence='MODERATE_EVIDENCE'
                elif n>=15: confidence='WEAK_EVIDENCE'
            timeline.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'context':ctx,'primary':primary_name,
                'secondary':secondary['name'] if secondary else None,'actual':actual,'actual_rank':primary_rank,'hit5':bool(primary_rank and primary_rank<=5),
                'hit10':bool(primary_rank and primary_rank<=10),'hit21':bool(primary_rank and primary_rank<=21),'hit36':bool(primary_rank and primary_rank<=36),
                'confidence':confidence,'decision_reason':decision_reason,'tenure':tenure[house] if selected else 0,'freeze_hash':primary_hash,
                'incumbent_strength':incumbent_strength['tier'] if incumbent_strength else None,'house_policy':house_policy,'discriminator_mode':disc_meta.get('mode'),
                'canonical_primary_rank':canonical_primary_rank if selected else None,'fusion_active':fusion_status['active'] if selected else False,
                'candidate_rescue_active':rescue_active if selected else False,'candidate_rescue_challenger':rescue_proposal['challenger'] if rescue_proposal else None,
                'contextual_rescue_active':rescue_active if selected else False,'contextual_rescue_reason':contextual_status.get('reason') if selected else 'NO_PRIMARY'})
    return evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history,discriminator_log,shadow_events,boundary_log,boundary_counts,boundary_shadow,tournament_log,tournament_counts,fusion_shadow,fusion_log,candidate_rescue_shadow,candidate_rescue_log,contextual_rescue_shadow,contextual_rescue_log


def report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles):
    rep=v25.report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    rep['model']='DHAPPA v3.2 — Contextual Rescue Attribution Lab'
    rep['strict_temporal_rule']='rank-6–12 rescue context is selected only from prior completed frozen proposals; current target outcome is appended to context history only after election freeze'
    rep['election_features']=rep.get('election_features',[])+['prospective_route_discriminator','online_prior_only_logistic_reranker','15_30_60_route_trajectory','route_peer_disagreement','family_diversity','fallback_to_v2_5_when_meta_sample_insufficient','qualification_boundary_bands','near_qualified_challenger','prior_only_boundary_rescue_proof','damage_bounded_boundary_admission']
    return rep


def save_all(root,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history,discriminator_log,shadow_events,boundary_log,boundary_counts,boundary_shadow,tournament_log,tournament_counts,fusion_shadow,fusion_log,candidate_rescue_shadow,candidate_rescue_log,contextual_rescue_shadow,contextual_rescue_log):
    root=Path(root); out=root/'reports'; out.mkdir(parents=True,exist_ok=True)
    rep=report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    (out/'dynamic_primary_engine_backtest_v3_2.json').write_text(json.dumps(rep,indent=2),encoding='utf-8')
    (out/'candidate_level_fusion_v3_0.json').write_text(json.dumps(fusion_log,indent=2),encoding='utf-8')
    (out/'candidate_level_fusion_shadow_v3_0.json').write_text(json.dumps({h:v for h,v in fusion_shadow.items()},indent=2),encoding='utf-8')
    (out/'candidate_rank6_12_rescue_v3_2.json').write_text(json.dumps(candidate_rescue_log,indent=2),encoding='utf-8')
    (out/'candidate_rank6_12_rescue_shadow_v3_2.json').write_text(json.dumps({h:v for h,v in candidate_rescue_shadow.items()},indent=2),encoding='utf-8')
    (out/'contextual_rescue_attribution_v3_2.json').write_text(json.dumps(contextual_rescue_log,indent=2),encoding='utf-8')
    (out/'contextual_rescue_shadow_v3_2.json').write_text(json.dumps({h:{k:v for k,v in d.items()} for h,d in contextual_rescue_shadow.items()},indent=2),encoding='utf-8')
    (out/'dynamic_election_decisions_v2_9.json').write_text(json.dumps(election_debug,indent=2),encoding='utf-8')
    (out/'prospective_route_discriminator_v2_9.json').write_text(json.dumps(discriminator_log,indent=2),encoding='utf-8')
    (out/'prospective_route_discriminator_shadow_v2_9.json').write_text(json.dumps({h:v for h,v in shadow_events.items()},indent=2),encoding='utf-8')
    (out/'qualification_boundary_rescue_v2_9.json').write_text(json.dumps(boundary_log,indent=2),encoding='utf-8')
    (out/'qualification_boundary_summary_v2_9.json').write_text(json.dumps({h:{k:boundary_counts[(h,k)] for k in ('near_tested','rescued','near_rejected')} for h in HOUSES},indent=2),encoding='utf-8')
    (out/'qualification_boundary_shadow_v2_9.json').write_text(json.dumps({h:v for h,v in boundary_shadow.items()},indent=2),encoding='utf-8')
    (out/'post_admission_challenger_tournament_v2_9.json').write_text(json.dumps(tournament_log,indent=2),encoding='utf-8')
    (out/'post_admission_tournament_summary_v2_9.json').write_text(json.dumps({h:{state:tournament_counts[(h,state)] for state in ('BOUNDARY_CHALLENGER_WINS_TOURNAMENT','CANONICAL_PRIMARY_RETAINED','NO_DECISION_RETAIN_PRIMARY')} for h in HOUSES},indent=2),encoding='utf-8')
    modes={h:Counter(x['mode'] for x in discriminator_log if x['house']==h) for h in HOUSES}
    md=['# DHAPPA v2.9 — Post-Admission Challenger Tournament','',
        'v2.9 preserves v2.8 qualification rescue and adds a dedicated prior-only head-to-head tournament between an admitted boundary challenger and the canonical Primary. The challenger does not need to beat the old route-score hierarchy; it must prove paired rescue value with bounded damage.','',
        '## House metrics','',
        '| House | Elected | Coverage | Top5 elected | Top10 elected | Top21 elected | Top36 elected | MRR | Switches | Current primary |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for h,m in rep['house_metrics'].items():
        md.append(f"| {h} | {m['elected_targets']} | {m['election_coverage_pct']}% | {m['primary_top5_pct_elected']}% | {m['primary_top10_pct_elected']}% | {m['primary_top21_pct_elected']}% | {m['primary_top36_pct_elected']}% | {m['mrr_elected']} | {m['switches']} | {m['current_primary']} |")
    md += ['', '## Discriminator activation']
    for h in HOUSES: md.append(f"- **{h}:** {dict(modes[h])}")
    md += ['', '## Boundary rescue activity']
    for h in HOUSES: md.append(f"- **{h}:** tested={boundary_counts[(h,'near_tested')]}, rescued={boundary_counts[(h,'rescued')]}, rejected={boundary_counts[(h,'near_rejected')]}")
    md += ['', '## Post-admission tournament activity']
    for h in HOUSES: md.append(f"- **{h}:** wins={tournament_counts[(h,'BOUNDARY_CHALLENGER_WINS_TOURNAMENT')]}, retained={tournament_counts[(h,'CANONICAL_PRIMARY_RETAINED')]}, no_decision={tournament_counts[(h,'NO_DECISION_RETAIN_PRIMARY')]}")
    md += ['', '## Leakage guard','- Route features exist before outcome reveal.','- Training labels for a target are appended only after that target election is frozen.','- Oracle-best route from v2.6 is never supplied as an input feature.','- If prior meta evidence is insufficient, v2.5 scoring is used.']
    
    fcounts={h:sum(1 for x in fusion_log if x['house']==h and x['active']) for h in HOUSES}
    md[0]='# DHAPPA v3.2 — Contextual Rescue Attribution Lab'
    md += ['', '## Candidate-level fusion activation']
    for h in HOUSES: md.append(f"- **{h}:** live fusion targets={fcounts[h]}, shadow samples={len(fusion_shadow[h])}")
    md += ['', 'Fusion is activated only from prior completed shadow evidence; current-target outcome cannot activate its own fusion ranking.']

    rcounts={h:sum(1 for x in candidate_rescue_log if x['house']==h and x['active']) for h in HOUSES}
    proposals={h:sum(1 for x in candidate_rescue_log if x['house']==h) for h in HOUSES}
    md += ['', '## Rank-6–12 rescue activity']
    for h in HOUSES: md.append(f"- **{h}:** frozen proposals={proposals[h]}, live rescue activations={rcounts[h]}, shadow samples={len(candidate_rescue_shadow[h])}")
    md += ['', 'The rescue decision is frozen from prior-only candidate evidence. The current target outcome is used only after freeze to score the proposal for future survival gating.']
    md += ['', '## Contextual rescue attribution']
    for h in HOUSES:
        clog=[x for x in contextual_rescue_log if x['house']==h]
        act=sum(1 for x in clog if x['active'])
        survived=sum(1 for x in clog if x.get('contextual_status',{}).get('active'))
        md.append(f"- **{h}:** contextual proposals={len(clog)}, contexts-survived={survived}, live contextual rescues={act}")
    md += ['', 'A contextual rescue can activate only if the broad v3.1 survival gate and at least one prior-only contextual cohort both survive. Same-target outcomes never define their own context eligibility.']
    (out/'DHAPPA_CONTEXTUAL_RESCUE_ATTRIBUTION_V3_2_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    return rep
