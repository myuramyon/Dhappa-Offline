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


def run_walkforward(rows,min_train=45,max_combo=3,min_tenure=7,challenger_margin=0.010):
    evals=[]; combo_evals=[]; timeline=[]
    profiles=defaultdict(lambda:defaultdict(list)); combo_profiles=defaultdict(lambda:defaultdict(list))
    context_profiles=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    prev_primary={h:None for h in HOUSES}; tenure=Counter(); switches=Counter(); no_primary=Counter()
    election_debug=[]; calibration_events=defaultdict(list); policy_history=[]
    current_policy={h:'BALANCED' for h in HOUSES}; recent_surviving_policy={h:'BALANCED' for h in HOUSES}
    meta_x=defaultdict(list); meta_y=defaultdict(list); discriminator_log=[]; shadow_events=defaultdict(list)

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
            routes=[]
            for name in names:
                past=profiles[house][name]; m=v25.metric(past); sc=v25.score_metric(m)
                if sc<=-900: continue
                cs=v25._context_score(context_profiles,house,name,ctx); cmod,cn=(cs if cs else (0.0,0))
                rr=v25._route_record((name,),past,sc,context_mod=cmod,context_n=cn)
                if rr['window']['qualified']: routes.append(rr)
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
                    rr=v25._route_record(mem,past,pscore,red,incremental,cmod,cn)
                    if incremental>0.003 and red<0.72 and rr['window']['qualified']: routes.append(rr)

            routes.sort(key=lambda x:x['score'],reverse=True)
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

            if selected is None:
                primary_name='NO_QUALIFIED_PRIMARY'; primary_rank=None; primary_hash=None; secondary=None
                if incumbent_name and decision_reason.startswith('INCUMBENT_FAILED'): prev_primary[house]=None
            else:
                primary_name=selected['name']; primary_ranked=route_rankings[primary_name]; primary_rank=primary_ranked.index(actual)+1
                primary_hash=v25.hash_prediction(target['date'],cutoff,house,'PRIMARY:'+primary_name,primary_ranked)
                secondary=next((r for r in ranked_routes if r['name']!=primary_name and set(r['members']).isdisjoint(set(selected['members']))),None)
                if prev_primary[house] and prev_primary[house]!=primary_name: switches[house]+=1; tenure[house]=1
                elif prev_primary[house]==primary_name: tenure[house]+=1
                else: tenure[house]=1
                prev_primary[house]=primary_name

            election_debug.append({'date':target['date'],'house':house,'context':ctx,'decision':decision_reason,'selected':primary_name,
                'candidate':candidate['name'] if candidate else None,'incumbent':incumbent_name,'routes_considered':len(routes),
                'discriminator':disc_meta,'candidate_discriminator_score':disc_scores.get(candidate['name']) if candidate else None,
                'house_policy':house_policy,'paired_proof':paired_proof,'incumbent_strength':incumbent_strength})
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

            # Outcome reveal. First score the pre-frozen discriminator proposal versus the v2.5 baseline for FUTURE activation only.
            if meta_candidate is not None and baseline_candidate is not None:
                shadow_events[house].append({'date':target['date'],'meta':meta_candidate['name'],'baseline':baseline_candidate['name'],
                    'meta_rank':route_rankings[meta_candidate['name']].index(actual)+1,
                    'baseline_rank':route_rankings[baseline_candidate['name']].index(actual)+1})
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
                'incumbent_strength':incumbent_strength['tier'] if incumbent_strength else None,'house_policy':house_policy,'discriminator_mode':disc_meta.get('mode')})
    return evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history,discriminator_log,shadow_events


def report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles):
    rep=v25.report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    rep['model']='DHAPPA Dynamic Primary Engine v2.7 — Prospective Route Discriminator'
    rep['strict_temporal_rule']='qualified route features scored using prior-only online model; current route labels appended only after election freeze and outcome reveal'
    rep['election_features']=rep.get('election_features',[])+['prospective_route_discriminator','online_prior_only_logistic_reranker','15_30_60_route_trajectory','route_peer_disagreement','family_diversity','fallback_to_v2_5_when_meta_sample_insufficient']
    return rep


def save_all(root,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug,calibration_events,policy_history,discriminator_log,shadow_events):
    root=Path(root); out=root/'reports'; out.mkdir(parents=True,exist_ok=True)
    rep=report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    (out/'dynamic_primary_engine_backtest_v2_7.json').write_text(json.dumps(rep,indent=2),encoding='utf-8')
    (out/'dynamic_election_decisions_v2_7.json').write_text(json.dumps(election_debug,indent=2),encoding='utf-8')
    (out/'prospective_route_discriminator_v2_7.json').write_text(json.dumps(discriminator_log,indent=2),encoding='utf-8')
    (out/'prospective_route_discriminator_shadow_v2_7.json').write_text(json.dumps({h:v for h,v in shadow_events.items()},indent=2),encoding='utf-8')
    modes={h:Counter(x['mode'] for x in discriminator_log if x['house']==h) for h in HOUSES}
    md=['# DHAPPA v2.7 — Prospective Route Discriminator','',
        'v2.7 re-ranks only already-qualified routes using an online prior-only classifier. Same-target outcomes are appended as training labels only after election freeze.','',
        '## House metrics','',
        '| House | Elected | Coverage | Top5 elected | Top10 elected | Top21 elected | Top36 elected | MRR | Switches | Current primary |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for h,m in rep['house_metrics'].items():
        md.append(f"| {h} | {m['elected_targets']} | {m['election_coverage_pct']}% | {m['primary_top5_pct_elected']}% | {m['primary_top10_pct_elected']}% | {m['primary_top21_pct_elected']}% | {m['primary_top36_pct_elected']}% | {m['mrr_elected']} | {m['switches']} | {m['current_primary']} |")
    md += ['', '## Discriminator activation']
    for h in HOUSES: md.append(f"- **{h}:** {dict(modes[h])}")
    md += ['', '## Leakage guard','- Route features exist before outcome reveal.','- Training labels for a target are appended only after that target election is frozen.','- Oracle-best route from v2.6 is never supplied as an input feature.','- If prior meta evidence is insufficient, v2.5 scoring is used.']
    (out/'DHAPPA_PROSPECTIVE_ROUTE_DISCRIMINATOR_V2_7_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    return rep
