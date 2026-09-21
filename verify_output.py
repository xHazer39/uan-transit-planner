"""Run after a plan: validate completeness, provenance and numerical convergence."""
import json,sys,math,hashlib,zipfile
from pathlib import Path
from datetime import datetime,time
from zoneinfo import ZoneInfo
import astropy.units as u
from astropy.coordinates import SkyCoord,EarthLocation
from astropy.time import Time
from observing import analyze,coverage,FULL_TRANSIT_TOLERANCE_SECONDS as TOL
from planner import read_csv
from reports import compute_selection,slug,curated_review_rows
import re

out=Path(sys.argv[1]);archive=out/'9_ARCHIVIO_COMPLETO';raw=archive/'dati_originali'
m=json.loads((archive/'manifest.json').read_text());events=json.loads((archive/'risultati.json').read_text())
p=m['profile'];targets=json.loads((raw/'targets.json').read_text())
assert m['status']=='complete'
assert m['event_count']==len(events)
for name,digest in m['source_sha256'].items():
    assert hashlib.sha256((raw/name).read_bytes()).hexdigest()==digest,name
zone=ZoneInfo(p['timezone'])
location=EarthLocation.from_geodetic(p['longitude']*u.deg,p['latitude']*u.deg,p['height_m']*u.m)
for t in targets:
    group=sorted((e for e in events if e['name']==t['name']),key=lambda e:e['cycle'])
    cycles=[e['cycle'] for e in group]
    assert len(cycles)==len(set(cycles)),('duplicate cycles',t['name'])
    coord=SkyCoord(t['RA'],t['Dec'],unit=(u.hourangle,u.deg))
    bounds=Time([datetime.combine(datetime.fromisoformat(m[k]).date(),time(),zone) for k in ['start','end_exclusive']],location=location)
    bjd=(bounds.tdb+bounds.light_travel_time(coord)).jd
    expected=list(range(math.ceil((bjd[0]-float(t['epoch']))/float(t['period'])),math.ceil((bjd[1]-float(t['epoch']))/float(t['period']))))
    assert cycles==expected,('missing events',t['name'],len(cycles),len(expected))
for e in events:
    for k in ['transit_percent','practical_transit_percent','baseline_before_percent','baseline_after_percent']:
        assert 0<=e[k]<=100,(e['name'],k,e[k])
    assert datetime.fromisoformat(e['ingress_utc'])<datetime.fromisoformat(e['mid_utc'])<datetime.fromisoformat(e['egress_utc'])
    assert e['timing_check_failed']==(abs(e['timing_residual_seconds'])>p['timing_residual_limit_seconds']),('timing flag drift',e['name'],e['cycle'])
    if e['practical']:
        assert datetime.fromisoformat(e['egress_local'])<=datetime.fromisoformat(e['practical_transit_end_limit_local'])
        assert datetime.fromisoformat(e['ingress_local'])>=datetime.fromisoformat(e['practical_start_local'])
    if e['category']=='PRIMA SCELTA':
        assert e['transit_percent']>=p['first_choice_min_percent']-0.05,(e['name'],e['transit_percent'])
        assert e['altitude_min_deg']>=p['preferred_altitude_deg']-0.05
        assert min(e['baseline_before_percent'],e['baseline_after_percent'])>=p['baseline_good_percent']-0.05
        assert e['moon_risk']=='BASSA',('moon',e['name'],e['mid_utc'],e['moon_risk'])
# Policy v2.2 eligibility gate: only real 100% transits (independent recomputation) may be
# classified, scheduled, scored or selected; everything else stays archive-only with a reason.
OPER={'PRIMA SCELTA','ALTERNATIVE','DA VALUTARE','NON CONSIGLIATO'}
for e in events:
    assert 'eligible' in e and 'exclusion_reason' in e and 'transit_uncovered_seconds' in e,('gate fields',e['name'],e['cycle'])
    assert e['transit_uncovered_seconds']>=0
    assert e['full_transit']==(e['transit_uncovered_seconds']<=TOL)==e['eligible'],('gate drift',e['name'],e['cycle'])
    if e['eligible']:
        assert e['exclusion_reason'] is None and e['quality_class'] in OPER and e['category']==e['quality_class']
        assert e['logistics_class'] in ('P1','P2','P3') and e['score'] is not None
        assert 'TRANSIT_NOT_100' not in e['reason_codes']
    else:
        assert e['exclusion_reason']=='TRANSIT_NOT_100' and e['category']=='NON ELEGGIBILE'
        assert e['quality_class'] is None and e['logistics_class'] is None and e['score'] is None
        assert not e.get('selection_role') and e['transit_percent']<100,('excluded event with role or 100%',e['name'],e['cycle'])
n_elig=sum(e['eligible'] for e in events);n_excl=sum(not e['eligible'] for e in events)
assert n_elig+n_excl==len(events)==m['event_count'],'archive must keep every enumerated cycle'
assert all(e['transit_percent']==100.0 or e['transit_uncovered_seconds']>0 for e in events)
# Policy v2.1 selection: roles must be operational (P1) and temporally diversified.
byt={}
for e in events:
    if e.get('selection_role'):
        assert e['eligible'] and e['full_transit'],('role on non-eligible',e['name'],e['cycle'])
        byt.setdefault(e['name'],[]).append(e)
POOL={}
for e in events:
    if e['eligible'] and e['logistics_class']=='P1' and e['quality_class'] in ('PRIMA SCELTA','ALTERNATIVE','DA VALUTARE'):
        POOL.setdefault(e['name'],[]).append(e)
ORDER=['PRIMARY','BACKUP1','BACKUP2']
for name,es in byt.items():
    for e in es:
        assert e['logistics_class']=='P1',('selected not P1',name,e['mid_utc'])
        assert e['selection_role'] in ORDER
    es.sort(key=lambda e:ORDER.index(e['selection_role']))
    fallback=p['backup_fallback_separation_days']*86400-120
    # Separation is required from EVERY earlier pick, not only from PRIMARY; a closer backup is
    # legitimate only on the documented fallback path, i.e. when no candidate of the target was
    # far enough from all of them. Derived from the events alone, independent of compute_selection.
    for i,e in enumerate(es[1:],1):
        picks=es[:i]
        if all(abs(e['mid_ts']-q['mid_ts'])>=fallback for q in picks):
            continue
        free=[c for c in POOL[name] if all(c is not q for q in picks)
              and all(abs(c['mid_ts']-q['mid_ts'])>=fallback for q in picks)]
        assert not free,('backup too close while a separated candidate existed',name,e['selection_role'],
                         min(abs(e['mid_ts']-q['mid_ts']) for q in picks)/86400,len(free))
# Reporting calendar (v2.1): complete, chronological, pure, roles preserved.
cal_path=archive/'calendario_prima_scelta.json'
assert cal_path.is_file(),'calendar json missing'
cal=json.loads(cal_path.read_text())
cal_ids=[r['event_id'] for r in cal]
assert len(cal_ids)==len(set(cal_ids)),('calendar duplicates',)
prima_p1={slug(e['name'])+'-c'+str(e['cycle']) for e in events
          if e.get('quality_class')=='PRIMA SCELTA' and e.get('logistics_class')=='P1'}
assert set(cal_ids)==prima_p1,('calendar incomplete or impure',len(set(cal_ids)),len(prima_p1))
mids=[datetime.fromisoformat(r['mid_local']) for r in cal]
assert mids==sorted(mids),('calendar not chronological',)
assert all(r['quality_class']=='PRIMA SCELTA' and r['logistics_class']=='P1' for r in cal)
stored_roles={(e['name'],e['cycle']):e.get('selection_role') for e in events if e.get('selection_role')}
for r in cal:
    want=stored_roles.get((r['target'],int(r['event_id'].rsplit('-c',1)[-1])))
    assert r['selection_role']==want,('calendar role drift',r['event_id'])
    assert r['display_role']==(r['selection_role'] or 'EXTRA'),('display role',r['event_id'])
fresh_sel=compute_selection(list(events),p)
for name,roles in fresh_sel.items():
    for role,e in roles:
        assert stored_roles.get((e['name'],e['cycle']))==role,('selection drift',name,e['cycle'])
assert m.get('reporting',{}).get('first_choice_scope')=='all PRIMA SCELTA + P1'
assert m['reporting']['calendar_events']==len(cal)
# Calendario operativo congiunto (PRIMA SCELTA + ALTERNATIVE, solo P1).
op=json.loads((archive/'0_CALENDARIO_OPERATIVO.json').read_text())
op_ids=[r['event_id'] for r in op]
assert len(op_ids)==len(set(op_ids)),('operational calendar duplicates',)
op_expected={slug(e['name'])+'-c'+str(e['cycle']) for e in events
             if e.get('logistics_class')=='P1' and e.get('quality_class') in ('PRIMA SCELTA','ALTERNATIVE')}
assert set(op_ids)==op_expected,('operational calendar incomplete/impure',len(set(op_ids)),len(op_expected))
op_mids=[datetime.fromisoformat(r['mid_local']) for r in op]
assert op_mids==sorted(op_mids),('operational calendar not chronological',)
assert all(r['quality_class'] in ('PRIMA SCELTA','ALTERNATIVE') and r['logistics_class']=='P1' for r in op)
assert m['reporting']['operational_calendar_events']==len(op)
for f in ['0_CALENDARIO_OPERATIVO.html','0_CALENDARIO_OPERATIVO.csv']:
    assert (archive/f).is_file(),('missing',f)
# Regression cases of the annual 2026-09-15 run: checked only when the package contains those events.
has=lambda name,prefix: any(e['name']==name and e['mid_local'].startswith(prefix) for e in events)
if has('KELT-16 b','2026-09-21T23:16'):
    kel=[r for r in op if r['target']=='KELT-16 b' and r['mid_local'].startswith('2026-09-21')]
    assert kel and kel[0]['quality_class']=='ALTERNATIVE',('KELT-16 21/09 missing or reclassified',kel)
# Dossier 1/2/3: set esatti, anchor, nessun ID duplicato, regression cases.
exp_d={'1_PRIMA_SCELTA':{('event-'+(slug(e['name'])+'-c'+str(e['cycle'])).lower())
        for e in events if e['quality_class']=='PRIMA SCELTA' and e['logistics_class']=='P1'},
       '2_ALTERNATIVE':{('event-'+(slug(e['name'])+'-c'+str(e['cycle'])).lower())
        for e in events if e['quality_class']=='ALTERNATIVE' and e['logistics_class']=='P1'}}
exp3=curated_review_rows(events,p)
_short_rows=set(map(lambda x:(x['name'],x['cycle'],x['mid_utc']),exp3))
exp_d['3_DA_VALUTARE']={'event-'+(slug(e['name'])+'-c'+str(e['cycle'])).lower() for e in exp3}
for base,anchors_expected in exp_d.items():
    hp=out/(base+'.html');assert hp.is_file(),('missing',base+'.html')
    assert (out/(base+".pdf")).is_file(),('missing',base+'.pdf')
    doc=hp.read_text()
    ids=re.findall(r'\bid="([^"]+)"',doc)
    assert len(ids)==len(set(ids)),('duplicated html ids',base)
    found=set(re.findall(r'id="(event-[^"]+)"',doc))
    assert found==anchors_expected,('dossier set mismatch',base,len(found),len(anchors_expected))
    for href in re.findall(r'href="#(event-[^"]+)"',doc):
        assert href in found,('anchor without target',base,href)
if has('WASP-77 A b','2026-11-10'):
    assert 'event-'+(slug('WASP-77 A b')+'-c'+str(next(e['cycle'] for e in events
            if e['name']=='WASP-77 A b' and e['mid_local'].startswith('2026-11-10')))).lower() in exp_d['1_PRIMA_SCELTA']
if has('KELT-16 b','2026-09-21T23:16'):
    k16='event-'+(slug('KELT-16 b')+'-c'+str(next(e['cycle'] for e in events
         if e['name']=='KELT-16 b' and e['mid_local'].startswith('2026-09-21T23:16')))).lower()
    assert k16 in exp_d['2_ALTERNATIVE'] and k16 not in exp_d['1_PRIMA_SCELTA'],('KELT-16 misplaced',)
# Identity di ogni frammento incorporato: target + midpoint TAPIR == planner (tol 2 min).
from reports import tapir_fragment_identity
from datetime import datetime as _DT
checked=0
for e in events:
    # solo le righe dei dossier 1/2/3 hanno frammento canonico obbligatorio
    in_d=(e['logistics_class']=='P1' and
          (e['quality_class'] in ('PRIMA SCELTA','ALTERNATIVE') or
           (e['name'],e['cycle'],e['mid_utc']) in _short_rows))
    if not in_d:
        continue
    canon=archive/(slug(e['name'])+'/tapir_event_c'+str(e['cycle'])+'.html')
    assert canon.is_file(),('canonical fragment missing',slug(e['name'])+'-c'+str(e['cycle']))
    name,mid=tapir_fragment_identity(canon.read_text())
    assert name==e['name'],('fragment target mismatch',slug(e['name'])+'-c'+str(e['cycle']),name)
    exp=_DT.fromisoformat(e['mid_utc']).replace(tzinfo=None)
    assert mid is not None and abs((mid-exp).total_seconds())<=120,('fragment mid mismatch',slug(e['name'])+'-c'+str(e['cycle']),str(mid))
    checked+=1
assert checked==len(exp_d['1_PRIMA_SCELTA'])+len(exp_d['2_ALTERNATIVE'])+len(exp_d['3_DA_VALUTARE']),('fragment identity coverage',checked)
# regression KELT-1: c2935 (16/09) e c2981 (11/11) frammenti distinti e coerenti
k1={e['cycle']:e for e in events if e['name']=='KELT-1 b' and e['cycle'] in (2935,2981)}
assert set(k1) in ({2935,2981},set()),('KELT-1 regression cycles partially present',set(k1))
for cyc,e in k1.items():
    frag=(archive/(slug(e['name'])+'/tapir_event_c'+str(e['cycle'])+'.html')).read_text()
    name,mid=tapir_fragment_identity(frag)
    exp=_DT.fromisoformat(e['mid_utc']).replace(tzinfo=None)
    assert name=='KELT-1 b' and abs((mid-exp).total_seconds())<=120,('KELT-1 regression',cyc,str(mid))
    assert abs((mid-exp).total_seconds())<=120
if k1:
    m2935=_DT.fromisoformat(k1[2935]['mid_utc']).replace(tzinfo=None)
    m2981=_DT.fromisoformat(k1[2981]['mid_utc']).replace(tzinfo=None)
    assert abs((m2935-m2981).total_seconds())>86400,('KELT-1 midpoints too close',)
# Re-evaluate up to three partial events at 30-second sampling, independent of rendering.
convergence=[]
for e in [e for e in events if 1<e['transit_percent']<99][:3]:
    t=next(t for t in targets if t['name']==e['name'])
    candidates=[]
    for f in raw.glob('*_all.txt'): candidates.extend(r for r in read_csv(f.read_text()) if r['Name']==e['name'])
    ref=Time(datetime.fromisoformat(e['mid_utc'])).jd
    r=min(candidates,key=lambda r:abs(float(r['jd_utc_exact'])-ref))
    fine=analyze(r,t,dict(p,sampling_seconds=30))
    delta=abs(fine['transit_percent']-e['transit_percent'])
    assert delta<0.05,delta
    convergence.append({'target':e['name'],'mid_utc':e['mid_utc'],'coverage_difference_percentage_points':delta})
# Concrete historic interval: 20:33--23:03, visible from 21:55; 68/150 = 45.333%.
assert abs(coverage(0,150,[(82,211)])-45.3333333333)<1e-8
# Every operational output row (calendars 0/1, dossiers 1/2/3, roles) is eligible & full transit;
# no TRANSIT_NOT_100 leaks into any operational artifact; excluded events stay in the archive.
by_id={slug(e['name'])+'-c'+str(e['cycle']):e for e in events}
oper_ids=set(cal_ids)|set(op_ids)|{i[len('event-'):] for s_ in exp_d.values() for i in s_}
low={k.lower():e for k,e in by_id.items()}
for ident in oper_ids:
    e=low.get(ident.lower())
    assert e is not None,('operational row unknown',ident)
    assert e['eligible'] and e['full_transit'] and e['transit_uncovered_seconds']<=TOL,('operational row not full transit',ident)
for f in ['0_CALENDARIO_OPERATIVO.json','0_CALENDARIO_OPERATIVO.csv','calendario_prima_scelta.json','calendario_prima_scelta.csv','1_PRIMA_SCELTA.ics','1_PRIMA_SCELTA.google_calendar.csv']:
    assert 'TRANSIT_NOT_100' not in (archive/f).read_text(),('exclusion leaked into',f)
for base in exp_d:
    assert 'TRANSIT_NOT_100' not in (out/(base+'.html')).read_text(),('exclusion leaked into',base)
for r in cal+op:
    assert by_id[r['event_id']]['eligible'],('calendar row not eligible',r['event_id'])
excluded={k for k,e in by_id.items() if not e['eligible']}
csv_ids={slug(r['name'])+'-c'+r['cycle'] for r in __import__('csv').DictReader((archive/'risultati.csv').open(encoding='utf-8'))}
assert excluded<=csv_ids and excluded<=set(by_id),('excluded events missing from archive',)
assert not ({k.lower() for k in excluded}&{i.lower() for i in oper_ids}),('excluded event in operational output',)
# DA VALUTARE semantics v2.2: full transit with another issue, never partial coverage.
for e in events:
    if e['quality_class']=='DA VALUTARE':
        assert e['full_transit'] and 'TRANSIT_COVERAGE_LOW' not in e['reason_codes'],('DA VALUTARE partial',e['name'],e['cycle'])
z=out.with_suffix('.zip')
with zipfile.ZipFile(z) as f:
    assert f.testzip() is None
    for name in ['0_LEGGIMI.txt','1_PRIMA_SCELTA.pdf','2_ALTERNATIVE.pdf','3_DA_VALUTARE.pdf']:
        assert out.name+'/'+name in f.namelist()
print(json.dumps({'status':'PASS','events':len(events),'targets':len(targets),'complete_orbit_enumeration':True,
                  'eligible_full_transit':n_elig,'excluded_transit_not_100':n_excl,
                  'hashes_and_zip':True,'max_timing_residual_seconds':m['max_timing_residual_seconds'],
                  'convergence_120s_vs_30s':convergence},indent=2))
