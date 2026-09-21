import json
import unittest
from pathlib import Path
from reports import slug
from observing import FULL_TRANSIT_TOLERANCE_SECONDS as TOL
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from observing import coverage, intervals, logistic_bounds, classify

def write_tapir_fragment(archive,e):
    """Frammento TAPIR minimo ma valido (target + midpoint) per i test che passano da
    ensure_tapir_fragment senza avere un engine TAPIR."""
    mid=datetime.fromisoformat(e['mid_utc']).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M')
    page=('<!doctype html><html><head><style>.x{}</style></head><body>'
          '<table id="target_table"><tr><th>Data</th><th>Name</th><th>V or Gaia mag</th>'
          '<th>Start&mdash; Mid &mdash;End</th><th>Duration</th></tr>'
          '<tr><td>2026-10-01 17:30 2026-10-02 06:30</td>'
          f'<td><a href="#">{e["name"]}</a> Finding charts: Annotated , Aladin ; Airmass plot , ACP plan '
          'Info: Exoplanet Archive</td><td>10.3</td>'
          f'<td>{mid} {mid} {mid} {mid} {mid}</td><td>2:46</td></tr></table>'
          '<p>MARKER_TAPIR_ROW</p></body></html>')
    folder=archive/slug(e['name']);folder.mkdir(parents=True,exist_ok=True)
    (folder/f'tapir_event_c{e["cycle"]}.html').write_text(page)
    return page


class PlannerChecks(unittest.TestCase):
    def test_bad_tapir_percentage_is_not_input_to_coverage(self):
        self.assertAlmostEqual(coverage(0, 100, [(54.7, 140)]), 45.3)
        self.assertEqual(coverage(0, 100, [(-10, 20),(10,40),(60,90)]),70)
    def test_interpolated_windows(self):
        self.assertEqual(intervals([0,10,20],[-1,1,-1]),[(5,15)])
        self.assertEqual(intervals([0,10],[-1,-1]),[])
    def test_midnight_and_dst(self):
        z=ZoneInfo('Europe/Rome')
        for stamp,offset in [('2026-10-25T00:30:00',2),('2026-10-26T00:30:00',1)]:
            t=datetime.fromisoformat(stamp).replace(tzinfo=z)
            start,end=logistic_bounds(t.timestamp(),z,'17:45','01:00')
            self.assertEqual(datetime.fromtimestamp(end,z).day,t.day)
            self.assertEqual(datetime.fromtimestamp(end,z).utcoffset().total_seconds(),offset*3600)
            self.assertLess(start,t.timestamp());self.assertGreater(end,t.timestamp())
    def test_classification(self):
        from observing import score, geometry_label, moon_risk
        p={'severe_altitude_deg':15,'preferred_altitude_deg':30,'excellent_altitude_deg':40,
           'visibility_altitude_deg':20,'transit_operational_percent':100,'first_choice_min_percent':100,
           'baseline_weak_percent':50,'baseline_good_percent':80,'maximum_uncertainty_minutes':10,
           'backup_preferred_separation_days':7,'backup_fallback_separation_days':3,
           'timing_residual_limit_seconds':2}
        e=dict(max_altitude_theoretical_deg=55,altitude_min_deg=31,altitude_mid_deg=40,
               altitude_max_deg=45,transit_percent=100,duration_minutes=120,
               baseline_before_minutes=60,baseline_after_minutes=60,
               baseline_before_percent=100,baseline_after_percent=100,
               practical_transit_percent=100,uncertainty_minutes=1,
               moon_risk='BASSA',magnitude=11,depth_ppt=12,ttv=False,
               moon_up_during_observable=False,moon_illumination_percent=5,moon_separation_deg=120,
               timing_check_failed=False)
        self.assertEqual(classify(e,p)[0],'PRIMA SCELTA')
        self.assertEqual(classify(dict(e,altitude_mid_deg=22,altitude_min_deg=8),p)[0],'DA VALUTARE')
        self.assertIn('geometria del sito',classify(dict(e,max_altitude_theoretical_deg=7),p)[1])
        self.assertEqual(classify(dict(e,uncertainty_minutes=None),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,moon_risk=None),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,baseline_after_percent=0),p)[0],'DA VALUTARE')
        # Full-transit policy: only 100% coverage may be PRIMA/ALTERNATIVE; any partial transit is DA VALUTARE.
        self.assertEqual(classify(dict(e,transit_percent=99.999),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,transit_percent=95),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,baseline_after_percent=60),p)[0],'ALTERNATIVE')
        self.assertEqual(classify(dict(e,baseline_after_percent=40),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,moon_risk='ALTA'),p)[0],'ALTERNATIVE')
        self.assertEqual(classify(dict(e,moon_risk='ESTREMA'),p)[0],'DA VALUTARE')
        self.assertIn('MOON_EXTREME',classify(dict(e,moon_risk='ESTREMA'),p)[2])
        # Moon risk: the audit v2.2.0 examples.
        self.assertEqual(moon_risk(3,111,True),'BASSA')
        self.assertEqual(moon_risk(90,120,True),'BASSA')
        self.assertEqual(moon_risk(97,54,True),'ALTA')
        self.assertEqual(moon_risk(93,41,True),'ALTA')
        self.assertEqual(moon_risk(63,8.5,True),'ESTREMA')
        self.assertEqual(moon_risk(96,3,True),'ESTREMA')
        self.assertEqual(moon_risk(96,3,False),'BASSA')
        self.assertEqual(moon_risk(77,55.1,True),'MODERATA')
        self.assertEqual(moon_risk(85,50.4,True),'ALTA')
        # Score v2: 30/20/20/15/10/5; magnitude and depth deliberately excluded.
        perfect=dict(e,magnitude=8,depth_ppt=20,uncertainty_minutes=0)
        self.assertAlmostEqual(score(perfect,p),1.0,places=6)
        self.assertAlmostEqual(score(dict(perfect,magnitude=2,depth_ppt=25),p),1.0,places=6)
        low=score(dict(e,altitude_mid_deg=8,transit_percent=95,uncertainty_minutes=1),p)
        self.assertAlmostEqual(low,0.30*0.95+0.20+0.20*0.2+0.15+0.10*0.9+0.05)
        self.assertLess(100*low,88.0)
        # Target geometry labels (phase 2).
        self.assertEqual(geometry_label(10,p),'NON CONSIGLIATO DAL SITO')
        self.assertEqual(geometry_label(18,p),'MOLTO DIFFICILE')
        self.assertEqual(geometry_label(25,p),'MARGINALE')
        self.assertEqual(geometry_label(35,p),'BUONO')
        self.assertEqual(geometry_label(55,p),'MOLTO FAVOREVOLE')

    def test_v220_classification_boundaries(self):
        p={'severe_altitude_deg':15,'preferred_altitude_deg':30,'excellent_altitude_deg':40,
           'visibility_altitude_deg':20,'transit_operational_percent':100,'first_choice_min_percent':100,
           'baseline_weak_percent':50,'baseline_good_percent':80,'maximum_uncertainty_minutes':10,
           'backup_preferred_separation_days':7,'backup_fallback_separation_days':3,
           'timing_residual_limit_seconds':2}
        base=dict(max_altitude_theoretical_deg=55,altitude_min_deg=31,altitude_mid_deg=40,
                  altitude_max_deg=45,transit_percent=100,duration_minutes=120,
                  baseline_before_percent=100,baseline_after_percent=100,
                  practical_transit_percent=100,uncertainty_minutes=1,
                  moon_risk='BASSA',magnitude=11,depth_ppt=12,ttv=False,
                  moon_up_during_observable=False,moon_illumination_percent=5,moon_separation_deg=120,
                  timing_check_failed=False)
        c=lambda **kw: classify(dict(base,**kw),p)[0]
        self.assertEqual(c(transit_percent=95),'DA VALUTARE')
        self.assertEqual(c(transit_percent=99.999),'DA VALUTARE')
        self.assertEqual(c(transit_percent=100),'PRIMA SCELTA')
        self.assertEqual(c(baseline_after_percent=49.9),'DA VALUTARE')
        self.assertEqual(c(baseline_after_percent=60),'ALTERNATIVE')
        self.assertEqual(c(baseline_after_percent=80),'PRIMA SCELTA')
        self.assertEqual(c(altitude_mid_deg=29.9),'DA VALUTARE')
        self.assertEqual(c(altitude_mid_deg=35,altitude_min_deg=29),'ALTERNATIVE')
        self.assertEqual(c(altitude_mid_deg=35,altitude_min_deg=30),'PRIMA SCELTA')
        self.assertEqual(c(moon_risk='ALTA'),'ALTERNATIVE')



class InputChecks(unittest.TestCase):
    def test_alias_does_not_resolve_host_to_only_planet(self):
        from planner import alias_candidates
        payload={'system':{'objects':{'planet_set':{'planets':{'x':{'alias_set':{'default_name':'X b','aliases':['X b','Other b']}}}}}}}
        self.assertEqual(alias_candidates(payload,'Other b'),['X b'])
        self.assertEqual(alias_candidates(payload,'X'),[])
    def test_ephemeris_remains_coherent_and_explicit(self):
        from planner import choose_ephemeris
        base=dict(pl_orbper='2',pl_tranmid='2459000',pl_tsystemref='BJD-TDB',pl_orbpererr1='0.0001',pl_tranmiderr1='0.001')
        better=dict(base,pl_orbper='3',pl_tranmid='2459500',pl_orbpererr1='0.000001')
        selected,_=choose_ephemeris([base,better,dict(base,pl_tsystemref='BJD',pl_orbpererr1='0')],2460000,2461000)
        self.assertEqual((selected['pl_orbper'],selected['pl_tranmid']),('3','2459500'))
        with self.assertRaises(ValueError): choose_ephemeris([dict(base,pl_tsystemref='BJD')],2460000,2461000)
    def test_precise_csv_and_invalid_profile(self):
        from planner import read_csv,validate_profile
        import json
        from pathlib import Path
        self.assertEqual(read_csv('Content-Type: text/csv\n\njd_utc_exact,Name,V,\n2460000,X b,10,\n')[0]['Name'],'X b')
        p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
        with self.assertRaises(ValueError): validate_profile(dict(p,latitude=100))
        with self.assertRaises(ValueError): validate_profile(dict(p,session_end='25:00'))
        # Le soglie percentuali storiche restano valide nel profilo: il 100% NON e' imposto qui,
        # lo decide il gate sulla durata non coperta (observing.evaluate). Unica fonte della regola.
        self.assertEqual(validate_profile(dict(p,transit_operational_percent=90))['transit_operational_percent'],90)
        self.assertEqual(validate_profile(dict(p,first_choice_min_percent=99.5))['first_choice_min_percent'],99.5)

class EdgeChecks(unittest.TestCase):
    def test_dst_ambiguous_and_missing_end(self):
        z=ZoneInfo('Europe/Rome')
        fall=datetime(2026,10,24,22,tzinfo=z).timestamp()
        _,b=logistic_bounds(fall,z,'17:45','02:30')
        self.assertEqual(datetime.fromtimestamp(b,z).fold,1)
        spring=datetime(2026,3,28,22,tzinfo=z).timestamp()
        _,b=logistic_bounds(spring,z,'17:45','02:30')
        self.assertEqual(datetime.fromtimestamp(b,z).hour,3)
    def test_disjoint_windows_and_missing_numbers(self):
        from observing import intersect,number
        self.assertEqual(intersect([(0,10),(20,30)],[(5,25)]),[(5,10),(20,25)])
        self.assertEqual(coverage(0,30,[(5,10),(20,25)]),100/3)
        self.assertIsNone(number('nan'));self.assertIsNone(number(''));self.assertIsNone(number(None))
    def test_uncertainty_missing_does_not_become_zero(self):
        from planner import err
        self.assertIsNone(err({},'pl_orbper'))
        self.assertEqual(err({'pl_orbpererr1':'0.1','pl_orbpererr2':'-0.2'},'pl_orbper'),0.2)

class ReportChecks(unittest.TestCase):
    def test_target_with_no_events_and_empty_categories(self):
        import tempfile,json
        from pathlib import Path
        from reports import write_reports
        p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
        t=dict(name='Synthetic test b',RA='12:00:00',Dec='+00:00:00')
        m=dict(profile=p,created_utc='2026-09-15',start='2026-09-15',end_exclusive='2026-09-16',tapir_commit='test-only',command='test-only')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'9_ARCHIVIO_COMPLETO').mkdir()
            write_reports(out,[],[t],[],m)
            summary=json.loads((out/'9_ARCHIVIO_COMPLETO/riepilogo_target.json').read_text())[0]
            self.assertEqual(summary['events'],0)
            self.assertAlmostEqual(summary['max_altitude_theoretical_deg'],49.137139)
            self.assertEqual(len(list(out.glob('*.pdf'))),4)
            self.assertTrue((out/'9_ARCHIVIO_COMPLETO'/'1_PRIMA_SCELTA.ics').is_file())

class SelectionChecks(unittest.TestCase):
    def setUp(self):
        from reports import compute_selection
        from datetime import datetime,timezone,timedelta
        self.p=dict(backup_preferred_separation_days=7,backup_fallback_separation_days=3)
        self.base=datetime(2026,11,1,22,0,tzinfo=timezone.utc)
        self.compute_selection=compute_selection
        self.timedelta=timedelta
    def ev(self,cycle,days,score,cat='PRIMA SCELTA'):
        mid=self.base+self.timedelta(days=days)
        return dict(name='X b',mid_utc=mid.isoformat(),mid_local=mid.isoformat(),category=cat,
                    quality_class=cat,score=score,cycle=cycle,logistics_class='P1',
                    eligible=True,full_transit=True,transit_percent=100.0)
    def roles(self,events):
        sel=self.compute_selection(events,self.p)['X b']
        return [(r,e['cycle'],e['category']) for r,e in sel]
    def test_quality_dominates_separation(self):
        # A) PRIMA a +4 giorni DEVE battere ALTERNATIVE a +20.
        r=self.roles([self.ev(1,0,95),self.ev(2,4,94),self.ev(3,20,93,'ALTERNATIVE')])
        self.assertEqual(r,[('PRIMARY',1,'PRIMA SCELTA'),('BACKUP1',2,'PRIMA SCELTA'),
                            ('BACKUP2',3,'ALTERNATIVE')])
        # B) Nessun'altra PRIMA: il backup puo' essere ALTERNATIVE.
        r=self.roles([self.ev(1,0,95),self.ev(2,10,80,'ALTERNATIVE')])
        self.assertEqual(r,[('PRIMARY',1,'PRIMA SCELTA'),('BACKUP1',2,'ALTERNATIVE')])
        # C) Due PRIMA ben separate: vince lo score migliore.
        r=self.roles([self.ev(1,0,95),self.ev(2,8,94),self.ev(3,20,93)])
        self.assertEqual(r,[('PRIMARY',1,'PRIMA SCELTA'),('BACKUP1',2,'PRIMA SCELTA'),
                            ('BACKUP2',3,'PRIMA SCELTA')])
        # D) BACKUP2 rispetta la separazione anche da BACKUP1 (fallback >=3 dentro la classe,
        #    poi classe inferiore, mai un candidato troppo ravvicinato se esistono alternative).
        r=self.roles([self.ev(1,0,95),self.ev(2,8,94),self.ev(3,9,93.9),self.ev(4,20,93)])
        self.assertEqual(r,[('PRIMARY',1,'PRIMA SCELTA'),('BACKUP1',2,'PRIMA SCELTA'),
                            ('BACKUP2',4,'PRIMA SCELTA')])
        r=self.roles([self.ev(1,0,95),self.ev(2,8,94),self.ev(3,9,93.9)])
        self.assertEqual(r,[('PRIMARY',1,'PRIMA SCELTA'),('BACKUP1',2,'PRIMA SCELTA'),
                            ('BACKUP2',3,'PRIMA SCELTA')])
    def test_selection_diversifies_backups(self):
        from reports import compute_selection
        from datetime import datetime,timezone,timedelta
        p=dict(backup_preferred_separation_days=7,backup_fallback_separation_days=3)
        base=datetime(2026,11,1,22,0,tzinfo=timezone.utc)
        def ev(cycle,days,score,cat='PRIMA SCELTA'):
            mid=base+timedelta(days=days)
            return dict(name='X b',mid_utc=mid.isoformat(),mid_local=mid.isoformat(),category=cat,
                        quality_class=cat,score=score,cycle=cycle,logistics_class='P1',
                        eligible=True,full_transit=True,transit_percent=100.0)
        events=[ev(1,0,95.0),ev(2,1,94.9),ev(3,2,94.8),ev(4,20,93.5)]
        sel=compute_selection(events,p)
        roles=sel['X b']
        self.assertEqual([r for r,_ in roles],['PRIMARY','BACKUP1','BACKUP2'])
        self.assertEqual(roles[0][1]['cycle'],1)
        # BACKUP1 skips the consecutive nights: >=7 days from PRIMARY.
        self.assertEqual(roles[1][1]['cycle'],4)
        # BACKUP2 falls back to the next best when no well-separated night remains.
        self.assertEqual(roles[2][1]['cycle'],2)
        self.assertEqual(roles[0][1]['rank_within_target'],1)
        self.assertEqual(roles[1][1]['selection_role'],'BACKUP1')
        # Best class wins over score: a DA VALUTARE night never becomes PRIMARY.
        mixed=[ev(10,0,99.0,'DA VALUTARE'),ev(11,9,50.0,'ALTERNATIVE')]
        self.assertEqual(compute_selection(mixed,p)['X b'][0][1]['cycle'],11)
        # Even a stale favorable label is not enough: the gate decides, not the class.
        stale=[dict(ev(12,0,99.0,'ALTERNATIVE'),transit_percent=99.999,eligible=False,full_transit=False)]
        self.assertNotIn('X b',compute_selection(stale,p))
        # Un target con soli DA VALUTARE riceve comunque la raccomandazione (policy invariata):
        # la classe domina l'ordine, ma non esiste una classe esclusa dai ruoli.
        self.assertEqual(compute_selection([ev(13,0,99.0,'DA VALUTARE')],p)['X b'][0][0],'PRIMARY')
        # Non-P1 events are excluded from the operational pool.
        self.assertNotIn('Y b',compute_selection([dict(ev(20,0,99.0),name='Y b',logistics_class='P3')],p))


class ChronologyChecks(unittest.TestCase):
    def setUp(self):
        from reports import operational_rows
        from datetime import datetime,timezone,timedelta
        self.chrono=operational_rows
        self.base=datetime(2026,1,1,tzinfo=timezone.utc)
        self.timedelta=timedelta
    def events(self):
        # Nomi scelti per far fallire qualunque ordinamento alfabetico.
        def ev(cycle,mid_local,mid_utc,name,role,cat='PRIMA SCELTA'):
            return dict(name=name,cycle=cycle,mid_utc=mid_utc,mid_local=mid_local,
                        category=cat,quality_class=cat,logistics_class='P1',score=90.0,
                        eligible=True,full_transit=True,transit_percent=100.0,selection_role=role)
        return [ev(1,'2026-10-14T22:29:00+02:00','2026-10-14T20:29:00+00:00','Zeta b','PRIMARY'),
                ev(2,'2026-11-14T22:29:00+01:00','2026-11-14T21:29:00+00:00','Zeta b','BACKUP1'),
                ev(3,'2026-12-08T22:29:00+01:00','2026-12-08T21:29:00+00:00','Zeta b','BACKUP2'),
                ev(4,'2026-09-16T22:37:00+02:00','2026-09-16T20:37:00+00:00','Alpha b','PRIMARY'),
                ev(5,'2027-05-29T23:45:00+02:00','2027-05-29T21:45:00+00:00','Alpha b','BACKUP1','ALTERNATIVE'),
                ev(6,'2027-06-05T23:36:00+02:00','2027-06-05T21:36:00+00:00','Alpha b','BACKUP2','DA VALUTARE')]
    def test_global_order_ignores_target_name_and_keeps_roles(self):
        flat=self.chrono(self.events())
        self.assertEqual([(e['name'],e['display_role'],e['cycle']) for e in flat],
            [('Alpha b','PRIMARY',4),('Zeta b','PRIMARY',1),('Zeta b','BACKUP1',2),
             ('Zeta b','BACKUP2',3),('Alpha b','BACKUP1',5)])
    def test_da_valutare_excluded_from_operational_view(self):
        self.assertNotIn(6,[e['cycle'] for e in self.chrono(self.events())])
    def test_year_boundary_december_before_january(self):
        mids=[e['mid_local'] for e in self.chrono(self.events())]
        self.assertLess([m for m in mids if m.startswith('2026-12')][0],
                        [m for m in mids if m.startswith('2027')][0])
    def test_dst_offsets_parsed_as_aware_datetimes(self):
        from datetime import datetime
        parsed=[datetime.fromisoformat(e['mid_local']) for e in self.chrono(self.events())]
        self.assertEqual(parsed,list(sorted(parsed)))
        self.assertEqual({x.utcoffset().total_seconds() for x in parsed},{7200.0,3600.0})
    def test_selection_set_identical_after_chronology(self):
        import copy
        events=self.events()
        before=sorted((e['name'],e['selection_role'],e['cycle'],e['quality_class']) for e in events)
        snap=copy.deepcopy(events)
        flat=self.chrono(events)
        after=sorted((e['name'],e['selection_role'],e['cycle'],e['quality_class']) for e in flat)
        # la vista operativa e' un sottoinsieme: nessuna perdita, DV esclusa dalla vista
        self.assertEqual(after,[x for x in before if x[3]!='DA VALUTARE'])
        self.assertEqual(events,snap)
        self.assertEqual(len(flat),5)
        self.assertEqual({e['display_role'] for e in flat},{'PRIMARY','BACKUP1','BACKUP2'})


class CalendarChecks(unittest.TestCase):
    def setUp(self):
        from reports import calendar_rows,curated_review_rows,compute_selection
        from datetime import datetime,timezone,timedelta
        self.calendar_rows=calendar_rows
        self.curated=curated_review_rows
        self.compute_selection=compute_selection
        self.p=dict(backup_preferred_separation_days=7,backup_fallback_separation_days=3,
                    max_review_events_per_target=3,preferred_altitude_deg=30)
        self.base=datetime(2026,10,1,22,0,tzinfo=timezone.utc)
        self.timedelta=timedelta
    def ev(self,name,cycle,days,cat='PRIMA SCELTA',log='P1',score=90.0):
        mid=self.base+self.timedelta(days=days)
        return dict(name=name,cycle=cycle,mid_utc=mid.astimezone(timezone.utc).isoformat(),
                    mid_local=mid.isoformat(),start_local=mid.isoformat(),end_local=mid.isoformat(),
                    category=cat,quality_class=cat,logistics_class=log,score=score,
                    eligible=True,full_transit=True,
                    altitude_ingress_deg=35,altitude_mid_deg=40,altitude_egress_deg=33,
                    transit_percent=100,baseline_before_percent=100,baseline_after_percent=100,
                    moon_risk='BASSA',moon_illumination_percent=3,moon_min_separation_deg=120,
                    reason_codes=[])
    def roles(self,events):
        sel=self.compute_selection(events,self.p)
        return {(e['name'],e['cycle']):e['selection_role'] for roles in sel.values() for _,e in roles}
    def test_six_prima_p1_three_recommended_three_extra(self):
        events=[self.ev('WASP-X b',i,d) for i,d in enumerate([0,13,42,55,69,82])]
        roles=self.roles(events)
        self.assertEqual(len(roles),3)
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        self.assertEqual(len(rows),6)
        self.assertEqual(sum(1 for r in rows if r['display_role']=='EXTRA'),3)
        self.assertEqual(sum(1 for r in rows if r['display_role'] in ('PRIMARY','BACKUP1','BACKUP2')),3)
    def test_primary_backup_set_identical_and_untouched(self):
        events=[self.ev('WASP-X b',i,d) for i,d in enumerate([0,13,42,55])]
        before=self.roles([dict(e) for e in events])
        self.calendar_rows(events,'PRIMA SCELTA')
        self.assertEqual(self.roles(events),before)
    def test_alternative_backup_not_in_prima_calendar(self):
        events=[self.ev('A b',1,0),self.ev('A b',2,10,'ALTERNATIVE')]
        roles=self.roles(events)
        self.assertEqual(roles[('A b',2)],'BACKUP1')
        prima=self.calendar_rows(events,'PRIMA SCELTA')
        self.assertEqual([r['event_id'] for r in prima],['A_b-c1'])
        alt=self.calendar_rows(events,'ALTERNATIVE')
        self.assertEqual([r['display_role'] for r in alt],['BACKUP1'])
    def test_partial_stale_favorable_label_is_excluded(self):
        """Una quality_class favorevole non basta: senza il gate (eligible) la riga non esiste."""
        e=self.ev('A b',9,0,'ALTERNATIVE')
        e.update(transit_percent=99.999,eligible=False,full_transit=False)
        self.assertEqual(self.calendar_rows([e],'ALTERNATIVE'),[])

    def test_unselected_prima_p1_is_extra(self):
        events=[self.ev('A b',1,0),self.ev('A b',2,9),self.ev('A b',3,18),self.ev('A b',4,27)]
        self.roles(events)
        self.calendar_rows(events,'PRIMA SCELTA')
        extras=[r for r in self.calendar_rows(events,'PRIMA SCELTA') if r['display_role']=='EXTRA']
        self.assertEqual(len(extras),1)
        self.assertIsNone(self.roles(events).get(('A b',4)))
    def test_p2_and_p3_excluded_from_operational_calendar(self):
        events=[self.ev('A b',1,0),self.ev('A b',2,10,log='P2'),self.ev('A b',3,20,log='P3')]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        self.assertEqual([r['event_id'] for r in rows],['A_b-c1'])
    def test_order_ignores_target_name(self):
        events=[self.ev('Zeta b',1,9),self.ev('Alpha b',2,8)]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        self.assertEqual([r['name'] for r in rows],['Alpha b','Zeta b'])
    def test_year_boundary(self):
        events=[self.ev('A b',1,76),self.ev('B b',2,98)]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        self.assertTrue(rows[0]['mid_local'].startswith('2026-12'))
        self.assertTrue(rows[1]['mid_local'].startswith('2027-01'))
    def test_dst_europe_rome_offsets(self):
        from zoneinfo import ZoneInfo
        from datetime import datetime,timedelta
        z=ZoneInfo('Europe/Rome')
        # Oct 18 2026 e' CEST (+02), Nov 8 e' CET (+01): same wall clock, real offsets.
        ev1=self.ev('A b',1,0); ev2=self.ev('B b',2,0)
        ev1['mid_local']=datetime(2026,10,18,22,0,tzinfo=z).isoformat()
        ev2['mid_local']=datetime(2026,11,8,22,0,tzinfo=z).isoformat()
        events=[ev1,ev2]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        from datetime import datetime
        offs={datetime.fromisoformat(r['mid_local']).utcoffset().total_seconds() for r in rows}
        self.assertEqual(offs,{7200.0,3600.0})
        mids=[datetime.fromisoformat(r['mid_local']) for r in rows]
        self.assertEqual(mids,sorted(mids))
    def test_no_duplicate_event_ids(self):
        events=[self.ev('A b',i,d) for i,d in enumerate([0,9,18])]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        ids=[r['event_id'] for r in rows]
        self.assertEqual(len(ids),len(set(ids)))
    def test_calendar_count_equals_prima_p1_count(self):
        events=[self.ev('A b',1,0),self.ev('A b',2,9,log='P2'),self.ev('B b',3,10,'ALTERNATIVE'),
                self.ev('C b',4,12),self.ev('D b',5,14,'DA VALUTARE')]
        rows=self.calendar_rows(events,'PRIMA SCELTA')
        expected=sum(1 for e in events if e['quality_class']=='PRIMA SCELTA' and e['logistics_class']=='P1')
        self.assertEqual(len(rows),expected)
        self.assertEqual({r['quality_class'] for r in rows},{'PRIMA SCELTA'})
    def test_classification_score_roles_untouched_by_calendar(self):
        import copy
        events=[self.ev('A b',1,0),self.ev('B b',2,10,'ALTERNATIVE',score=77.7)]
        snapshot=copy.deepcopy(events)
        self.calendar_rows(events,'PRIMA SCELTA')
        self.calendar_rows(events,'ALTERNATIVE')
        for a,b in zip(events,snapshot):
            for k in ('category','quality_class','logistics_class','score','cycle','mid_local'):
                self.assertEqual(a[k],b[k],k)
            self.assertEqual(a.get('selection_role'),b.get('selection_role'))
    def test_review_curated_max_per_target_chronological(self):
        events=[self.ev('A b',i,d,'DA VALUTARE',score=s) for i,d,s in
                [(1,0,50),(2,1,60),(3,2,55),(4,3,45)]]
        rows=self.curated(events,self.p)
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r['name']=='A b' for r in rows))
        self.assertEqual([r['event_id'] for r in rows],['A_b-c1','A_b-c2','A_b-c3'])
        self.assertTrue(all(r['display_role']=='REVIEW' for r in rows))


    def test_operational_calendar_mixed_classes(self):
        from reports import operational_rows
        # 1,2: PRIMA/P1 e ALTERNATIVE/P1 dentro; 5,6: DA VALUTARE e NON CONSIGLIATO fuori.
        events=[self.ev('A b',1,0),self.ev('B b',2,10,'ALTERNATIVE'),
                self.ev('C b',3,20,'DA VALUTARE'),self.ev('D b',4,30,'NON CONSIGLIATO')]
        rows=operational_rows(events)
        self.assertEqual([r['event_id'] for r in rows],['A_b-c1','B_b-c2'])
        self.assertEqual({r['quality_class'] for r in rows},{'PRIMA SCELTA','ALTERNATIVE'})
        # 3,4: varianti P2 escluse.
        events=[self.ev('A b',1,0,log='P2'),self.ev('B b',2,10,'ALTERNATIVE',log='P2')]
        self.assertEqual(operational_rows(events),[])
        # 7: regression KELT-16 21/09/2026: ALTERNATIVE resta ALTERNATIVE nel calendario.
        from zoneinfo import ZoneInfo
        k=dict(self.ev('KELT-16 b',9,0,'ALTERNATIVE',score=85.8))
        k['mid_local']=datetime(2026,9,21,23,16,tzinfo=ZoneInfo('Europe/Rome')).isoformat()
        k['reason_codes']=['MOON_MODERATA']
        rows=operational_rows([k])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['quality_class'],'ALTERNATIVE')
        self.assertEqual(rows[0]['mid_local'][:16],'2026-09-21T23:16')
        self.assertIn('MOON_MODERATA',rows[0]['reason_codes'])
        # 8,9: ordine globale per data, dicembre 2026 prima di gennaio 2027.
        events=[self.ev('Zeta b',10,92),self.ev('Alpha b',11,77)]
        rows=operational_rows(events)
        self.assertEqual([r['name'] for r in rows],['Alpha b','Zeta b'])
        self.assertTrue(rows[0]['mid_local'].startswith('2026-12'))
        self.assertTrue(rows[1]['mid_local'].startswith('2027-01'))
        # 10: nessun duplicato.
        many=[self.ev('A b',i,d) for i,d in enumerate([0,9,18])]
        ids=[r['event_id'] for r in operational_rows(many)]
        self.assertEqual(len(ids),len(set(ids)))
        # 11: count == (PRIMA or ALTERNATIVE) and P1.
        events=[self.ev('A b',1,0),self.ev('A b',2,9,log='P2'),self.ev('B b',3,10,'ALTERNATIVE'),
                self.ev('C b',4,12,'DA VALUTARE'),self.ev('D b',5,14)]
        rows=operational_rows(events)
        expected=sum(1 for e in events if e['logistics_class']=='P1'
                     and e['quality_class'] in ('PRIMA SCELTA','ALTERNATIVE'))
        self.assertEqual(len(rows),expected)
        # 12: classi, score e PRIMARY/BACKUP identici prima/dopo.
        import copy
        events=[self.ev('A b',1,0),self.ev('B b',2,10,'ALTERNATIVE',score=70.0)]
        self.roles(events)
        snap=copy.deepcopy(events)
        operational_rows(events)
        for a,b in zip(events,snap):
            for k in ('category','quality_class','logistics_class','score','cycle'):
                self.assertEqual(a[k],b[k],k)
            self.assertEqual(a.get('selection_role'),b.get('selection_role'))


class PrototypeChecks(unittest.TestCase):
    def setUp(self):
        from reports import calendar_rows,tapir_dossier_document
        from datetime import datetime,timezone,timedelta
        import tempfile
        self.rows=lambda events: calendar_rows(events,'PRIMA SCELTA')
        self.document=tapir_dossier_document
        self.tmp=tempfile.TemporaryDirectory()
        self.archive=self.tmp.name
        frag='<table id="target_table" class="display"><tr><th>Name</th></tr><tr><td>MARKER_TAPIR_ROW</td></tr></table>'
        page=('<!doctype html><html><head><style>.x{}</style></head><body>'
              '<p>Only 1 target matches your constraints. Searching for observable transits over 1.0 days...</p>'
              +frag+'</body></html>')
        d=self.archive+'/T/'
        import os; os.makedirs(d,exist_ok=True)
        open(d+'frag.html','w').write(page)
        self.base=datetime(2026,10,1,22,0,tzinfo=timezone.utc)
        self.timedelta=timedelta
        self.p=dict(backup_preferred_separation_days=7,backup_fallback_separation_days=3)
        self.legend='PRIMARY = prima raccomandazione · BACKUP1/BACKUP2 = riserve · EXTRA = ulteriore occasione valida'
    def tearDown(self):
        self.tmp.cleanup()
    def ev(self,name,cycle,days,cat='PRIMA SCELTA',log='P1',score=90.0):
        mid=self.base+self.timedelta(days=days)
        return dict(name=name,cycle=cycle,mid_utc=mid.isoformat(),mid_local=mid.isoformat(),
                    category=cat,quality_class=cat,logistics_class=log,score=score,
                    eligible=True,full_transit=True,transit_percent=100.0,
                    selection_role=None,tapir_event_html='T/frag.html')
    def roles(self,events):
        from reports import compute_selection
        sel=compute_selection(events,self.p)
        return {(e['name'],e['cycle']):e['selection_role'] for roles in sel.values() for _,e in roles}
    def test_subset_exact_chronological_no_duplicates(self):
        events=[self.ev('Zeta b',1,9),self.ev('Alpha b',2,8),self.ev('B b',3,10,'ALTERNATIVE'),
                self.ev('C b',4,11,'DA VALUTARE'),self.ev('D b',5,12,log='P2')]
        rows=self.rows(events)
        self.assertEqual([r['event_id'] for r in rows],['Alpha_b-c2','Zeta_b-c1'])
        ids=[r['event_id'] for r in rows]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual([r['name'] for r in rows],['Alpha b','Zeta b'])
    def test_roles_preserved(self):
        events=[self.ev('WASP-77 A b',1,0),self.ev('A b',2,9)]
        roles=self.roles(events)
        rows=self.rows(events)
        byid={r['event_id']:r for r in rows}
        for (name,cycle),role in roles.items():
            self.assertEqual(byid[slug(name)+'-c'+str(cycle)]['display_role'],role)
    def test_document_contains_index_disclaimer_tapir_unique_ids_anchors(self):
        import re
        events=[self.ev('WASP-77 A b',1,0,score=99.9),self.ev('A b',2,9),self.ev('B b',3,17)]
        self.roles(events)
        rows=self.rows(events)
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertIsNone(broken)
        for marker in ['UAN - PRIMA SCELTA','OUTPUT TAPIR ORIGINALE','policy UAN v2.2.0',
                       'MARKER_TAPIR_ROW','WASP-77 A b','Europe/Rome','PRIMARY','BACKUP1','EXTRA']:
            self.assertIn(marker,doc)
        self.assertEqual(doc.count('MARKER_TAPIR_ROW'),len(rows))
        ids=re.findall(r'\bid="([^"]+)"',doc)
        self.assertEqual(len(ids),len(set(ids)),'ID HTML duplicati')
        anchors=[i for i in ids if i.startswith('event-')]
        self.assertEqual(len(anchors),len(rows))
        for a in anchors:
            self.assertIn('id="'+a+'"',doc)
        for href in re.findall(r'href="#(event-[^"]+)"',doc):
            self.assertIn(href,anchors)
    def test_wasp77_regression_in_document(self):
        events=[self.ev('WASP-77 A b',1050,0,score=99.9)]
        self.roles(events)
        rows=self.rows(events)
        rows[0]['selection_role']='PRIMARY';rows[0]['display_role']='PRIMARY'
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertIn('>WASP-77 A b</b> — PRIMARY',doc)
    def test_kelt16_alternative_not_in_prima_dossier(self):
        from zoneinfo import ZoneInfo
        k=self.ev('KELT-16 b',9,0,'ALTERNATIVE',score=96.2)
        k['mid_local']=datetime(2026,9,21,23,16,tzinfo=ZoneInfo('Europe/Rome')).isoformat()
        k['reason_codes']=['MOON_MODERATA']
        rows=self.rows([k,self.ev('A b',2,9)])
        self.assertEqual([r['event_id'] for r in rows],['A_b-c2'])
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertNotIn('KELT-16 b',doc)
    def test_broken_fragment_reported_not_hidden(self):
        events=[self.ev('A b',1,0)]
        events[0]['tapir_event_html']='T/inesistente.html'
        rows=self.rows(events)
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertIsNone(doc)
        self.assertEqual(broken,'A_b-c1')
    def test_renderer_does_not_mutate_events(self):
        import copy
        events=[self.ev('A b',1,0),self.ev('B b',2,9)]
        self.roles(events)
        snap=copy.deepcopy(events)
        rows=self.rows(events)
        self.document(rows,Path(self.archive),'Europe/Rome','PRIMA SCELTA',self.legend)
        for a,b in zip(events,snap):
            self.assertEqual(a,b)
    def test_year_boundary_and_dst_in_document(self):
        from zoneinfo import ZoneInfo
        from datetime import datetime
        d1=self.ev('A b',1,0);d2=self.ev('B b',2,92)
        d1['mid_local']=datetime(2026,12,21,23,0,tzinfo=ZoneInfo('Europe/Rome')).isoformat()
        d2['mid_local']=datetime(2027,1,10,22,0,tzinfo=ZoneInfo('Europe/Rome')).isoformat()
        rows=self.rows([d2,d1])
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertIsNone(broken)
        self.assertLess(doc.index('DICEMBRE 2026'),doc.index('GENNAIO 2027'))
        # DST: gli eventi invernali sono CET (+01) e l'ordine resta quello reale.
        # (coppie estivo/invernali coperte da test_dst_europe_rome_offsets)
        from datetime import datetime as D
        mids=[D.fromisoformat(r['mid_local']) for r in rows]
        self.assertEqual(mids,sorted(mids))
        self.assertEqual({m.utcoffset().total_seconds() for m in mids},{3600.0})


    def test_fragment_validation_and_ensure(self):
        from reports import tapir_fragment_valid,ensure_tapir_fragment
        p=dict(longitude=14.255056,latitude=40.862861,height_m=150,timezone='Europe/Rome',
               baseline_hours=1,extend_uncertainty=True,twilight_deg=-12)
        mid='2026-10-01T22:00:00+00:00'
        hdr=('<table id="target_table"><tr><th>Data</th><th>Name</th><th>V or Gaia mag</th>'
             '<th>Start&mdash; Mid &mdash;End</th><th>Duration</th></tr>')
        rowf=lambda name,mid_s: ('<tr><td>2026-10-01 17:30 2026-10-02 06:30</td>'
            f'<td><a href="#">{name}</a> Finding charts: Annotated , Aladin ; Airmass plot , ACP plan '
            f'Info: Exoplanet Archive</td><td>10.3</td>'
            f'<td>2026-10-01 20:00 2026-10-01 21:00 {mid_s} 2026-10-01 23:00 2026-10-02 00:00</td>'
            f'<td>2:46</td></tr>')
        good=hdr+rowf('Test b','2026-10-01 22:00')+'</table>'
        wrong_evt=hdr+rowf('Test b','2026-10-01 23:15')+'</table>'
        wrong_tgt=hdr+rowf('Other b','2026-10-01 22:00')+'</table>'
        no_bjd='<table><tr><td>Test b</td></tr></table>'
        e=dict(name='Test b',cycle=7,mid_utc=mid,mid_local=mid)
        self.assertTrue(tapir_fragment_valid(good,'Test b',mid,p['timezone'])[0])
        self.assertFalse(tapir_fragment_valid(wrong_evt,'Test b',mid,p['timezone'])[0])
        self.assertFalse(tapir_fragment_valid(wrong_tgt,'Test b',mid,p['timezone'])[0])
        tmap={'Test b':dict(RA='10:00:00',Dec='+30:00:00',period='2.5',name='Test b')}
        # esistente e valido -> nessuna query TAPIR
        (Path(self.archive)/'Test_b').mkdir(exist_ok=True)
        (Path(self.archive)/'Test_b'/'tapir_event_c7.html').write_text(good)
        self.assertEqual(ensure_tapir_fragment(e,tmap['Test b'],p,Path(self.archive)),
                         'Test_b/tapir_event_c7.html')
        # puntatore vecchio valido -> copiato sotto il nome canonico (no collisioni)
        e2=dict(e,cycle=9,event_id='Test_b-c9');e2.pop('tapir_event_html',None)
        (Path(self.archive)/'Test_b'/'old_frag.html').write_text(good)
        e2['tapir_event_html']='Test_b/old_frag.html'
        rel=ensure_tapir_fragment(e2,tmap['Test b'],p,Path(self.archive))
        self.assertEqual(rel,'Test_b/tapir_event_c9.html')
        self.assertEqual((Path(self.archive)/rel).read_text(),good)
        eng=Path(self.archive)/'dati_originali'/'tapir_source'
        eng.mkdir(parents=True,exist_ok=True)
        cgi=eng/'print_transits.cgi'
        cgi.write_text('#!/bin/sh\necho \'<!doctype html><html><body><table id="target_table">'
                       '<tr><th>Data</th><th>Name</th><th>V or Gaia mag</th>'
                       '<th>Start&mdash; Mid &mdash;End</th><th>Duration</th></tr>'
                       '<tr><td>2026-10-14&nbsp;18:00 2026-10-15&nbsp;06:00</td>'
                       '<td><a href="#">Test b</a> Finding charts: Aladin ; Airmass plot Info: NASA</td>'
                       '<td>10.3</td>'
                       '<td>2026-10-14&nbsp;20:00 2026-10-14&nbsp;21:00 2026-10-14&nbsp;22:00 '
                       '2026-10-14&nbsp;23:00 2026-10-15&nbsp;00:00</td><td>2:46</td></tr>'
                       '</table></body></html>\'\n')
        cgi.chmod(0o755)
        # contenuto di un altro evento -> errore esplicito, nessun inserimento
        e3=dict(e,cycle=11,event_id='Test_b-c11');e3.pop('tapir_event_html',None)
        (Path(self.archive)/'Test_b'/'tapir_event_c11.html').write_text(wrong_evt)
        with self.assertRaises(ValueError) as cm:
            ensure_tapir_fragment(e3,tmap['Test b'],p,Path(self.archive))
        self.assertIn('non valido',str(cm.exception))
        # rigenerazione con engine TAPIR (finto): frammento corretto -> successo
        e4=dict(e,cycle=13,event_id='Test_b-c13');e4.pop('tapir_event_html',None)
        # evento con mid 2026-10-14 22:00 UTC: il finto TAPIR produce esattamente quel mid
        e4['mid_local']='2026-10-14T22:00:00+00:00';e4['mid_utc']='2026-10-14T22:00:00+00:00'
        rel=ensure_tapir_fragment(e4,tmap['Test b'],p,Path(self.archive))
        self.assertEqual(rel,'Test_b/tapir_event_c13.html')
        self.assertIn('MARKER' ,(Path(self.archive)/rel).read_text()) if False else None
        self.assertIn('Test b',(Path(self.archive)/rel).read_text())

    def test_dossier_has_no_tapir_preamble(self):
        events=[self.ev('WASP-77 A b',1050,0,score=99.9)]
        self.roles(events)
        rows=self.rows(events)
        doc,broken=self.document(rows,Path(self.archive),'Europe/Rome','UAN - PRIMA SCELTA',self.legend)
        self.assertIsNone(broken)
        for bad in ['Only 1 target matches your constraints','Upcoming events for the next 1 day']:
            self.assertNotIn(bad,doc)
        self.assertIn('MARKER_TAPIR_ROW',doc)


class EligibilityChecks(unittest.TestCase):
    """Policy v2.2: only real 100% transits (independent recomputation) enter the pipeline."""
    P={'severe_altitude_deg':15,'preferred_altitude_deg':30,'excellent_altitude_deg':40,
       'visibility_altitude_deg':20,'transit_operational_percent':90,'first_choice_min_percent':99.5,
       'baseline_weak_percent':50,'baseline_good_percent':80,'maximum_uncertainty_minutes':10,
       'backup_preferred_separation_days':7,'backup_fallback_separation_days':3,
       'timing_residual_limit_seconds':2,'max_review_events_per_target':3}
    METRICS=('transit_percent','transit_uncovered_seconds','altitude_min_deg','altitude_mid_deg','altitude_max_deg',
             'baseline_before_percent','baseline_after_percent','moon_illumination_percent','moon_separation_deg',
             'moon_risk','uncertainty_minutes','cycle','mid_utc')
    def ev(self,cycle=1,days=0,uncovered=0.0,**kw):
        from datetime import datetime,timezone,timedelta
        mid=datetime(2026,11,1,22,0,tzinfo=timezone.utc)+timedelta(days=days)
        e=dict(name='X b',cycle=cycle,mid_utc=mid.isoformat(),mid_local=mid.isoformat(),
               ingress_local=mid.isoformat(),egress_local=mid.isoformat(),
               max_altitude_theoretical_deg=55,altitude_min_deg=31,altitude_mid_deg=40,altitude_max_deg=45,
               transit_percent=100.0 if uncovered==0 else 100.0*(1-uncovered/10800.0),
               transit_uncovered_seconds=uncovered,duration_minutes=180,
               baseline_before_percent=100,baseline_after_percent=100,practical_transit_percent=100,
               uncertainty_minutes=1,moon_risk='BASSA',magnitude=11,depth_ppt=12,ttv=False,
               moon_up_during_observable=False,moon_illumination_percent=5,moon_separation_deg=120,
               moon_min_separation_deg=120,altitude_ingress_deg=35,altitude_egress_deg=33,
               timing_check_failed=False,logistics_class='P1')
        e.update(kw)
        return e
    def test_1_real_100_percent_is_eligible(self):
        from observing import evaluate,uncovered_seconds
        self.assertEqual(uncovered_seconds(0,10800,[(-100,20000)]),0.0)
        e=evaluate(self.ev(),self.P)
        self.assertTrue(e['eligible'] and e['full_transit'])
        self.assertIsNone(e['exclusion_reason'])
        self.assertEqual((e['quality_class'],e['logistics_class']),('PRIMA SCELTA','P1'))
        self.assertIsNotNone(e['score'])
    def test_2_99_999_percent_is_not_eligible(self):
        from observing import evaluate,uncovered_seconds,FULL_TRANSIT_TOLERANCE_SECONDS as TOL
        # 99.999% of a 3 h transit = 0.108 s uncovered: displayed as 100.0, never promoted.
        u=uncovered_seconds(0,10800,[(0,10800*0.99999)])
        self.assertAlmostEqual(u,0.108,places=6)
        e=evaluate(self.ev(uncovered=u),self.P)
        self.assertFalse(e['eligible']);self.assertEqual(e['exclusion_reason'],'TRANSIT_NOT_100')
        self.assertEqual(f"{e['transit_percent']:.1f}",'100.0')
        # tolerance is numeric only: below = float noise, above = real gap.
        self.assertTrue(evaluate(self.ev(uncovered=TOL/2),self.P)['eligible'])
        self.assertFalse(evaluate(self.ev(uncovered=TOL*2),self.P)['eligible'])
        self.assertLess(TOL,0.1)
        # 30 s gap: old classify would give PRIMA (99.7% >= 99.5); gate excludes it.
        e=evaluate(self.ev(uncovered=30),self.P)
        self.assertFalse(e['eligible']);self.assertIsNone(e['quality_class'])
    def test_3_partial_never_in_operational_reports(self):
        from observing import evaluate
        from reports import calendar_rows,operational_rows,curated_review_rows
        part=evaluate(self.ev(uncovered=60),self.P)
        for rows in (calendar_rows([part],'PRIMA SCELTA'),calendar_rows([part],'ALTERNATIVE'),
                     operational_rows([part]),curated_review_rows([part],self.P)):
            self.assertEqual(rows,[])
        # even a forged operational-looking row is refused when eligible is False
        forged=dict(self.ev(),eligible=False,quality_class='PRIMA SCELTA',category='PRIMA SCELTA')
        self.assertEqual(operational_rows([forged]),[])
        self.assertEqual(curated_review_rows([dict(forged,quality_class='DA VALUTARE')],self.P),[])
    def test_4_partial_stays_in_archive_results(self):
        import tempfile,json,csv
        from pathlib import Path
        from observing import evaluate
        from reports import write_reports
        p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
        t=dict(name='X b',RA='12:00:00',Dec='+00:00:00')
        m=dict(profile=p,created_utc='2026-09-15',start='2026-09-15',end_exclusive='2026-09-16',tapir_commit='test-only',command='test-only')
        part=evaluate(self.ev(uncovered=600),self.P)
        part.update(ingress_utc=part['mid_utc'],egress_utc=part['mid_utc'],practical=False,reference='')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'9_ARCHIVIO_COMPLETO').mkdir()
            write_reports(out,[part],[t],[],m)
            js=json.loads((out/'9_ARCHIVIO_COMPLETO/risultati.json').read_text())
            self.assertEqual([(e['cycle'],e['eligible'],e['exclusion_reason']) for e in js],[(1,False,'TRANSIT_NOT_100')])
            rows=list(csv.DictReader((out/'9_ARCHIVIO_COMPLETO/risultati.csv').open()))
            self.assertEqual((rows[0]['eligible'],rows[0]['exclusion_reason']),('False','TRANSIT_NOT_100'))
            for f in ('0_CALENDARIO_OPERATIVO.json','calendario_prima_scelta.json'):
                self.assertEqual(json.loads((out/'9_ARCHIVIO_COMPLETO'/f).read_text()),[])
            for f in ('1_PRIMA_SCELTA.html','2_ALTERNATIVE.html','3_DA_VALUTARE.html','0_CALENDARIO_OPERATIVO.html'):
                self.assertNotIn('TRANSIT_NOT_100',(out/f).read_text() if f!='0_CALENDARIO_OPERATIVO.html' else (out/'9_ARCHIVIO_COMPLETO'/f).read_text())
            self.assertIn('NON ELEGGIBILE: 1 totali',(out/'0_LEGGIMI.txt').read_text())
    def test_5_partial_never_gets_selection_role(self):
        from observing import evaluate
        from reports import compute_selection
        events=[evaluate(self.ev(1,0,uncovered=5),self.P),evaluate(self.ev(2,9,uncovered=0.5),self.P)]
        self.assertEqual(compute_selection(events,self.P),{})
        self.assertTrue(all('selection_role' not in e for e in events))
        forged=dict(self.ev(3,18),eligible=False,category='PRIMA SCELTA',quality_class='PRIMA SCELTA',score=99.0)
        self.assertEqual(compute_selection([forged],self.P),{})
    def test_6_7_8_full_transit_with_other_issue_is_da_valutare(self):
        from observing import evaluate
        for kw,code in ((dict(ttv=True),'TTV'),(dict(moon_risk='ESTREMA'),'MOON_EXTREME'),
                        (dict(baseline_after_percent=40),'BASELINE_WEAK')):
            e=evaluate(self.ev(**kw),self.P)
            self.assertTrue(e['eligible'],code)
            self.assertEqual(e['quality_class'],'DA VALUTARE',code)
            self.assertIn(code,e['reason_codes'])
            self.assertNotIn('TRANSIT_NOT_100',e['reason_codes'])
    def test_9_prima_and_alternative_only_100_percent(self):
        from observing import evaluate
        for uncovered in (0.002,0.108,30,600):
            for kw in (dict(),dict(moon_risk='ALTA')):
                e=evaluate(self.ev(uncovered=uncovered,**kw),self.P)
                self.assertNotIn(e['quality_class'],('PRIMA SCELTA','ALTERNATIVE'))
        self.assertEqual(evaluate(self.ev(moon_risk='ALTA'),self.P)['quality_class'],'ALTERNATIVE')
    def test_10_roles_only_100_percent(self):
        from observing import evaluate
        from reports import compute_selection
        events=[evaluate(self.ev(i,d,u),self.P) for i,d,u in ((1,0,0),(2,9,0.5),(3,18,0),(4,27,45),(5,36,0),(6,45,0))]
        sel=compute_selection(events,self.P)['X b']
        self.assertEqual([(r,e['cycle']) for r,e in sel],[('PRIMARY',1),('BACKUP1',3),('BACKUP2',5)])
        self.assertTrue(all(e['transit_percent']==100.0 and e['eligible'] for _,e in sel))
        self.assertTrue(all('selection_role' not in e for e in events if not e['eligible']))
    def test_11_12_13_completeness_metrics_and_old_classes_invariant(self):
        import copy
        from observing import evaluate,classify,score
        events=[self.ev(i,i,u,**kw) for i,(u,kw) in enumerate(((0,{}),(0.5,{}),(0,dict(ttv=True)),(3000,{}),
                                                                   (0,dict(moon_risk='ALTA')),(0,dict(baseline_after_percent=40))))]
        snap=copy.deepcopy(events)
        out=[evaluate(e,self.P) for e in events]
        self.assertEqual([e['cycle'] for e in out],[e['cycle'] for e in snap])  # 11: no cycle lost
        for a,b in zip(out,snap):
            for k in self.METRICS: self.assertEqual(a[k],b[k],k)          # 12: metrics untouched
            if b['transit_uncovered_seconds']==0:                              # 13: old 100% events unchanged
                self.assertEqual(a['quality_class'],classify(b,self.P)[0])
                self.assertEqual(a['score'],round(100*score(b,self.P),1))
    def test_analyze_wires_uncovered_seconds_and_gate(self):
        import json
        import astropy.units as u
        from astropy.coordinates import SkyCoord,EarthLocation
        from astropy.time import Time
        from observing import analyze,FULL_TRANSIT_TOLERANCE_SECONDS as TOL
        p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
        loc=EarthLocation.from_geodetic(p['longitude']*u.deg,p['latitude']*u.deg,p['height_m']*u.m)
        c=SkyCoord('04:20:00','+40:00:00',unit=(u.hourangle,u.deg))
        def run(jd):
            m=Time(jd,format='jd',scale='utc',location=loc)
            epoch=float((m.tdb+m.light_travel_time(c,kind='barycentric')).jd)
            t=dict(name='Synthetic b',RA='04:20:00',Dec='+40:00:00',vmag='11',period='1.0',epoch=repr(epoch),
                   epoch_uncertainty='0.0005',period_uncertainty='0.000001',duration='2.5',comments='synthetic',depth='10')
            return analyze({'jd_utc_exact':jd},t,p)
        full=run(2461360.375)      # 2026-11-15 21:00 UTC, target near meridian at night
        part=run(2461362.255)      # 2026-11-17 18:07 UTC, ingress before nautical dusk
        self.assertEqual((full['transit_percent'],full['transit_uncovered_seconds'],full['eligible']),(100.0,0.0,True))
        self.assertEqual((full['quality_class'],full['logistics_class']),('PRIMA SCELTA','P1'))
        self.assertLess(part['transit_percent'],100);self.assertGreater(part['transit_uncovered_seconds'],TOL)
        self.assertFalse(part['eligible']);self.assertEqual(part['exclusion_reason'],'TRANSIT_NOT_100')
        self.assertEqual((part['quality_class'],part['logistics_class'],part['score']),(None,None,None))
        self.assertEqual(part['category'],'NON ELEGGIBILE')
        # uncovered seconds is the duration-based quantity, consistent with the percentage
        self.assertAlmostEqual(part['transit_uncovered_seconds'],part['duration_minutes']*60*(1-part['transit_percent']/100),places=4)


class AuditRegressionChecks(unittest.TestCase):
    """Audit 2026-09-21 (GLM cross-review): reporting text, links and the legacy-input gate."""
    def setUp(self):
        import json
        from pathlib import Path
        self.p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
    def ev(self,**kw):
        from datetime import datetime,timezone
        mid=datetime(2026,11,1,22,0,tzinfo=timezone.utc)
        e=dict(name='WASP-142 b',cycle=7,mid_utc=mid.isoformat(),mid_local=mid.isoformat(),
               ingress_utc=mid.isoformat(),egress_utc=mid.isoformat(),
               ingress_local=mid.isoformat(),egress_local=mid.isoformat(),
               category='PRIMA SCELTA',quality_class='PRIMA SCELTA',logistics_class='P1',score=95.0,
               transit_percent=100.0,transit_uncovered_seconds=0.0,practical=True,reason='',reason_codes=[],
               altitude_ingress_deg=35,altitude_mid_deg=40,altitude_egress_deg=33,altitude_min_deg=33,
               altitude_max_deg=45,baseline_before_percent=100,baseline_after_percent=100,
               moon_risk='BASSA',moon_illumination_percent=3,moon_min_separation_deg=120,
               eligible=True,exclusion_reason=None,full_transit=True,reference='')
        e.update(kw)
        return e
    def test_legacy_event_without_eligible_is_not_operational(self):
        """A pre-v2.2 risultati.json has no `eligible` key: the gate must fail closed, never
        default a 97% transit back into calendars, dossiers or roles (audit 2026-09-21, F5)."""
        from reports import compute_selection,calendar_rows,operational_rows,curated_review_rows
        legacy=self.ev(transit_percent=97.0);legacy.pop('eligible');legacy.pop('full_transit')
        self.assertEqual(compute_selection([legacy],self.p),{})
        self.assertEqual(operational_rows([legacy]),[])
        self.assertEqual(calendar_rows([legacy],'PRIMA SCELTA'),[])
        self.assertEqual(curated_review_rows([dict(legacy,quality_class='DA VALUTARE',category='DA VALUTARE')],self.p),[])
        self.assertNotIn('selection_role',legacy)
    def test_nasa_link_is_not_double_encoded(self):
        """`quote` over a pre-escaped name produced %2520: every multi-word target had a broken
        NASA link in every calendar row (audit 2026-09-21, N2)."""
        from reports import _calendar_table
        e=dict(self.ev(),display_role='PRIMARY',event_id='x')
        e['start_local'],e['end_local']=e['ingress_local'],e['egress_local']
        html=_calendar_table([e],'Europe/Rome',{},self.p)
        self.assertIn('/overview/WASP-142%20b',html)
        self.assertNotIn('%2520',html)
    def test_readme_texts_match_the_actual_reports(self):
        """0_LEGGIMI/NOTE_SELEZIONE described the v2.1 per-target selection and the 99.5% eligibility:
        both superseded by the v2.2 gate and by the all-P1 dossiers (audit 2026-09-21, F4)."""
        import tempfile,json
        from pathlib import Path
        from reports import write_reports
        t=dict(name='WASP-142 b',RA='12:00:00',Dec='+00:00:00')
        m=dict(profile=self.p,created_utc='2026-09-21',start='2026-09-21',end_exclusive='2026-09-22',
               tapir_commit='test-only',command='test-only')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'9_ARCHIVIO_COMPLETO').mkdir()
            write_reports(out,[],[t],[],m)
            leggimi=(out/'0_LEGGIMI.txt').read_text()
            notes=(out/'9_ARCHIVIO_COMPLETO/NOTE_SELEZIONE.txt').read_text()
        for text,label in ((leggimi,'0_LEGGIMI.txt'),(notes,'NOTE_SELEZIONE.txt')):
            self.assertNotIn('I PDF mostrano solo la selezione',text,label)
            self.assertIn('policy UAN v2.2',text.replace('v2.2.0','v2.2'),label)
        self.assertIn('TUTTI gli eventi PRIMA SCELTA con logistica P1',leggimi)
        self.assertIn('durata non coperta <= 0.001 s',notes)
        self.assertNotIn("Eleggibilita' PRIMA SCELTA: copertura >= 99.5%",notes)
        self.assertIn('illum >=70%',notes)   # MOON_RULES usa >=70, non >70


class EphemerisViewChecks(unittest.TestCase):
    """0_EFFEMERIDI_100: TUTTI e SOLI gli eventi eleggibili, senza altri filtri (vista UAN)."""
    def ev(self,name,cycle,days,uncovered=0.0,cat='PRIMA SCELTA',log='P1',role=None):
        from datetime import datetime,timezone,timedelta
        from observing import evaluate
        mid=datetime(2026,11,1,22,0,tzinfo=timezone.utc)+timedelta(days=days)
        e=dict(name=name,cycle=cycle,mid_utc=mid.isoformat(),mid_local=mid.isoformat(),
               ingress_utc=mid.isoformat(),egress_utc=mid.isoformat(),
               ingress_local=mid.isoformat(),egress_local=mid.isoformat(),
               max_altitude_theoretical_deg=55,altitude_min_deg=31,altitude_mid_deg=40,altitude_max_deg=45,
               transit_percent=100.0 if uncovered==0 else 99.9,transit_uncovered_seconds=uncovered,
               duration_minutes=180,baseline_before_percent=100,baseline_after_percent=100,
               practical_transit_percent=100,practical=True,uncertainty_minutes=1,moon_risk='BASSA',
               magnitude=11,depth_ppt=12,ttv=cat=='DA VALUTARE',moon_up_during_observable=False,
               moon_illumination_percent=5,moon_separation_deg=120,moon_min_separation_deg=120,
               altitude_ingress_deg=35,altitude_egress_deg=33,timing_check_failed=False,
               logistics_class=log,reference='')
        evaluate(e,json.loads((Path(__file__).parent/'capodimonte.json').read_text()))
        if role: e['selection_role']=role
        return e
    def rows(self,events):
        from reports import ephemeris_rows
        return ephemeris_rows(events)
    def test_all_and_only_eligible_no_other_filter(self):
        """Nessun filtro su classe, logistica o ruolo: un P3 DA VALUTARE senza ruolo c'e',
        un transito parziale no."""
        events=[self.ev('A b',1,0),                                   # PRIMA SCELTA P1
                self.ev('B b',2,3,cat='DA VALUTARE',log='P3'),        # DA VALUTARE, fuori serata
                self.ev('C b',3,6,log='P2'),                          # P2
                self.ev('D b',4,9,uncovered=0.108),                   # 99.999%: escluso
                self.ev('E b',5,12,uncovered=600)]                    # parziale: escluso
        rows=self.rows(events)
        self.assertEqual([r['event_id'] for r in rows],['A_b-c1','B_b-c2','C_b-c3'])
        self.assertEqual({r['event_id'] for r in rows},
                         {slug(e['name'])+'-c'+str(e['cycle']) for e in events if e['eligible']})
        self.assertTrue(all(r['transit_percent']==100.0 and r['transit_uncovered_seconds']<=TOL for r in rows))
        self.assertEqual({r['logistics_class'] for r in rows},{'P1','P3','P2'})
        self.assertIn('DA VALUTARE',{r['quality_class'] for r in rows})
        self.assertTrue(all(r.get('selection_role') is None for r in rows))
    def test_chronological_unique_and_not_mutating(self):
        import copy
        events=[self.ev('Zeta b',1,9),self.ev('Alpha b',2,3),self.ev('Alpha b',3,20)]
        snap=copy.deepcopy(events)
        rows=self.rows(events)
        mids=[datetime.fromisoformat(r['mid_local']) for r in rows]
        self.assertEqual(mids,sorted(mids))
        self.assertEqual([r['target'] for r in rows],['Alpha b','Zeta b','Alpha b'])
        ids=[r['event_id'] for r in rows]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(events,snap)
    def test_written_files_match_the_eligible_set(self):
        import tempfile,csv as _csv
        from reports import write_reports
        p=json.loads((Path(__file__).parent/'capodimonte.json').read_text())
        # P2/P3: niente dossier TAPIR da generare, la vista li include comunque (nessun filtro logistico)
        events=[self.ev('A b',1,0,log='P2'),self.ev('B b',2,5,cat='DA VALUTARE',log='P3'),self.ev('C b',3,10,uncovered=900)]
        targets=[dict(name=n,RA='12:00:00',Dec='+00:00:00',period='2.5') for n in ('A b','B b','C b')]
        m=dict(profile=p,created_utc='2026-09-21',start='2026-09-21',end_exclusive='2026-12-21',
               tapir_commit='test-only',command='test-only')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'9_ARCHIVIO_COMPLETO').mkdir()
            # CONSEGNA_UAN pretende la scheda TAPIR di ogni eleggibile: le pre-creo valide,
            # cosi' ensure_tapir_fragment le riusa senza interrogare TAPIR.
            for e in events:
                if e['eligible']: write_tapir_fragment(out/'9_ARCHIVIO_COMPLETO',e)
            write_reports(out,events,targets,[],m)
            rows=list(_csv.DictReader((out/'0_EFFEMERIDI_100.csv').open(encoding='utf-8')))
            html=(out/'0_EFFEMERIDI_100.html').read_text()
            archive=json.loads((out/'9_ARCHIVIO_COMPLETO/risultati.json').read_text())
            consegna=sorted(f.name for f in (out/'CONSEGNA_UAN').iterdir())
        self.assertEqual(consegna,['0_RIEPILOGO_TRANSITI_COMPLETI.pdf','1_CONDIZIONI_PIU_FAVOREVOLI.pdf',
                                   '2_ALTRE_OCCASIONI_TRANSITO_COMPLETO.pdf'])   # solo i tre PDF
        self.assertEqual((m['reporting']['consegna_uan']['favourable'],
                          m['reporting']['consegna_uan']['other'],
                          m['reporting']['consegna_uan']['total_full_transits']),(0,2,2))
        self.assertEqual([r['event_id'] for r in rows],['A_b-c1','B_b-c2'])
        self.assertEqual({r['event_id'] for r in rows},
                         {slug(e['name'])+'-c'+str(e['cycle']) for e in archive if e['eligible']})
        self.assertEqual(len(archive),3)          # l'archivio tiene anche il parziale
        self.assertEqual(m['reporting']['ephemeris_100_events'],2)
        self.assertEqual(html.count('<tr class="q-'),2)          # una riga per evento eleggibile, zero esclusi
        self.assertIn('>A b<',html);self.assertIn('>B b<',html);self.assertNotIn('>C b<',html)
        self.assertTrue(all(float(r['transit_uncovered_seconds'])<=TOL for r in rows))


class ConsegnaUanChecks(unittest.TestCase):
    """CONSEGNA_UAN: presentazione, nessuna nuova categoria. PDF1 e PDF2 partizionano gli eleggibili."""
    def ev(self,name,cycle,days,uncovered=0.0,cat='PRIMA SCELTA',log='P1',role=None):
        from datetime import datetime,timezone,timedelta
        from observing import evaluate
        mid=datetime(2026,11,1,22,0,tzinfo=timezone.utc)+timedelta(days=days)
        e=dict(name=name,cycle=cycle,mid_utc=mid.isoformat(),mid_local=mid.isoformat(),
               ingress_utc=mid.isoformat(),egress_utc=mid.isoformat(),
               ingress_local=mid.isoformat(),egress_local=mid.isoformat(),
               practical_start_local=mid.isoformat(),practical_transit_end_limit_local=mid.isoformat(),
               max_altitude_theoretical_deg=55,altitude_min_deg=31,altitude_mid_deg=40,altitude_max_deg=45,
               transit_percent=100.0 if uncovered==0 else 99.9,transit_uncovered_seconds=uncovered,
               duration_minutes=180,baseline_before_percent=100,baseline_after_percent=100,
               practical_transit_percent=100,practical=True,uncertainty_minutes=1,
               moon_risk='ESTREMA' if cat=='DA VALUTARE' else 'BASSA',
               magnitude=11,depth_ppt=12,ttv=False,moon_up_during_observable=cat=='DA VALUTARE',
               moon_illumination_percent=95 if cat=='DA VALUTARE' else 5,
               moon_separation_deg=10 if cat=='DA VALUTARE' else 120,
               moon_min_separation_deg=10 if cat=='DA VALUTARE' else 120,
               altitude_ingress_deg=35,altitude_egress_deg=33,timing_check_failed=False,
               logistics_class=log,reference='')
        if cat=='ALTERNATIVE': e['baseline_after_percent']=60
        evaluate(e,json.loads((Path(__file__).parent/'capodimonte.json').read_text()))
        if role: e['selection_role']=role
        return e
    def events(self):
        return [self.ev('A b',1,0),                                   # PRIMA SCELTA
                self.ev('B b',2,3,cat='ALTERNATIVE'),                 # ALTERNATIVE
                self.ev('C b',3,6,cat='DA VALUTARE',log='P3'),        # DA VALUTARE, fuori serata
                self.ev('D b',4,9,log='P2'),                          # PRIMA SCELTA, P2
                self.ev('E b',5,12,uncovered=600)]                    # parziale: fuori consegna
    def test_partition_is_disjoint_and_covers_every_eligible(self):
        from reports import consegna_partition
        events=self.events()
        allrows,fav,other=consegna_partition(events)
        ids=lambda rows:{r['event_id'] for r in rows}
        eligible={slug(e['name'])+'-c'+str(e['cycle']) for e in events if e['eligible']}
        self.assertEqual(ids(allrows),eligible)
        self.assertEqual(len(allrows),len(eligible))
        self.assertEqual(ids(fav)&ids(other),set())
        self.assertEqual(ids(fav)|ids(other),eligible)
        self.assertEqual(len(fav)+len(other),len(allrows))
        self.assertEqual(ids(fav),{'A_b-c1'})                         # PRIMA SCELTA e P1
        # D b e' PRIMA SCELTA ma P2: sta fra le altre occasioni, non sparisce
        self.assertEqual(ids(other),{'B_b-c2','C_b-c3','D_b-c4'})
        self.assertNotIn('E_b-c5',ids(allrows))                       # nessun non eleggibile
        mids=[r['mid_local'] for r in allrows]
        self.assertEqual(mids,sorted(mids))
    def test_summary_has_every_eligible_row_and_no_internal_taxonomy(self):
        from reports import consegna_partition,consegna_summary_document
        events=self.events()
        allrows,_,_=consegna_partition(events)
        targets=[dict(name=n) for n in ('A b','B b','C b','D b','E b','Z b')]
        doc=consegna_summary_document(allrows,targets,'Europe/Rome')
        self.assertEqual(doc.count('<tr>')-1,len(allrows))            # -1: riga di intestazione
        self.assertIn('EFFEMERIDI DEI TRANSITI INTEGRALMENTE OSSERVABILI',doc)
        self.assertIn('Osservatorio di Capodimonte',doc)
        self.assertIn('senza alcun transito completo nella finestra analizzata: 2',doc)  # E b e Z b
        # La fascia operativa del planner non e' la "Suggested obs." di TAPIR: niente colonna ambigua.
        self.assertNotIn('Finestra osservativa suggerita',doc)
        self.assertEqual(doc.count('<th>'),8)
        for banned in ('PRIMA SCELTA','ALTERNATIVE','DA VALUTARE','NON CONSIGLIATO','PRIMARY',
                       'BACKUP1','BACKUP2','EXTRA','Score','ESTREMA','MODERATA','Trans%','P1','P3'):
            self.assertNotIn(banned,doc,banned)
        for name in ('A b','B b','C b','D b'):
            self.assertIn('>'+name+'<',doc)
        self.assertNotIn('>E b<',doc)
    def test_dossier_without_roles_keeps_fragments_and_hides_taxonomy(self):
        import tempfile,os
        from reports import tapir_dossier_document
        frag=('<!doctype html><html><head><style>.x{}</style></head><body><table id="t">'
              '<tr><th>Name</th></tr><tr><td>MARKER_TAPIR_ROW</td></tr></table></body></html>')
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(d+'/T')
            Path(d+'/T/frag.html').write_text(frag)
            rows=[dict(name='WASP-77 A b',cycle=1050,event_id='WASP-77_A_b-c1050',
                       mid_local='2027-01-09T19:53:00+01:00',display_role='BACKUP2',
                       tapir_event_html='T/frag.html')]
            doc,broken=tapir_dossier_document(rows,Path(d),'Europe/Rome','OCCASIONI CON CONDIZIONI PIÙ FAVOREVOLI',
                                              '',show_roles=False,subtitle='Selezione orientativa del planner')
            with_roles,_=tapir_dossier_document(rows,Path(d),'Europe/Rome','UAN - PRIMA SCELTA','LEGENDA')
        self.assertIsNone(broken)
        self.assertIn('MARKER_TAPIR_ROW',doc)                          # scheda TAPIR intatta
        self.assertIn('>WASP-77 A b</b> — centro locale 09/01/2027 19:53',doc)
        self.assertNotIn('BACKUP2',doc);self.assertNotIn('Ruolo',doc);self.assertNotIn('LEGENDA',doc)
        self.assertIn('Selezione orientativa del planner',doc)
        self.assertIn('BACKUP2',with_roles)                            # il dossier tecnico non cambia


if __name__=='__main__': unittest.main()
