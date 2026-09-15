#!/usr/bin/env python3
"""UAN Transit Planner: a local TAPIR orchestration CLI."""
import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time as clock
import warnings
from datetime import date,datetime,timedelta,timezone,time
from urllib.parse import urlencode
from urllib.request import urlopen,Request
from zoneinfo import ZoneInfo
from astropy.time import Time
from observing import number,analyze
from reports import slug,write_reports,BASE,compute_selection

ROOT=Path(__file__).resolve().parent
NASA='https://exoplanetarchive.ipac.caltech.edu/'
FIELDS='pl_name,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_orbsmax,pl_orbincl,rastr,decstr,ra,dec,st_rad,pl_radj,pl_trandep,pl_trandur,pl_trandurerr1,pl_trandurerr2,pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_imppar,pl_ratdor,pl_ratror,sy_vmag,sy_gaiamag'


def log(message): print(message,flush=True)


def dump(path,data): path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')


def read_csv(text):
    lines=text.splitlines()
    start=next((i for i,s in enumerate(lines) if s.startswith('Name,V,') or s.startswith('jd_utc_exact,Name,V,') or s.startswith('name,RA,')),None)
    if start is None: raise ValueError('Output TAPIR non CSV; leggere il log originale')
    return [r for r in csv.DictReader(lines[start:]) if r.get('Name') or r.get('name')]


def write_csv(path,rows,fields=None):
    if fields is None: fields=list(rows[0])
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def download(url,dest,cache=None,offline=False):
    meta_path=dest.with_suffix(dest.suffix+'.meta.json')
    error=None
    if not offline:
        for attempt in range(2):
            try:
                with urlopen(Request(url,headers={'User-Agent':'UAN-Transit-Planner/1.0'}),timeout=60) as r:
                    body=r.read()
                if not body: raise ValueError('Risposta vuota')
                dest.write_bytes(body)
                meta={'url':url,'acquired_utc':datetime.now(timezone.utc).isoformat(),'cache':False}
                dump(meta_path,meta)
                return body.decode('utf-8-sig')
            except Exception as exc:
                error=str(exc)
                log(f'  Download tentativo {attempt+1}/2: {error}')
    if cache:
        cached=cache/dest.name;cm=cache/meta_path.name
        if cached.is_file() and cm.is_file():
            meta=json.loads(cm.read_text())
            if meta.get('url')!=url: raise ValueError(f'Cache non corrispondente alla query: {cached}')
            shutil.copy2(cached,dest);meta.update(cache=True,download_error=error,offline=offline)
            dump(meta_path,meta)
            log(f'  CACHE ESPLICITA: {cached.name}, acquisizione {meta["acquired_utc"]}')
            return dest.read_text(encoding='utf-8-sig')
    raise ValueError(f'Dati NASA non disponibili: {error or "cache assente/non valida"}')


def normalize(name):
    return re.sub(r'[\s_-]+','',name).casefold()


def alias_candidates(payload,requested):
    planets=payload.get('system',{}).get('objects',{}).get('planet_set',{}).get('planets',{})
    return sorted({obj['alias_set']['default_name'] for obj in planets.values()
                   if obj.get('requested_object')=='True' or
                   any(normalize(a)==normalize(requested) for a in obj.get('alias_set',{}).get('aliases',[]))})


def resolve(requested,composite,raw,cache,offline):
    mapping={};rejected=[]
    for name in requested:
        matches=[r['pl_name'] for r in composite if normalize(r['pl_name'])==normalize(name)]
        try:
            if not matches:
                url=NASA+'cgi-bin/Lookup/nph-aliaslookup.py?'+urlencode({'objname':name})
                payload=json.loads(download(url,raw/f'alias_{hashlib.sha256(name.encode()).hexdigest()[:12]}.json',cache,offline))
                matches=alias_candidates(payload,name)
            if len(set(matches))!=1:
                raise ValueError('Nome assente o ambiguo; candidati: '+', '.join(matches))
            canonical=matches[0]
            if not any(r['pl_name']==canonical for r in composite):
                raise ValueError('Target non presente nel catalogo dei pianeti transitanti')
            mapping[name]=canonical
        except (ValueError,KeyError) as exc:
            rejected.append({'requested':name,'reason':str(exc)})
    return list(dict.fromkeys(mapping.values())),mapping,rejected


def err(row,key):
    vals=[abs(v) for v in (number(row.get(key+'err1')),number(row.get(key+'err2'))) if v is not None]
    return max(vals) if vals else None


def choose_ephemeris(rows,begin,end):
    eligible=[];excluded=[]
    for r in rows:
        period=number(r.get('pl_orbper'));epoch=number(r.get('pl_tranmid'))
        if period is None or period<=0 or epoch is None or epoch<=0:
            excluded.append({'reference':r.get('pl_refname'),'reason':'Periodo/epoca mancanti o non validi'});continue
        standard=re.sub(r'[^A-Z]','',r.get('pl_tsystemref','').upper())
        if standard!='BJDTDB':
            excluded.append({'reference':r.get('pl_refname'),'reason':'Sistema temporale non BJD-TDB esplicito','system':r.get('pl_tsystemref')});continue
        pe,ee=err(r,'pl_orbper'),err(r,'pl_tranmid')
        n=max(abs(begin-epoch),abs(end-epoch))/period
        score=math.hypot(ee,n*pe) if pe is not None and ee is not None else math.inf
        eligible.append((score,0 if r.get('default_flag')=='1' else 1,r))
    if not eligible: raise ValueError('Nessuna effemeride coerente con periodo/epoca e BJD-TDB esplicito')
    chosen=min(eligible,key=lambda x:(x[0],x[1],x[2].get('pl_refname','')))[2].copy()
    return chosen,excluded


def perl_env():
    env=os.environ.copy()
    env['PERL5LIB']=str(Path.home()/'perl5/lib/perl5')+(os.pathsep+env['PERL5LIB'] if env.get('PERL5LIB') else '')
    return env


def run_perl(script,cwd,args=None,query=None):
    env=perl_env()
    if query is not None:
        env.update(REQUEST_METHOD='GET',QUERY_STRING=urlencode(query),GATEWAY_INTERFACE='CGI/1.1')
    proc=subprocess.run(['perl',str(script),*(args or [])],cwd=cwd,env=env,text=True,capture_output=True,timeout=180)
    return proc


def make_catalog(names,rows,composite,engine,raw,start,end,rejected):
    targets=[];selected={};begin=Time(str(start)).jd;finish=Time(str(end)).jd
    for name in names:
        try:
            source,excluded=choose_ephemeris([r for r in rows if r['pl_name']==name],begin,finish)
            ancillary=next(r for r in composite if r['pl_name']==name)
            duration=number(source.get('pl_trandur'))
            duration_fallback=duration is None or duration<=0
            if duration_fallback:
                duration=number(ancillary.get('pl_trandur'))
                source['pl_trandur']=str(duration) if duration is not None else ''
            if duration is None or duration<=0 or duration>=float(source['pl_orbper'])*24:
                raise ValueError('Durata mancante/non valida o >= periodo; nessuna stima inventata')
            if number(source.get('ra')) is None or number(source.get('dec')) is None:
                raise ValueError('Coordinate mancanti nella riga PS scelta')
            write_csv(engine/'selected.txt',[source])
            write_csv(engine/'exoplanet_archive_transits_full_composite.txt',[ancillary])
            proc=run_perl(engine/'parse_exoplanets_csv_nasa.pl',engine,['selected.txt'])
            (raw/f'parser_{slug(name)}.log').write_text(proc.stderr)
            if proc.returncode: raise ValueError('Parser NASA fallito: '+proc.stderr[-300:])
            converted=read_csv(proc.stdout)
            if len(converted)!=1: raise ValueError('Il parser non ha prodotto una singola riga valida')
            target=converted[0]
            for k in ['period','epoch','duration']:
                if number(target.get(k)) is None or float(target[k])<=0: raise ValueError('Campo TAPIR non valido: '+k)
            target['ttv']=ancillary.get('ttv_flag')=='1'
            selected[name]={'selected_ps_row':source,'duration_from_composite':duration_fallback,
                            'composite_row':ancillary,'excluded_ps_rows':excluded,
                            'selection':'Minimo errore massimo ai due estremi; periodo/epoca dalla stessa riga BJD-TDB'}
            targets.append(target)
        except (ValueError,StopIteration) as exc:
            rejected.append({'requested':name,'reason':str(exc)})
    dump(raw/'selected_ephemerides.json',selected)
    if targets:
        write_csv(engine/'transit_targets.csv',targets,fields=['name','RA','Dec','vmag','epoch','epoch_uncertainty','period','period_uncertainty','duration','comments','depth'])
        shutil.copy2(engine/'transit_targets.csv',raw/'transit_targets.csv')
    return targets


def tapir_events(t,p,start,days,engine,raw,folder):
    all_events={};ground_events={};offset=0;queries=[]
    # Bound chunks below TAPIR's output limit even for ultra-short orbital periods.
    chunk=max(1,min(90,int(float(t['period'])*300)))
    while offset<days:
        n=min(chunk,days-offset)
        day=start+timedelta(days=offset)
        query=dict(observatory_string='Specified_Lat_Long',observatory_latitude=p['latitude'],
                   observatory_longitude=p['longitude'],timezone=p['timezone'],use_utc=1,
                   start_date=(day-timedelta(days=1)).strftime('%m-%d-%Y'),days_to_print=n+2,days_in_past=0,
                   minimum_start_elevation=0,minimum_end_elevation=0,and_vs_or='or',minimum_ha=-12,
                   maximum_ha=12,baseline_hrs=p['baseline_hours'],show_unc=int(p['extend_uncertainty']),
                   minimum_depth=-999,maximum_V_mag=99,minimum_priority=0,twilight=p['twilight_deg'],
                   target_string='^'+re.escape(t['name'])+'$',max_airmass=4,single_object=0)
        for kind,space,form in [('all',1,2),('ground',0,2),('html',0,1)]:
            q=dict(query,space=space,print_html=form);queries.append(q)
            proc=run_perl(engine/'print_transits.cgi',engine,query=q)
            prefix=f'{slug(t["name"])}_{offset:04d}_{kind}'
            (raw/(prefix+'.txt')).write_text(proc.stdout)
            (raw/(prefix+'.log')).write_text(proc.stderr)
            if proc.returncode: raise ValueError(f'TAPIR fallito per {t["name"]}: {proc.stderr[-500:]}')
            if kind=='html':
                body=proc.stdout[proc.stdout.lower().find('<!doctype'):] if '<!doctype' in proc.stdout.lower() else proc.stdout[proc.stdout.lower().find('<html'):]
                body=re.sub(r'<head[^>]*>',lambda m:m.group(0)+'<base href="'+BASE+'">',body,count=1,flags=re.I)
                body=re.sub(r'(<body[^>]*>)',lambda m:m.group(0)+'<p style="background:#fff2cf;padding:12px"><b>OUTPUT TAPIR ORIGINALE NON VALIDATO.</b> Percentuali da verificare nelle schede locali. Query terrestre a quota 0°.</p>',body,count=1,flags=re.I)
                (folder/f'tapir_{offset:04d}.html').write_text(body)
            else:
                parsed=read_csv(proc.stdout)
                if len(parsed)>=990: raise ValueError('Possibile troncamento TAPIR: ridurre ampiezza query')
                destination=all_events if kind=='all' else ground_events
                for r in parsed:
                    if r.get('Name')!=t['name']: continue
                    mid=number(r.get('jd_utc_exact'))
                    if mid is None: raise ValueError('JD UTC preciso mancante nel template')
                    key=round(mid,7)
                    if key in destination and destination[key]!=r:
                        # Display windows may differ at query boundaries; retain and count deduplication.
                        pass
                    destination[key]=r
        offset+=n
    return list(all_events.values()),ground_events,queries


def tapir_event_html(t,p,e,engine,raw,folder,idx):
    """One ground TAPIR HTML query bounded to a single event: table for the category PDFs."""
    mid_local=datetime.fromisoformat(e['mid_local'])
    evening=mid_local.date() if mid_local.hour>=12 else mid_local.date()-timedelta(days=1)
    days=1 if float(t['period'])<2.2 else 2
    query=dict(observatory_string='Specified_Lat_Long',observatory_latitude=p['latitude'],
               observatory_longitude=p['longitude'],timezone=p['timezone'],use_utc=1,
               start_date=evening.strftime('%m-%d-%Y'),days_to_print=days,days_in_past=0,
               minimum_start_elevation=0,minimum_end_elevation=0,and_vs_or='or',minimum_ha=-12,
               maximum_ha=12,baseline_hrs=p['baseline_hours'],show_unc=int(p['extend_uncertainty']),
               minimum_depth=-999,maximum_V_mag=99,minimum_priority=0,twilight=p['twilight_deg'],
               target_string='^'+re.escape(t['name'])+'$',max_airmass=4,single_object=0,space=0,print_html=1)
    proc=run_perl(engine/'print_transits.cgi',engine,query=query)
    name=f'{slug(t["name"])}_event_{idx:04d}'
    (raw/(name+'.txt')).write_text(proc.stdout)
    (raw/(name+'.log')).write_text(proc.stderr)
    if proc.returncode: raise ValueError('TAPIR fallito (evento): '+proc.stderr[-200:])
    body=proc.stdout[proc.stdout.lower().find('<!doctype'):] if '<!doctype' in proc.stdout.lower() else proc.stdout[proc.stdout.lower().find('<html'):]
    body=re.sub(r'<head[^>]*>',lambda m:m.group(0)+'<base href="'+BASE+'">',body,count=1,flags=re.I)
    (folder/f'tapir_event_{idx:04d}.html').write_text(body)
    return f'{folder.name}/tapir_event_{idx:04d}.html'


def arguments(argv=None):
    parser=argparse.ArgumentParser(description='Pianifica transiti con TAPIR e verifica indipendente Astropy.')
    sub=parser.add_subparsers(dest='action',required=True)
    plan=sub.add_parser('plan')
    plan.add_argument('names',nargs='*');plan.add_argument('--targets',type=Path)
    plan.add_argument('--site',default='capodimonte',help='capodimonte oppure percorso JSON')
    plan.add_argument('--start',type=date.fromisoformat)
    plan.add_argument('--days',type=int,default=365)
    plan.add_argument('--tapir',type=Path,default=Path.home()/'Downloads/Tapir')
    plan.add_argument('--output',type=Path,help='Cartella nuova; non deve esistere')
    plan.add_argument('--cache',type=Path,help='dati_originali di una precedente esecuzione, fallback esplicito')
    plan.add_argument('--offline',action='store_true',help='Usa soltanto la cache esplicitamente indicata')
    plan.add_argument('--session-start',help='nautical_twilight oppure HH:MM')
    plan.add_argument('--session-end',help='HH:MM, fine del transito')
    plan.add_argument('--min-altitude',type=float)
    plan.add_argument('--max-v',type=float,help='Limite facoltativo sulla banda V; senza V il filtro non è verificabile')
    plan.add_argument('--min-depth',type=float,help='Profondità minima facoltativa in ppt')
    args=parser.parse_args(argv)
    if not 1<=args.days<=3660: parser.error('--days deve essere fra 1 e 3660')
    if args.offline and not args.cache: parser.error('--offline richiede --cache')
    if args.targets:
        args.names += [x.strip() for x in args.targets.read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')]
    args.names=list(dict.fromkeys(n.strip() for n in args.names if n.strip()))
    if not args.names or len(args.names)>100: parser.error('Inserire da 1 a 100 nomi di pianeti')
    return args


def validate_profile(p):
    for k,lo,hi in [('latitude',-90,90),('longitude',-180,180),('height_m',-500,10000),
                    ('twilight_deg',-30,-1),('visibility_altitude_deg',0,89),('baseline_hours',0.5,24),
                    ('sampling_seconds',10,300),('preferred_altitude_deg',0,90),('severe_altitude_deg',0,90),
                    ('excellent_altitude_deg',0,90),('transit_operational_percent',50,100),
                    ('first_choice_min_percent',50,100),('baseline_weak_percent',0,100),
                    ('baseline_good_percent',0,100),('timing_residual_limit_seconds',0.1,60),
                    ('backup_preferred_separation_days',0,60),('backup_fallback_separation_days',0,60),
                    ('maximum_uncertainty_minutes',0,1440)]:
        v=number(p.get(k))
        if v is None or not lo<=v<=hi: raise ValueError(f'Profilo: {k} deve essere fra {lo} e {hi}')
    if p['baseline_weak_percent']>p['baseline_good_percent']:
        raise ValueError('Profilo: baseline_weak_percent non può superare baseline_good_percent')
    if p['backup_fallback_separation_days']>p['backup_preferred_separation_days']:
        raise ValueError('Profilo: fallback separazione backup supera quella preferita')
    if not isinstance(p['extend_uncertainty'],bool): raise ValueError('extend_uncertainty deve essere booleano')
    ZoneInfo(p['timezone'])
    for k in ('session_start','session_end','session_pref_start'):
        if k=='session_start' and p[k]=='nautical_twilight': continue
        if not re.fullmatch(r'\d{2}:\d{2}',p[k]): raise ValueError(k+' richiede HH:MM')
        t=time.fromisoformat(p[k])
        if 'start' in k and t.hour<12: raise ValueError('Inizio sessione fisso deve essere >=12:00')
    return p


def main(argv=None):
    args=arguments(argv);began=clock.monotonic()
    profile_path=ROOT/'capodimonte.json' if args.site=='capodimonte' else Path(args.site)
    p=json.loads(profile_path.read_text())
    if args.session_start: p['session_start']=args.session_start
    if args.session_end: p['session_end']=args.session_end
    if args.min_altitude is not None: p['visibility_altitude_deg']=args.min_altitude
    validate_profile(p)
    zone=ZoneInfo(p['timezone']);start=args.start or datetime.now(zone).date();end=start+timedelta(days=args.days)
    for value in [args.max_v,args.min_depth]:
        if value is not None and not math.isfinite(value): raise ValueError('Filtro numerico non finito')
    if args.min_depth is not None and args.min_depth<0: raise ValueError('Profondità minima negativa')
    tapir=args.tapir.expanduser().resolve()
    if not (tapir/'print_transits.cgi').is_file(): raise ValueError(f'TAPIR assente: {tapir}')
    created=datetime.now(timezone.utc)
    out=(args.output or Path.home()/'Downloads'/('GaetanoTrovato_'+created.strftime('%Y%m%d_%H%M%S_%f'))).expanduser().resolve()
    out.mkdir(parents=True,exist_ok=False)
    archive=out/'9_ARCHIVIO_COMPLETO';raw=archive/'dati_originali';raw.mkdir(parents=True)
    manifest=dict(created_utc=created.isoformat(),generated_at=created.isoformat(),
                  policy_version=p.get('policy_version','2.1'),start=str(start),end_exclusive=str(end),profile=p,
                  command=shlex.join([str(ROOT/'uan-transits'),*(argv or sys.argv[1:])]),requested=args.names,
                  versions={x:importlib.metadata.version(x) for x in ['astropy','astropy-iers-data','numpy','reportlab']},
                  python=sys.version,status='running',filters={'max_v':args.max_v,'min_depth_ppt':args.min_depth})
    try:
        manifest['git_commit']=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    except (subprocess.SubprocessError,OSError):
        manifest['git_commit']=None
    dump(archive/'manifest.json',manifest);dump(raw/'profile.json',p)
    warnfile=(raw/'warnings.log').open('w')
    warnings.showwarning=lambda message,category,filename,lineno,file=None,line=None: (warnfile.write(f'{category.__name__}: {message}\n'),warnfile.flush())
    try:
        manifest['tapir_commit']=subprocess.check_output(['git','-C',str(tapir),'rev-parse','HEAD'],text=True).strip()
        engine=raw/'tapir_source';engine.mkdir()
        tracked=subprocess.check_output(['git','-C',str(tapir),'ls-files'],text=True).splitlines()
        for name in tracked:
            source=tapir/name
            if source.is_file():
                dest=engine/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        original=(engine/'csv_text.tmpl').read_text()
        # Expose existing full-precision UTC JD; astronomical source code remains unchanged.
        augmented=original.replace('Name,V,','jd_utc_exact,Name,V,',1).replace('<TMPL_LOOP NAME="eclipse_info">','<TMPL_LOOP NAME="eclipse_info"><TMPL_VAR NAME="jd">,',1)
        if augmented==original: raise ValueError('Template CSV upstream cambiato: integrazione da aggiornare')
        (engine/'csv_text.tmpl').write_text(augmented)
        manifest['tapir_template_change']='Added jd_utc_exact column from existing jd variable only'
        planner_source=raw/'planner_source';planner_source.mkdir()
        for source in ROOT.glob('*.py'): shutil.copy2(source,planner_source/source.name)
        for name in ['capodimonte.json','requirements.txt','README.md','SPEC.txt']:
            if (ROOT/name).exists(): shutil.copy2(ROOT/name,planner_source/name)
        cache=args.cache.expanduser().resolve() if args.cache else None
        log('Aggiornamento catalogo NASA e risoluzione nomi...')
        q='select '+FIELDS+',ttv_flag,pl_tranmid_systemref,pl_trandur_reflink from pscomppars where tran_flag=1'
        text=download(NASA+'TAP/sync?'+urlencode({'query':q,'format':'csv'}),raw/'nasa_composite.csv',cache,args.offline)
        composite=list(csv.DictReader(io.StringIO(text)))
        if not composite or 'pl_name' not in composite[0]: raise ValueError('NASA composite non valido')
        names,mapping,rejected=resolve(args.names,composite,raw,cache,args.offline);manifest['resolved_names']=mapping
        rows=[]
        if names:
            quoted=','.join("'"+n.replace("'","''")+"'" for n in sorted(names))
            q='select '+FIELDS+',pl_refname,pl_tsystemref,default_flag from ps where tran_flag=1 and pl_name in ('+quoted+') order by pl_name'
            text=download(NASA+'TAP/sync?'+urlencode({'query':q,'format':'csv'}),raw/'nasa_ps.csv',cache,args.offline)
            rows=list(csv.DictReader(io.StringIO(text)))
        targets=make_catalog(names,rows,composite,engine,raw,start,end,rejected)
        accepted=[]
        for t in targets:
            depth=number(t['depth']);mag=number(t['vmag'])
            reason=None
            if args.min_depth is not None and (depth is None or depth<args.min_depth): reason='Filtro esplicito profondità minima; valore insufficiente o mancante'
            if args.max_v is not None and ('Mag is Gaia G' in t['comments'] or mag is None or mag==-99 or mag>args.max_v): reason='Filtro esplicito V; valore insufficiente o mancante'
            if reason: rejected.append({'requested':t['name'],'reason':reason})
            else: accepted.append(t)
        targets=accepted;dump(raw/'targets.json',targets)
        lower=datetime.combine(start,time(),zone).timestamp();upper=datetime.combine(end,time(),zone).timestamp()
        events=[];manifest['tapir_queries']={}
        for t in targets:
            log(f'TAPIR: {t["name"]} ...')
            folder=archive/slug(t['name']);folder.mkdir(exist_ok=True)
            candidates,ground,queries=tapir_events(t,p,start,args.days,engine,raw,folder)
            manifest['tapir_queries'][t['name']]=queries
            candidates=[r for r in candidates if lower<=Time(float(r['jd_utc_exact']),format='jd',scale='utc').unix<upper]
            candidates.sort(key=lambda r:float(r['jd_utc_exact']))
            log(f'  {len(candidates)} eventi; controllo indipendente delle finestre...')
            for i,r in enumerate(candidates):
                e=analyze(r,t,p,ground.get(round(float(r['jd_utc_exact']),7)))
                events.append(e)
                if (i+1)%25==0: log(f'  {t["name"]}: {i+1}/{len(candidates)}')
        log('Selezione PRIMARY/BACKUP1/BACKUP2 per target (policy v2.1)...')
        selection=compute_selection(events,p)
        tmap={t['name']:t for t in targets}
        for tname,roles in selection.items():
            t=tmap[tname];folder=archive/slug(tname)
            for idx,(role,e) in enumerate(roles):
                try:
                    e['tapir_event_html']=tapir_event_html(t,p,e,engine,raw,folder,idx)
                except (ValueError,OSError,subprocess.SubprocessError) as exc:
                    e['tapir_event_html']=None
                    log(f'  ATTENZIONE: tabella TAPIR non generata per {tname} ciclo {e["cycle"]}: {exc}')
        log('Generazione PDF, HTML e archivio...')
        manifest['counts'],manifest['selection_counts']=write_reports(out,events,targets,rejected,manifest,selection)
        from collections import Counter
        manifest['logistics_counts']=dict(Counter(e.get('logistics_class') for e in events))
        manifest['event_count']=len(events);manifest['excluded_targets']=rejected
        manifest['anomalies']=sum(e['tapir_anomaly'] for e in events)
        manifest['max_timing_residual_seconds']=max((abs(e['timing_residual_seconds']) for e in events),default=None)
        manifest['status']='complete' if targets else 'no_usable_targets'
        manifest['runtime_seconds_before_zip']=round(clock.monotonic()-began,2)
        warnfile.close()
        manifest['source_sha256']={str(f.relative_to(raw)):hashlib.sha256(f.read_bytes()).hexdigest() for f in raw.rglob('*') if f.is_file()}
        dump(archive/'manifest.json',manifest)
        zip_path=shutil.make_archive(str(out),'zip',root_dir=out.parent,base_dir=out.name)
        log(f'COMPLETATO: {out}\nZIP: {zip_path}\nEventi: {len(events)}; anomalie TAPIR: {manifest["anomalies"]}; tempo totale: {clock.monotonic()-began:.1f} s')
        return 0 if targets else 2
    except Exception as exc:
        manifest.update(status='failed',error=str(exc));dump(archive/'manifest.json',manifest)
        raise
    finally:
        if not warnfile.closed: warnfile.close()


if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('ERRORE: '+str(exc),file=sys.stderr);sys.exit(2)
