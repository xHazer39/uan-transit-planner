"""Readable local summaries, originals remain separate and explicitly unvalidated."""
import csv
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from observing import geometry_label
from astropy.coordinates import SkyCoord,EarthLocation
import astropy.units as u
from astropy.time import Time

CATEGORIES=['PRIMA SCELTA','ALTERNATIVE','DA VALUTARE','NON CONSIGLIATO']
BASE='https://astro.swarthmore.edu/transits/'


def slug(name):
    return re.sub(r'[^a-zA-Z0-9_.-]+','_',name).strip('._') or 'target'


def fmt(x,d=1):
    return 'n/d' if x is None else f'{x:.{d}f}'


def links(e,t,p):
    c=SkyCoord(t['RA'],t['Dec'],unit=(u.hourangle,u.deg))
    chart=BASE+'aladin.html?'+urlencode(dict(name=t['name'],ra=c.ra.deg,dec=c.dec.deg))
    # plot_airmass takes central JD in full, start/end as JD-2450000, as upstream template.
    mid=Time(datetime.fromisoformat(e['mid_utc'])).jd
    begin=Time(datetime.fromisoformat(e['ingress_utc'])).jd-2450000
    end=Time(datetime.fromisoformat(e['egress_utc'])).jd-2450000
    air=BASE+'plot_airmass.cgi?'+urlencode(dict(observatory_string='Specified_Lat_Long',
        observatory_latitude=p['latitude'],observatory_longitude=p['longitude'],
        target=t['name'],ra=c.ra.hour,dec=c.dec.deg,timezone=p['timezone'],jd=mid,
        jd_start=begin,jd_end=end,use_utc=0,max_airmass=4))
    return chart,air


def chromium_pdf(html_path,pdf_path):
    exe=shutil.which('chromium') or shutil.which('chromium-browser') or \
        ('/snap/bin/chromium' if os.path.exists('/snap/bin/chromium') else None)
    if not exe: return False
    try:
        r=subprocess.run([exe,'--headless','--disable-gpu','--virtual-time-budget=20000',
                          '--no-pdf-header-footer',f'--print-to-pdf={pdf_path}',str(html_path)],
                         capture_output=True,text=True,timeout=180)
    except (OSError,subprocess.SubprocessError):
        return False
    return r.returncode==0 and Path(pdf_path).is_file() and Path(pdf_path).stat().st_size>1000


TAPIR_KEEP_COLUMNS={0,1,2,3,4,5,7}

QUALITY_RANK={'PRIMA SCELTA':0,'ALTERNATIVE':1,'DA VALUTARE':2,'NON CONSIGLIATO':3}


def compute_selection(events,p):
    """Policy UAN v2.2.0: per-target PRIMARY + BACKUP1 + BACKUP2 from the P1 pool,
    restricted to exact-100% favorable events, ordered by quality class then score, with temporal diversification of backups."""
    by={}
    for e in events:
        if (e.get('logistics_class')=='P1' and e.get('category') in ('PRIMA SCELTA','ALTERNATIVE')
                and e.get('transit_percent',100)>=100):
            e['mid_ts']=datetime.fromisoformat(e['mid_utc']).timestamp()
            by.setdefault(e['name'],[]).append(e)
    selection={}
    for name,pool in by.items():
        pool.sort(key=lambda e:(QUALITY_RANK[e['category']],-e.get('score',0),e['mid_utc']))
        for rank,e in enumerate(pool,1): e['rank_within_target']=rank
        picks=[pool[0]]
        for role in ('BACKUP1','BACKUP2'):
            remaining=[e for e in pool if not any(e is q for q in picks)]
            got=None
            if remaining:
                # Quality dominates separation: best class first; within a class
                # prefer >= preferred separation, then >= fallback, then next class.
                for cat in ('PRIMA SCELTA','ALTERNATIVE'):
                    cls=[e for e in remaining if e['category']==cat]
                    if not cls: continue
                    for sep in (p['backup_preferred_separation_days'],p['backup_fallback_separation_days']):
                        got=next((e for e in cls if all(abs(e['mid_ts']-q['mid_ts'])>=sep*86400 for q in picks)),None)
                        if got: break
                    if got: break
                if got is None:
                    got=remaining[0]
            if got is None: break
            picks.append(got)
        roles=[('PRIMARY',picks[0])]
        if len(picks)>1: roles.append(('BACKUP1',picks[1]))
        if len(picks)>2: roles.append(('BACKUP2',picks[2]))
        for role,e in roles: e['selection_role']=role
        selection[name]=roles
    return selection


def _strip_hidden_columns(table):
    """Static equivalent of TAPIR's JS column visibility defaults."""
    def fix_row(m):
        row=m.group(0)
        cells=re.findall(r'<t[dh][^>]*>.*?</t[dh]>',row,re.S)
        if len(cells)!=14:
            return row
        return row[:row.index(cells[0])]+''.join(c for i,c in enumerate(cells) if i in TAPIR_KEEP_COLUMNS)+'</tr>'
    return re.sub(r'<tr[^>]*>.*?</tr>',fix_row,table,flags=re.S)


def _tapir_pieces(page):
    """(stylesheet links, intro paragraphs, cleaned table) from one TAPIR HTML page."""
    page=re.sub(r'<script.*?</script>','',page,flags=re.S|re.I)
    page=re.sub(r'<p style="background:#fff2cf.*?</p>','',page,flags=re.S|re.I)
    m=re.search(r'<table.*?</table>',page,flags=re.S|re.I)
    if not m: return None
    assets=''.join(re.findall(r'<link[^>]*stylesheet[^>]*>',page,flags=re.I))
    assets+=''.join(re.findall(r'<style.*?</style>',page,flags=re.S|re.I))
    intro=''
    for pat in (r'<p>Only 1 target matches.*?</p>',r'<h2>.*?</h2>',r'<h3>.*?</h3>'):
        mm=re.search(pat,page,flags=re.S|re.I)
        if mm: intro+=mm.group(0)
    return assets,intro,_strip_hidden_columns(m.group(0))


def _chromium_render(doc,path):
    tmpd=Path(tempfile.mkdtemp(prefix='uan-render-',dir=Path.home()))
    try:
        tmp=tmpd/'render.html'
        tmp.write_text(doc,encoding='utf-8')
        raw_pdf=tmpd/'out.pdf'
        ok=chromium_pdf(tmp,raw_pdf)
        if ok: shutil.move(str(raw_pdf),str(path))
    finally:
        shutil.rmtree(tmpd,ignore_errors=True)
    return ok


_HEAD=('<!doctype html><html lang="it"><meta charset="utf-8"><title>{title}</title>'
       '<base href="'+BASE+'">{assets}<style>@page{{size:A4 landscape;margin:9mm}}'
       'body{{font-family:"DejaVu Sans",sans-serif;font-size:11px}}h1{{font-size:17px;margin:2px 0}}'
       'h2{{font-size:13px}}h3{{font-size:12px}}h2.tgthdr{{border-bottom:2px solid #123b50;padding-bottom:2px}}'
       'h2.monthhdr{{font-size:15px;margin:10px 0 6px;color:#123b50;letter-spacing:1px}}'
       '.pb{{page-break-after:always}}.coverbox{{border:2px solid #000;padding:6px 10px;margin-bottom:8px}}'
       '.rolehdr{{margin:6px 0 2px}}'
       'table.cal{{border-collapse:collapse;width:100%;font-size:8.5px;margin-top:6px}}'
       'table.cal th{{background:#e5eef2;border:1px solid #b9ccd4;padding:2px 3px;text-align:left}}'
       'table.cal td{{border:1px solid #ccd8de;padding:2px 3px;vertical-align:top}}'
       'tr.monthrow td{{background:#123b50;color:#fff;font-weight:bold;font-size:10px;letter-spacing:1px}}'
       'tr.r-primary td.role{{color:#0a7d2c;font-weight:bold}}'
       'tr.r-backup td.role{{color:#14648a;font-weight:bold}}'
       'tr.r-extra td.role{{color:#555}}'
       'td.tgt{{font-weight:bold}}td.codes{{font-size:7.5px;color:#7a4a00}}'
       'td.q{{font-size:7.5px}}tr.q-prima td.q{{color:#0a7d2c;font-weight:bold}}tr.q-alt td.q{{color:#8a5a14}}'
       'a{{color:#126a8a;text-decoration:none}}'
       '</style><body>{body}</body></html>')
DOSSIER_CSS=('<style>table.idx{border-collapse:collapse;font-size:10px;margin:6px 0 10px}'
             'table.idx th,table.idx td{border:1px solid #ccd8de;padding:2px 6px;text-align:left}'
             'table.idx th{background:#e5eef2}'
             '.disclaimer{border:2px solid #123b50;background:#eef6f9;padding:8px;font-size:10px;margin:8px 0}'
             'h2.tapirband{background:#fff2cf;border:2px solid #b98a00;padding:6px;font-size:12px;margin:10px 0 6px;page-break-before:always}'
             'div.evblk{break-inside:avoid;margin:8px 0}</style>')


MONTHS_IT=('GENNAIO','FEBBRAIO','MARZO','APRILE','MAGGIO','GIUGNO',
           'LUGLIO','AGOSTO','SETTEMBRE','OTTOBRE','NOVEMBRE','DICEMBRE')


MONTHS_IT=('GENNAIO','FEBBRAIO','MARZO','APRILE','MAGGIO','GIUGNO',
           'LUGLIO','AGOSTO','SETTEMBRE','OTTOBRE','NOVEMBRE','DICEMBRE')


CALENDAR_FIELDS=['event_id','target','start_local','mid_local','end_local','quality_class',
                 'logistics_class','selection_role','display_role','score',
                 'altitude_start_deg','altitude_mid_deg','altitude_end_deg','transit_percent',
                 'baseline_before_percent','baseline_after_percent','moon_risk',
                 'moon_illumination_percent','moon_min_separation_deg','reason_codes']


def _prep_calendar(events,qualities,default_role):
    """Shared presentation-only row prep: P1 events of the given quality classes,
    chronological by mid_local. Never mutates input events."""
    rows=[dict(e) for e in events
          if (e.get('logistics_class')=='P1' and e.get('quality_class') in qualities
              and e.get('transit_percent',100)>=100)]
    for e in rows:
        e['display_role']=e.get('selection_role') or default_role
        e['event_id']=slug(e['name'])+'-c'+str(e['cycle'])
        e.setdefault('start_local',e.get('ingress_local'))
        e.setdefault('end_local',e.get('egress_local'))
        e.setdefault('target',e['name'])
    rows.sort(key=lambda e:datetime.fromisoformat(e['mid_local']))
    return rows


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


def tapir_event_html(t,p,e,engine,raw,folder,idx=None):
    """One ground TAPIR HTML query bounded to a single event: table for the dossiers.
    Fragment names are deterministic per event (cycle): no cross-generation collisions."""
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
    name=f'{slug(t["name"])}_event_c{e["cycle"]}'
    (raw/(name+'.txt')).write_text(proc.stdout)
    (raw/(name+'.log')).write_text(proc.stderr)
    if proc.returncode: raise ValueError('TAPIR fallito (evento): '+proc.stderr[-200:])
    body=proc.stdout[proc.stdout.lower().find('<!doctype'):] if '<!doctype' in proc.stdout.lower() else proc.stdout[proc.stdout.lower().find('<html'):]
    body=re.sub(r'<head[^>]*>',lambda m:m.group(0)+'<base href="'+BASE+'">',body,count=1,flags=re.I)
    (folder/f'tapir_event_c{e["cycle"]}.html').write_text(body)
    return f'{folder.name}/tapir_event_c{e["cycle"]}.html'



def tapir_fragment_identity(frag_html):
    """(target, mid_utc_naive) estratti dalla riga TAPIR autentica, o (None,None).
    La colonna Start-Mid-End e' individuata dall'header della tabella; il midpoint
    e' il terzo orario della cella (sugg-start, start, MID, end, sugg-end)."""
    headers=[]
    for row in re.findall(r'<tr[^>]*>.*?</tr>',frag_html,re.S):
        ths=re.findall(r'<th[^>]*>(.*?)</th>',row,re.S)
        if ths:
            headers=ths
            break
    col=None
    for i,th in enumerate(headers):
        if 'Start' in th and 'Mid' in th:
            col=i
            break
    if col is None:
        return None,None
    for row in re.findall(r'<tr[^>]*>.*?</tr>',frag_html,re.S):
        if 'Finding charts' not in row:
            continue
        cells=re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)
        if col>=len(cells):
            continue
        cell=cells[col].replace('&nbsp;',' ')
        dts=re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',cell)
        if len(dts)<3:
            continue
        nm=re.search(r'<a[^>]*>([^<]+)</a>',row)
        return (nm.group(1).strip() if nm else None,
                datetime.strptime(dts[2],'%Y-%m-%d %H:%M'))
    return None,None


def tapir_fragment_valid(frag_html,target_name,expected_mid_utc,tz,tol_s=120):
    """Content check del frammento TAPIR aggregato: il target e il midpoint
    (orari TAPIR convertiti in Europe/Rome) devono coincidere con l'evento
    del planner entro tol_s secondi. Restituisce (ok, motivo)."""
    name,mid=tapir_fragment_identity(frag_html)
    if name is None or mid is None:
        return False,'riga evento TAPIR (target/midpoint) non trovata nel frammento'
    if name!=target_name:
        return False,f'target TAPIR "{name}" != planner "{target_name}"'
    expected=datetime.fromisoformat(expected_mid_utc).replace(tzinfo=None)
    delta=abs((mid-expected).total_seconds())
    if delta>tol_s:
        return False,f'midpoint TAPIR discordante di {delta:.0f} s'
    return True,''


def ensure_tapir_fragment(e,t,p,archive):
    """Canonical, collision-free fragment for one dossier row:
    {slug}/tapir_event_c{cycle}.html. Strategies: (1) canonical path already valid,
    (2) stored pointer still valid -> copy it under the canonical name,
    (3) regenerate via a presentation-only TAPIR query. Every candidate is
    content-validated (planner target name + midpoint TAPIR in Europe/Rome within
    tolerance); on failure the invalid fragment is NEVER embedded - explicit error.
    Never mutates scientific fields."""
    rel=f"{slug(e['name'])}/tapir_event_c{e['cycle']}.html"
    path=archive/rel
    tz=ZoneInfo(p['timezone'])
    engine=archive/'dati_originali'/'tapir_source'
    reason='frammento assente'
    for attempt in range(3):
        if attempt==1:
            stored=e.get('tapir_event_html')
            if stored and (archive/stored).is_file() and (archive/stored) != path:
                shutil.copyfile(archive/stored,path)
        if attempt==2:
            tapir_event_html(t,p,e,engine,archive/'dati_originali',archive/slug(e['name']))
        if path.is_file():
            ok,reason=tapir_fragment_valid(path.read_text(),e['name'],e['mid_utc'],tz)
            if ok:
                return rel
        if attempt==2:
            raise ValueError(f'Frammento TAPIR non valido per {e["event_id"]} ({reason}); '
                             'nessun frammento sbagliato inserito nel dossier')
    raise ValueError('irraggiungibile')


def calendar_rows(events,quality):
    """All events of one quality class with logistics P1, globally chronological.
    Presentation only: never mutates events. display_role = selection_role or EXTRA."""
    return _prep_calendar(events,{quality},'EXTRA')


def operational_rows(events):
    """Operational calendar: PRIMA SCELTA and ALTERNATIVE events with logistics P1."""
    return _prep_calendar(events,{'PRIMA SCELTA','ALTERNATIVE'},'EXTRA')


def curated_review_rows(events,p):
    """DA VALUTARE: per target the best P1 events (max configured), then chronological."""
    by={}
    for e in events:
        if e.get('quality_class')=='DA VALUTARE' and e.get('logistics_class')=='P1':
            by.setdefault(e['name'],[]).append(e)
    picked=[]
    for name,group in by.items():
        group.sort(key=lambda e:(-e.get('score',0),e['mid_local']))
        picked+=group[:int(p['max_review_events_per_target'])]
    rows=[dict(e) for e in picked]
    for e in rows:
        e['display_role']=e.get('selection_role') or 'REVIEW'
        e['event_id']=slug(e['name'])+'-c'+str(e['cycle'])
        e.setdefault('start_local',e.get('ingress_local'))
        e.setdefault('end_local',e.get('egress_local'))
        e.setdefault('target',e['name'])
    rows.sort(key=lambda e:datetime.fromisoformat(e['mid_local']))
    return rows


def _calendar_table(rows,tz,target_map,p,notes=True):
    """Compact TAPIR-style calendar table (multiple events per page)."""
    from urllib.parse import quote
    head=('<tr><th>Data</th><th>Target</th><th>Classe</th><th>Role</th><th>Inizio</th><th>Centro</th><th>Fine</th>'
          '<th>El&deg; i/m/f</th><th>Trans%</th><th>Base% i/f</th><th>Luna</th><th>Rischio</th><th>Score</th>'
          '<th>Codes</th><th>Link</th></tr>')
    out=['<table class="cal">'+head]
    current=None
    for e in rows:
        mid=datetime.fromisoformat(e['mid_local'])
        if (mid.year,mid.month)!=current:
            current=(mid.year,mid.month)
            out.append('<tr class="monthrow"><td colspan="15">'+MONTHS_IT[mid.month-1]+' '+str(mid.year)+'</td></tr>')
        t=target_map.get(e['name'],{})
        chart,air=links(e,t,p) if t else ('#','#')
        nasa='https://exoplanetarchive.ipac.caltech.edu/overview/'+quote(e['name'].replace(' ','%20'))
        codes=','.join(e.get('reason_codes') or []) or '&mdash;'
        display=e.get('display_role','')
        role_cls={'PRIMARY':'r-primary','BACKUP1':'r-backup','BACKUP2':'r-backup'}.get(display,'r-extra')
        qcls='q-prima' if e.get('quality_class')=='PRIMA SCELTA' else 'q-alt'
        out.append('<tr class="'+role_cls+' '+qcls+'">'
            +'<td>'+mid.strftime('%d/%m')+'</td>'
            +'<td class="tgt">'+html.escape(e['name'])+'</td>'
            +'<td class="q">'+html.escape(e['quality_class'])+'</td>'
            +'<td class="role">'+display+'</td>'
            +'<td>'+datetime.fromisoformat(e['start_local']).strftime('%H:%M')+'</td>'
            +'<td>'+mid.strftime('%H:%M')+'</td>'
            +'<td>'+datetime.fromisoformat(e['end_local']).strftime('%H:%M')+'</td>'
            +'<td>'+fmt(e['altitude_ingress_deg'],0)+'/'+fmt(e['altitude_mid_deg'],0)+'/'+fmt(e['altitude_egress_deg'],0)+'</td>'
            +'<td>'+fmt(e['transit_percent'],0)+'</td>'
            +'<td>'+fmt(e['baseline_before_percent'],0)+'/'+fmt(e['baseline_after_percent'],0)+'</td>'
            +'<td>'+fmt(e['moon_illumination_percent'],0)+'% @'+fmt(e['moon_min_separation_deg'],0)+'&deg;</td>'
            +'<td>'+html.escape(e.get('moon_risk') or '&mdash;')+'</td>'
            +'<td>'+fmt(e.get('score'),1)+'</td>'
            +'<td class="codes">'+codes+'</td>'
            +'<td><a href="'+html.escape(chart,quote=True)+'">chart</a> <a href="'+html.escape(air,quote=True)+'">air</a> '
            +'<a href="'+html.escape(nasa,quote=True)+'">NASA</a></td></tr>')
    out.append('</table>')
    return '\n'.join(out)


def calendar_document(rows,title,tz,target_map,p):
    table=_calendar_table(rows,tz,target_map,p)
    body=(f'<div class="coverbox"><h1>{html.escape(title)}</h1>'
          f'<p><b>Orari del calendario: ora locale {html.escape(tz)}.</b> '
          f'{len(rows)} eventi; PRIMARY/BACKUP1/BACKUP2 = raccomandazioni principali, '
          f'EXTRA = ulteriore occasione valida (stessa classe, non selezionata tra le tre principali).</p></div>'
          f'<p style="font-size:10px">El&deg; i/m/f = altezza a inizio/centro/fine transito; Base% i/f = baseline osservabile '
          f'prima/dopo (denominatore = finestra richiesta); Luna = illuminazione @ separazione minima; '
          f'copertura e baseline sono ricalcoli indipendenti, non le percentuali TAPIR.</p>'+table)
    return _HEAD.format(title=title,assets='',body=body)


def write_google_calendar(archive,rows):
    """Esporta la shortlist per Google Calendar: ICS (formato nativo, timezone-safe)
    + CSV nel template Google. Orari = inizio/fine transito in ora locale."""
    # ponytail: niente folding ICS a 75 ottetti - Google accetta righe lunghe
    ics=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//UAN Transit Planner//IT','CALSCALE:GREGORIAN']
    with (archive/'1_PRIMA_SCELTA.google_calendar.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['Subject','Start Date','Start Time','End Date','End Time','All Day Event','Description','Location','Private'])
        for e in rows:
            ti=datetime.fromisoformat(e['ingress_local']);te=datetime.fromisoformat(e['egress_local'])
            tu=datetime.fromisoformat(e['mid_local'])
            summary=f"{e['name']} transito ({e['quality_class']}, {e['display_role']})"
            desc=(f"Ruolo: {e['display_role']} | Classe: {e['quality_class']} | Score: {fmt(e.get('score'))}\n"
                  f"Transito osservabile: {fmt(e['transit_percent'],0)}% | Baseline i/f: "
                  f"{fmt(e['baseline_before_percent'],0)}/{fmt(e['baseline_after_percent'],0)}%\n"
                  f"Quota i/m/f: {fmt(e['altitude_ingress_deg'],0)}/{fmt(e['altitude_mid_deg'],0)}/{fmt(e['altitude_egress_deg'],0)} gradi\n"
                  f"Luna: {fmt(e['moon_illumination_percent'],0)}% a {fmt(e['moon_min_separation_deg'],0)} gradi ({e['moon_risk']})\n"
                  f"Motivo: {e.get('reason','')}\n"
                  f"Sito: Osservatorio Astronomico di Capodimonte (ora locale)\n"
                  f"Dettagli TAPIR: https://astro.swarthmore.edu/transits/")
            ics+=['BEGIN:VEVENT',f'UID:{e["event_id"]}@uan-transit-planner',
                  'DTSTAMP:'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                  'DTSTART:'+ti.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                  'DTEND:'+te.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                  'SUMMARY:'+summary.replace(',','\\,'),
                  'DESCRIPTION:'+desc.replace('\n','\\n').replace(',','\\,').replace(';','\\;'),
                  'LOCATION:Osservatorio Astronomico di Capodimonte',
                  'END:VEVENT']
            w.writerow([f"{e['name']} transito ({e['quality_class']}, {e['display_role']})",
                        ti.strftime('%m/%d/%Y'),ti.strftime('%I:%M:%S %p'),
                        te.strftime('%m/%d/%Y'),te.strftime('%I:%M:%S %p'),'False',
                        desc,'Osservatorio Astronomico di Capodimonte','True'])
    ics.append('END:VCALENDAR')
    (archive/'1_PRIMA_SCELTA.ics').write_text('\r\n'.join(ics)+'\r\n',encoding='utf-8')


def calendar_pdf(path,title,rows,tz,target_map,p):
    return _chromium_render(calendar_document(rows,title,tz,target_map,p),path)


def tapir_dossier_document(rows,archive,tz,title,role_legend):
    """Official dossier: planner index + disclaimer + authentic aggregated TAPIR fragments.
    rows must already be the chosen chronological subset. Presentation only: never mutates
    events, never reclassifies, never re-runs TAPIR. Returns (html, first_broken_event_id)."""
    idx=['<table class="idx"><tr><th>Data</th><th>Target</th><th>Centro locale</th><th>Ruolo</th></tr>']
    body=[];assets='';first=True;current=None
    for n,e in enumerate(rows):
        mid=datetime.fromisoformat(e['mid_local'])
        anchor='event-'+e['event_id'].lower()
        if (mid.year,mid.month)!=current:
            if current is not None:
                body.append('</div>')
            # month header + first finding of the month form one indivisible block
            body.append('<div class="evblk" id="'+anchor+'"><h2 class="monthhdr">'+MONTHS_IT[mid.month-1]+' '+str(mid.year)+'</h2>')
            current=(mid.year,mid.month)
        else:
            body.append('</div><div class="evblk" id="'+anchor+'">')
        idx.append('<tr><td><a href="#'+anchor+'">'+mid.strftime('%d/%m/%Y')+'</a></td><td class="tgt">'
                   +html.escape(e['name'])+'</td><td>'+mid.strftime('%H:%M')+'</td><td class="role">'
                   +e['display_role']+'</td></tr>')
        page=archive/e['tapir_event_html']
        pieces=_tapir_pieces(page.read_text()) if page.is_file() else None
        if pieces is None:
            return None,e['event_id']
        a,i,t=pieces
        if first:
            assets+=a;first=False
        # namespace every HTML id of the fragment: no duplicate ids in the aggregated page
        t=re.sub(r'\bid="([^"]*)"',lambda m:f'id="ev{n}-{m.group(1)}"',t)
        body.append('<p class="rolehdr"><b>'+html.escape(e['name'])+'</b> — '+e['display_role']
                    +' — centro locale '+mid.strftime('%d/%m/%Y %H:%M')+' '+html.escape(tz)+'</p>'+t)
    if rows: body.append('</div>')
    idx.append('</table>')
    period=(rows[0]['mid_local'][:10]+' → '+rows[-1]['mid_local'][:10]) if rows else 'n/d'
    ntarget=len({e['name'] for e in rows})
    cover=('<div class="coverbox"><h1>'+html.escape(title)+'</h1>'
           '<p><b>'+str(len(rows))+' finding</b> · '+str(ntarget)+' target · periodo '+period+'</p>'
           '<p>Timezone operativo del planner: <b>'+html.escape(tz)+'</b></p>'
           '<p>Ruoli: '+role_legend+'</p></div>')
    disclaimer=('<div class="disclaimer"><b>Gli eventi inclusi sono selezionati dal UAN Transit Planner '
                'secondo policy UAN v2.2.0.</b><br/>Orari dell\'indice: ora locale '+html.escape(tz)+'.<br/>'
                'I dati e gli orari mostrati nelle tabelle TAPIR sottostanti sono quelli originali TAPIR '
                'e possono essere espressi in UTC.<br/>TAPIR è utilizzato come formato di presentazione '
                'dettagliato; classificazione, selezione e verifiche operative sono determinate dal planner.</div>')
    tapir_band='<h2 class="tapirband">OUTPUT TAPIR ORIGINALE — orari della tabella TAPIR: UTC</h2>'
    body_html=(cover
               +'<h2 class="monthhdr">Indice cronologico (ora locale '+html.escape(tz)+')</h2>'
               +'\n'.join(idx)+disclaimer+tapir_band+'\n'.join(body))
    doc=_HEAD.format(title=title,assets=assets+DOSSIER_CSS,body=body_html)
    return doc,None


def write_calendar_files(archive,rows,name='calendario_prima_scelta'):
    """Machine-readable calendar (CSV+JSON), already chronological."""
    clean=[{k:(e.get(k) if k!='reason_codes' else list(e.get('reason_codes') or [])) for k in CALENDAR_FIELDS} for e in rows]
    (archive/(name+'.json')).write_text(json.dumps(clean,indent=2,ensure_ascii=False))
    with (archive/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=CALENDAR_FIELDS)
        w.writeheader()
        for r in clean:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    return clean


def write_reports(out,events,targets,rejections,manifest,selection=None):
    archive=out/'9_ARCHIVIO_COMPLETO';p=manifest['profile']
    events.sort(key=lambda e:(CATEGORIES.index(e['category']),e['mid_utc'],e['name']))
    if selection is None: selection=compute_selection(events,p)
    target_map={t['name']:t for t in targets}
    with (archive/'risultati.csv').open('w',newline='',encoding='utf-8') as f:
        fields=[]
        for e in events:
            fields+= [k for k in e if k not in fields]
        if not fields: fields=['name','category','reason']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for e in events:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in e.items()})
    (archive/'risultati.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
    (archive/'target_esclusi.json').write_text(json.dumps(rejections,ensure_ascii=False,indent=2))
    counts=Counter(e['category'] for e in events)
    # Calendari semanticamente puri: 1=PRIMA SCELTA+P1, 2=ALTERNATIVE+P1; 3=review curata.
    # 0=calendario operativo unico: PRIMA SCELTA e ALTERNATIVE insieme, solo P1 e copertura 100%.
    tz=p['timezone']
    cal1=calendar_rows(events,'PRIMA SCELTA')
    cal2=calendar_rows(events,'ALTERNATIVE')
    cal0=operational_rows(events)
    rev3=curated_review_rows(events,p)
    # 0_CALENDARIO_OPERATIVO: dashboard sintetica del planner (invariata).
    (archive/'0_CALENDARIO_OPERATIVO.html').write_text(calendar_document(cal0,'CALENDARIO OPERATIVO - PRIMA SCELTA e ALTERNATIVE',tz,target_map,p),encoding='utf-8')
    write_calendar_files(archive,cal0,'0_CALENDARIO_OPERATIVO')
    write_google_calendar(archive,cal1)
    if not calendar_pdf(out/'0_CALENDARIO_OPERATIVO.pdf','CALENDARIO OPERATIVO - PRIMA SCELTA e ALTERNATIVE',cal0,tz,target_map,p):
        raise ValueError('Rendering PDF fallito per 0_CALENDARIO_OPERATIVO (chromium)')
    manifest['reporting']={'calendar_mode':'chronological','timezone':tz,
        'first_choice_scope':'all PRIMA SCELTA + P1',
        'selection_roles_preserved':True,'extra_events_visible':True,
        'calendar_events':len(cal1),'calendar_extra_events':sum(1 for e in cal1 if e['display_role']=='EXTRA'),
        'operational_calendar_events':len(cal0),
        'operational_scope':'(PRIMA SCELTA or ALTERNATIVE) and P1 and transit_percent == 100',
        'dossiers':{'1_PRIMA_SCELTA':len(cal1),'2_ALTERNATIVE':len(cal2),'3_DA_VALUTARE':len(rev3)}}
    # Dossier 1/2/3: dettaglio nel formato TAPIR autentico (renderer downstream).
    role_std='PRIMARY = prima raccomandazione · BACKUP1/BACKUP2 = riserve · EXTRA = ulteriore occasione valida della stessa classe'
    dossiers=[('1_PRIMA_SCELTA','PRIMA SCELTA',cal1,role_std),
              ('2_ALTERNATIVE','ALTERNATIVE',cal2,role_std),
              ('3_DA_VALUTARE','DA VALUTARE — shortlist di review',rev3,
               role_std+' · REVIEW = evento nella shortlist di review del target')]
    for base,cat,rows,legend in dossiers:
        # Presentation assets: canonical collision-free fragment per row, content-validated
        # (target + BJD_TDB midpoint vs planner event). Regeneration is presentation-only.
        made=0
        for e in rows:
            t=target_map[e['name']]
            old=e.get('tapir_event_html')
            rel=ensure_tapir_fragment(e,t,p,archive)
            if rel!=old: made+=1
            e['tapir_event_html']=rel
        if made: print(f'Dossier {base}: {made} frammenti rigenerati/redirectati',flush=True)
        doc,broken=tapir_dossier_document(rows,archive,tz,'UAN - '+cat,legend)
        if doc is None:
            raise ValueError('Frammento TAPIR mancante per '+broken
                             +': rigenerare le tabelle evento prima del reporting (nessuna promozione automatica)')
        (out/(base+'.html')).write_text(doc,encoding='utf-8')
        if not _chromium_render(doc,out/(base+'.pdf')):
            raise ValueError('Rendering PDF fallito per '+base+' (chromium)')
        print(f'Dossier {base}: {len(rows)} finding, {made} tabelle TAPIR generate',flush=True)
    index=[]
    target_summaries=[]
    style='<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;color:#163541;padding:16px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid #ccd8de}th{background:#e5eef2}details{margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#126a8a}</style>'
    for t in targets:
        name=t['name'];folder=archive/slug(name);folder.mkdir(exist_ok=True)
        group=[e for e in events if e['name']==name]
        c=SkyCoord(t['RA'],t['Dec'],unit=(u.hourangle,u.deg))
        hmax=90-abs(p['latitude']-c.dec.deg)
        best=min((CATEGORIES.index(e['category']) for e in group),default=None)
        roles=selection.get(name,[])
        picks=[f"{e['mid_local'][:16].replace('T',' ')} ({e['category']}, score {fmt(e.get('score'))})" for _,e in roles]
        picks+=['']*(3-len(picks))
        p1_all=sorted((e for e in group if e.get('quality_class')=='PRIMA SCELTA' and e.get('logistics_class')=='P1'),
                      key=lambda e:e['mid_local'])
        extra_dates=[datetime.fromisoformat(e['mid_local']).strftime('%d/%m/%Y') for e in p1_all if not e.get('selection_role')]
        target_summaries.append(dict(name=name,max_altitude_theoretical_deg=hmax,
            geometry_class=geometry_label(hmax,p),events=len(group),
            p1_candidates=sum(e.get('logistics_class')=='P1' and e['category']!='NON CONSIGLIATO' for e in group),
            first_choice_p1_count=len(p1_all),extra_first_choice_p1_count=len(extra_dates),
            extra_first_choice_dates=', '.join(extra_dates),
            best_astronomical_class=CATEGORIES[best] if best is not None else 'NESSUN EVENTO NEL PERIODO',
            primary=picks[0],backup1=picks[1],backup2=picks[2]))
        index.append(f'<li><a href="{slug(name)}/index.html">{html.escape(name)}</a> - {len(group)} eventi</li>')
        parts=['<!doctype html><html lang="it"><meta charset="utf-8"><title>'+html.escape(name)+'</title>'+style,
               '<h1>'+html.escape(name)+f'</h1><p>Massima quota teorica dal sito: <b>{hmax:.1f}°</b>.</p><p>Schede degli eventi, non immagini del campo stellare. '
               'Metriche indipendenti Astropy; tutte le categorie e gli orari conservati.</p>',
               '<p>Query TAPIR originali (non corrette): '+ ' · '.join(f'<a href="{f.name}">{f.stem}</a>' for f in sorted(folder.glob('tapir_*.html')) )+'</p>']
        if not group: parts.append('<p>Nessun centro di transito nel periodo richiesto.</p>')
        parts.append('<table><tr><th>Centro locale</th><th>Classe</th><th>Transito</th><th>Quota min/centro/max</th><th>Fascia pratica</th></tr>')
        for e in group:
            parts.append('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in [e['mid_local'],e['category'],fmt(e['transit_percent'])+'%',
                '/'.join(fmt(e[k]) for k in ('altitude_min_deg','altitude_mid_deg','altitude_max_deg'))+'°','Sì' if e['practical'] else 'No'])+'</tr>')
        parts.append('</table>')
        for e in group:
            chart,air=links(e,t,p)
            parts.append('<details><summary>'+html.escape(e['mid_local']+' — '+e['reason'])+'</summary>'+
                         f'<p><a href="{html.escape(chart)}">Carta del campo Aladin</a> · <a href="{html.escape(air)}">Airmass</a></p>'+
                         '<pre>'+html.escape(json.dumps(e,indent=2,ensure_ascii=False))+'</pre></details>')
        parts.append('</html>');(folder/'index.html').write_text('\n'.join(parts))
    (archive/'riepilogo_target.json').write_text(json.dumps(target_summaries,indent=2,ensure_ascii=False))
    with (archive/'riepilogo_target.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['name','max_altitude_theoretical_deg','geometry_class','events',
                                       'p1_candidates','first_choice_p1_count','extra_first_choice_p1_count',
                                       'extra_first_choice_dates','best_astronomical_class','primary','backup1','backup2'])
        w.writeheader();w.writerows(target_summaries)
    (archive/'index.html').write_text('<!doctype html><html lang="it"><meta charset="utf-8"><title>Archivio UAN</title>'+style+
                                     '<h1>Archivio completo</h1><ul>'+''.join(index)+'</ul><h2>Target esclusi</h2><pre>'+html.escape(json.dumps(rejections,indent=2,ensure_ascii=False))+'</pre></html>')
    selection_counts=Counter(e['category'] for roles in selection.values() for _,e in roles)
    summary='\n'.join(f'{c}: {counts[c]} totali; {selection_counts.get(c,0)} selezionati come PRIMARY/BACKUP' for c in CATEGORIES)
    logistics_counts=Counter(e.get('logistics_class','P3?') for e in events)
    log_summary='; '.join(f'{k}: {logistics_counts.get(k,0)}' for k in ('P1','P2','P3'))
    target_text='\n'.join(f'{t["name"]}: geometria {t["geometry_class"]} (quota teorica {t["max_altitude_theoretical_deg"]:.1f}°); '
                          f'{t["p1_candidates"]} candidati operativi (P1); PRIMARY {t["primary"] or "nessuno"}; '
                          f'BACKUP1 {t["backup1"] or "nessuno"}; BACKUP2 {t["backup2"] or "nessuno"}' for t in target_summaries)
    readme=f'''UAN TRANSIT PLANNER - policy UAN v{p.get('policy_version','2.1')}
Esecuzione UTC: {manifest['created_utc']}
Periodo dei centri di transito: {manifest['start']} incluso, {manifest['end_exclusive']} escluso, in {p['timezone']}.
Sito: {p['name']} ({p['latitude']}, {p['longitude']}, {p['height_m']} m).

COME LEGGERE IL PACCHETTO
Classificazione completa di tutti gli eventi nell'archivio; i PDF mostrano solo
la selezione operativa per target (policy UAN v2.2.0; solo transiti al 100% ricevono PRIMARY/BACKUP).
1_PRIMA_SCELTA.pdf: per ogni target con almeno una PRIMA SCELTA operativa:
PRIMARY + BACKUP1 + BACKUP2 come tabelle TAPIR originali.
2_ALTERNATIVE.pdf: target il cui miglior evento operativo e' ALTERNATIVE: selezione per target.
3_DA_VALUTARE.pdf: target con solo eventi da valutare: massimo 3 migliori con motivo esplicito.
9_ARCHIVIO_COMPLETO/index.html: TUTTI gli eventi, anche fuori orario e non consigliati.
risultati.csv / risultati.json: metriche e reason codes completi. target_esclusi.json: esclusioni.
riepilogo_target.csv: geometria del sito, candidati operativi e selezione per target.
Le schede HTML sono tabelle di eventi; le carte del campo e i grafici airmass sono link online.

RISULTATI
{summary}

LOGISTICA
{log_summary}
P1: transito interamente fra {p['session_pref_start']} e le {p['session_end']}; P2: parzialmente
nella serata operativa; P3: fuori normale serata (archivio scientifico, non nei PDF).

PER TARGET
{target_text}

Target esclusi: {len(rejections)}. Vedi archivio per motivi e fonti.

ORARI E COPERTURA
Ora locale {p['timezone']} con offset stagionale esplicito; UTC nell'archivio.
Copertura astronomica: target >= {p['visibility_altitude_deg']}°, Sole <= {p['twilight_deg']}°.
La soglia di {p['preferred_altitude_deg']}° riguarda la qualità e non la ricerca iniziale.
Disponibilità: {p['session_start']} fino alle {p['session_end']} della notte osservativa.
La baseline post-transito può terminare dopo questo limite. Controllare la sessione desiderata.
Il filtro pratico richiede ingresso e uscita nella fascia oraria; una classe DA VALUTARE
può avere soltanto una parte del transito al buio o sopra la soglia.

VALIDITÀ
Le categorie sono organizzative, non un protocollo ufficiale UAN né categorie TAPIR.
Il risultato non garantisce una misura fotometrica: strumento, stelle di confronto,
saturazione, seeing, meteo e riduzione non sono modellati.
Per osservare in futuro aggiornare catalogo ed effemeridi, ricontrollare Luna e orari.
Leggere NOTE_SELEZIONE.txt per ricostruire metodologia, dati e limitazioni.
'''
    (out/'0_LEGGIMI.txt').write_text(readme)
    notes=readme+f'''
METODO E PROVENIENZA
Fonte coordinate: {p['coordinate_source']}
TAPIR: https://github.com/elnjensen/Tapir ; commit {manifest['tapir_commit']}.
NASA: https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html
Astropy: https://docs.astropy.org/en/stable/time/index.html
Alias: https://exoplanetarchive.ipac.caltech.edu/docs/sysaliases.html

Periodi ed epoche vengono scelti dalla STESSA riga PS, solo BJD-TDB espliciti,
minimizzando il massimo errore propagato agli estremi della finestra richiesta.
Senza errori completi si preferisce una riga default coerente e si segnala incertezza ignota.
Durata e proprietà fotometriche possono provenire da PSCompPars: il fallback è registrato.
Il parser NASA upstream converte i campi nel formato TAPIR, compresa profondità % -> ppt.
Una profondità stimata e l'uso di Gaia G sono identificabili nei commenti/provenienza.
Le righe PS escluse e la riga scelta si trovano in dati_originali/selected_ephemerides.json.
Non si presume che BJD senza scala dichiarata significhi BJD-TDB.

TAPIR genera tutti gli eventi usando space=1 SOLO per enumerarli senza filtri geometrici.
Le percentuali della query space non sono usate come osservabilità da terra.
Una seconda query terrestre, quota 0°, conserva le percentuali originali e gli HTML.
Il confronto delle percentuali usa un ricalcolo Astropy alla STESSA soglia 0°.
Le metriche operative usano invece {p['visibility_altitude_deg']}°.
L'unica modifica alla copia di TAPIR è nel template CSV: aggiunge jd_utc_exact,
JD UTC completo non arrotondato come i campi jd_mid originali (JD-2450000).
Nessuna modifica al motore o al checkout originale.

Il centro UTC viene da TAPIR. Astropy verifica BJD_TDB = UTC convertito in TDB +
light travel time baricentrico. Residui >2 s penalizzano la classe.
Tempi ingresso/uscita ricostruiti dal centro e dalla durata del catalogo TAPIR.
Il periodo è lineare: TTV note penalizzano il target; non è un modello dinamico.
Errore centro = sqrt(sigma_epoca^2 + ciclo^2*sigma_periodo^2), covarianza non disponibile.
Errori mancanti restano null; l'errore sulla durata non è propagato ai contatti.
La baseline per lato è 60*baseline_hours minuti, più 1 sigma del centro se disponibile.
Ogni percentuale baseline ha quel denominatore per lato, non la somma dei due lati.
La baseline pratica prima è limitata anche dall’inizio disponibilità; quella dopo può
superare il limite del transito. I PDF mostrano i minuti pratici; le classi restano astronomiche.
Le finestre notturne nell’archivio sono limitate alla sessione calcolata, non all’intera notte.
Gli orari configurati ambigui in autunno usano la seconda occorrenza, quelli inesistenti
in primavera vengono spostati avanti. Il crepuscolo viene calcolato sulla notte effettiva.

Le finestre sono intersezioni di quota e notte, con campionamento di {p['sampling_seconds']} s
ed interpolazione lineare separata dei passaggi per quota/Sole. Non si riempiono i buchi.
Le quote min/max sono campionate, con ingresso/centro/uscita sempre inclusi.
Rifrazione disattivata, orizzonte piano; ostacoli locali non modellati.
La copertura è durata dell'intersezione / durata del transito. Non si tronca un 915%:
si conserva il dato TAPIR e si usa il nuovo calcolo. Scarti >2 punti percentuali sono segnalati.
Copertura favorevole: PRIMA SCELTA e ALTERNATIVE richiedono il 100% esatto del transito osservabile; nessun quasi-100 viene promosso.
Luna: metriche al centro, minimo della distanza campionato ogni <=10 minuti;
livelli di rischio BASSA/MODERATA/ALTA/ESTREMA (dettagli nella sezione POLICY).

POLICY UAN TRANSIT PLANNER v2.2.0 (gerarchia rigida; uno score alto non compensa livelli superiori)
1. Integrita' temporale: TTV, residuo BJD > {p['timing_residual_limit_seconds']:.0f} s o errore centro > {p['maximum_uncertainty_minutes']:.0f} min -> DA VALUTARE.
2. Geometria del target dal sito: quota teorica < {p['severe_altitude_deg']}° -> NON CONSIGLIATO DAL SITO
   ({p['severe_altitude_deg']}-{p['visibility_altitude_deg']}° MOLTO DIFFICILE, {p['visibility_altitude_deg']}-{p['preferred_altitude_deg']}° MARGINALE,
   {p['preferred_altitude_deg']}-{p['excellent_altitude_deg']}° BUONO, >= {p['excellent_altitude_deg']}° MOLTO FAVOREVOLE).
3. Copertura transito (ricalcolata indipendentemente, mai la percentuale TAPIR alla cieca):
   solo 100% esatto -> eleggibile PRIMA SCELTA/ALTERNATIVE; qualsiasi valore inferiore -> DA VALUTARE.
4. Baseline per lato (denominatore = finestra richiesta, 1 h + 1 sigma): < {p['baseline_weak_percent']:.0f}% su un lato -> DA VALUTARE;
   {p['baseline_weak_percent']:.0f}-{p['baseline_good_percent']:.0f}% -> max ALTERNATIVE; >= {p['baseline_good_percent']:.0f}% entrambi -> eleggibile PRIMA SCELTA.
5. Quota evento (assoluta, mai relativa al massimo del target): centro < {p['preferred_altitude_deg']}° -> DA VALUTARE;
   centro >= {p['preferred_altitude_deg']}° con minimo < {p['preferred_altitude_deg']}° -> max ALTERNATIVE; tutto >= {p['preferred_altitude_deg']}° -> eleggibile PRIMA SCELTA.
6. Effemeride: vedi fase 1 (TTV o sigma > 10 min -> DA VALUTARE).
7. Luna (solo se sopra l'orizzonte; sotto orizzonte = BASSA):
   ESTREMA -> DA VALUTARE: illum >=90% & sep <40°, oppure >=70% & sep <20°, oppure >=40% & sep <10°;
   ALTA -> max ALTERNATIVE: illum >=80% & sep <60°, oppure >=50% & sep <40°, oppure >=20% & sep <20°;
   MODERATA -> max ALTERNATIVE: illum >70% & sep <=100°, oppure >=50% & sep <=70°, oppure >=20% & sep <=40°;
   BASSA: nessuna penalita'. La distanza puo' essere piu' grave della fase lunare.
8. Logistica separata dalla qualita' (logistics_class): P1 transito interamente fra
   {p['session_pref_start']} e {p['session_end']}; P2 parzialmente in serata; P3 fuori normale serata (archivio scientifico).
   La baseline post-transito puo' terminare dopo il limite del transito.
9. Score secondario (solo ordinamento dentro la stessa classe): 30% copertura transito + 20% baseline minima
   + 20% quota centro (saturazione a {p['excellent_altitude_deg']}°) + 15% Luna (penalita' continua illum/100*exp(-sep/45))
   + 10% affidabilita' temporale + 5% comodita' oraria. Magnitudine e profondità sono esposte ma NON
   entrano nello score finche' non esiste un profilo reale di telescopio/camera (saturazione, rumore).
Ogni evento porta reason_codes auditabili (es. MOON_HIGH, ALTITUDE_MID_LOW, TARGET_GEOMETRY_MARGINALE).
SELEZIONE (presentation): PRIMARY + BACKUP1 + BACKUP2 per target dal pool operativo P1, ordinati per
classe poi score, con diversificazione temporale: separazione preferita >= {p['backup_preferred_separation_days']:.0f} giorni,
fallback >= {p['backup_fallback_separation_days']:.0f}. I PDF mostrano solo la selezione; tutto il resto resta nell'archivio.

LIMITI COMPUTAZIONALI
Per errori molto grandi la finestra calcolata per lato è limitata a min(P/2, 24 ore),
ma il denominatore richiesto e il flag di limitazione sono conservati.
Astropy usa effemeridi builtin e IERS distribuito con la dipendenza; avvisi sono in warnings.log.
Le previsioni future di rotazione terrestre e le effemeridi planetarie non sono misure future.
Una versione locale uguale al sito non equivale a controllo astronomico indipendente.
Gli HTML originali sono query separate. I PDF sono sintesi locali con conteggi propri.

PARAMETRI, VERSIONI E FILE
Vedi manifest.json, profilo e snapshot del sorgente in dati_originali.
Gli hash SHA256 dei file originali sono nel manifest finale.
Comando riproducibile: {manifest['command']}
'''
    (archive/'NOTE_SELEZIONE.txt').write_text(notes)
    return dict(counts),dict(selection_counts)
