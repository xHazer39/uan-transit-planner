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
from datetime import datetime
from urllib.parse import urlencode
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from observing import geometry_label
from astropy.coordinates import SkyCoord
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


def make_pdf(path,title,events,targets,p):
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallUAN',fontName='Helvetica',fontSize=8.2,leading=11,spaceAfter=4))
    styles.add(ParagraphStyle(name='CardUAN',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=colors.HexColor('#123b50'),spaceAfter=5))
    para=lambda s: Paragraph(s,styles['SmallUAN'])
    story=[Paragraph('UAN Transit Planner',styles['Title']),Paragraph(title,styles['Heading1']),
           para(f'{html.escape(p["name"])} | {html.escape(p["timezone"])} | {len(events)} eventi in fascia pratica'),
           para(f'Copertura: quota ≥ {p["visibility_altitude_deg"]}° e Sole ≤ {p["twilight_deg"]}°. '
                'Orari con data e offset UTC. La baseline può terminare dopo il limite del transito. '
                'Sintesi locale di eventi TAPIR con metriche Astropy; categorie organizzative, non ufficiali UAN.'),Spacer(1,12)]
    if not events:
        story.append(para('Nessun evento soddisfa questa categoria e la disponibilità pratica nell’intervallo richiesto. '
                          'Consultare l’archivio completo per gli eventi fuori orario e le esclusioni.'))
    for e in events:
        chart,air=links(e,targets[e['name']],p)
        head=Paragraph(html.escape(e['name'])+' · '+html.escape(e['mid_local'][:10]),styles['CardUAN'])
        rows=[['Ingresso locale','Centro locale','Uscita locale'],
              [e[k].replace('T',' ') for k in ('ingress_local','mid_local','egress_local')],
              ['Quote ingresso / centro / uscita','Transito / entro orari','Baseline pratica prima / dopo'],
              [f'{fmt(e["altitude_ingress_deg"])} / {fmt(e["altitude_mid_deg"])} / {fmt(e["altitude_egress_deg"])}°',
               f'{fmt(e["transit_percent"])}% / {fmt(e["practical_transit_percent"])}%',
               f'{fmt(e.get("practical_baseline_before_minutes",e["baseline_before_minutes"]))} / {fmt(e.get("practical_baseline_after_minutes",e["baseline_after_minutes"]))} min']]
        table=Table([[para(html.escape(str(v))) for v in row] for row in rows],colWidths=[171]*3)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5eef2')),
              ('BACKGROUND',(0,2),(-1,2),colors.HexColor('#e5eef2')),('VALIGN',(0,0),(-1,-1),'TOP'),
              ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
        info=f'Durata {fmt(e["duration_minutes"])} min · quota min/max {fmt(e["altitude_min_deg"])} / {fmt(e["altitude_max_deg"])}° · '
        info+=f'{html.escape(e["magnitude_band"])} {fmt(e["magnitude"])} · profondità {fmt(e["depth_ppt"])} ppt.'
        moon=f'Luna al centro: {fmt(e["moon_illumination_percent"])}% a {fmt(e["moon_separation_deg"])}°, quota {fmt(e["moon_altitude_mid_deg"])}°. '
        moon+=f'Incertezza centro: {fmt(e["uncertainty_minutes"])} min. Baseline richiesta per lato: {fmt(e["baseline_denominator_minutes_per_side"])} min.'
        session='Sessione desiderata: '+e['session_start_local'].replace('T',' ')+' → '+e['session_end_local'].replace('T',' ')
        card=[head,table,Spacer(1,5),para(info),para(moon),para(html.escape(session)),
              para('<b>'+html.escape(e['reason'])+'</b>'),para(html.escape(e.get('logistics_note',''))),
              para(f'<link href="{html.escape(chart,quote=True)}" color="#14648a">Carta del campo (Aladin, online)</link> · '
                   f'<link href="{html.escape(air,quote=True)}" color="#14648a">Grafico airmass (online)</link>'),Spacer(1,15)]
        story.append(KeepTogether(card))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.grey)
        canvas.drawString(40,23,'Ricalcolare le effemeridi prima di osservare. Dettagli e fonti nell’archivio.')
        canvas.drawRightString(A4[0]-40,23,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=35,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)


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
    """Policy UAN v2.1: per-target PRIMARY + BACKUP1 + BACKUP2 from the P1 pool,
    ordered by quality class then score, with temporal diversification of backups."""
    by={}
    for e in events:
        if e.get('logistics_class')=='P1' and e['category']!='NON CONSIGLIATO':
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
                for cat in ('PRIMA SCELTA','ALTERNATIVE','DA VALUTARE'):
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
       'a{{color:#126a8a;text-decoration:none}}</style><body>{body}</body></html>')


MONTHS_IT=('GENNAIO','FEBBRAIO','MARZO','APRILE','MAGGIO','GIUGNO',
           'LUGLIO','AGOSTO','SETTEMBRE','OTTOBRE','NOVEMBRE','DICEMBRE')


def chronological_selection(groups):
    """Presentation-only: flatten per-target roles into one global list ordered by
    mid_local (timezone-aware ISO, Europe/Rome). Never changes roles or classes."""
    flat=[(name,role,e) for name,roles in groups for role,e in roles]
    flat.sort(key=lambda item:datetime.fromisoformat(item[2]['mid_local']))
    return flat


CALENDAR_FIELDS=['event_id','target','start_local','mid_local','end_local','quality_class',
                 'logistics_class','selection_role','display_role','score',
                 'altitude_start_deg','altitude_mid_deg','altitude_end_deg','transit_percent',
                 'baseline_before_percent','baseline_after_percent','moon_risk',
                 'moon_illumination_percent','moon_min_separation_deg','reason_codes']


def calendar_rows(events,quality):
    """All events of one quality class with logistics P1, globally chronological.
    Presentation only: never mutates events. display_role = selection_role or EXTRA."""
    rows=[dict(e) for e in events
          if e.get('quality_class')==quality and e.get('logistics_class')=='P1']
    for e in rows:
        e['display_role']=e.get('selection_role') or 'EXTRA'
        e['event_id']=slug(e['name'])+'-c'+str(e['cycle'])
        e.setdefault('start_local',e.get('ingress_local'))
        e.setdefault('end_local',e.get('egress_local'))
        e.setdefault('target',e['name'])
    rows.sort(key=lambda e:datetime.fromisoformat(e['mid_local']))
    return rows


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
    head=('<tr><th>Data</th><th>Target</th><th>Role</th><th>Inizio</th><th>Centro</th><th>Fine</th>'
          '<th>El&deg; i/m/f</th><th>Trans%</th><th>Base% i/f</th><th>Luna</th><th>Score</th>'
          '<th>Codes</th><th>Link</th></tr>')
    out=['<table class="cal">'+head]
    current=None
    for e in rows:
        mid=datetime.fromisoformat(e['mid_local'])
        if (mid.year,mid.month)!=current:
            current=(mid.year,mid.month)
            out.append('<tr class="monthrow"><td colspan="13">'+MONTHS_IT[mid.month-1]+' '+str(mid.year)+'</td></tr>')
        t=target_map.get(e['name'],{})
        chart,air=links(e,t,p) if t else ('#','#')
        nasa='https://exoplanetarchive.ipac.caltech.edu/overview/'+quote(e['name'].replace(' ','%20'))
        codes=','.join(e.get('reason_codes') or []) or '&mdash;'
        display=e.get('display_role','')
        role_cls={'PRIMARY':'r-primary','BACKUP1':'r-backup','BACKUP2':'r-backup'}.get(display,'r-extra')
        out.append('<tr class="'+role_cls+'">'
            +'<td>'+mid.strftime('%d/%m')+'</td>'
            +'<td class="tgt">'+html.escape(e['name'])+'</td>'
            +'<td class="role">'+display+'</td>'
            +'<td>'+datetime.fromisoformat(e['start_local']).strftime('%H:%M')+'</td>'
            +'<td>'+mid.strftime('%H:%M')+'</td>'
            +'<td>'+datetime.fromisoformat(e['end_local']).strftime('%H:%M')+'</td>'
            +'<td>'+fmt(e['altitude_ingress_deg'],0)+'/'+fmt(e['altitude_mid_deg'],0)+'/'+fmt(e['altitude_egress_deg'],0)+'</td>'
            +'<td>'+fmt(e['transit_percent'],0)+'</td>'
            +'<td>'+fmt(e['baseline_before_percent'],0)+'/'+fmt(e['baseline_after_percent'],0)+'</td>'
            +'<td>'+fmt(e['moon_illumination_percent'],0)+'% @'+fmt(e['moon_min_separation_deg'],0)+'&deg;</td>'
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


def calendar_pdf(path,title,rows,tz,target_map,p):
    return _chromium_render(calendar_document(rows,title,tz,target_map,p),path)


def write_calendar_files(archive,rows):
    """Machine-readable calendar (CSV+JSON), already chronological."""
    clean=[{k:(e.get(k) if k!='reason_codes' else list(e.get('reason_codes') or [])) for k in CALENDAR_FIELDS} for e in rows]
    (archive/'calendario_prima_scelta.json').write_text(json.dumps(clean,indent=2,ensure_ascii=False))
    with (archive/'calendario_prima_scelta.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=CALENDAR_FIELDS)
        w.writeheader()
        for r in clean:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    return clean


def selection_tapir_pdf(path,title,groups,archive,note,tz):
    """Selection PDF in global chronological order with month separators."""
    flat=chronological_selection(groups)
    assets='';intro='';body=[];first_fragment=True;current_month=None
    for name,role,e in flat:
        mid=datetime.fromisoformat(e['mid_local'])
        body.append('<div class="pb">')
        if (mid.year,mid.month)!=current_month:
            body.append('<h2 class="monthhdr">'+MONTHS_IT[mid.month-1]+' '+str(mid.year)+'</h2>')
            current_month=(mid.year,mid.month)
        body.append('<h2 class="tgthdr">'+html.escape(name)+' — '+role+'</h2>')
        body.append('<p>Centro locale: '+mid.strftime('%d/%m/%Y %H:%M')+' '+html.escape(tz)
                    +'<br/>Classe: '+html.escape(e['category'])
                    +'<br/>Score: '+fmt(e.get('score'))+'</p>')
        page=(archive/e['tapir_event_html']).read_text()
        pieces=_tapir_pieces(page)
        if pieces is None: return False
        a,i,t=pieces
        if first_fragment:
            assets+=a;intro+=i;first_fragment=False
        body.append('<p style="font-size:10px">Tabella TAPIR originale: orari UTC.</p>')
        body.append(t)
        body.append('</div>')
    cover=('<div class="coverbox"><h1>'+html.escape(title)+'</h1>'
           '<p><b>'+str(len(groups))+' target, '+str(len(flat))+' eventi selezionati in ordine cronologico.</b></p></div>'
           '<p style="font-size:10px">'+note+'</p>')
    doc=_HEAD.format(title=title,assets=assets,body=cover+intro+'\n'.join(body))
    return _chromium_render(doc,path)


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
    note=('Policy UAN v2.1: PRIMARY + BACKUP1 + BACKUP2 sono le tre raccomandazioni principali '
          'per target (pool P1, qualita\' prima della separazione: >= '
          +str(int(p['backup_preferred_separation_days']))+' giorni, fallback >= '
          +str(int(p['backup_fallback_separation_days']))+'): sono raccomandazioni, NON un filtro. '
          'EXTRA = ulteriore occasione valida della stessa classe, non nascosta. '
          'Percentuali di copertura/baseline ricalcolate in modo indipendente; TAPIR resta nel dettaglio per evento. '
          'Tutti gli eventi sono conservati in 9_ARCHIVIO_COMPLETO.')
    # Calendari semanticamente puri: 1=PRIMA SCELTA+P1, 2=ALTERNATIVE+P1; 3=review curata.
    tz=p['timezone']
    cal1=calendar_rows(events,'PRIMA SCELTA')
    cal2=calendar_rows(events,'ALTERNATIVE')
    rev3=curated_review_rows(events,p)
    (archive/'1_PRIMA_SCELTA.html').write_text(calendar_document(cal1,'CALENDARIO OPERATIVO - PRIMA SCELTA',tz,target_map,p),encoding='utf-8')
    (archive/'2_ALTERNATIVE.html').write_text(calendar_document(cal2,'ALTERNATIVE - occasioni operative',tz,target_map,p),encoding='utf-8')
    write_calendar_files(archive,cal1)
    manifest['reporting']={'calendar_mode':'chronological','timezone':tz,
        'first_choice_scope':'all PRIMA SCELTA + P1',
        'selection_roles_preserved':True,'extra_events_visible':True,
        'calendar_events':len(cal1),'calendar_extra_events':sum(1 for e in cal1 if e['display_role']=='EXTRA')}
    for i,(category,rows) in enumerate([('PRIMA SCELTA',cal1),('ALTERNATIVE',cal2),('DA VALUTARE',rev3)],1):
        target=out/f'{i}_{category.replace(" ","_")}.pdf'
        if not rows:
            make_pdf(target,category,[],target_map,p); continue
        try:
            if calendar_pdf(target,category,rows,tz,target_map,p): continue
        except (OSError,KeyError):
            pass
        make_pdf(target,category,rows,target_map,p)
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
la selezione operativa per target (policy UAN v2.1).
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
Eleggibilita' PRIMA SCELTA: copertura >= {p['first_choice_min_percent']:.1f}% (policy v2.1).
Luna: metriche al centro, minimo della distanza campionato ogni <=10 minuti;
livelli di rischio BASSA/MODERATA/ALTA/ESTREMA (dettagli nella sezione POLICY).

POLICY UAN TRANSIT PLANNER v2.1 (gerarchia rigida; uno score alto non compensa livelli superiori)
1. Integrita' temporale: TTV, residuo BJD > {p['timing_residual_limit_seconds']:.0f} s o errore centro > {p['maximum_uncertainty_minutes']:.0f} min -> DA VALUTARE.
2. Geometria del target dal sito: quota teorica < {p['severe_altitude_deg']}° -> NON CONSIGLIATO DAL SITO
   ({p['severe_altitude_deg']}-{p['visibility_altitude_deg']}° MOLTO DIFFICILE, {p['visibility_altitude_deg']}-{p['preferred_altitude_deg']}° MARGINALE,
   {p['preferred_altitude_deg']}-{p['excellent_altitude_deg']}° BUONO, >= {p['excellent_altitude_deg']}° MOLTO FAVOREVOLE).
3. Copertura transito (ricalcolata indipendentemente, mai la percentuale TAPIR alla cieca):
   < {p['transit_operational_percent']:.0f}% -> DA VALUTARE; {p['transit_operational_percent']:.0f}-{p['first_choice_min_percent']:.1f}% -> max ALTERNATIVE; >= {p['first_choice_min_percent']:.1f}% -> eleggibile PRIMA SCELTA.
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
