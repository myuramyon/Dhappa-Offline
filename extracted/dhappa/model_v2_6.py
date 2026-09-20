from __future__ import annotations
from collections import defaultdict, Counter
from itertools import combinations
import json, statistics
from pathlib import Path
from . import model_v2_5 as v25

HOUSES=v25.HOUSES


def _route_rank(rankings, members, rel, indep, actual):
    ranked=rankings[members[0]] if len(members)==1 else v25.fuse(rankings,tuple(members),rel,indep)
    return ranked.index(actual)+1, ranked


def counterfactual_lab(rows, timeline, election_debug, min_train=45, max_combo=3):
    """Replay route universe prior-only, then use revealed outcomes only for diagnostics.
    The oracle labels are NEVER used for the election that generated the same target.
    """
    profiles=defaultdict(lambda:defaultdict(list))
    combo_profiles=defaultdict(lambda:defaultdict(list))
    context_profiles=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    tlmap={(x['date'],x['house']):x for x in timeline}
    dbgmap={(x['date'],x['house']):x for x in election_debug}
    records=[]

    for i in range(min_train,len(rows)):
        target=rows[i]; history=rows[:i]; cutoff=history[-1]['date']
        for house in HOUSES:
            actual=target.get(house)
            if not actual: continue
            ctx=v25._context_key(history,house,target['date'])
            outputs={e.name:e.rank(history,house,target['date']) for e in v25.ENGINES}
            rankings={k:o.ranking for k,o in outputs.items()}
            rel={name:max(.001,v25.score_metric(v25.metric(profiles[house][name]))) for name in rankings}
            names=list(rankings)
            qualified_names=sorted(names,key=lambda n:rel[n],reverse=True)[:6]
            indep={tuple(sorted((a,b))):v25.jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}

            # Reconstruct prior-only eligible route set exactly as v2.5 qualification layer.
            eligible=[]
            single_status={}
            for name in names:
                past=profiles[house][name]; m=v25.metric(past); sc=v25.score_metric(m)
                cs=v25._context_score(context_profiles,house,name,ctx); cmod,cn=(cs if cs else (0.0,0))
                if sc<=-900:
                    single_status[name]={'eligible':False,'reason':'INSUFFICIENT_SAMPLE'}
                    continue
                rr=v25._route_record((name,),past,sc,context_mod=cmod,context_n=cn)
                ok=rr['window']['qualified']
                single_status[name]={'eligible':ok,'reason':'QUALIFIED' if ok else 'WINDOW_QUALIFICATION_FAILED','score':rr['score']}
                if ok: eligible.append(rr)

            combo_status={}
            combo_current=[]
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem)
                    past=combo_profiles[house][key]
                    rank, ranked=_route_rank(rankings,mem,rel,indep,actual)
                    combo_current.append((key,mem,ranked,rank))
                    if len(past)<20:
                        combo_status[key]={'eligible':False,'reason':'INSUFFICIENT_SAMPLE'}; continue
                    pm=v25.metric(past); pscore=v25.score_metric(pm)
                    strongest=max((v25.score_metric(v25.metric(profiles[house][x])) for x in mem),default=-999)
                    incremental=pscore-strongest
                    red=sum(indep[tuple(sorted(x))] for x in combinations(mem,2))/max(1,len(list(combinations(mem,2))))
                    cs=v25._context_score(context_profiles,house,key,ctx); cmod,cn=(cs if cs else (0.0,0))
                    rr=v25._route_record(mem,past,pscore,red,incremental,cmod,cn)
                    ok=(incremental>0.003 and red<0.72 and rr['window']['qualified'])
                    combo_status[key]={'eligible':ok,'reason':'QUALIFIED' if ok else 'SURVIVAL_FAILED','incremental':incremental,'redundancy':red,'score':rr['score']}
                    if ok: eligible.append(rr)
            eligible.sort(key=lambda x:x['score'],reverse=True)

            # Outcome-revealed diagnostic ranks. These are not available to election.
            singles=[]
            for name in names:
                r=rankings[name].index(actual)+1
                singles.append({'route':name,'rank':r,'eligible':single_status.get(name,{}).get('eligible',False),'reason':single_status.get(name,{}).get('reason')})
            combos=[]
            for key,mem,ranked,r in combo_current:
                st=combo_status.get(key,{})
                combos.append({'route':key,'rank':r,'eligible':st.get('eligible',False),'reason':st.get('reason')})
            all_routes=singles+combos
            elig_names={r['name'] for r in eligible}
            eligible_outcomes=[x for x in all_routes if x['route'] in elig_names]
            best_single=min(singles,key=lambda x:x['rank'])
            best_combo=min(combos,key=lambda x:x['rank']) if combos else None
            best_any=min(all_routes,key=lambda x:x['rank'])
            best_eligible=min(eligible_outcomes,key=lambda x:x['rank']) if eligible_outcomes else None

            t=tlmap[(target['date'],house)]; d=dbgmap.get((target['date'],house),{})
            selected=t['primary']; sr=t['actual_rank']
            candidate=d.get('candidate'); incumbent=d.get('incumbent')
            route_rank={x['route']:x['rank'] for x in all_routes}
            candidate_rank=route_rank.get(candidate) if candidate else None
            incumbent_rank=route_rank.get(incumbent) if incumbent else None

            # Hierarchical miss attribution at Top-5, with useful-rank fallback diagnostics.
            if selected=='NO_QUALIFIED_PRIMARY':
                if best_eligible and best_eligible['rank']<=5:
                    cls='ABSTENTION_OPPORTUNITY_COST'
                elif best_any['rank']<=5:
                    cls='QUALIFICATION_MISS'
                elif best_any['rank']>36:
                    cls='GENERATION_MISS'
                else:
                    cls='NO_TOP5_ROUTE_AVAILABLE'
            elif sr is not None and sr<=5:
                # Correct protection is specifically a rejected switch where incumbent beat challenger.
                if candidate and incumbent and selected==incumbent and candidate!=incumbent and incumbent_rank is not None and candidate_rank is not None and incumbent_rank<candidate_rank:
                    cls='CORRECT_PROTECTION'
                else:
                    cls='HIT'
            else:
                alt_eligible=[x for x in eligible_outcomes if x['route']!=selected]
                best_alt=min(alt_eligible,key=lambda x:x['rank']) if alt_eligible else None
                if best_alt and best_alt['rank']<=5:
                    cls='ELECTION_MISS'
                elif best_any['rank']<=5:
                    cls='QUALIFICATION_MISS'
                elif best_any['rank']>36:
                    cls='GENERATION_MISS'
                else:
                    cls='RANKING_DEPTH_MISS'

            records.append({
                'date':target['date'],'source_cutoff':cutoff,'house':house,'actual':actual,
                'selected':selected,'selected_rank':sr,'decision_reason':t.get('decision_reason'),
                'candidate':candidate,'candidate_rank':candidate_rank,'incumbent':incumbent,'incumbent_rank':incumbent_rank,
                'best_eligible_route':best_eligible['route'] if best_eligible else None,'best_eligible_rank':best_eligible['rank'] if best_eligible else None,
                'best_single_route':best_single['route'],'best_single_rank':best_single['rank'],
                'best_combination_route':best_combo['route'] if best_combo else None,'best_combination_rank':best_combo['rank'] if best_combo else None,
                'best_any_route':best_any['route'],'best_any_rank':best_any['rank'],
                'eligible_route_count':len(eligible_outcomes),'classification':cls,
                'oracle_top5_available':best_any['rank']<=5,'eligible_top5_available':bool(best_eligible and best_eligible['rank']<=5),
                'selected_top5':bool(sr and sr<=5),'selected_top10':bool(sr and sr<=10),
            })

            # Reveal and append all route outcomes only after diagnostic snapshot is fixed.
            for name, ranked in rankings.items():
                r=ranked.index(actual)+1
                ev=v25.Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,v25.hash_prediction(target['date'],cutoff,house,name,ranked))
                profiles[house][name].append(ev); context_profiles[house][name][ctx].append(ev)
            for key,mem,ranked,r in combo_current:
                ev=v25.Eval(target['date'],cutoff,house,key,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,v25.hash_prediction(target['date'],cutoff,house,key,ranked))
                combo_profiles[house][key].append(ev); context_profiles[house][key][ctx].append(ev)
    return records


def summarize_counterfactual(records):
    out={}
    for h in HOUSES:
        rr=[x for x in records if x['house']==h]; n=len(rr)
        counts=Counter(x['classification'] for x in rr)
        selected5=sum(x['selected_top5'] for x in rr)
        eligible5=sum(x['eligible_top5_available'] for x in rr)
        oracle5=sum(x['oracle_top5_available'] for x in rr)
        out[h]={
            'targets':n,'classifications':dict(counts),
            'selected_top5_pct_all':round(100*selected5/max(1,n),2),
            'eligible_route_top5_ceiling_pct_diagnostic':round(100*eligible5/max(1,n),2),
            'all_route_top5_ceiling_pct_diagnostic':round(100*oracle5/max(1,n),2),
            'eligible_rescue_gap_pp':round(100*(eligible5-selected5)/max(1,n),2),
            'qualification_rescue_gap_pp':round(100*(oracle5-eligible5)/max(1,n),2),
            'abstention_opportunity_cost':counts.get('ABSTENTION_OPPORTUNITY_COST',0),
            'election_misses':counts.get('ELECTION_MISS',0),
            'qualification_misses':counts.get('QUALIFICATION_MISS',0),
            'generation_misses':counts.get('GENERATION_MISS',0),
            'ranking_depth_misses':counts.get('RANKING_DEPTH_MISS',0),
            'correct_protections':counts.get('CORRECT_PROTECTION',0),
        }
    return out


def save_counterfactual(root, records):
    root=Path(root); out=root/'reports'; out.mkdir(parents=True,exist_ok=True)
    summary=summarize_counterfactual(records)
    (out/'route_counterfactual_election_lab_v2_6.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (out/'route_counterfactual_summary_v2_6.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    md=['# DHAPPA v2.6 — Route-Level Counterfactual Election Lab','',
        'This is a diagnostic layer over v2.5. Outcome-revealed oracle ranks are used only after the same-target election is frozen; they are not fed back into that target prediction.','',
        '## House-wise counterfactual diagnosis','',
        '| House | Targets | Selected Top5 | Eligible-route Top5 ceiling* | All-route Top5 ceiling* | Election miss | Qualification miss | Generation miss | Ranking-depth miss | Abstention opportunity | Correct protection |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for h,m in summary.items():
        md.append(f"| {h} | {m['targets']} | {m['selected_top5_pct_all']}% | {m['eligible_route_top5_ceiling_pct_diagnostic']}% | {m['all_route_top5_ceiling_pct_diagnostic']}% | {m['election_misses']} | {m['qualification_misses']} | {m['generation_misses']} | {m['ranking_depth_misses']} | {m['abstention_opportunity_cost']} | {m['correct_protections']} |")
    md += ['', '*Ceilings are hindsight diagnostic upper bounds, not achievable prospective performance claims.','',
           '## Classification rules','- **ELECTION_MISS:** selected route missed Top-5 while another already-qualified route contained the actual in Top-5.','- **QUALIFICATION_MISS:** no eligible alternative rescued Top-5, but a generated single/combination rejected by qualification did.','- **GENERATION_MISS:** even the best generated route ranked the actual below Top-36.','- **RANKING_DEPTH_MISS:** a route generated the actual within Top-36, but none placed it in Top-5.','- **ABSTENTION_OPPORTUNITY_COST:** the system abstained while a qualified route had the actual in Top-5.','- **CORRECT_PROTECTION:** a proposed challenger was rejected and the retained incumbent ranked the revealed outcome better.','',
           '## Intended use','Use this report to decide whether the next engineering effort belongs in election, qualification, ranking/generation, or abstention logic. Do not train directly on the oracle-best route identity for the same target.']
    (out/'DHAPPA_ROUTE_COUNTERFACTUAL_V2_6_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    return summary
