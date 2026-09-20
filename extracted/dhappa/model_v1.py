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
    if not evals:return {'n':0,'h5':0,'h10':0,'h21':0,'h36':0,'mrr':0,'median_rank':101,'mean_rank':101,'stability':0}
    n=len(evals); ranks=[e.rank for e in evals]
    h=lambda k: sum(e.rank<=k for e in evals)/n
    # stability from 15-vs-expanding gap and rank variance
    recent=evals[-15:]; recent_h=sum(e.rank<=10 for e in recent)/len(recent)
    long_h=h(10); stability=max(0,1-abs(recent_h-long_h)-min(statistics.pstdev(ranks)/100,0.5))
    return {'n':n,'h5':h(5),'h10':h(10),'h21':h(21),'h36':h(36),'mrr':sum(e.reciprocal_rank for e in evals)/n,'median_rank':statistics.median(ranks),'mean_rank':sum(ranks)/n,'stability':stability}

def score_metric(m):
    if m['n']<12:return -999
    sample=min(1,m['n']/60)
    # no arbitrary probability; election utility only
    return sample*(0.34*m['h5']+0.22*m['h10']+0.12*m['h21']+0.07*m['h36']+0.15*m['mrr']+0.10*m['stability'])

def jaccard_top(a,b,k=21):
    A=set(a[:k]);B=set(b[:k]);u=len(A|B);return len(A&B)/u if u else 0

def fuse(rankings:Dict[str,List[str]], members:Tuple[str,...], reliability:Dict[str,float], independence:Dict[Tuple[str,str],float]):
    s=defaultdict(float)
    for e in members:
        rel=max(.05,reliability.get(e,.1))
        redundancy=[]
        for o in members:
            if o!=e: redundancy.append(independence.get(tuple(sorted((e,o))),0))
        pen=(sum(redundancy)/len(redundancy)) if redundancy else 0
        weight=rel*(1-0.55*pen)
        for i,p in enumerate(rankings[e][:50]): s[p]+=weight/(3+i)
    return sorted(ALL,key=lambda p:(-s[p],p))

def window_metrics(evs):
    return {str(w):metric(evs[-w:]) for w in (15,30,60)} | {'expanding':metric(evs)}

def run_walkforward(rows,min_train=45,max_combo=3):
    evals=[]; combo_evals=[]; timeline=[]; prev_primary={h:None for h in HOUSES}; switches=Counter()
    profiles=defaultdict(lambda:defaultdict(list)); combo_profiles=defaultdict(lambda:defaultdict(list))
    for i in range(min_train,len(rows)):
        target=rows[i]; history=rows[:i]  # target is t-1; history ends at t-2
        cutoff=history[-1]['date']
        for house in HOUSES:
            actual=target.get(house)
            if not actual: continue
            outputs={e.name:e.rank(history,house,target['date']) for e in ENGINES}
            rankings={k:v.ranking for k,v in outputs.items()}
            # freeze singles before reveal
            for name,ranked in rankings.items():
                r=ranked.index(actual)+1
                ev=Eval(target['date'],cutoff,house,name,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,hash_prediction(target['date'],cutoff,house,name,ranked))
                evals.append(ev); profiles[house][name].append(ev)
            # prior-only reliability and independence
            rel={name:max(.001,score_metric(metric(profiles[house][name][:-1]))) for name in rankings}
            names=list(rankings)
            qualified_names=sorted(names,key=lambda n:rel[n],reverse=True)[:6]
            indep={}
            for a,b in combinations(names,2): indep[tuple(sorted((a,b)))]=jaccard_top(rankings[a],rankings[b])
            # build candidates using ONLY prior evals; current single outcome was appended, so strip current via[:-1]
            candidates=[]
            for name in names:
                m=metric(profiles[house][name][:-1]); sc=score_metric(m)
                if sc>-900: candidates.append(((name,),sc,rankings[name],m))
            # qualified pairs/triplets based on prior performance if enough history
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem)
                    past=combo_profiles[house][key]
                    pm=metric(past); best=max((score_metric(metric(profiles[house][x][:-1])) for x in mem),default=-999)
                    if pm['n']>=15:
                        inc=score_metric(pm)-best
                        redundancy=sum(indep[tuple(sorted(x))] for x in combinations(mem,2))/max(1,len(list(combinations(mem,2))))
                        qscore=score_metric(pm)+max(0,inc)*.6-redundancy*.08
                        if inc>0.005 and redundancy<0.75: candidates.append((mem,qscore,None,pm))
            candidates.sort(key=lambda x:x[1],reverse=True)
            primary_mem=candidates[0][0] if candidates else (max(names,key=lambda n:rel[n]),)
            primary_rank=rankings[primary_mem[0]] if len(primary_mem)==1 else fuse(rankings,primary_mem,rel,indep)
            secondary=None
            for cand in candidates[1:]:
                if set(cand[0]).isdisjoint(set(primary_mem)):
                    secondary=cand[0];break
            # Current combination evals are now frozen and then judged
            for size in range(2,max_combo+1):
                for mem in combinations(qualified_names,size):
                    key='+'.join(mem); ranked=fuse(rankings,mem,rel,indep); r=ranked.index(actual)+1
                    ev=Eval(target['date'],cutoff,house,key,actual,r,r<=5,r<=10,r<=21,r<=36,1/r,hash_prediction(target['date'],cutoff,house,key,ranked))
                    combo_evals.append(ev); combo_profiles[house][key].append(ev)
            pr=primary_rank.index(actual)+1
            primary_name='+'.join(primary_mem)
            if prev_primary[house] and prev_primary[house]!=primary_name:switches[house]+=1
            prev_primary[house]=primary_name
            confidence='INSUFFICIENT_EVIDENCE'
            prior_n=min((metric(profiles[house][x][:-1])['n'] for x in primary_mem),default=0)
            if prior_n>=60: confidence='STRONG_EVIDENCE'
            elif prior_n>=30: confidence='MODERATE_EVIDENCE'
            elif prior_n>=15: confidence='WEAK_EVIDENCE'
            timeline.append({'date':target['date'],'source_cutoff':cutoff,'house':house,'primary':primary_name,'secondary':'+'.join(secondary) if secondary else None,'actual':actual,'actual_rank':pr,'hit5':pr<=5,'hit10':pr<=10,'hit21':pr<=21,'hit36':pr<=36,'confidence':confidence,'freeze_hash':hash_prediction(target['date'],cutoff,house,'PRIMARY:'+primary_name,primary_rank)})
    return evals,combo_evals,timeline,switches,profiles,combo_profiles

def report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles):
    house={}
    for h in HOUSES:
        tl=[x for x in timeline if x['house']==h]
        house[h]={
          'targets':len(tl),'primary_top5_pct':round(100*sum(x['hit5'] for x in tl)/max(1,len(tl)),2),
          'primary_top10_pct':round(100*sum(x['hit10'] for x in tl)/max(1,len(tl)),2),
          'primary_top21_pct':round(100*sum(x['hit21'] for x in tl)/max(1,len(tl)),2),
          'primary_top36_pct':round(100*sum(x['hit36'] for x in tl)/max(1,len(tl)),2),
          'mrr':round(sum(1/x['actual_rank'] for x in tl)/max(1,len(tl)),4),
          'median_rank':statistics.median([x['actual_rank'] for x in tl]) if tl else None,
          'mean_rank':round(sum(x['actual_rank'] for x in tl)/max(1,len(tl)),2),
          'switches':switches[h],
          'current_primary':tl[-1]['primary'] if tl else None,
        }
        leaders=[]
        for e,evs in profiles[h].items():
            m=metric(evs);leaders.append((score_metric(m),e,m))
        house[h]['single_leaders']=[{'engine':e,**{k:(round(v*100,2) if k in {'h5','h10','h21','h36','mrr','stability'} else round(v,2) if isinstance(v,float) else v) for k,v in m.items()}} for _,e,m in sorted(leaders,reverse=True)[:5]]
        combos=[]
        for k,evs in combo_profiles[h].items():
            m=metric(evs); best=max((metric(profiles[h][x])['h10'] for x in k.split('+')),default=0); inc=m['h10']-best
            if m['n']>=30: combos.append((score_metric(m),k,m,inc))
        house[h]['combination_leaders']=[{'combination':k,'incremental_top10':round(inc*100,2),**{kk:(round(v*100,2) if kk in {'h5','h10','h21','h36','mrr','stability'} else round(v,2) if isinstance(v,float) else v) for kk,v in m.items()}} for _,k,m,inc in sorted(combos,reverse=True)[:5]]
    return {'model':'DHAPPA Dynamic Primary Engine Scratch v1.0','rows':len(rows),'date_range':[rows[0]['date'],rows[-1]['date']],'strict_temporal_rule':'for target row t-1, engine history ends at immediately preceding row t-2; prediction hash frozen before outcome evaluation','engine_count':len(ENGINES),'engines':[{'name':e.name,'family':e.family} for e in ENGINES],'house_metrics':house}

def save_all(root,rows,evals,combo_evals,timeline,switches,profiles,combo_profiles):
    out=Path(root)/'reports'; out.mkdir(parents=True,exist_ok=True)
    rep=report(rows,evals,combo_evals,timeline,switches,profiles,combo_profiles)
    def dump(name,obj): (out/name).write_text(json.dumps(obj,indent=2,default=str),encoding='utf-8')
    dump('dynamic_primary_engine_backtest.json',rep)
    dump('primary_engine_election_timeline.json',timeline)
    dump('single_engine_performance.json',{h:{e:window_metrics(v) for e,v in profiles[h].items()} for h in HOUSES})
    dump('engine_combination_performance.json',{h:{e:window_metrics(v) for e,v in combo_profiles[h].items()} for h in HOUSES})
    # failure classification
    failures=[]
    for x in timeline:
        if x['actual_rank']>36: typ='GENERATION_OR_DEEP_RANK_FAILURE'
        elif x['actual_rank']>5: typ='RANKING_FAILURE'
        else: typ='HIT'
        failures.append({**x,'failure_type':typ})
    dump('generation_vs_ranking_failure.json',failures)
    integrity={'no_current_target_used_for_generation':True,'history_slice':'rows[:target_index]','freeze_hash':'sha256(date,cutoff,house,engine,ranking)','evaluated_after_freeze':True,'notes':['Target date itself may be used as calendar metadata; target outcome is never passed to engines.','Combination election uses only prior combination evaluations; current target is appended only after election/freeze.']}
    dump('primary_engine_integrity_report.json',integrity)
    md=['# DHAPPA Dynamic Primary Engine Report','',f"Dataset: **{rep['rows']} rows**, {rep['date_range'][0]} → {rep['date_range'][1]}",'', '## Methodology','Strict walk-forward: for each target row (`t-1`), only rows ending at the immediately preceding row (`t-2`) are supplied to engines. Rankings are hashed before the target outcome is evaluated.','', '## Engines']
    md += [f"- {e['name']} ({e['family']})" for e in rep['engines']]
    md += ['', '## House-wise Dynamic Primary Results','', '| House | Targets | Top5 | Top10 | Top21 | Top36 | MRR | Mean rank | Switches | Current primary |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for h,m in rep['house_metrics'].items(): md.append(f"| {h} | {m['targets']} | {m['primary_top5_pct']}% | {m['primary_top10_pct']}% | {m['primary_top21_pct']}% | {m['primary_top36_pct']}% | {m['mrr']} | {m['mean_rank']} | {m['switches']} | {m['current_primary']} |")
    md += ['', '## Interpretation','This is a research backtest, not a probability claim. A large candidate tier has a correspondingly large random baseline (Top-5=5%, Top-10=10%, Top-21=21%, Top-36=36%). Selection value should therefore be judged by rank quality, stability, and forward lift rather than raw coverage alone.','', '## Integrity conclusion','The scratch model removes UI coupling and enforces one temporal kernel, immutable prediction hashes, house-wise election, prior-only engine/combination profiles, and explicit ranking-failure logging.']
    (out/'DHAPPA_DYNAMIC_PRIMARY_ENGINE_REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    return rep
