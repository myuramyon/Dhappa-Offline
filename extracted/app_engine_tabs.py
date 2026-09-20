from __future__ import annotations
import csv, io, json, os, sys, webbrowser, threading, shutil, hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dhappa import model_v2_5 as core
from dhappa_logging import log as audit_log, log_exception, sha256_file

DATA_PATH = ROOT / 'data' / 'Merged_Workbook.csv'
BACKUP_DIR = ROOT / 'data' / 'backups'
METRICS_PATH = ROOT / 'reports' / 'single_engine_performance.json'
CONS_METRICS_PATH = ROOT / 'reports' / 'consensus36_performance.json'
CONS_WEIGHTS_PATH = ROOT / 'reports' / 'consensus36_weights.json'
WF_ENGINE_PATH = ROOT / 'reports' / 'engine_walkforward_validation.json'
WF_ENGINE_HITS_PATH = ROOT / 'reports' / 'engine_house_hit_rates.json'
WF_WINDOW_PATH = ROOT / 'reports' / 'engine_window_metrics.json'
WF_CONS_PATH = ROOT / 'reports' / 'consensus_walkforward_validation.json'
WF_CONS_HITS_PATH = ROOT / 'reports' / 'consensus_house_hit_rates.json'
WF_HISTORY_PATH = ROOT / 'reports' / 'walkforward_history.jsonl'
WF_FAILURE_PATH = ROOT / 'reports' / 'walkforward_failure_analysis.json'
WF_INTEGRITY_PATH = ROOT / 'reports' / 'walkforward_integrity_report.json'
DAYWISE_PATH = ROOT / 'reports' / 'daywise_walkforward_validation.jsonl'
HOUSE_DAILY_PATH = ROOT / 'reports' / 'house_daily_hit_summary.json'
LEADERBOARD_PATH = ROOT / 'reports' / 'engine_house_leaderboard.json'
BEST_ENGINE_PATH = ROOT / 'reports' / 'best_engine_by_house.json'
SWEEP_PATH = ROOT / 'reports' / 'walkforward_sweep_summary.json'
WINDOW_PERFORMANCE_PATH = ROOT / 'reports' / 'engine_window_performance.json'
DATA_LOCK = threading.RLock()

CONS_WEIGHTS_DEFAULT={
 'DATE_TRIAD':1.50,'PREVIOUS_DAY':1.10,'DELTA_MATRIX':0.90,'G_SQUARE':1.00,
 'G_SQUARE_HARMONICS':1.00,'HARUF_PYRAMID':1.20,'LOOKBACK_5':1.00,'ECHO_7':0.80,
 'HOT_RECENCY':0.70,'RASHI_FAMILY':0.90,'TRANSITION_MARKOV':1.20,'MODEL_F':1.30,
}

def _load_json(path, default):
    try: return json.load(open(path, encoding='utf-8')) if path.exists() else default
    except Exception: return default

ROWS = core.load_csv(DATA_PATH)
METRICS = _load_json(METRICS_PATH,{})
CONS_METRICS = _load_json(CONS_METRICS_PATH,{})
CONS_WEIGHTS = _load_json(CONS_WEIGHTS_PATH,CONS_WEIGHTS_DEFAULT)
WALKFORWARD = {'engines':{},'consensus':{},'integrity':{}}
ENGINE_MAP = {e.name: e for e in core.ENGINES}
ENGINE_ORDER = [e.name for e in core.ENGINES]
ENGINE_FAMILY = {e.name: e.family for e in core.ENGINES}
ENGINE_DESCRIPTIONS = {
    'DATE_TRIAD':'Calendar/date-derived anchors with reverse and mirror extensions.',
    'PREVIOUS_DAY':'Previous-house-result transformations and digit arithmetic.',
    'DELTA_MATRIX':'Two-step digit delta propagation and transformed variants.',
    'G_SQUARE':'G-Square digit field derived from the latest house result.',
    'G_SQUARE_HARMONICS':'Expanded harmonic digit field around the G-Square source.',
    'HARUF_PYRAMID':'Recent digit-frequency Haruf layers and pyramid transforms.',
    'LOOKBACK_5':'Five-draw recency, palti/mirror and root-family reinforcement.',
    'ECHO_7':'7/14/21-lag echo recurrence with palti and mirror support.',
    'HOT_RECENCY':'Decay-weighted historical frequency plus bounded gap bonus.',
    'RASHI_FAMILY':'Root-family concentration with recent reverse/mirror support.',
    'TRANSITION_MARKOV':'Observed pair/digit transitions from the latest house state.',
    'MODEL_F':'Composite rank fusion across selected core engines.'
}

ALIASES={
 'date':'Date','drawdate':'Date','draw_date':'Date',
 'deshawar':'Deshawar','ds':'Deshawar','dswr':'Deshawar',
 'faridabad':'Faridabad','fb':'Faridabad','frbd':'Faridabad',
 'ghaziabad':'Ghaziabad','gb':'Ghaziabad','gzbd':'Ghaziabad',
 'gali':'Gali','gl':'Gali',
}

def consensus36(rankings_by_engine):
    score=defaultdict(float); supporters=defaultdict(list); contribution=defaultdict(dict)
    for eng_name, ranking in rankings_by_engine.items():
        top=ranking[:36]; n=max(1,len(top)); w=float(CONS_WEIGHTS.get(eng_name,1.0))
        for idx,cand in enumerate(top):
            c=w*((n-idx)/n); score[cand]+=c; supporters[cand].append(eng_name); contribution[cand][eng_name]=round(c,6)
    ranked=sorted([f'{i:02d}' for i in range(100)],key=lambda c:(-score[c],-len(supporters[c]),c))
    details=[{'rank':i+1,'number':c,'score':round(score[c],6),'support_count':len(supporters[c]),'engines':supporters[c],'contributions':contribution[c]} for i,c in enumerate(ranked[:36])]
    return ranked,details

def metric(events):
    if not events:return {'n':0,'h5':0,'h10':0,'h21':0,'h36':0,'mrr':0,'median_rank':101,'mean_rank':101}
    ranks=sorted(e['rank'] for e in events); n=len(ranks)
    med=ranks[n//2] if n%2 else (ranks[n//2-1]+ranks[n//2])/2
    return {'n':n,'h5':sum(r<=5 for r in ranks)/n,'h10':sum(r<=10 for r in ranks)/n,'h21':sum(r<=21 for r in ranks)/n,'h36':sum(r<=36 for r in ranks)/n,'mrr':sum(1/r for r in ranks)/n,'median_rank':med,'mean_rank':sum(ranks)/n}

def windows(events):
    out={str(w):metric(events[-w:]) for w in (15,30,60)}; out['expanding']=metric(events); return out

def freeze_hash(rows):
    raw=json.dumps(rows,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]

def wf_record(target, source_cutoff, actual, ranking, source):
    generation=bool(ranking)
    rank=ranking.index(actual)+1 if generation and actual in ranking else None
    failure=None if rank is not None else 'GENERATION_FAILURE' if not generation else 'RANKING_FAILURE'
    return {'target_date':target,'source_cutoff':source_cutoff,'actual':actual,'actual_rank':rank,'top5':bool(rank and rank<=5),'top10':bool(rank and rank<=10),'top21':bool(rank and rank<=21),'top36':bool(rank and rank<=36),'hit':bool(rank and rank<=36),'failure':failure,'freeze_hash':freeze_hash(source),'ranking':ranking[:36] if ranking else []}

def wf_summary(records):
    evaluated=[r for r in records if r['actual_rank'] is not None]
    ranks=[r['actual_rank'] for r in evaluated]
    n=len(evaluated)
    if n:
        ordered=sorted(ranks); med=ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2
        result={'samples':n,'h5':sum(r<=5 for r in ranks)/n,'h10':sum(r<=10 for r in ranks)/n,'h21':sum(r<=21 for r in ranks)/n,'h36':sum(r<=36 for r in ranks)/n,'mrr':sum(1/r for r in ranks)/n,'mean_rank':sum(ranks)/n,'median_rank':med,'best_rank':min(ranks),'worst_rank':max(ranks)}
    else: result={'samples':0,'h5':0,'h10':0,'h21':0,'h36':0,'mrr':0,'mean_rank':None,'median_rank':None,'best_rank':None,'worst_rank':None}
    failures=[r for r in records if r['failure']]
    result.update({'generation_failures':sum(r['failure']=='GENERATION_FAILURE' for r in failures),'ranking_failures':sum(r['failure']=='RANKING_FAILURE' for r in failures),'generation_failure_pct':sum(r['failure']=='GENERATION_FAILURE' for r in failures)/len(records) if records else 0,'ranking_failure_pct':sum(r['failure']=='RANKING_FAILURE' for r in failures)/len(records) if records else 0,'evidence':'INSUFFICIENT_EVIDENCE' if n<30 else 'STRONG_EVIDENCE' if result['h5']>=.15 else 'MODERATE_EVIDENCE' if result['h5']>=.07 else 'WEAK_EVIDENCE'})
    return result

def build_walkforward():
    engine_records={n:{h:[] for h in core.HOUSES} for n in ENGINE_ORDER}; consensus_records={h:[] for h in core.HOUSES}; history=[]; integrity=[]
    for i in range(15,len(ROWS)):
        source=ROWS[:i]; target=ROWS[i]; cutoff=source[-1]['date'] if source else None; by_house={h:{} for h in core.HOUSES}
        for name in ENGINE_ORDER:
            for house in core.HOUSES:
                out=ENGINE_MAP[name].rank(source,house,target['date']); ranking=out.ranking if out and getattr(out,'ranking',None) else []
                by_house[house][name]=ranking
                record=wf_record(target['date'],cutoff,target.get(house),ranking,source); record.update({'model':name,'house':house,'weekday':datetime.strptime(target['date'],'%Y-%m-%d').strftime('%A'),'parity':'odd' if target.get(house) and int(target[house])%2 else 'even' if target.get(house) else None})
                engine_records[name][house].append(record); history.append(record)
                integrity.append({'model':name,'house':house,'target_date':target['date'],'source_cutoff':cutoff,'pass':bool(cutoff and cutoff<target['date'])})
        for house in core.HOUSES:
            ranking,_=consensus36(by_house[house]); record=wf_record(target['date'],cutoff,target.get(house),ranking,source); record.update({'model':'CONSENSUS_36','house':house,'weekday':datetime.strptime(target['date'],'%Y-%m-%d').strftime('%A'),'parity':'odd' if target.get(house) and int(target[house])%2 else 'even' if target.get(house) else None}); consensus_records[house].append(record); history.append(record); integrity.append({'model':'CONSENSUS_36','house':house,'target_date':target['date'],'source_cutoff':cutoff,'pass':bool(cutoff and cutoff<target['date'])})
    engine_metrics={n:{h:{'15':wf_summary(records[-15:]),'30':wf_summary(records[-30:]),'60':wf_summary(records[-60:]),'expanding':wf_summary(records)} for h,records in houses.items()} for n,houses in engine_records.items()}; consensus_metrics={h:{'15':wf_summary(records[-15:]),'30':wf_summary(records[-30:]),'60':wf_summary(records[-60:]),'expanding':wf_summary(records)} for h,records in consensus_records.items()}
    failed=[x for x in integrity if not x['pass']]; data={'engines':engine_records,'consensus':consensus_records,'engine_metrics':engine_metrics,'consensus_metrics':consensus_metrics,'integrity':{'records':len(integrity),'failures':len(failed),'pass':not failed}}
    data.update(build_daywise_outputs(data))
    ROOT.joinpath('reports').mkdir(exist_ok=True)
    WF_ENGINE_PATH.write_text(json.dumps(engine_records,indent=2),encoding='utf-8'); WF_ENGINE_HITS_PATH.write_text(json.dumps({n:{h:metrics['expanding'] for h,metrics in houses.items()} for n,houses in engine_metrics.items()},indent=2),encoding='utf-8'); WF_WINDOW_PATH.write_text(json.dumps(engine_metrics,indent=2),encoding='utf-8'); WF_CONS_PATH.write_text(json.dumps(consensus_records,indent=2),encoding='utf-8'); WF_CONS_HITS_PATH.write_text(json.dumps({h:metrics['expanding'] for h,metrics in consensus_metrics.items()},indent=2),encoding='utf-8'); WF_HISTORY_PATH.write_text('\n'.join(json.dumps(r) for r in history)+'\n',encoding='utf-8'); WF_FAILURE_PATH.write_text(json.dumps({'generation_failures':sum(r['failure']=='GENERATION_FAILURE' for r in history),'ranking_failures':sum(r['failure']=='RANKING_FAILURE' for r in history)},indent=2),encoding='utf-8'); WF_INTEGRITY_PATH.write_text(json.dumps(data['integrity'],indent=2),encoding='utf-8'); DAYWISE_PATH.write_text('\n'.join(json.dumps(r) for r in data['daywise'])+'\n',encoding='utf-8'); HOUSE_DAILY_PATH.write_text(json.dumps(data['house_daily'],indent=2),encoding='utf-8'); LEADERBOARD_PATH.write_text(json.dumps(data['leaderboard'],indent=2),encoding='utf-8'); BEST_ENGINE_PATH.write_text(json.dumps(data['best_engine'],indent=2),encoding='utf-8'); SWEEP_PATH.write_text(json.dumps(data['sweep_summary'],indent=2),encoding='utf-8'); WINDOW_PERFORMANCE_PATH.write_text(json.dumps(engine_metrics,indent=2),encoding='utf-8')
    return data

def build_daywise_outputs(data):
    models=[*ENGINE_ORDER,'CONSENSUS_36']; by_model={n:(data['consensus'] if n=='CONSENSUS_36' else data['engines'][n]) for n in models}
    def hit(record,tier): return bool(record.get('actual_rank') and record['actual_rank']<=tier)
    dates=sorted({r['target_date'] for rows in data['consensus'].values() for r in rows}); daywise=[]
    for date in dates:
        houses={}
        for house in core.HOUSES:
            record=next(r for r in by_model['CONSENSUS_36'][house] if r['target_date']==date)
            houses[house]={'actual':record['actual'],'rank':record['actual_rank'],'hit':hit(record,5),'source_cutoff':record['source_cutoff'],'freeze_hash':record['freeze_hash']}
        hits=sum(item['hit'] for item in houses.values()); daywise.append({'date':date,'day':datetime.strptime(date,'%Y-%m-%d').strftime('%A'),'houses':houses,'hits':hits,'misses':4-hits,'sweep':'FULL SWEEP' if hits==4 else 'STRONG DAY' if hits==3 else 'PARTIAL DAY' if hits==2 else 'WEAK DAY' if hits==1 else 'COMPLETE MISS'})
    leaderboards={}; best={}
    for house in core.HOUSES:
        rows=[]
        for model in models:
            metrics=data['consensus_metrics'][house] if model=='CONSENSUS_36' else data['engine_metrics'][model][house]; expanding=metrics['expanding']; recent30=metrics['30']; recent60=metrics['60']
            score=.45*expanding['h5']+.25*expanding['h10']+.15*expanding['mrr']+.10*recent30['h5']+.05*recent60['h5']
            rows.append({'model':model,'score':score,'h5':expanding['h5'],'h10':expanding['h10'],'h21':expanding['h21'],'h36':expanding['h36'],'mrr':expanding['mrr'],'samples':expanding['samples'],'recent30_h5':recent30['h5'],'recent60_h5':recent60['h5'],'evidence':expanding['evidence'],'windows':metrics})
        rows.sort(key=lambda row:(row['samples']>=30,row['score']),reverse=True)
        for rank,row in enumerate(rows,1): row['rank']=rank
        long_best=max(rows,key=lambda row:row['h5']); recent30_best=max(rows,key=lambda row:(row['samples']>=30,row['recent30_h5'])); recent60_best=max(rows,key=lambda row:(row['samples']>=30,row['recent60_h5'])); selected=rows[0]
        leaderboards[house]=rows; best[house]={'house':house,'tier':5,'best_engine':selected['model'],'hit_rate':selected['h5'],'hit_count':round(selected['h5']*selected['samples']),'samples':selected['samples'],'recent_30_hit_rate':selected['recent30_h5'],'recent_60_hit_rate':selected['recent60_h5'],'mrr':selected['mrr'],'long_term_best':long_best['model'],'recent_30_best':recent30_best['model'],'recent_60_best':recent60_best['model'],'regime_disagreement':len({long_best['model'],recent30_best['model'],recent60_best['model']})>1}
    sweep={str(tier):{'evaluated_days':len(daywise),'distribution':{str(n):sum(1 for row in daywise if sum(hit(next(r for r in by_model['CONSENSUS_36'][house] if r['target_date']==row['date']),tier) for house in core.HOUSES)==n) for n in range(5)}} for tier in (5,10,21,36)}
    return {'daywise':daywise,'house_daily':{'tier':5,'rows':daywise,'evaluated_days':len(daywise),'average_houses_hit':sum(row['hits'] for row in daywise)/len(daywise) if daywise else 0},'leaderboard':leaderboards,'best_engine':best,'sweep_summary':sweep}

def ensure_walkforward():
    global WALKFORWARD
    if not WALKFORWARD.get('engine_metrics') and WF_ENGINE_PATH.exists() and WF_CONS_PATH.exists():
        WALKFORWARD={'engines':_load_json(WF_ENGINE_PATH,{}),'consensus':_load_json(WF_CONS_PATH,{}),'engine_metrics':_load_json(WF_WINDOW_PATH,{}),'consensus_metrics':_load_json(CONS_METRICS_PATH,{}),'integrity':_load_json(WF_INTEGRITY_PATH,{})}
    return WALKFORWARD

def house_name(value):
    return {'DS':'Deshawar','FB':'Faridabad','GB':'Ghaziabad','GL':'Gali'}.get(str(value or '').upper(), value)

def walkforward_view(model, house, window, start=None, end=None):
    data=ensure_walkforward(); house=house_name(house) or core.HOUSES[0]; window=window if window in {'15','30','60','expanding'} else 'expanding'
    records=data.get('consensus',{}).get(house,[]) if model=='CONSENSUS_36' else data.get('engines',{}).get(model,{}).get(house,[])
    if not records:
        records=build_walkforward_subset(model,house)
    records=[r for r in records if (not start or r['target_date']>=start) and (not end or r['target_date']<=end)]
    return {'ok':True,'model':model,'house':house,'window':window,'metrics':wf_summary(records[-15:] if window=='15' else records[-30:] if window=='30' else records[-60:] if window=='60' else records),'records':records}

def build_walkforward_subset(model, house):
    records=[]; names=ENGINE_ORDER if model=='CONSENSUS_36' else [model]
    for i in range(15,len(ROWS)):
        source=ROWS[:i]; target=ROWS[i]; rankings={}
        for name in names:
            out=ENGINE_MAP[name].rank(source,house,target['date']); rankings[name]=out.ranking if out and getattr(out,'ranking',None) else []
        ranking=consensus36(rankings)[0] if model=='CONSENSUS_36' else rankings[model]
        record=wf_record(target['date'],source[-1]['date'],target.get(house),ranking,source)
        record.update({'model':model,'house':house,'weekday':datetime.strptime(target['date'],'%Y-%m-%d').strftime('%A'),'parity':'odd' if target.get(house) and int(target[house])%2 else 'even' if target.get(house) else None})
        records.append(record)
    return records

def ensure_daywise():
    data=ensure_walkforward()
    if 'daywise' not in data:
        data.update(build_daywise_outputs(data))
    return data

def daywise_response(params):
    data=ensure_daywise(); model=(params.get('model') or params.get('engine') or ['CONSENSUS_36'])[0]; model='CONSENSUS_36' if str(model).upper() in {'ALL','CONSENSUS','CONSENSUS_36'} else str(model).upper().replace('-','_')
    try: tier=int((params.get('tier') or ['5'])[0]); tier=tier if tier in {5,10,21,36} else 5
    except ValueError: tier=5
    start=(params.get('from') or [''])[0]; end=(params.get('to') or [''])[0]; source=data['consensus'] if model=='CONSENSUS_36' else data['engines'].get(model,{})
    dates=sorted({r['target_date'] for rows in source.values() for r in rows}); rows=[]
    abbreviations={'Deshawar':'DS','Faridabad':'FB','Ghaziabad':'GB','Gali':'GL'}
    for date in dates:
        if start and date<start or end and date>end: continue
        houses={}
        for house in core.HOUSES:
            record=next(r for r in source[house] if r['target_date']==date); houses[abbreviations[house]]={'actual':record['actual'],'hit':bool(record['actual_rank'] and record['actual_rank']<=tier),'rank':record['actual_rank'],'freeze_hash':record['freeze_hash']}
        hits=sum(item['hit'] for item in houses.values()); rows.append({'date':date,'day':datetime.strptime(date,'%Y-%m-%d').strftime('%A'),'houses':houses,'hits':hits,'misses':4-hits,'sweep':'FULL SWEEP' if hits==4 else 'STRONG DAY' if hits==3 else 'PARTIAL DAY' if hits==2 else 'WEAK DAY' if hits==1 else 'COMPLETE MISS'})
    return {'ok':True,'model':model,'tier':tier,'data':rows,'summary':{'evaluated_days':len(rows),'sweeps':sum(r['hits']==4 for r in rows),'strong_days':sum(r['hits']==3 for r in rows),'partial_days':sum(r['hits']==2 for r in rows),'weak_days':sum(r['hits']==1 for r in rows),'complete_miss_days':sum(r['hits']==0 for r in rows),'average_houses_hit':sum(r['hits'] for r in rows)/len(rows) if rows else 0}}

def leaderboard_response(house, tier, window):
    data=ensure_walkforward(); house=house_name(house) or 'Deshawar'; window=window if window in {'15','30','60','expanding'} else 'expanding'; models=[*ENGINE_ORDER,'CONSENSUS_36']; rows=[]
    for model in models:
        metrics=(data['consensus_metrics'][house] if model=='CONSENSUS_36' else data['engine_metrics'][model][house])[window]; rows.append({'model':model,**metrics})
    rows.sort(key=lambda row:(row['samples']>=30,row[f'h{tier}']),reverse=True)
    for rank,row in enumerate(rows,1): row['rank']=rank
    return {'ok':True,'house':house,'tier':tier,'window':window,'models':rows}

def rebuild_metrics():
    global METRICS,CONS_METRICS,WALKFORWARD
    started=datetime.utcnow().isoformat()+'Z'
    audit_log('metrics','rebuild_start',row_count=len(ROWS),engine_count=len(ENGINE_ORDER),houses=list(core.HOUSES))
    WALKFORWARD=build_walkforward()
    METRICS={h:{n:WALKFORWARD['engine_metrics'][n][h] for n in ENGINE_ORDER} for h in core.HOUSES}
    CONS_METRICS=WALKFORWARD['consensus_metrics']
    ROOT.joinpath('reports').mkdir(exist_ok=True)
    METRICS_PATH.write_text(json.dumps(METRICS,indent=2),encoding='utf-8')
    CONS_METRICS_PATH.write_text(json.dumps(CONS_METRICS,indent=2),encoding='utf-8')
    CONS_WEIGHTS_PATH.write_text(json.dumps(CONS_WEIGHTS,indent=2),encoding='utf-8')
    audit_log('metrics','rebuild_complete',started_utc=started,row_count=len(ROWS),engine_count=len(ENGINE_ORDER),houses=list(core.HOUSES),metrics_path=str(METRICS_PATH),consensus_metrics_path=str(CONS_METRICS_PATH))

def strict_number(v, field):
    if v is None:return None
    s=str(v).strip()
    if not s or s.lower() in {'nan','none','xx','x','-','na','n/a'}: return None
    try:
        x=int(float(s))
        if 0<=x<=99:return f'{x:02d}'
    except: pass
    raise ValueError(f'{field}: invalid value {v!r}; expected 00-99 or blank')

def canonical_header(name):
    key=str(name).strip().lower().replace(' ','').replace('-','_')
    return ALIASES.get(key)

def parse_import_text(text, has_header=True):
    text=(text or '').replace('\ufeff','').strip()
    if not text:return [],['No data supplied']
    errors=[]; parsed=[]
    if has_header:
        reader=csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:return [],['CSV header is missing']
        colmap={f:canonical_header(f) for f in reader.fieldnames}
        if 'Date' not in colmap.values():return [],['Missing Date column']
        for line_no,r in enumerate(reader,start=2):
            try:
                normalized={}
                for src,val in r.items():
                    dst=colmap.get(src)
                    if dst: normalized[dst]=val
                d=core.parse_date(str(normalized.get('Date','')).strip()).strftime('%Y-%m-%d')
                row={'date':d}
                for h in core.HOUSES: row[h]=strict_number(normalized.get(h,''),h)
                if not any(row[h] for h in core.HOUSES): raise ValueError('all four house values are blank')
                parsed.append(row)
            except Exception as e: errors.append(f'Line {line_no}: {e}')
    else:
        for line_no,line in enumerate(text.splitlines(),start=1):
            if not line.strip():continue
            try:
                parts=[x.strip() for x in next(csv.reader([line]))]
                if len(parts)!=5: raise ValueError('expected 5 fields: Date, Deshawar, Faridabad, Ghaziabad, Gali')
                d=core.parse_date(parts[0]).strftime('%Y-%m-%d')
                row={'date':d,'Deshawar':strict_number(parts[1],'Deshawar'),'Faridabad':strict_number(parts[2],'Faridabad'),'Ghaziabad':strict_number(parts[3],'Ghaziabad'),'Gali':strict_number(parts[4],'Gali')}
                if not any(row[h] for h in core.HOUSES): raise ValueError('all four house values are blank')
                parsed.append(row)
            except Exception as e:errors.append(f'Line {line_no}: {e}')
    # Merge duplicate dates within import, later nonblank values win.
    merged={}
    for r in parsed:
        if r['date'] not in merged:merged[r['date']]=r.copy()
        else:
            for h in core.HOUSES:
                if r[h] is not None:merged[r['date']][h]=r[h]
    return [merged[k] for k in sorted(merged)],errors

def import_preview(text, has_header=True):
    rows,errors=parse_import_text(text,has_header)
    rows_desc=sorted(rows,key=lambda r:r['date'],reverse=True)
    existing={r['date']:r for r in ROWS}
    duplicate=sum(1 for r in rows if r['date'] in existing)
    new=sum(1 for r in rows if r['date'] not in existing)
    changes=0
    for r in rows:
        old=existing.get(r['date'])
        if old and any(r[h] is not None and r[h]!=old.get(h) for h in core.HOUSES):changes+=1
    preview_rows=[]
    for row in rows_desc:
        old=existing.get(row['date'])
        changed={h:{'existing':old.get(h),'incoming':row.get(h)} for h in core.HOUSES if old and row.get(h) is not None and row.get(h)!=old.get(h)}
        status='NEW' if old is None else 'UPDATE' if changed else 'UNCHANGED'
        preview_rows.append({**row,'status':status,'existing':old.copy() if old else None,'changes':changed})
    result={'valid_rows':len(rows),'error_count':len(errors),'errors':errors[:100],'new_dates':new,'duplicate_dates':duplicate,'dates_with_changes':changes,'first_date':rows_desc[0]['date'] if rows_desc else None,'last_date':rows_desc[-1]['date'] if rows_desc else None,'rows':preview_rows,'sample':preview_rows[:8]}
    audit_log('imports','preview',has_header=has_header,valid_rows=result['valid_rows'],error_count=result['error_count'],new_dates=new,duplicate_dates=duplicate,dates_with_changes=changes,first_date=result['first_date'],last_date=result['last_date'],payload_bytes=len((text or '').encode('utf-8')))
    return result

def save_rows(rows):
    DATA_PATH.parent.mkdir(exist_ok=True); BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    if DATA_PATH.exists():
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path=BACKUP_DIR/f'Merged_Workbook_before_{stamp}.csv'
        shutil.copy2(DATA_PATH,backup_path)
        audit_log('changes','data_backup_created',path=str(backup_path),sha256=sha256_file(backup_path),bytes=backup_path.stat().st_size)
    tmp=DATA_PATH.with_suffix('.csv.tmp')
    with open(tmp,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['Date','Deshawar','Faridabad','Gali','Ghaziabad']);w.writeheader()
        for r in rows:w.writerow({'Date':r['date'],'Deshawar':r.get('Deshawar') or '','Faridabad':r.get('Faridabad') or '','Gali':r.get('Gali') or '','Ghaziabad':r.get('Ghaziabad') or ''})
    os.replace(tmp,DATA_PATH)
    audit_log('changes','dataset_saved',path=str(DATA_PATH),rows=len(rows),sha256=sha256_file(DATA_PATH),bytes=DATA_PATH.stat().st_size)

def commit_import(text, has_header=True, strategy='merge'):
    global ROWS
    incoming,errors=parse_import_text(text,has_header)
    if errors: raise ValueError('Import rejected; fix validation errors first: '+errors[0])
    if not incoming: raise ValueError('No valid rows to import')
    with DATA_LOCK:
        before_count=len(ROWS)
        before_last=ROWS[-1]['date'] if ROWS else None
        if strategy=='replace': final=incoming
        else:
            merged={r['date']:r.copy() for r in ROWS}
            for r in incoming:
                if r['date'] not in merged:merged[r['date']]=r.copy()
                else:
                    for h in core.HOUSES:
                        if r[h] is not None:merged[r['date']][h]=r[h]
            final=[merged[k] for k in sorted(merged)]
        save_rows(final); ROWS=core.load_csv(DATA_PATH); rebuild_metrics()
    result={'ok':True,'rows_after_import':len(ROWS),'first_date':ROWS[0]['date'],'last_date':ROWS[-1]['date'],'strategy':strategy,'metrics_rebuilt':True}
    audit_log('imports','commit',strategy=strategy,has_header=has_header,incoming_rows=len(incoming),rows_before=before_count,rows_after=len(ROWS),last_date_before=before_last,last_date_after=result['last_date'],dataset_sha256=sha256_file(DATA_PATH))
    return result

def daily_api_row(row):
    return {'date':row['date'],'day':datetime.strptime(row['date'],'%Y-%m-%d').strftime('%A'),'DS':row.get('Deshawar'),'FB':row.get('Faridabad'),'GB':row.get('Ghaziabad'),'GL':row.get('Gali')}

def daily_query(params):
    with DATA_LOCK:
        source=[r.copy() for r in ROWS]
    start=(params.get('from') or [''])[0]
    end=(params.get('to') or [''])[0]
    house=(params.get('house') or ['ALL'])[0].upper()
    search=(params.get('search') or [''])[0].strip().lower()
    sort=(params.get('sort') or ['newest'])[0].lower()
    if start: source=[r for r in source if r['date']>=start]
    if end: source=[r for r in source if r['date']<=end]
    if house in {'DS','FB','GB','GL'}:
        field={'DS':'Deshawar','FB':'Faridabad','GB':'Ghaziabad','GL':'Gali'}[house]
        source=[r for r in source if r.get(field) is not None]
    if search:
        source=[r for r in source if search in r['date'].lower() or search in datetime.strptime(r['date'],'%Y-%m-%d').strftime('%d-%m-%Y').lower() or any(search in str(r.get(h) or '').lower() for h in core.HOUSES)]
    source.sort(key=lambda r:r['date'],reverse=sort!='oldest')
    return source

def daily_response(params):
    filtered=daily_query(params)
    try: page=max(1,int((params.get('page') or ['1'])[0]))
    except ValueError: page=1
    try: page_size=min(100,max(1,int((params.get('page_size') or ['50'])[0])))
    except ValueError: page_size=50
    total=len(filtered); start=(page-1)*page_size
    with DATA_LOCK: dataset=[r.copy() for r in ROWS]
    counts={h:sum(r.get(h) is not None for r in dataset) for h in core.HOUSES}
    return {'ok':True,'data':[daily_api_row(r) for r in filtered[start:start+page_size]],'meta':{'total_rows':len(dataset),'filtered_rows':total,'page':page,'page_size':page_size,'pages':max(1,(total+page_size-1)//page_size),'first_date':dataset[0]['date'] if dataset else None,'last_date':dataset[-1]['date'] if dataset else None,'recorded':counts}}

def daily_payload_to_text(payload, existing=None):
    date=core.parse_date(str(payload.get('date','')).strip()).strftime('%Y-%m-%d')
    values=[]
    for key in ('DS','FB','GB','GL'):
        value=payload[key] if key in payload else (existing.get({'DS':'Deshawar','FB':'Faridabad','GB':'Ghaziabad','GL':'Gali'}[key]) if existing else None)
        values.append('' if value is None else strict_number(value,key))
    if not any(values): raise ValueError('At least one house value is required')
    return ','.join([date,*values])

def export_daily_csv(params):
    rows=daily_query(params); out=io.StringIO(); writer=csv.writer(out); writer.writerow(['Date','Day','DS','FB','GB','GL'])
    for row in rows:
        api_row=daily_api_row(row); writer.writerow([api_row['date'],api_row['day'],api_row['DS'] or '',api_row['FB'] or '',api_row['GB'] or '',api_row['GL'] or ''])
    return out.getvalue().encode('utf-8-sig')

HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DHAPPA — Engine Lab</title>
<style>
:root{--bg:#0b1020;--panel:#121a2f;--panel2:#18223b;--text:#eef3ff;--muted:#9eacc9;--line:#293657;--good:#82e6ad;--warn:#ffd27d;--bad:#ff9a9a;--accent:#8fb6ff;--pool:#7557d6;--import:#0b6f76}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#090e1a,#0d1426);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}header{position:sticky;top:0;z-index:10;background:rgba(9,14,26,.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:18px 22px}h1{font-size:22px;margin:0 0 5px}.sub{color:var(--muted);font-size:13px}.controls{display:flex;gap:12px;align-items:center;margin-top:12px;flex-wrap:wrap}select,button,input,textarea{background:#151e35;color:var(--text);border:1px solid #354464;border-radius:9px;padding:9px 11px}button{cursor:pointer}.wrap{padding:16px 22px 36px;max-width:1700px;margin:auto}.tabs{display:flex;gap:7px;overflow:auto;padding:3px 0 12px;position:sticky;top:105px;background:#0d1426;z-index:8}.tab{white-space:nowrap;font-size:12px}.tab.active{background:#27416e;border-color:#567cc0}.tab.pool{border-color:#6f59be}.tab.pool.active{background:#493582}.tab.import{border-color:#2a9ea6}.tab.import.active{background:#125c63}.hero{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-bottom:14px}.hero.poolhero{border-color:#5d4a9d;background:linear-gradient(135deg,#181a39,#151d34)}.hero.importhero{border-color:#247e86;background:linear-gradient(135deg,#12343a,#151d34)}.hero h2{margin:0 0 6px;font-size:20px}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#263554;color:#cfe0ff;font-size:12px}.poolpill{background:#493582;color:#efeaff}.importpill{background:#125c63;color:#d9ffff}.desc{color:var(--muted);max-width:900px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(4,minmax(260px,1fr));gap:12px}@media(max-width:1200px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.grid{grid-template-columns:1fr}}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}.card h3{margin:0 0 10px;font-size:15px}.nums{display:flex;flex-wrap:wrap;gap:6px}.num{min-width:32px;text-align:center;padding:6px 7px;border-radius:7px;background:#1f2c48;font-weight:650;font-size:12px}.num.top5{background:#355d48}.num.actual{outline:2px solid #ffd27d}.num.poolnum{background:#2c2552}.section{margin-top:10px}.label{color:var(--muted);font-size:11px;margin-bottom:6px}.actualrow{margin:10px 0;padding:8px;background:#10172a;border-radius:9px;font-size:12px}.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}table{width:100%;border-collapse:collapse;font-size:11px}th,td{text-align:right;padding:5px;border-bottom:1px solid #26324e}th:first-child,td:first-child{text-align:left}.meta{font-size:11px;color:var(--muted);word-break:break-word;margin-top:8px}.foot{color:var(--muted);font-size:11px;margin-top:15px}.pooltable{max-height:330px;overflow:auto;border:1px solid #283555;border-radius:9px}.pooltable table{min-width:620px}.pooltable td.eng{text-align:left;white-space:normal}.rankbadge{font-weight:700;color:#d9cbff}.importgrid{display:grid;grid-template-columns:1.2fr 1fr;gap:14px}@media(max-width:900px){.importgrid{grid-template-columns:1fr}}.importbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}.importbox h3{margin-top:0}.wide{width:100%}textarea{width:100%;min-height:150px;font-family:ui-monospace,Consolas,monospace;font-size:12px;resize:vertical}.rowform{display:grid;grid-template-columns:1.3fr repeat(4,1fr);gap:8px}.actionrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}.preview{margin-top:12px;padding:10px;border:1px solid var(--line);border-radius:9px;background:#10172a;white-space:pre-wrap;font-size:12px}.filedrop{display:block;border:1px dashed #4b6388;border-radius:10px;padding:14px;text-align:center}.mutedbox{background:#10172a;padding:10px;border-radius:9px;color:var(--muted);font-size:12px}
</style></head><body>
<header><h1>DHAPPA — 12 Engine Lab + 36 Consensus Pool + Data Import</h1><div class="sub">Individual engines · consensus pool · CSV bulk import · line-item entry · validation & backups</div><div class="controls" id="evalControls"><label>Evaluation date <select id="date"></select></label><button onclick="loadEval()">Refresh</button><span id="status" class="sub"></span></div></header>
<div class="wrap"><div id="tabs" class="tabs"></div><div id="content"></div></div>
<script>
let state=null, active='CONSENSUS_36', tabsMeta=[], importText=''; const pct=x=>(100*x).toFixed(2)+'%'; const fmt=x=>(x??0).toFixed(4);
async function api(path,opt){let r=await fetch(path,opt);let j=await r.json();if(!r.ok)throw new Error(j.error||'Request failed');return j}
async function init(){await refreshMeta();active='CONSENSUS_36';renderTabs();await loadEval()}
async function refreshMeta(){const meta=await api('/api/meta');const d=document.getElementById('date');let old=d.value;d.innerHTML='';meta.dates.slice().reverse().forEach(x=>{let o=document.createElement('option');o.value=x;o.textContent=x;d.appendChild(o)});let o=document.createElement('option');o.value='NEXT';o.textContent='NEXT TARGET (latest history + 1 day)';d.insertBefore(o,d.firstChild);d.value=(old&&[...d.options].some(x=>x.value===old))?old:'NEXT';tabsMeta=[{name:'DATA_IMPORT',family:'data'},{name:'CONSENSUS_36',family:'ensemble'},...meta.engines];window.meta=meta}
function renderTabs(){let t=document.getElementById('tabs');t.innerHTML='';tabsMeta.forEach(e=>{let b=document.createElement('button');b.className='tab '+(e.name==='CONSENSUS_36'?'pool ':'')+(e.name==='DATA_IMPORT'?'import ':'')+(e.name===active?'active':'');b.textContent=e.name==='CONSENSUS_36'?'36 CONSENSUS POOL':e.name==='DATA_IMPORT'?'BULK DATA IMPORT':e.name;b.onclick=()=>{active=e.name;renderTabs();render()};t.appendChild(b)})}
async function loadEval(){if(active==='DATA_IMPORT'){renderImport();return}document.getElementById('status').textContent='Loading…';let q=document.getElementById('date').value;state=await api('/api/evaluate?date='+encodeURIComponent(q));document.getElementById('status').textContent='Source cutoff: '+state.source_cutoff+' · target: '+state.target_date;render()}
function block(label,arr,actual,pool=false){return `<div class="section"><div class="label">${label}</div><div class="nums">${arr.map((n,i)=>`<span class="num ${i<5?'top5':''} ${n===actual?'actual':''} ${pool?'poolnum':''}">${n}</span>`).join('')}</div></div>`}
function metricsTable(m){if(!m)return '<div class="meta">No historical profile available.</div>';let rows=['15','30','60','expanding'].map(w=>{let x=m[w];return `<tr><td>${w}</td><td>${x.n}</td><td>${pct(x.h5)}</td><td>${pct(x.h10)}</td><td>${pct(x.h21)}</td><td>${pct(x.h36)}</td><td>${fmt(x.mrr)}</td><td>${Number(x.mean_rank).toFixed(1)}</td></tr>`}).join('');return `<table><thead><tr><th>Window</th><th>N</th><th>H@5</th><th>H@10</th><th>H@21</th><th>H@36</th><th>MRR</th><th>Mean Rank</th></tr></thead><tbody>${rows}</tbody></table>`}
function consensusDetailTable(details){return `<div class="pooltable"><table><thead><tr><th>Rank</th><th>Number</th><th>Score</th><th>Support</th><th style="text-align:left">Contributing engines</th></tr></thead><tbody>${details.map(d=>`<tr><td><span class="rankbadge">${d.rank}</span></td><td>${d.number}</td><td>${d.score.toFixed(3)}</td><td>${d.support_count}/12</td><td class="eng">${d.engines.join(', ')||'—'}</td></tr>`).join('')}</tbody></table></div>`}
function renderConsensus(){let c=state.consensus;let cards=Object.entries(c.houses).map(([h,x])=>{let actual=x.actual;let ar=actual?`Actual <b>${actual}</b> · consensus rank <b>${x.actual_rank}</b> · <span class="${x.actual_rank<=5?'good':x.actual_rank<=36?'warn':'bad'}">${x.actual_rank<=5?'TOP-5 HIT':x.actual_rank<=10?'TOP-10':x.actual_rank<=21?'TOP-21':x.actual_rank<=36?'TOP-36':'OUTSIDE TOP-36'}</span>`:'Forward target · outcome not available';return `<div class="card"><h3>${h}</h3><div class="actualrow">${ar}</div>${block('Top 5',x.ranking.slice(0,5),actual,true)}${block('Ranks 6–10',x.ranking.slice(5,10),actual,true)}${block('Ranks 11–21',x.ranking.slice(10,21),actual,true)}${block('Ranks 22–36',x.ranking.slice(21,36),actual,true)}<div class="section"><div class="label">Historical 36 Consensus performance</div>${metricsTable(x.metrics)}</div><div class="section"><div class="label">Top-36 candidate evidence</div>${consensusDetailTable(x.details)}</div></div>`}).join('');document.getElementById('content').innerHTML=`<div class="hero poolhero"><div><h2>36 CONSENSUS POOL</h2><span class="pill poolpill">WEIGHTED BORDA · CURRENT 12 ENGINE REGISTRY</span><p class="desc">Each engine contributes its frozen Top-36. Imported data immediately feeds this tab after validation and metrics rebuild.</p></div></div><div class="grid">${cards}</div>`}
function renderEngine(){let e=state.engines.find(x=>x.name===active);if(!e)return;let cards=Object.entries(e.houses).map(([h,x])=>{let actual=x.actual;let ar=actual?`Actual <b>${actual}</b> · rank <b>${x.actual_rank}</b>`:'Forward target · outcome not available';return `<div class="card"><h3>${h}</h3><div class="actualrow">${ar}</div>${block('Top 5',x.ranking.slice(0,5),actual)}${block('Ranks 6–10',x.ranking.slice(5,10),actual)}${block('Ranks 11–21',x.ranking.slice(10,21),actual)}${block('Ranks 22–36',x.ranking.slice(21,36),actual)}<div class="section"><div class="label">Historical performance</div>${metricsTable(x.metrics)}</div><div class="meta">Engine meta: ${JSON.stringify(x.meta)}</div></div>`}).join('');document.getElementById('content').innerHTML=`<div class="hero"><div><h2>${e.name}</h2><span class="pill">${e.family}</span><p class="desc">${e.description}</p></div></div><div class="grid">${cards}</div>`}
function renderImport(){document.getElementById('status').textContent=`Dataset: ${window.meta?.row_count||0} rows · ${window.meta?.first_date||''} to ${window.meta?.last_date||''}`;document.getElementById('content').innerHTML=`<div class="hero importhero"><div><h2>Bulk Data Import</h2><span class="pill importpill">CSV + PASTE + SINGLE LINE</span><p class="desc">Import historical draw data safely. Every commit creates a timestamped backup, validates dates and 00–99 values, merges duplicate dates deterministically, reloads all 12 engines, and rebuilds engine + 36 Consensus metrics.</p></div></div><div class="importgrid"><div class="importbox"><h3>1. CSV file upload</h3><label class="filedrop">Choose CSV<input id="csvFile" type="file" accept=".csv,text/csv" style="display:block;margin:10px auto 0" onchange="readCsv(this)"></label><div class="mutedbox" style="margin-top:10px">Supported headers: Date, Deshawar/DS, Faridabad/FB, Ghaziabad/GB, Gali/GL. Column order does not matter. Values must be 00–99 or blank.</div><div class="actionrow"><select id="strategy"><option value="merge">MERGE with current data</option><option value="replace">REPLACE current data</option></select><button onclick="previewCsv()">Preview & Validate</button><button onclick="commitCsv()">Import CSV</button></div><div id="csvPreview" class="preview">No file loaded.</div></div><div class="importbox"><h3>2. Paste multiple line items</h3><textarea id="lines" placeholder="One row per line, no header:\n2026-09-20,35,21,07,86\n2026-09-21,42,18,55,09\n\nOrder: Date, Deshawar, Faridabad, Ghaziabad, Gali"></textarea><div class="actionrow"><button onclick="previewLines()">Preview Lines</button><button onclick="commitLines()">Import Lines</button></div><div id="linePreview" class="preview">Ready for line-wise bulk paste.</div></div><div class="importbox"><h3>3. Single row entry</h3><div class="rowform"><input id="rDate" placeholder="YYYY-MM-DD"><input id="rDS" placeholder="DS"><input id="rFB" placeholder="FB"><input id="rGB" placeholder="GB"><input id="rGL" placeholder="GL"></div><div class="actionrow"><button onclick="commitSingle()">Add / Update Row</button></div><div id="singlePreview" class="preview">Duplicate date: nonblank values update that date; other existing house values are preserved.</div></div><div class="importbox"><h3>Import behavior</h3><div class="mutedbox">• MERGE is default and safest.<br>• Duplicate dates are merged; later nonblank imported values win.<br>• Invalid rows reject the entire commit—no partial silent import.<br>• Blank/XX/NA house cells are treated as missing.<br>• A backup is written under <b>data/backups/</b> before every commit.<br>• Engine and consensus historical metrics rebuild after import.<br>• Current normalized dataset can be exported anytime.</div><div class="actionrow"><button onclick="window.location='/api/data.csv'">Download Current CSV</button><button onclick="refreshMeta().then(()=>{renderTabs();renderImport()})">Refresh Dataset Status</button></div></div></div>`}
async function readCsv(el){let f=el.files[0];if(!f)return;importText=await f.text();document.getElementById('csvPreview').textContent=`Loaded ${f.name} · ${(f.size/1024).toFixed(1)} KB`;}
function showPreview(id,p){
  const rows = Array.isArray(p.rows) ? p.rows : [];
  const summary = `Valid rows: ${p.valid_rows}\nErrors: ${p.error_count}\nNew dates: ${p.new_dates}\nDuplicate dates: ${p.duplicate_dates}\nDates with changed values: ${p.dates_with_changes}\nRange: ${p.first_date||'—'} → ${p.last_date||'—'}`;
  const errorText = p.errors && p.errors.length ? `\n\nErrors:\n${p.errors.join('\n')}` : '';
  const listHtml = rows.length ? `<div style="margin-top:12px;max-height:340px;overflow:auto;border:1px solid #293657;border-radius:9px;background:#10172a;">
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:#18223b;">
          <th style="padding:8px;text-align:left;border-bottom:1px solid #293657;">Date</th>
          <th style="padding:8px;text-align:right;border-bottom:1px solid #293657;">DS</th>
          <th style="padding:8px;text-align:right;border-bottom:1px solid #293657;">FB</th>
          <th style="padding:8px;text-align:right;border-bottom:1px solid #293657;">GB</th>
          <th style="padding:8px;text-align:right;border-bottom:1px solid #293657;">GL</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(r=>`<tr><td style="padding:8px 8px;border-bottom:1px solid #1e2a43;">${r.date}</td><td style="padding:8px 8px;text-align:right;border-bottom:1px solid #1e2a43;">${r.Deshawar ?? ''}</td><td style="padding:8px 8px;text-align:right;border-bottom:1px solid #1e2a43;">${r.Faridabad ?? ''}</td><td style="padding:8px 8px;text-align:right;border-bottom:1px solid #1e2a43;">${r.Ghaziabad ?? ''}</td><td style="padding:8px 8px;text-align:right;border-bottom:1px solid #1e2a43;">${r.Gali ?? ''}</td></tr>`).join('')}
      </tbody>
    </table>
  </div>` : '';
  document.getElementById(id).innerHTML = `${summary}${errorText}${listHtml}`;
}
async function previewCsv(){try{showPreview('csvPreview',await api('/api/import/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:importText,has_header:true})}))}catch(e){document.getElementById('csvPreview').textContent=e.message}}
async function commitCsv(){if(!importText)return alert('Choose a CSV first');if(!confirm('Commit this CSV import? A backup will be created.'))return;let el=document.getElementById('csvPreview');el.textContent='Importing and rebuilding metrics…';try{let r=await api('/api/import/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:importText,has_header:true,strategy:document.getElementById('strategy').value})});el.textContent=`SUCCESS\nRows: ${r.rows_after_import}\nRange: ${r.first_date} → ${r.last_date}\nMetrics rebuilt: ${r.metrics_rebuilt}`;await refreshMeta()}catch(e){el.textContent='FAILED: '+e.message}}
async function previewLines(){let text=document.getElementById('lines').value;try{showPreview('linePreview',await api('/api/import/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,has_header:false})}))}catch(e){document.getElementById('linePreview').textContent=e.message}}
async function commitLines(){let text=document.getElementById('lines').value;if(!text.trim())return alert('Paste one or more rows first');let el=document.getElementById('linePreview');el.textContent='Importing and rebuilding metrics…';try{let r=await api('/api/import/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,has_header:false,strategy:'merge'})});el.textContent=`SUCCESS · ${r.rows_after_import} total rows · through ${r.last_date}`;await refreshMeta()}catch(e){el.textContent='FAILED: '+e.message}}
async function commitSingle(){let vals=['rDate','rDS','rFB','rGB','rGL'].map(id=>document.getElementById(id).value.trim());let text=vals.map((v,i)=>i?v:v).join(',');let el=document.getElementById('singlePreview');el.textContent='Saving and rebuilding metrics…';try{let r=await api('/api/import/commit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,has_header:false,strategy:'merge'})});el.textContent=`SUCCESS · ${vals[0]} saved · ${r.rows_after_import} total rows`;await refreshMeta()}catch(e){el.textContent='FAILED: '+e.message}}
function render(){if(active==='DATA_IMPORT')renderImport();else if(active==='CONSENSUS_36')renderConsensus();else renderEngine()}init();
</script></body></html>'''

def evaluate(date_token:str):
    eval_started=datetime.utcnow().isoformat()+'Z'
    with DATA_LOCK:
        rows=ROWS[:]
    if date_token=='NEXT':
        history=rows; last=datetime.strptime(rows[-1]['date'],'%Y-%m-%d'); target_date=(last+timedelta(days=1)).strftime('%Y-%m-%d'); actual_row=None
    else:
        idx=next((i for i,r in enumerate(rows) if r['date']==date_token),None)
        if idx is None or idx==0:raise ValueError('Date not found or no prior history')
        history=rows[:idx];target_date=rows[idx]['date'];actual_row=rows[idx]
    cutoff=history[-1]['date'] if history else None;engines=[];house_rankings={h:{} for h in core.HOUSES}
    for name in ENGINE_ORDER:
        eng=ENGINE_MAP[name];houses={}
        for house in core.HOUSES:
            out=eng.rank(history,house,target_date);house_rankings[house][name]=out.ranking;actual=actual_row.get(house) if actual_row else None;rank=out.ranking.index(actual)+1 if actual and actual in out.ranking else None
            houses[house]={'ranking':out.ranking[:36],'actual':actual,'actual_rank':rank,'metrics':METRICS.get(house,{}).get(name),'meta':out.meta}
        engines.append({'name':name,'family':ENGINE_FAMILY[name],'description':ENGINE_DESCRIPTIONS.get(name,''),'houses':houses})
    consensus_houses={}
    for house in core.HOUSES:
        ranked,details=consensus36(house_rankings[house]);actual=actual_row.get(house) if actual_row else None;actual_rank=ranked.index(actual)+1 if actual else None;cm=CONS_METRICS.get(house,{})
        metrics={k:cm.get(k) for k in ('15','30','60','expanding')} if cm else None;consensus_houses[house]={'ranking':ranked[:36],'actual':actual,'actual_rank':actual_rank,'metrics':metrics,'details':details}
    for e in engines:
        audit_log('engines','engine_target_complete',target_date=target_date,source_cutoff=cutoff,engine=e['name'],family=e['family'],houses=list(e['houses'].keys()))
        for house,x in e['houses'].items():
            audit_log('predictions','engine_prediction',target_date=target_date,source_cutoff=cutoff,engine=e['name'],house=house,top36=x['ranking'],actual=x['actual'],actual_rank=x['actual_rank'])
    for house,x in consensus_houses.items():
        audit_log('consensus','consensus_prediction',target_date=target_date,source_cutoff=cutoff,house=house,top36=x['ranking'],actual=x['actual'],actual_rank=x['actual_rank'],weights=CONS_WEIGHTS)
    cutoff_ok=(cutoff is None or cutoff < target_date)
    audit_log('integrity','evaluation_cutoff_check',target_date=target_date,source_cutoff=cutoff,pass_check=cutoff_ok,date_token=date_token)
    audit_log('runtime','evaluation_complete',target_date=target_date,source_cutoff=cutoff,date_token=date_token,started_utc=eval_started,engine_count=len(engines))
    return {'target_date':target_date,'source_cutoff':cutoff,'engines':engines,'consensus':{'name':'CONSENSUS_36','weights':CONS_WEIGHTS,'houses':consensus_houses}}

class Handler(BaseHTTPRequestHandler):
    def _json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def _body_json(self):
        n=int(self.headers.get('Content-Length','0'));return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
    def do_GET(self):
        p=urlparse(self.path)
        query=parse_qs(p.query)
        audit_log('access','http_get',path=p.path,query=p.query,client=self.client_address[0] if self.client_address else None)
        if p.path in ('/','/index.html'):
            static_index = (ROOT / 'static' / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(static_index)))
            self.end_headers()
            self.wfile.write(static_index)
            return
        if p.path.startswith('/static/'):
            resource = ROOT / 'static' / p.path.removeprefix('/static/')
            if resource.exists() and resource.is_file():
                content = resource.read_bytes()
                mime = 'text/css; charset=utf-8' if resource.suffix == '.css' else 'application/javascript; charset=utf-8' if resource.suffix == '.js' else 'text/html; charset=utf-8'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if p.path=='/api/meta':
            with DATA_LOCK: rows=ROWS[:]
            self._json({'dates':[r['date'] for r in rows[1:]],'engines':[{'name':n,'family':ENGINE_FAMILY[n]} for n in ENGINE_ORDER],'row_count':len(rows),'first_date':rows[0]['date'] if rows else None,'last_date':rows[-1]['date'] if rows else None});return
        if p.path=='/api/evaluate':
            token=query.get('date',['NEXT'])[0]
            try:self._json(evaluate(token))
            except Exception as e:
                log_exception('evaluation_error',e,date_token=token,path=p.path);self._json({'error':str(e)},400)
            return
        if p.path=='/api/data/daily':
            self._json(daily_response(query));return
        if p.path.startswith('/api/data/daily/'):
            date_token=p.path.rsplit('/',1)[-1]
            with DATA_LOCK: row=next((r.copy() for r in ROWS if r['date']==date_token),None)
            if row is None:self._json({'error':'Date not found'},404)
            else:self._json({'ok':True,'data':daily_api_row(row)})
            return
        if p.path=='/api/data/export':
            raw=export_daily_csv(query);self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="DHAPPA_daily_view.csv"');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if p.path.startswith('/api/engines/') and p.path.endswith('/walkforward'):
            engine_id=p.path.split('/')[3]; model=next((n for n in ENGINE_ORDER if n.lower()==engine_id.lower() or n.lower().replace('_','-')==engine_id.lower()),engine_id.upper().replace('-','_'))
            self._json(walkforward_view(model,(query.get('house') or ['DS'])[0],(query.get('window') or ['expanding'])[0],(query.get('from') or [None])[0],(query.get('to') or [None])[0]));return
        if p.path=='/api/consensus/36/walkforward':
            self._json(walkforward_view('CONSENSUS_36',(query.get('house') or ['DS'])[0],(query.get('window') or ['expanding'])[0],(query.get('from') or [None])[0],(query.get('to') or [None])[0]));return
        if p.path=='/api/walkforward/house-summary':
            house=house_name((query.get('house') or ['DS'])[0]); data=ensure_walkforward(); models=[]
            for model in [*ENGINE_ORDER,'CONSENSUS_36']:
                if model=='CONSENSUS_36': metric_source=data.get('consensus_metrics') or CONS_METRICS
                else: metric_source=data.get('engine_metrics',{}).get(model) or {house:METRICS.get(house,{}).get(model,{})}
                metrics=metric_source[house]['expanding']
                models.append({'model':model,**metrics})
            self._json({'ok':True,'house':house,'models':models,'integrity':data['integrity']});return
        if p.path=='/api/walkforward/daywise':
            self._json(daywise_response(query));return
        if p.path=='/api/walkforward/house-leaderboard':
            try: tier=int((query.get('tier') or ['5'])[0])
            except ValueError: tier=5
            self._json(leaderboard_response((query.get('house') or ['DS'])[0],tier,(query.get('window') or ['expanding'])[0]));return
        if p.path=='/api/walkforward/best-engine-by-house':
            data=ensure_daywise(); tier=int((query.get('tier') or ['5'])[0]); result={}
            for house,rows in data['leaderboard'].items():
                selected=max(rows,key=lambda row:(row['samples']>=30,row.get(f'h{tier}',row['h5'])))
                result[house]={'house':house,'tier':tier,'best_engine':selected['model'],'hit_rate':selected.get(f'h{tier}',selected['h5']),'hit_count':round(selected.get(f'h{tier}',selected['h5'])*selected['samples']),'samples':selected['samples'],'recent_30_hit_rate':selected['recent30_h5'],'recent_60_hit_rate':selected['recent60_h5'],'mrr':selected['mrr']}
            self._json({'ok':True,'tier':tier,'data':result});return
        if p.path=='/api/walkforward/summary':
            data=ensure_daywise(); tier=int((query.get('tier') or ['5'])[0]); daily=daywise_response({'model':['CONSENSUS_36'],'tier':[str(tier)]}); self._json({'ok':True,'tier':tier,'daily':daily['summary'],'best_engine':data['best_engine'],'sweep':data['sweep_summary'].get(str(tier),{})});return
        if p.path=='/api/data.csv':
            raw=DATA_PATH.read_bytes();self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="DHAPPA_current_data.csv"');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        self.send_error(404)
    def do_POST(self):
        p=urlparse(self.path)
        try:
            b=self._body_json()
            audit_log('access','http_post',path=p.path,client=self.client_address[0] if self.client_address else None,content_length=int(self.headers.get('Content-Length','0')),payload_redacted=True)
            if p.path=='/api/import/preview':self._json(import_preview(b.get('text',''),bool(b.get('has_header',True))));return
            if p.path=='/api/data/import/validate':self._json(import_preview(b.get('text',''),bool(b.get('has_header',True))));return
            if p.path=='/api/import/commit':self._json(commit_import(b.get('text',''),bool(b.get('has_header',True)),b.get('strategy','merge')));return
            if p.path=='/api/data/import/commit':self._json(commit_import(b.get('text',''),bool(b.get('has_header',True)),b.get('strategy','merge')));return
            if p.path=='/api/data/daily':
                text=daily_payload_to_text(b)
                self._json(commit_import(text,False,'merge'));return
            self.send_error(404)
        except Exception as e:
            log_exception('http_post_error',e,path=p.path);self._json({'error':str(e)},400)
    def do_PATCH(self):
        p=urlparse(self.path)
        try:
            b=self._body_json()
            if not p.path.startswith('/api/data/daily/'):
                self.send_error(404);return
            date_token=p.path.rsplit('/',1)[-1]
            with DATA_LOCK: existing=next((r.copy() for r in ROWS if r['date']==date_token),None)
            if existing is None:
                self._json({'error':'Date not found'},404);return
            b['date']=date_token
            self._json(commit_import(daily_payload_to_text(b,existing),False,'merge'));return
        except Exception as e:
            log_exception('http_patch_error',e,path=p.path);self._json({'error':str(e)},400)
    def log_message(self,fmt,*args):pass

def main():
    host='127.0.0.1';port=int(os.environ.get('DHAPPA_PORT','8765'));print(f'DHAPPA Engine Lab + 36 Consensus + Bulk Import: http://{host}:{port}');print('Press Ctrl+C to stop.')
    audit_log('runtime','application_start',host=host,port=port,row_count=len(ROWS),first_date=ROWS[0]['date'] if ROWS else None,last_date=ROWS[-1]['date'] if ROWS else None,engine_count=len(ENGINE_ORDER),dataset_sha256=sha256_file(DATA_PATH) if DATA_PATH.exists() else None)
    audit_log('security','local_bind',host=host,port=port,network_exposure='loopback_only')
    if os.environ.get('DHAPPA_NO_BROWSER')!='1':
        try:webbrowser.open(f'http://{host}:{port}')
        except:pass
    ThreadingHTTPServer((host,port),Handler).serve_forever()
if __name__=='__main__':main()
