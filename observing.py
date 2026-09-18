"""Visibility independent of TAPIR's fractions; all interval endpoints are UTC seconds."""
import math
from functools import lru_cache
from datetime import date, datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
import numpy as np
import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body, get_sun
from astropy.time import Time
from astropy.utils import iers

# Bundled IERS predictions are recorded in provenance; avoid hidden network waits.
iers.conf.auto_download = False
iers.conf.auto_max_age = None


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def merge(windows):
    result = []
    for a,b in sorted(windows):
        if b <= a:
            continue
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0],max(b,result[-1][1]))
        else:
            result.append((a,b))
    return result


def overlap(a,b,windows):
    return sum(max(0,min(b,y)-max(a,x)) for x,y in merge(windows))


def coverage(a,b,windows):
    if b <= a:
        raise ValueError('Intervallo non positivo')
    return 100*overlap(a,b,windows)/(b-a)


def intervals(t,margin):
    """Piecewise linear positive intervals, retaining separate night/altitude gaps."""
    result=[]
    for a,b,x,y in zip(t[:-1],t[1:],margin[:-1],margin[1:]):
        if x >= 0 and y >= 0:
            result.append((float(a),float(b)))
        elif (x >= 0) != (y >= 0):
            crossing=float(a+(b-a)*(-x)/(y-x))
            result.append((float(a),crossing) if x>=0 else (crossing,float(b)))
    return merge(result)


def intersect(left,right):
    return merge((max(a,c),min(b,d)) for a,b in left for c,d in right if min(b,d)>max(a,c))


def logistic_bounds(mid,zone,start,end):
    local=datetime.fromtimestamp(mid,zone)
    # Observing night is named by the preceding local noon, not by UTC date.
    evening=local.date() if local.hour>=12 else local.date()-timedelta(days=1)
    begin=time(12) if start=='nautical_twilight' else time.fromisoformat(start)
    finish=time.fromisoformat(end)
    a=datetime.combine(evening,begin,zone)
    b=datetime.combine(evening+(timedelta(days=1) if finish<=begin else timedelta()),finish,zone).replace(fold=1)
    if datetime.fromtimestamp(b.timestamp(),zone).replace(tzinfo=None)!=b.replace(tzinfo=None):
        b=b.replace(fold=0)  # Nonexistent spring clock time shifts forward; autumn uses later occurrence.
    return a.timestamp(),b.timestamp()


@lru_cache(maxsize=2048)
def nautical_start(evening,latitude,longitude,height,zone_name,twilight):
    zone=ZoneInfo(zone_name)
    begin=datetime.combine(date.fromisoformat(evening),time(12),zone).timestamp()
    end=datetime.combine(date.fromisoformat(evening)+timedelta(days=1),time(12),zone).timestamp()
    grid=np.linspace(begin,end,math.ceil((end-begin)/120)+1)
    location=EarthLocation.from_geodetic(longitude*u.deg,latitude*u.deg,height*u.m)
    times=Time(grid,format='unix',scale='utc')
    alt=get_sun(times).transform_to(AltAz(obstime=times,location=location,pressure=0*u.hPa)).alt.deg
    windows=intervals(grid,twilight-alt)
    return windows[0][0] if windows else None


def geometry_label(max_alt,p):
    """Policy UAN v2.1, phase 2: structural geometry of the target from this site."""
    if max_alt < p['severe_altitude_deg']: return 'NON CONSIGLIATO DAL SITO'
    if max_alt < p['visibility_altitude_deg']: return 'MOLTO DIFFICILE'
    if max_alt < p['preferred_altitude_deg']: return 'MARGINALE'
    if max_alt < p['excellent_altitude_deg']: return 'BUONO'
    return 'MOLTO FAVOREVOLE'


# Policy UAN v2.1, phase 7: lunar risk levels (illumination %, separation deg).
# ESTREMA/ALTA use strict separation (<); MODERATA uses inclusive (<=).
MOON_RULES=(('ESTREMA',((90,40),(70,20),(40,10)),False),
            ('ALTA',((80,60),(50,40),(20,20)),False),
            ('MODERATA',((70,100),(50,70),(20,40)),True))


def moon_risk(illum,sep,up):
    """Lunar risk only when the Moon is above the horizon; below horizon = BASSA."""
    if not up or illum is None or sep is None:
        return 'BASSA'
    for name,rules,inclusive in MOON_RULES:
        for im,sm in rules:
            if illum>=im and (sep<=sm if inclusive else sep<sm):
                return name
    return 'BASSA'


def score(e,p):
    """Secondary 0-1 ordering score (policy UAN v2.1). Never overrides the class.
    Magnitude and depth are deliberately excluded until a real instrument profile exists."""
    up=e.get('moon_up_during_observable',e.get('moon_up_during_transit',False))
    if not up or e['moon_illumination_percent'] is None or e['moon_separation_deg'] is None:
        moon=1.0
    else:
        moon=1.0-(e['moon_illumination_percent']/100)*math.exp(-e['moon_separation_deg']/45)
    if e.get('timing_check_failed'):
        timing=0.0
    elif e['uncertainty_minutes'] is None:
        timing=0.5
    else:
        timing=1.0-min(e['uncertainty_minutes'],p['maximum_uncertainty_minutes'])/p['maximum_uncertainty_minutes']
    base=min(e['baseline_before_percent'],e['baseline_after_percent'])/100.0
    alt=min(max(e['altitude_mid_deg'],0.0),p['excellent_altitude_deg'])/p['excellent_altitude_deg']
    return (0.30*e['transit_percent']/100.0+0.20*base+0.20*alt+0.15*moon
            +0.10*timing+0.05*e['practical_transit_percent']/100.0)


def classify(e,p):
    """Policy UAN v2.1 hierarchy. Returns (quality_class, human reason, reason_codes)."""
    codes=[]
    if e['max_altitude_theoretical_deg'] < p['severe_altitude_deg']:
        codes.append('TARGET_GEOMETRY_NOT_RECOMMENDED')
        return 'NON CONSIGLIATO','Target basso per geometria del sito',codes
    if e['max_altitude_theoretical_deg'] < p['preferred_altitude_deg']:
        codes.append('TARGET_GEOMETRY_'+geometry_label(e['max_altitude_theoretical_deg'],p).replace(' ','_'))
    if e['altitude_max_deg'] < p['severe_altitude_deg'] or e['transit_percent']==0:
        codes.append('EVENT_NOT_OBSERVABLE')
        return 'NON CONSIGLIATO','Evento senza transito utile sopra la soglia e al buio',codes
    if any(e.get(k) is None for k in ('uncertainty_minutes','magnitude','depth_ppt')) or e.get('moon_risk') is None:
        codes.append('DATA_MISSING')
        return 'DA VALUTARE','Dati mancanti: impossibile assegnare una classe favorevole',codes
    if e.get('ttv'):
        codes.append('TTV')
        return 'DA VALUTARE','TTV segnalate: effemeride lineare da verificare',codes
    if e.get('timing_check_failed'):
        codes.append('TIMING_FAILED')
        return 'DA VALUTARE','Conversione temporale indipendente discordante',codes
    if e['uncertainty_minutes'] > p['maximum_uncertainty_minutes']:
        codes.append('UNCERTAINTY_HIGH')
        return 'DA VALUTARE','Incertezza temporale elevata',codes
    baseline=min(e['baseline_before_percent'],e['baseline_after_percent'])
    coverage_tol=p.get('full_transit_tolerance_percentage_points',1e-6)
    if e['transit_percent'] < p['transit_operational_percent']-coverage_tol:
        codes.append('TRANSIT_COVERAGE_LOW')
        return 'DA VALUTARE',f'Copertura transito non completa: {e["transit_percent"]:.6f}% osservabile; richiesto {p["transit_operational_percent"]:.0f}%',codes
    if baseline < p['baseline_weak_percent']:
        codes.append('BASELINE_WEAK')
        return 'DA VALUTARE',f'Baseline debole: {baseline:.0f}% osservabile su almeno un lato',codes
    if e['altitude_mid_deg'] < p['preferred_altitude_deg']:
        codes.append('ALTITUDE_MID_LOW')
        return 'DA VALUTARE','Centro del transito sotto la quota desiderata',codes
    if e['moon_risk']=='ESTREMA':
        codes.append('MOON_EXTREME')
        return 'DA VALUTARE',f'Luna ESTREMA: {e["moon_illumination_percent"]:.0f}% a {e["moon_separation_deg"]:.1f}° (sopra orizzonte)',codes
    issues=[]
    if e['transit_percent'] < p['first_choice_min_percent']-coverage_tol:
        codes.append('TRANSIT_PARTIAL')
        issues.append(f'transito {e["transit_percent"]:.1f}% (sotto {p["first_choice_min_percent"]:.1f}%)')
    if baseline < p['baseline_good_percent']:
        codes.append('BASELINE_MODERATE')
        issues.append(f'baseline {baseline:.0f}% (sotto {p["baseline_good_percent"]:.0f}%)')
    if e['altitude_min_deg'] < p['preferred_altitude_deg']:
        codes.append('ALTITUDE_PART_LOW')
        issues.append('parte del transito sotto la quota desiderata')
    if e['moon_risk'] in ('MODERATA','ALTA'):
        codes.append('MOON_'+e['moon_risk'].upper())
        issues.append(f'Luna {e["moon_risk"].lower()}: {e["moon_illumination_percent"]:.0f}% a {e["moon_separation_deg"]:.1f}°')
    if issues:
        return 'ALTERNATIVE','Valido con compromessi: '+'; '.join(issues),codes
    return 'PRIMA SCELTA','Transito completo, baseline buona, quota e Luna nei limiti',codes


def analyze(raw,target,p,ground=None):
    location=EarthLocation.from_geodetic(p['longitude']*u.deg,p['latitude']*u.deg,p['height_m']*u.m)
    coord=SkyCoord(target['RA'],target['Dec'],unit=(u.hourangle,u.deg),frame='icrs')
    mid=Time(float(raw['jd_utc_exact']),format='jd',scale='utc',location=location)
    m=float(mid.unix)
    duration=float(target['duration'])*3600
    a,b=m-duration/2,m+duration/2
    period=float(target['period']); epoch=float(target['epoch'])
    bary=mid.tdb+mid.light_travel_time(coord,kind='barycentric')
    cycle=round((bary.jd-epoch)/period)
    residual=float((bary.jd-(epoch+cycle*period))*86400)
    pe=number(target['period_uncertainty']); ee=number(target['epoch_uncertainty'])
    unc=None if pe is None or ee is None else math.hypot(ee,cycle*pe)*1440
    requested=p['baseline_hours']*3600
    extended=requested+(unc*60 if p['extend_uncertainty'] and unc is not None else 0)
    # ponytail: cap *calculation span* for ambiguous multi-orbit errors; class is DA VALUTARE.
    # Preserve requested denominator; a non-linear ephemeris is needed beyond this limit.
    span=min(extended,period*86400/2,86400)
    left,right=a-span,b+span
    grid=np.unique(np.concatenate([np.arange(left,right,p['sampling_seconds']),[left,a,m,b,right]]))
    times=Time(grid,format='unix',scale='utc',location=location)
    frame=AltAz(obstime=times,location=location,pressure=0*u.hPa)
    alt=coord.transform_to(frame).alt.deg
    sunalt=get_sun(times).transform_to(frame).alt.deg
    night=intervals(grid,p['twilight_deg']-sunalt)
    above=intervals(grid,alt-p['visibility_altitude_deg'])
    windows=intersect(night,above)
    ground_windows=intersect(night,intervals(grid,alt))
    zone=ZoneInfo(p['timezone'])
    logistics=logistic_bounds(m,zone,p['session_start'],p['session_end'])
    evening=datetime.fromtimestamp(logistics[0],zone).date().isoformat()
    dusk=nautical_start(evening,p['latitude'],p['longitude'],p['height_m'],p['timezone'],p['twilight_deg'])
    logistics=(max(logistics[0],dusk) if dusk is not None else logistics[1],logistics[1])
    practical=intersect(windows,[logistics])
    transit_percent=coverage(a,b,windows)
    usable=coverage(a,b,practical)
    trans=(grid>=a)&(grid<=b)
    exact=[float(alt[np.where(grid==x)[0][0]]) for x in (a,m,b)]
    # Moon sampled throughout the observable transit (or midpoint when none is visible).
    lunar_grid=np.unique(np.concatenate(([m],np.linspace(a,b,max(3,math.ceil(duration/600)+1)))))
    lunar_times=Time(lunar_grid,format='unix',scale='utc',location=location)
    lunar_frame=AltAz(obstime=lunar_times,location=location,pressure=0*u.hPa)
    moon=get_body('moon',lunar_times,location)
    sun=get_body('sun',lunar_times,location)
    moon_horizontal=moon.transform_to(lunar_frame)
    sep=moon_horizontal.separation(coord.transform_to(lunar_frame)).deg
    elong=moon.separation(sun).rad
    phase=np.arctan2(sun.distance.to_value(u.km)*np.sin(elong),
                    moon.distance.to_value(u.km)-sun.distance.to_value(u.km)*np.cos(elong))
    illumination=(1+np.cos(phase))*50
    lunar_up=moon_horizontal.alt.deg>0
    visible=np.array([any(x<=t<=y for x,y in windows) for t in lunar_grid])
    moon_up_observable=bool(np.any(lunar_up & visible))
    mi=int(np.argmin(abs(lunar_grid-m)))
    iso=lambda t: datetime.fromtimestamp(t,timezone.utc).isoformat(timespec='seconds')
    local=lambda t: datetime.fromtimestamp(t,zone).isoformat(timespec='seconds')
    before=overlap(a-extended,a,windows)/60
    after=overlap(b,b+extended,windows)/60
    practical_before=overlap(max(a-extended,logistics[0]),a,windows)/60
    original=number(ground.get('percent_transit_observable')) if ground else None
    raw_recalc=coverage(a,b,ground_windows)
    delta=None if original is None else raw_recalc-original
    magnitude=number(target['vmag']);depth=number(target['depth'])
    if magnitude == -99: magnitude=None
    if depth is not None and depth<=0: depth=None
    e=dict(name=target['name'],ingress_utc=iso(a),mid_utc=iso(m),egress_utc=iso(b),
           ingress_local=local(a),mid_local=local(m),egress_local=local(b),duration_minutes=duration/60,
           altitude_ingress_deg=exact[0],altitude_mid_deg=exact[1],altitude_egress_deg=exact[2],
           altitude_min_deg=float(min(alt[trans])),altitude_max_deg=float(max(alt[trans])),
           max_altitude_theoretical_deg=90-abs(p['latitude']-coord.dec.deg),
           transit_percent=transit_percent,practical_transit_percent=usable,
           baseline_before_minutes=before,baseline_after_minutes=after,
           practical_baseline_before_minutes=practical_before,practical_baseline_after_minutes=after,
           logistics_note='Baseline iniziale ridotta dalla disponibilità' if practical_before+0.01<before else 'Baseline non ridotta dagli orari; il dopo può superare il limite del transito',
           baseline_before_percent=round(100*before/(extended/60),6),baseline_after_percent=round(100*after/(extended/60),6),
           baseline_denominator_minutes_per_side=extended/60,baseline_computation_capped=span<extended,
           session_start_local=local(a-extended),session_end_local=local(b+extended),
           practical_start_local=local(logistics[0]),practical_transit_end_limit_local=local(logistics[1]),
           practical=bool(usable>0 and a>=logistics[0] and b<=logistics[1]),
           visible_windows_utc=[(iso(x),iso(y)) for x,y in windows],
           night_windows_utc=[(iso(x),iso(y)) for x,y in night],
           altitude_windows_utc=[(iso(x),iso(y)) for x,y in above],
           magnitude=magnitude,magnitude_band='Gaia G' if 'Mag is Gaia G' in target['comments'] else 'V',
           depth_ppt=depth,moon_illumination_percent=float(illumination[mi]),
           moon_separation_deg=float(sep[mi]),moon_min_separation_deg=float(min(sep)),
           moon_altitude_mid_deg=float(moon_horizontal.alt.deg[mi]),moon_up_during_transit=bool(np.any(lunar_up)),
           moon_up_during_observable=moon_up_observable,
           uncertainty_minutes=unc,cycle=cycle,
           timing_residual_seconds=residual,
           timing_check_failed=abs(residual)>p['timing_residual_limit_seconds'],
           ttv=target.get('ttv',False),tapir_ground_percent=original,
           tapir_ground_recalculated_percent=raw_recalc,tapir_ground_delta_percentage_points=delta,
           tapir_anomaly=(original is not None and (not 0<=original<=100 or abs(delta)>2)),
           reference=target['comments'])
    e['moon_risk']=moon_risk(e['moon_illumination_percent'],e['moon_min_separation_deg'],
                             e['moon_altitude_mid_deg']>0 or e['moon_up_during_observable'])
    pref=logistic_bounds(m,zone,p['session_pref_start'],p['session_end'])
    if a>=pref[0] and b<=pref[1]:
        e['logistics_class']='P1'
    elif usable>0:
        e['logistics_class']='P2'
    else:
        e['logistics_class']='P3'
        e['logistics_note']='Evento fuori dalla normale serata: conservato nell\'archivio scientifico'
    e['tapir_discrepancy_reason']=('Ricalcolo indipendente degli intervalli a quota 0°, Sole <= soglia; '
                                 'TAPIR usa estremi e arrotondamenti diversi' if e['tapir_anomaly'] else '')
    e['score']=round(100*score(e,p),1)
    e['category'],e['reason'],e['reason_codes']=classify(e,p)
    if e['logistics_class']=='P2': e['reason_codes']=e['reason_codes']+['LOGISTICS_PARTIAL']
    elif e['logistics_class']=='P3': e['reason_codes']=e['reason_codes']+['LOGISTICS_OUT_OF_SESSION']
    e['quality_class']=e['category']
    e['downgrade_reason']=e['reason'] if e['category'] in ('ALTERNATIVE','DA VALUTARE','NON CONSIGLIATO') else ''
    return e
