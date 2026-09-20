from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import Counter, defaultdict
from itertools import combinations
from math import exp, log, sqrt
import csv, hashlib, json, statistics
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional

HOUSES = ("Deshawar","Faridabad","Ghaziabad","Gali")
ALL = [f"{i:02d}" for i in range(100)]

def norm(v):
    s = str(v).strip()
    if not s or s.lower() in {"nan","none"}: return None
    try: return f"{int(float(s)):02d}" if 0 <= int(float(s)) <= 99 else None
    except: return None

def rev(p): return p[::-1]
def mirror(p): return ''.join(str(9-int(x)) for x in p)
def root(p): return str((int(p[0])+int(p[1]))%10)
def parse_date(s):
    for fmt in ("%Y-%m-%d","%m/%d/%Y","%d/%m/%Y"):
        try: return datetime.strptime(s,fmt)
        except: pass
    raise ValueError(s)

def load_csv(path):
    rows=[]
    with open(path,newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            d=parse_date(r['Date'])
            row={'date':d.strftime('%Y-%m-%d')}
            for h in HOUSES: row[h]=norm(r.get(h,''))
            rows.append(row)
    rows.sort(key=lambda x:x['date'])
    # last duplicate date wins only if it adds data
    merged={}
    for r in rows:
        if r['date'] not in merged: merged[r['date']]=r
        else:
            for h in HOUSES:
                if r[h] is not None: merged[r['date']][h]=r[h]
    return [merged[k] for k in sorted(merged)]

@dataclass
class EngineOutput:
    engine: str
    ranking: List[str]
    meta: dict

class Engine:
    name='BASE'; family='base'
    def rank(self, history, house, target_date): raise NotImplementedError
    def out(self, scores, **meta):
        ranking=sorted(ALL,key=lambda p:(-scores.get(p,0.0),p))
        return EngineOutput(self.name,ranking,meta)

def house_series(history,house): return [r[house] for r in history if r.get(house)]

def decay_counts(vals, half_life=15):
    c=defaultdict(float); n=len(vals)
    for i,p in enumerate(vals): c[p]+=0.5**((n-1-i)/half_life)
    return c

class DateTriad(Engine):
    name='DATE_TRIAD'; family='calendar'
    def rank(self,history,house,target_date):
        d=parse_date(target_date); x=(d.day+d.month+sum(map(int,str(d.year))))%10
        anchors={(x*10+x)%100,(x*11+9)%100,(x*7+d.weekday()*3)%100,(d.day*3+d.month*7)%100}
        scores={p:0 for p in ALL}
        for a in anchors:
            p=f'{a:02d}'; scores[p]+=4; scores[rev(p)]+=2; scores[mirror(p)]+=1
        return self.out(scores,x=x)

class PrevDay(Engine):
    name='PREVIOUS_DAY'; family='transition'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if not vals:return self.out(scores)
        p=vals[-1]; a,b=map(int,p)
        cand={p:5,rev(p):4,mirror(p):2,f'{(a+b)%10}{b}':3,f'{a}{(a+b)%10}':3,f'{abs(a-b)}{(a+b)%10}':2}
        for q,w in cand.items(): scores[q]+=w
        return self.out(scores,source=p)

class DeltaMatrix(Engine):
    name='DELTA_MATRIX'; family='delta'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if len(vals)<2:return self.out(scores)
        a,b=map(int,vals[-1]); c,d=map(int,vals[-2]); da=(a-c)%10; db=(b-d)%10
        variants=[((a+da)%10,(b+db)%10,5),((a-db)%10,(b+da)%10,3),((a+db)%10,(b+da)%10,2)]
        for x,y,w in variants:
            p=f'{x}{y}'; scores[p]+=w; scores[rev(p)]+=w*.6
        return self.out(scores,delta=[da,db])

class GSquare(Engine):
    name='G_SQUARE'; family='square'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if not vals:return self.out(scores)
        a,b=map(int,vals[-1]); digits=[a,b,(a+b)%10,(a-b)%10,(b-a)%10,(a+5)%10,(b+5)%10]
        for i,x in enumerate(digits):
            for j,y in enumerate(digits):
                scores[f'{x}{y}'] += 1/(1+abs(i-j))
        return self.out(scores,source=vals[-1])

class GSquareHarmonics(Engine):
    name='G_SQUARE_HARMONICS'; family='square'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if not vals:return self.out(scores)
        a,b=map(int,vals[-1]); base=[a,b,(a+b)%10,(a+3*b)%10,(3*a+b)%10,(9-a)%10,(9-b)%10]
        for x in base:
            for y in base: scores[f'{x}{y}']+=1
        return self.out(scores,source=vals[-1])

class HarufPyramid(Engine):
    name='HARUF_PYRAMID'; family='haruf'
    def rank(self,history,house,target_date):
        vals=house_series(history,house)[-12:]; scores={p:0 for p in ALL}
        if not vals:return self.out(scores)
        digits=[]
        for p in vals: digits.extend(map(int,p))
        freq=Counter(digits); top=[d for d,_ in freq.most_common(6)]
        if len(top)<2: top=list(range(10))[:6]
        layer=top[:]
        for _ in range(3): layer += [(layer[i]+layer[i+1])%10 for i in range(len(layer)-1)]
        wf=Counter(layer)
        for p in ALL: scores[p]=wf[int(p[0])]+wf[int(p[1])] + (2 if int(p[0]) in top[:3] and int(p[1]) in top[:3] else 0)
        return self.out(scores,top_haruf=top)

class Lookback5(Engine):
    name='LOOKBACK_5'; family='recency'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); recent=vals[-5:]; scores={p:0 for p in ALL}
        for age,p in enumerate(reversed(recent)):
            w=5-age; scores[p]+=w; scores[rev(p)]+=w*.8; scores[mirror(p)]+=w*.35
            r=root(p)
            for q in ALL:
                if root(q)==r: scores[q]+=w*.08
        return self.out(scores)

class Echo7(Engine):
    name='ECHO_7'; family='echo'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        for lag,w in ((7,5),(14,3),(21,2)):
            if len(vals)>=lag:
                p=vals[-lag]; scores[p]+=w; scores[rev(p)]+=w*.7; scores[mirror(p)]+=w*.25
        return self.out(scores)

class HotRecency(Engine):
    name='HOT_RECENCY'; family='frequency'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); c=decay_counts(vals[-90:],12); scores={p:c[p] for p in ALL}
        for p in ALL:
            # gap bonus only small; avoids pure frequency lock-in
            try: gap=next(i for i,q in enumerate(reversed(vals[-60:])) if q==p)
            except StopIteration: gap=60
            scores[p]+=min(gap,30)/60
        return self.out(scores)

class RashiFamily(Engine):
    name='RASHI_FAMILY'; family='family'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if not vals:return self.out(scores)
        recent=vals[-10:]; rc=Counter(root(p) for p in recent)
        for p in ALL:
            scores[p]=rc[root(p)]*1.5
            if rev(p) in recent:scores[p]+=2
            if mirror(p) in recent:scores[p]+=1
        return self.out(scores)

class TransitionMarkov(Engine):
    name='TRANSITION_MARKOV'; family='transition'
    def rank(self,history,house,target_date):
        vals=house_series(history,house); scores={p:0 for p in ALL}
        if len(vals)<3:return self.out(scores)
        last=vals[-1]; trans=defaultdict(Counter)
        for a,b in zip(vals[:-1],vals[1:]): trans[a][b]+=1
        for q,n in trans[last].items(): scores[q]+=n*4
        # digit transition fallback
        t0=defaultdict(Counter); t1=defaultdict(Counter)
        for a,b in zip(vals[:-1],vals[1:]): t0[a[0]][b[0]]+=1; t1[a[1]][b[1]]+=1
        for p in ALL: scores[p]+=t0[last[0]][p[0]]+t1[last[1]][p[1]]
        return self.out(scores,source=last)

class ModelF(Engine):
    name='MODEL_F'; family='composite'
    def __init__(self, base): self.base=base
    def rank(self,history,house,target_date):
        scores={p:0 for p in ALL}
        members=[e for e in self.base if e.name in {'DATE_TRIAD','G_SQUARE','HARUF_PYRAMID','LOOKBACK_5','HOT_RECENCY'}]
        for e in members:
            r=e.rank(history,house,target_date).ranking
            for i,p in enumerate(r[:36]): scores[p]+=1/(3+i)
        return self.out(scores,members=[e.name for e in members])

BASE_ENGINES=[DateTriad(),PrevDay(),DeltaMatrix(),GSquare(),GSquareHarmonics(),HarufPyramid(),Lookback5(),Echo7(),HotRecency(),RashiFamily(),TransitionMarkov()]
ENGINES=BASE_ENGINES+[ModelF(BASE_ENGINES)]

@dataclass
class Eval:
    date:str; source_cutoff:str; house:str; engine:str; actual:str; rank:int; hit5:bool; hit10:bool; hit21:bool; hit36:bool; reciprocal_rank:float; freeze_hash:str

def hash_prediction(date,cutoff,house,engine,ranking):
    raw=json.dumps([date,cutoff,house,engine,ranking],separators=(',',':'))
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

def metric(evals:List[Eval]):
    if not evals:
        return {'n':0,'h5':0,'h10':0,'h21':0,'h36':0,'mrr':0,'median_rank':101,'mean_rank':101,'stability':0}
    n=len(evals); ranks=[e.rank for e in evals]
    h=lambda k: sum(e.rank<=k for e in evals)/n
    recent=evals[-15:]
    recent_h=sum(e.rank<=10 for e in recent)/len(recent)
    long_h=h(10)
    stability=max(0,1-abs(recent_h-long_h)-min(statistics.pstdev(ranks)/100,0.5))
    return {'n':n,'h5':h(5),'h10':h(10),'h21':h(21),'h36':h(36),'mrr':sum(e.reciprocal_rank for e in evals)/n,
            'median_rank':statistics.median(ranks),'mean_rank':sum(ranks)/n,'stability':stability}

def score_metric(m):
    if m['n']<15:return -999
    sample=min(1,m['n']/60)
    # Election utility, never interpreted as probability.
    return sample*(0.34*m['h5']+0.22*m['h10']+0.12*m['h21']+0.07*m['h36']+0.15*m['mrr']+0.10*m['stability'])

def jaccard_top(a,b,k=21):
    A=set(a[:k]);B=set(b[:k]);u=len(A|B);return len(A&B)/u if u else 0

def fuse(rankings:Dict[str,List[str]], members:Tuple[str,...], reliability:Dict[str,float], independence:Dict[Tuple[str,str],float]):
    s=defaultdict(float)
    for e in members:
        rel=max(.02,reliability.get(e,.05))
        redundancy=[independence.get(tuple(sorted((e,o))),0) for o in members if o!=e]
        pen=(sum(redundancy)/len(redundancy)) if redundancy else 0
        weight=rel*(1-0.60*pen)
        for i,p in enumerate(rankings[e][:50]): s[p]+=weight/(3+i)
    return sorted(ALL,key=lambda p:(-s[p],p))

def window_metrics(evs):
    return {str(w):metric(evs[-w:]) for w in (15,30,60)} | {'expanding':metric(evs)}

def _window_agreement(evs):
    """Prior-only agreement across 15/30/60/expanding windows."""
    if len(evs)<15:return {'score':0.0,'positive':0,'windows':{},'qualified':False}
    ms=window_metrics(evs)
    available=[w for w in ('15','30','60','expanding') if ms[w]['n']>=15]
    vals=[]; positive=0
    # Against random ranking baselines, with Top10/MRR carrying most signal.
    for w in available:
        m=ms[w]
        lift10=m['h10']-.10
        lift5=m['h5']-.05
        rank_lift=(50.5-m['mean_rank'])/50.5
        local=.50*lift10+.25*lift5+.15*m['mrr']+.10*rank_lift
        vals.append(local)
        if lift10>0 or lift5>0 or rank_lift>0: positive+=1
    agreement=(positive/len(available)) if available else 0
    dispersion=statistics.pstdev(vals) if len(vals)>1 else 0
    score=(sum(vals)/len(vals) if vals else 0)+.03*agreement-.20*dispersion
    return {'score':score,'positive':positive,'available':len(available),'windows':ms,
            'qualified':len(available)>=2 and agreement>=.67 and score>0}

def _context_key(history,house,target_date):
    vals=house_series(history,house)
    d=parse_date(target_date)
    last=vals[-1] if vals else 'NA'
    palti_recent='P1' if vals and rev(last) in vals[-7:-1] else 'P0'
    repeat='R1' if vals.count(last)>=2 else 'R0'
    gap='G0'
    if vals:
        try: gapn=next(i for i,q in enumerate(reversed(vals[:-1])) if q==last)+1
        except StopIteration: gapn=99
        gap='GSHORT' if gapn<=7 else ('GMID' if gapn<=21 else 'GLONG')
    return f'DOW{d.weekday()}|{palti_recent}|{repeat}|{gap}'

def _context_score(context_profiles,house,route,ctx):
    evs=context_profiles[house][route].get(ctx,[])
    if len(evs)<12:return None
    m=metric(evs)
    # small contextual modifier, capped to prevent regime overfit
    raw=.55*(m['h10']-.10)+.25*(m['h5']-.05)+.20*((50.5-m['mean_rank'])/50.5)
    return max(-.04,min(.04,raw)),len(evs)

def _route_record(members, prior_evs, base_score, redundancy=0.0, incremental=0.0, context_mod=0.0, context_n=0):
    wa=_window_agreement(prior_evs)
    score=base_score + .35*wa['score'] + context_mod - .08*redundancy + .35*max(0,incremental)
    return {'members':tuple(members),'name':'+'.join(members),'score':score,'window':wa,'n':len(prior_evs),
            'redundancy':redundancy,'incremental':incremental,'context_mod':context_mod,'context_n':context_n}

def _paired_by_date(challenger_evs, incumbent_evs):
    c={e.date:e for e in challenger_evs}; i={e.date:e for e in incumbent_evs}
    dates=sorted(set(c)&set(i))
    return [(c[d],i[d]) for d in dates]

def _sign_test_two_sided(wins, losses):
    """Exact two-sided sign-test p-value on non-tied paired rank wins/losses."""
    n=wins+losses
    if n<=0:return 1.0
    k=min(wins,losses)
    tail=sum(__import__('math').comb(n,j) for j in range(k+1))/(2**n)
    return min(1.0,2*tail)

def _paired_challenger_proof(challenger_evs, incumbent_evs):
    """Prior-only paired evidence on identical historical targets.
    Positive mean_rank_delta means challenger ranked the actual outcome better.
    """
    pairs=_paired_by_date(challenger_evs,incumbent_evs)
    n=len(pairs)
    if n==0:
        return {'n':0,'qualified':False,'reason':'NO_PAIRED_HISTORY'}
    def calc(ps):
        nn=len(ps)
        if not nn:return {'n':0,'mean_rank_delta':0,'wins':0,'losses':0,'ties':0,'win_rate':0,'rescued_top5':0,'damaged_top5':0,'net_top5':0,'net_top10':0,'mrr_delta':0,'sign_p':1.0}
        deltas=[ie.rank-ce.rank for ce,ie in ps]
        wins=sum(d>0 for d in deltas); losses=sum(d<0 for d in deltas); ties=nn-wins-losses
        rescued=sum(ie.rank>5 and ce.rank<=5 for ce,ie in ps)
        damaged=sum(ie.rank<=5 and ce.rank>5 for ce,ie in ps)
        net10=sum((1 if ce.rank<=10 else 0)-(1 if ie.rank<=10 else 0) for ce,ie in ps)
        return {'n':nn,'mean_rank_delta':sum(deltas)/nn,'wins':wins,'losses':losses,'ties':ties,
                'win_rate':wins/max(1,wins+losses),'rescued_top5':rescued,'damaged_top5':damaged,
                'net_top5':rescued-damaged,'net_top10':net10,
                'mrr_delta':sum((1/ce.rank)-(1/ie.rank) for ce,ie in ps)/nn,
                'sign_p':_sign_test_two_sided(wins,losses)}
    overall=calc(pairs)
    windows={str(w):calc(pairs[-w:]) for w in (15,30,60) if n>=w}
    positive_windows=sum(1 for m in windows.values() if m['mean_rank_delta']>0 and m['net_top5']>=0 and m['net_top10']>=0)
    # Challenger must prove paired improvement rather than merely own a higher unpaired composite score.
    qualified=(n>=20 and overall['mean_rank_delta']>0 and overall['net_top5']>=0 and overall['rescued_top5']>=overall['damaged_top5']
               and overall['mrr_delta']>=0 and overall['win_rate']>=0.50 and positive_windows>=max(1,len(windows)//2))
    strength='INSUFFICIENT'
    if qualified:
        strength='MODERATE'
        if n>=60 and overall['net_top5']>0 and overall['win_rate']>0.52 and overall['sign_p']<=0.20 and positive_windows>=2:
            strength='STRONG'
        elif overall['net_top5']==0 and overall['mean_rank_delta']<1:
            strength='WEAK'
    return {**overall,'windows':windows,'positive_windows':positive_windows,'qualified':qualified,'strength':strength,
            'reason':'PAIRED_SUPERIORITY_PASSED' if qualified else 'PAIRED_SUPERIORITY_NOT_PROVEN'}

def _route_history(profiles, combo_profiles, house, route_name):
    return combo_profiles[house][route_name] if '+' in route_name else profiles[house][route_name]


def _incumbent_strength(route_evs):
    """Classify incumbent from PRIOR-ONLY evidence. Tier controls replacement friction."""
    if not route_evs or len(route_evs) < 15:
        return {'tier':'FAILING','reason':'INSUFFICIENT_HISTORY','metric':metric(route_evs),'window':_window_agreement(route_evs)}
    m=metric(route_evs); wa=_window_agreement(route_evs); r15=metric(route_evs[-15:])
    # Failure is based on sustained/recent deterioration, not one miss.
    failing = (r15['h10'] < .067 and r15['mean_rank'] > 52) or (wa['score'] < -.025)
    strong = (len(route_evs)>=60 and wa['qualified'] and m['h10']>=.11 and m['stability']>=.42 and r15['h10']>=.067)
    moderate = (len(route_evs)>=30 and wa['qualified'] and (m['h10']>=.095 or m['h5']>=.045))
    if failing: tier='FAILING'
    elif strong: tier='STRONG'
    elif moderate: tier='MODERATE'
    else: tier='WEAK'
    return {'tier':tier,'reason':'PRIOR_ONLY_TIER','metric':m,'recent15':r15,'window':wa}

def _asymmetric_switch_gate(tier, candidate, incumbent, proof, tenure):
    """Return (allow, reason). Strong champions get maximum protection; weak/failing do not."""
    gap=candidate['score']-incumbent['score']
    if tier=='STRONG':
        ok=(tenure>=7 and gap>=.010 and proof and proof['qualified'] and proof['net_top5']>=0 and proof['mrr_delta']>=0)
        return ok, 'STRONG_CHAMPION_PROOF_PASSED' if ok else 'STRONG_CHAMPION_PROTECTED'
    if tier=='MODERATE':
        ok=(tenure>=5 and gap>=.006 and proof and proof['n']>=15 and proof['net_top5']>=0 and proof['mean_rank_delta']>0 and proof['mrr_delta']>=-.002)
        return ok, 'MODERATE_CHAMPION_CHALLENGED' if ok else 'MODERATE_CHAMPION_RETAINED'
    if tier=='WEAK':
        # Faster path: paired evidence can be weaker, but damage budget may not be negative.
        ok=(tenure>=3 and gap>=.002 and proof and proof['n']>=12 and proof['net_top5']>=0 and (proof['mean_rank_delta']>0 or proof['mrr_delta']>0))
        return ok, 'WEAK_CHAMPION_FAST_REPLACEMENT' if ok else 'WEAK_CHAMPION_TEMP_RETAIN'
    # FAILING: do not lock in a deteriorating incumbent. Candidate itself already passed route qualification.
    ok=(tenure>=2 and gap>=-.003)
    return ok, 'FAILING_CHAMPION_REPLACED' if ok else 'FAILING_CHAMPION_ABSTAIN'


def run_walkforward(rows,min_train=45,max_combo=3,min_tenure=7,challenger_margin=0.010):
    evals=[]; combo_evals=[]; timeline=[]
    profiles=defaultdict(lambda:defaultdict(list)); combo_profiles=defaultdict(lambda:defaultdict(list))
    context_profiles=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    prev_primary={h:None for h in HOUSES}; tenure=Counter(); switches=Counter(); no_primary=Counter()
    election_debug=[]

    for i in range(min_train,len(rows)):
        target=rows[i]; history=rows[:i]; cutoff=history[-1]['date']
        for house in HOUSES:
            actual=target.get(house)
            if not actual: continue
            ctx=_context_key(history,house,target['date'])
            outputs={e.name:e.rank(history,house,target['date']) for e in ENGINES}
            rankings={k:v.ranking for k,v in outputs.items()}
            # Immutable single freezes happen before election/reveal.
            single_hashes={name:hash_prediction(target['date'],cutoff,house,name,ranked) for name,ranked in rankings.items()}

            # PRIOR-ONLY reliability and current top-overlap independence.
            rel={name:max(.001,score_metric(metric(profiles[house][name]))) for name in rankings}
            names=list(rankings)
            qualified_names=sorted(names,key=lambda n:rel[n],reverse=True)[:6]
            indep={tuple(sorted((a,b))):jaccard_top(rankings[a],rankings[b]) for a,b in combinations(names,2)}

            routes=[]
            # Single route qualification: multi-window agreement is mandatory.
            for name in names:
                past=profiles[house][name]
                m=metric(past); sc=score_metric(m)
                if sc<=-900: continue
                cs=_context_score(context_profiles,house,name,ctx)
                cmod,cn=(cs if cs else (0.0,0))
                rr=_route_record((name,),past,sc,context_mod=cmod,context_n=cn)
                if rr['window']['qualified']: routes.append(rr)

            # Combination survival universe from prior-strong singles only.
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem); past=combo_profiles[house][key]
                    if len(past)<20: continue
                    pm=metric(past); pscore=score_metric(pm)
                    if pscore<=-900: continue
                    strongest=max((score_metric(metric(profiles[house][x])) for x in mem),default=-999)
                    incremental=pscore-strongest
                    red=sum(indep[tuple(sorted(x))] for x in combinations(mem,2))/max(1,len(list(combinations(mem,2))))
                    # Survival test: positive increment + redundancy ceiling + window agreement.
                    cs=_context_score(context_profiles,house,key,ctx); cmod,cn=(cs if cs else (0.0,0))
                    rr=_route_record(mem,past,pscore,red,incremental,cmod,cn)
                    survived=(incremental>0.003 and red<0.72 and rr['window']['qualified'])
                    if survived: routes.append(rr)

            routes.sort(key=lambda x:x['score'],reverse=True)
            candidate=routes[0] if routes else None
            incumbent_name=prev_primary[house]
            incumbent=next((r for r in routes if r['name']==incumbent_name),None) if incumbent_name else None
            decision_reason='NO_ROUTE_PASSED_QUALIFICATION'
            selected=None
            paired_proof=None
            if candidate and incumbent and candidate['name']!=incumbent_name:
                paired_proof=_paired_challenger_proof(
                    _route_history(profiles,combo_profiles,house,candidate['name']),
                    _route_history(profiles,combo_profiles,house,incumbent_name))

            incumbent_strength=None
            # Explicit abstention if nothing has robust prior evidence.
            if candidate is None:
                selected=None; no_primary[house]+=1; tenure[house]=0
            elif incumbent_name is None:
                selected=candidate; decision_reason='INITIAL_QUALIFIED_CHAMPION'
            elif incumbent is None:
                # A route that no longer survives qualification cannot be protected indefinitely.
                if tenure[house]>=2:
                    selected=candidate; decision_reason='INCUMBENT_FAILED_SURVIVAL_FAST_REPLACEMENT'
                else:
                    selected=None; decision_reason='INCUMBENT_FAILED_SURVIVAL_ABSTAIN'
                    no_primary[house]+=1
            elif candidate['name']==incumbent_name:
                incumbent_strength=_incumbent_strength(_route_history(profiles,combo_profiles,house,incumbent_name))
                selected=incumbent; decision_reason='CHAMPION_RETAINED'
            else:
                incumbent_strength=_incumbent_strength(_route_history(profiles,combo_profiles,house,incumbent_name))
                tier=incumbent_strength['tier']
                allow,reason=_asymmetric_switch_gate(tier,candidate,incumbent,paired_proof,tenure[house])
                if allow:
                    selected=candidate; decision_reason=reason
                elif tier=='FAILING':
                    # If failing incumbent cannot be credibly replaced, abstain instead of forcing it.
                    selected=None; decision_reason=reason; no_primary[house]+=1
                    prev_primary[house]=None; tenure[house]=0
                else:
                    selected=incumbent; decision_reason=reason

            if selected is None:
                primary_name='NO_QUALIFIED_PRIMARY'; primary_rank=None; primary_hash=None
                secondary=None
                if incumbent_name and decision_reason.startswith('INCUMBENT_FAILED'):
                    prev_primary[house]=None
                election_debug.append({'date':target['date'],'house':house,'context':ctx,'decision':decision_reason,'selected':primary_name,
                                       'candidate':candidate['name'] if candidate else None,'candidate_score':candidate['score'] if candidate else None,
                                       'routes_considered':len(routes),'paired_proof':paired_proof,'incumbent_strength':incumbent_strength})
            else:
                primary_mem=selected['members']; primary_name=selected['name']
                primary_ranked=rankings[primary_mem[0]] if len(primary_mem)==1 else fuse(rankings,primary_mem,rel,indep)
                primary_rank=primary_ranked.index(actual)+1
                primary_hash=hash_prediction(target['date'],cutoff,house,'PRIMARY:'+primary_name,primary_ranked)
                secondary=next((r for r in routes if r['name']!=primary_name and set(r['members']).isdisjoint(set(primary_mem))),None)
                if prev_primary[house] and prev_primary[house]!=primary_name:
                    switches[house]+=1; tenure[house]=1
                elif prev_primary[house]==primary_name: tenure[house]+=1
                else: tenure[house]=1
                prev_primary[house]=primary_name
                election_debug.append({'date':target['date'],'house':house,'context':ctx,'decision':decision_reason,'selected':primary_name,
                                       'selected_score':selected['score'],'candidate':candidate['name'] if candidate else None,
                                       'candidate_score':candidate['score'] if candidate else None,'incumbent':incumbent_name,
                                       'tenure':tenure[house],'routes_considered':len(routes),'window':selected['window'],
                                       'context_n':selected['context_n'],'context_mod':selected['context_mod'],'paired_proof':paired_proof,'incumbent_strength':incumbent_strength})

            # Freeze qualified combination rankings BEFORE outcome-profile updates.
            combo_current=[]
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem); ranked=fuse(rankings,mem,rel,indep)
                    combo_current.append((key,mem,ranked,hash_prediction(target['date'],cutoff,house,key,ranked)))

            # REVEAL/EVALUATE phase starts here: append current target only now.
            current_single={}
            for name,ranked in rankings.items():
                r=ranked.index(actual)+1
                ev=Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,single_hashes[name])
                evals.append(ev); profiles[house][name].append(ev); current_single[name]=ev
                context_profiles[house][name][ctx].append(ev)
            for key,mem,ranked,fh in combo_current:
                r=ranked.index(actual)+1
                ev=Eval(target['date'],cutoff,house,key,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,fh)
                combo_evals.append(ev); combo_profiles[house][key].append(ev); context_profiles[house][key][ctx].append(ev)

            confidence='INSUFFICIENT_EVIDENCE'
            if selected:
                wn=selected['window']['available']; n=selected['n']; pos=selected['window']['positive']
                if n>=60 and wn>=4 and pos>=3: confidence='STRONG_EVIDENCE'
                elif n>=30 and wn>=3 and pos>=2: confidence='MODERATE_EVIDENCE'
                elif n>=15: confidence='WEAK_EVIDENCE'
            timeline.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'context':ctx,'primary':primary_name,
                             'secondary':secondary['name'] if secondary else None,'actual':actual,'actual_rank':primary_rank,
                             'hit5':bool(primary_rank and primary_rank<=5),'hit10':bool(primary_rank and primary_rank<=10),
                             'hit21':bool(primary_rank and primary_rank<=21),'hit36':bool(primary_rank and primary_rank<=36),
                             'confidence':confidence,'decision_reason':decision_reason,'tenure':tenure[house] if selected else 0,
                             'freeze_hash':primary_hash,'incumbent_strength':incumbent_strength['tier'] if incumbent_strength else None})
    return evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug

def report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles):
    house={}
    for h in HOUSES:
        tl=[x for x in timeline if x['house']==h]
        elected=[x for x in tl if x['primary']!='NO_QUALIFIED_PRIMARY']
        n=max(1,len(elected))
        house[h]={
          'targets':len(tl),'elected_targets':len(elected),'abstentions':len(tl)-len(elected),
          'election_coverage_pct':round(100*len(elected)/max(1,len(tl)),2),
          'primary_top5_pct_elected':round(100*sum(x['hit5'] for x in elected)/n,2),
          'primary_top10_pct_elected':round(100*sum(x['hit10'] for x in elected)/n,2),
          'primary_top21_pct_elected':round(100*sum(x['hit21'] for x in elected)/n,2),
          'primary_top36_pct_elected':round(100*sum(x['hit36'] for x in elected)/n,2),
          'primary_top5_pct_all_targets':round(100*sum(x['hit5'] for x in elected)/max(1,len(tl)),2),
          'mrr_elected':round(sum(1/x['actual_rank'] for x in elected if x['actual_rank'])/n,4),
          'median_rank_elected':statistics.median([x['actual_rank'] for x in elected]) if elected else None,
          'mean_rank_elected':round(sum(x['actual_rank'] for x in elected)/n,2) if elected else None,
          'switches':switches[h], 'current_primary':tl[-1]['primary'] if tl else None,
        }
        leaders=[]
        for e,evs in profiles[h].items():
            m=metric(evs);leaders.append((score_metric(m),e,m,_window_agreement(evs)))
        house[h]['single_leaders']=[{'engine':e,'window_agreement':round(wa['score'],4),
            **{k:(round(v*100,2) if k in {'h5','h10','h21','h36','mrr','stability'} else round(v,2) if isinstance(v,float) else v) for k,v in m.items()}}
            for _,e,m,wa in sorted(leaders,reverse=True)[:5]]
    return {'model':'DHAPPA Dynamic Primary Engine v2.2','rows':len(rows),'date_range':[rows[0]['date'],rows[-1]['date']],
            'strict_temporal_rule':'generate/freeze/elect using rows[:target_index] only; append target evaluations only after election',
            'election_features':['champion_challenger_gating','15_30_60_expanding_agreement','minimum_tenure_hysteresis',
                                 'combination_survival_test','contextual_regime_modifier','NO_QUALIFIED_PRIMARY','paired_challenger_proof','asymmetric_champion_protection','incumbent_strength_tiers','damage_budget','fast_weak_challenger_path','failing_incumbent_abstention'],
            'engine_count':len(ENGINES),'engines':[{'name':e.name,'family':e.family} for e in ENGINES],'house_metrics':house}

def save_all(root,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles,election_debug=None):
    out=Path(root)/'reports'; out.mkdir(parents=True,exist_ok=True)
    rep=report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    def dump(name,obj): (out/name).write_text(json.dumps(obj,indent=2,default=str),encoding='utf-8')
    dump('dynamic_primary_engine_backtest_v2_2.json',rep)
    dump('primary_engine_election_timeline_v2_2.json',timeline)
    dump('single_engine_performance_v2_2.json',{h:{e:window_metrics(v) for e,v in profiles[h].items()} for h in HOUSES})
    dump('engine_combination_performance_v2_2.json',{h:{e:window_metrics(v) for e,v in combo_profiles[h].items()} for h in HOUSES})
    dump('dynamic_election_decisions_v2_2.json',election_debug or [])
    failures=[]
    for x in timeline:
        if x['primary']=='NO_QUALIFIED_PRIMARY': typ='ABSTAIN_NO_QUALIFIED_PRIMARY'
        elif x['actual_rank']>36: typ='GENERATION_OR_DEEP_RANK_FAILURE'
        elif x['actual_rank']>5: typ='RANKING_FAILURE'
        else: typ='HIT'
        failures.append({**x,'failure_type':typ})
    dump('generation_vs_ranking_failure_v2_2.json',failures)
    integrity={'version':'v2.2','no_current_target_used_for_generation':True,'history_slice':'rows[:target_index]',
               'election_before_target_profile_update':True,'freeze_hash':'sha256(date,cutoff,house,engine,ranking)',
               'explicit_abstention_state':True,'paired_challenger_proof':True,'asymmetric_champion_protection':True,'strength_tiers':['STRONG','MODERATE','WEAK','FAILING'],'minimum_tenure':'tier-dependent: 7/5/3/2',
               'notes':['Current target is not appended to single or combination profiles until after primary election.',
                        'Context keys use target calendar metadata plus history ending at t-2, never target outcome.',
                        'NO_QUALIFIED_PRIMARY is emitted when no route passes prior-only multi-window qualification.']}
    dump('primary_engine_integrity_report_v2_1.json',integrity)
    md=['# DHAPPA Dynamic Primary Engine v2.2 Report','',f"Dataset: **{rep['rows']} rows**, {rep['date_range'][0]} → {rep['date_range'][1]}",'',
        '## V2.2 election architecture','Champion/challenger gating with asymmetric incumbent protection. STRONG/MODERATE/WEAK/FAILING incumbent tiers receive progressively lower replacement friction. Paired rank evidence and a Top-5 damage budget are retained, while failing incumbents may be replaced rapidly or yield `NO_QUALIFIED_PRIMARY` rather than being locked in.','',
        '## Temporal methodology','For each target (`t-1`), engines receive only history ending at the immediately preceding row (`t-2`). Rankings and election are frozen first. The target result is appended to performance profiles only after election.','',
        '## House-wise results','',
        '| House | Targets | Elected | Abstain | Coverage | Top5/elected | Top10/elected | Top21/elected | Top36/elected | MRR | Mean rank | Switches | Current |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for h,m in rep['house_metrics'].items():
        md.append(f"| {h} | {m['targets']} | {m['elected_targets']} | {m['abstentions']} | {m['election_coverage_pct']}% | {m['primary_top5_pct_elected']}% | {m['primary_top10_pct_elected']}% | {m['primary_top21_pct_elected']}% | {m['primary_top36_pct_elected']}% | {m['mrr_elected']} | {m['mean_rank_elected']} | {m['switches']} | {m['current_primary']} |")
    md += ['', '## Interpretation','V2.2 is allowed to abstain and uses tier-dependent challenger proof rather than universal champion protection. Therefore conditional hit rates on elected targets must be read together with election coverage; lower coverage can inflate conditional metrics. The all-target Top-5 measure is retained in JSON to prevent selective-reporting bias. Random ranking references remain Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%.','',
           '## Integrity conclusion','V2.2 preserves prior-only election ordering while making champion protection asymmetric to avoid weak-incumbent lock-in. Election and route qualification are now performed entirely from previously completed targets, followed by immutable freeze and only then outcome evaluation.']
    (out/'DHAPPA_DYNAMIC_PRIMARY_ENGINE_V2_2_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    return rep
