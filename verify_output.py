"""Run after a plan: validate completeness, provenance and numerical convergence."""
import json,sys,math,hashlib,zipfile
from pathlib import Path
from datetime import datetime,time
from zoneinfo import ZoneInfo
import astropy.units as u
from astropy.coordinates import SkyCoord,EarthLocation
from astropy.time import Time
from observing import analyze,coverage
from planner import read_csv
from reports import compute_selection,slug

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
    assert abs(e['timing_residual_seconds'])<2
    if e['practical']:
        assert datetime.fromisoformat(e['egress_local'])<=datetime.fromisoformat(e['practical_transit_end_limit_local'])
        assert datetime.fromisoformat(e['ingress_local'])>=datetime.fromisoformat(e['practical_start_local'])
    if e['category']=='PRIMA SCELTA':
        assert e['transit_percent']>=p['first_choice_min_percent']-0.05,(e['name'],e['transit_percent'])
        assert e['altitude_min_deg']>=p['preferred_altitude_deg']-0.05
        assert min(e['baseline_before_percent'],e['baseline_after_percent'])>=p['baseline_good_percent']-0.05
        assert e['moon_risk']=='BASSA',('moon',e['name'],e['mid_utc'],e['moon_risk'])
# Policy v2.1 selection: roles must be operational (P1) and temporally diversified.
byt={}
for e in events:
    if e.get('selection_role'): byt.setdefault(e['name'],[]).append(e)
for name,es in byt.items():
    for e in es:
        assert e['logistics_class']=='P1',('selected not P1',name,e['mid_utc'])
        assert e['selection_role'] in ('PRIMARY','BACKUP1','BACKUP2')
    for e in es[1:]:
        gap=abs(e['mid_ts']-es[0]['mid_ts'])
        assert gap>=p['backup_fallback_separation_days']*86400-120,('backup too close',name,gap/86400)
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
if any(t['name']=='KELT-16 b' for t in targets):
    kel=[r for r in op if r['target']=='KELT-16 b' and r['mid_local'].startswith('2026-09-21')]
    assert kel and kel[0]['quality_class']=='ALTERNATIVE',('KELT-16 21/09 missing or reclassified',kel)
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
z=out.with_suffix('.zip')
with zipfile.ZipFile(z) as f:
    assert f.testzip() is None
    for name in ['0_LEGGIMI.txt','1_PRIMA_SCELTA.pdf','2_ALTERNATIVE.pdf','3_DA_VALUTARE.pdf']:
        assert out.name+'/'+name in f.namelist()
print(json.dumps({'status':'PASS','events':len(events),'targets':len(targets),'complete_orbit_enumeration':True,
                  'hashes_and_zip':True,'max_timing_residual_seconds':m['max_timing_residual_seconds'],
                  'convergence_120s_vs_30s':convergence},indent=2))
