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
        assert e['transit_percent']>=99.9 and e['altitude_min_deg']>=p['preferred_altitude_deg']
        assert not e['moon_critical']
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
