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


def _strip_hidden_columns(table):
    """Static equivalent of TAPIR's JS column visibility defaults."""
    def fix_row(m):
        row=m.group(0)
        cells=re.findall(r'<t[dh][^>]*>.*?</t[dh]>',row,re.S)
        if len(cells)!=14:
            return row
        return row[:row.index(cells[0])]+''.join(c for i,c in enumerate(cells) if i in TAPIR_KEEP_COLUMNS)+'</tr>'
    return re.sub(r'<tr[^>]*>.*?</tr>',fix_row,table,flags=re.S)


def tapir_table_pdf(path,title,events,archive):
    """Category PDF as original TAPIR tables (one bounded query per event), like the historic packet."""
    frags=[];assets=''
    for k,e in enumerate(events):
        page=(archive/e['tapir_event_html']).read_text()
        page=re.sub(r'<script.*?</script>','',page,flags=re.S|re.I)
        page=re.sub(r'<p style="background:#fff2cf.*?</p>','',page,flags=re.S|re.I)
        m=re.search(r'<table.*?</table>',page,flags=re.S|re.I)
        if not m: return False
        if k==0:
            assets+=''.join(re.findall(r'<link[^>]*stylesheet[^>]*>',page,flags=re.I))
            assets+=''.join(re.findall(r'<style.*?</style>',page,flags=re.S|re.I))
            intro=''
            for pat in (r'<p>Only 1 target matches.*?</p>',r'<h2>.*?</h2>',r'<h3>.*?</h3>'):
                mm=re.search(pat,page,flags=re.S|re.I)
                if mm: intro+=mm.group(0)
        else:
            intro=''
        frags.append((intro,_strip_hidden_columns(m.group(0))))
    names=sorted({e['name'] for e in events})
    closing=' per prime.' if title=='PRIMA SCELTA' else ' come riserva o per valutazione.'
    body=['<div class="coverbox"><h1>'+html.escape(title)+' - '+html.escape(', '.join(names))+'</h1>'
          '<p><b>'+str(len(events))+' occasioni consigliate'+closing+'</b></p></div>',
          '<p style="font-size:10px">Tabelle TAPIR originali, una query per evento. Percentuali TAPIR non validate: '
          'le verifiche indipendenti sono in risultati.csv e nelle schede dell\'archivio. '
          'Orari locali con offset e UTC; testo colorato = parte di transito in luce o sotto quota scelta.</p>']
    for intro,frag in frags:
        body.append('<div class="pb">'+intro+frag+'</div>')
    doc=('<!doctype html><html lang="it"><meta charset="utf-8"><title>'+html.escape(title)+'</title>'
         '<base href="'+BASE+'">'+assets
         +'<style>@page{size:A4 landscape;margin:9mm}'
         'body{font-family:"DejaVu Sans",sans-serif;font-size:11px}h1{font-size:17px;margin:2px 0}'
         'h2{font-size:13px}h3{font-size:12px}.pb{page-break-after:always}'
         '.coverbox{border:2px solid #000;padding:6px 10px;margin-bottom:8px}</style><body>'
         +'\n'.join(body)+'</body></html>')
    # Snap chromium cannot access /tmp: render inside a home-owned temp dir, then move.
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


def write_reports(out,events,targets,rejections,manifest):
    archive=out/'9_ARCHIVIO_COMPLETO';p=manifest['profile']
    events.sort(key=lambda e:(CATEGORIES.index(e['category']),e['mid_utc'],e['name']))
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
    practical=Counter(e['category'] for e in events if e['practical'])
    for i,category in enumerate(CATEGORIES[:3],1):
        evs=[e for e in events if e['category']==category and e['practical']]
        target=out/f'{i}_{category.replace(" ","_")}.pdf'
        try:
            if evs and all(e.get('tapir_event_html') for e in evs) and tapir_table_pdf(target,category,evs,archive):
                continue
        except (OSError,KeyError):
            pass
        make_pdf(target,category,evs,target_map,p)
    index=[]
    target_summaries=[]
    style='<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;color:#163541;padding:16px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;text-align:left;border-bottom:1px solid #ccd8de}th{background:#e5eef2}details{margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#126a8a}</style>'
    for t in targets:
        name=t['name'];folder=archive/slug(name);folder.mkdir(exist_ok=True)
        group=[e for e in events if e['name']==name]
        c=SkyCoord(t['RA'],t['Dec'],unit=(u.hourangle,u.deg))
        hmax=90-abs(p['latitude']-c.dec.deg)
        best=min((CATEGORIES.index(e['category']) for e in group),default=None)
        cands=[e for e in group if e['practical'] and e['category']!='NON CONSIGLIATO']
        cands.sort(key=lambda e:(CATEGORIES.index(e['category']),-e.get('score',0),e['mid_utc']))
        picks=[f"{e['mid_local'][:16].replace('T',' ')} ({e['category']}, score {fmt(e.get('score'))})" for e in cands[:3]]
        picks+=['']*(3-len(picks))
        target_summaries.append(dict(name=name,max_altitude_theoretical_deg=hmax,
            geometry_class=geometry_label(hmax,p),events=len(group),
            practical_candidates=sum(e['practical'] and e['category']!='NON CONSIGLIATO' for e in group),
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
                                       'practical_candidates','best_astronomical_class','primary','backup1','backup2'])
        w.writeheader();w.writerows(target_summaries)
    (archive/'index.html').write_text('<!doctype html><html lang="it"><meta charset="utf-8"><title>Archivio UAN</title>'+style+
                                     '<h1>Archivio completo</h1><ul>'+''.join(index)+'</ul><h2>Target esclusi</h2><pre>'+html.escape(json.dumps(rejections,indent=2,ensure_ascii=False))+'</pre></html>')
    summary='\n'.join(f'{c}: {counts[c]} totali; {practical[c]} in fascia pratica' for c in CATEGORIES)
    target_text='\n'.join(f'{t["name"]}: geometria {t["geometry_class"]} (quota teorica {t["max_altitude_theoretical_deg"]:.1f}°); '
                          f'{t["practical_candidates"]} candidati pratici; PRIMARY {t["primary"] or "nessuno"}; '
                          f'BACKUP1 {t["backup1"] or "nessuno"}; BACKUP2 {t["backup2"] or "nessuno"}' for t in target_summaries)
    readme=f'''UAN TRANSIT PLANNER v1
Esecuzione UTC: {manifest['created_utc']}
Periodo dei centri di transito: {manifest['start']} incluso, {manifest['end_exclusive']} escluso, in {p['timezone']}.
Sito: {p['name']} ({p['latitude']}, {p['longitude']}, {p['height_m']} m).

COME LEGGERE IL PACCHETTO
1_PRIMA_SCELTA.pdf: occasioni che soddisfano le euristiche di qualità e gli orari.
2_ALTERNATIVE.pdf: transiti completi con condizioni meno favorevoli.
3_DA_VALUTARE.pdf: casi parziali, bassi, incerti o con baseline insufficiente.
I PDF vuoti spiegano che non ci sono eventi nella categoria.
9_ARCHIVIO_COMPLETO/index.html: tutti gli eventi, anche fuori orario e non consigliati.
risultati.csv / risultati.json: metriche complete. target_esclusi.json: problemi per target.
Le schede HTML sono tabelle di eventi; le carte del campo e i grafici airmass sono link online.

RISULTATI
{summary}

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
Tolleranza transito completo: {p['complete_tolerance_seconds']} s mancanti.
Luna: metriche al centro, minimo della distanza campionato ogni <=10 minuti;
penalità se contemporaneamente sopra orizzonte, nel transito visibile,
illuminazione >= {p['moon_bright_percent']}% e distanza <= {p['moon_close_deg']}°.
Una Luna brillante lontana non è automaticamente penalizzata.

POLICY UAN TRANSIT PLANNER v1 (soglie configurabili nel profilo, nessuno score compensativo)
Geometria teorica massima = 90 - abs(latitudine - declinazione J2000). Etichetta target:
sotto {p['severe_altitude_deg']}° NON CONSIGLIATO DAL SITO; fino a {p['visibility_altitude_deg']}° MOLTO DIFFICILE;
fino a {p['preferred_altitude_deg']}° MARGINALE; fino a {p['excellent_altitude_deg']}° BUONO; oltre MOLTO FAVOREVOLE.
L'etichetta descrive il target, non l'evento: 25° restano 25° reali anche se sono il massimo possibile.
Evento: copertura transito <{p['transit_operational_percent']:.0f}% -> non operativo (DA VALUTARE);
90-99% valido (ALTERNATIVE); 100% (tolleranza {p['complete_tolerance_seconds']} s) ideale.
Baseline osservabile per lato, denominatore = finestra richiesta (1 h + 1 sigma): <{p['baseline_weak_percent']:.0f}% debole
(DA VALUTARE); {p['baseline_weak_percent']:.0f}-{p['baseline_good_percent']:.0f}% accettabile (ALTERNATIVE); >= {p['baseline_good_percent']:.0f}% buona.
Centro transito sotto {p['preferred_altitude_deg']}°: DA VALUTARE. Le quote sono assolute, mai relative al massimo del target.
Dati mancanti, TTV, errore centro > {p['maximum_uncertainty_minutes']} min, residuo temporale > 2 s: DA VALUTARE.
Luna: penalita' solo nella zona critica (illuminazione >= {p['moon_bright_percent']:.0f}%, distanza <= {p['moon_close_deg']:.0f}°,
sopra orizzonte durante il transito osservabile); una Luna brillante ma lontana non scarta l'evento.
PRIMA SCELTA: transito completo, baseline >= {p['baseline_good_percent']:.0f}% per lato, tutto sopra {p['preferred_altitude_deg']}°, Luna ed errori nei limiti.
NON CONSIGLIATO: collo di bottiglia strutturale (geometria target) o evento senza transito utile al buio.
Magnitudine e profondità sono esposte, senza inventare una sensibilità dello strumento.

SCORE SECONDARIO 0-100 (solo ordinamento interno, mai sopra le classi):
30% copertura transito + 15% baseline (minimo per lato) + 20% quota centro (saturazione a {p['excellent_altitude_deg']:.0f}°)
+ 10% Luna (penalita' continua: (illuminazione/100)*(1-distanza/180); Luna sotto orizzonte = nessuna penalita')
+ 10% magnitudine (V/G da 8 a 16) + 10% profondità (saturazione a 20 ppt) + 5% praticità oraria.
Valori mancanti di magnitudine/profondità: 0,5 neutro, nessun credito inventato.
PRIMARY, BACKUP1, BACKUP2: per ogni target i primi tre eventi pratici ordinati per classe
(operativa prima) e poi per score decrescente; indicati in riepilogo_target.csv e nel LEGGIMI.

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
    return dict(counts),dict(practical)
