import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from observing import coverage, intervals, logistic_bounds, classify

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
           'visibility_altitude_deg':20,'transit_operational_percent':90,'first_choice_min_percent':99.5,
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
        # v2.1 coverage: >=99.5 eligible PRIMA; 90-99.5 max ALTERNATIVE; <90 DA VALUTARE.
        self.assertEqual(classify(dict(e,transit_percent=99.4),p)[0],'ALTERNATIVE')
        self.assertEqual(classify(dict(e,transit_percent=89),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,baseline_after_percent=60),p)[0],'ALTERNATIVE')
        self.assertEqual(classify(dict(e,baseline_after_percent=40),p)[0],'DA VALUTARE')
        self.assertEqual(classify(dict(e,moon_risk='ALTA'),p)[0],'ALTERNATIVE')
        self.assertEqual(classify(dict(e,moon_risk='ESTREMA'),p)[0],'DA VALUTARE')
        self.assertIn('MOON_EXTREME',classify(dict(e,moon_risk='ESTREMA'),p)[2])
        # Moon risk: the audit v2.1 examples.
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
            self.assertEqual(len(list(out.glob('*.pdf'))),3)

class SelectionChecks(unittest.TestCase):
    def test_selection_diversifies_backups(self):
        from reports import compute_selection
        from datetime import datetime,timezone,timedelta
        p=dict(backup_preferred_separation_days=7,backup_fallback_separation_days=3)
        base=datetime(2026,11,1,22,0,tzinfo=timezone.utc)
        def ev(cycle,days,score,cat='PRIMA SCELTA'):
            mid=base+timedelta(days=days)
            return dict(name='X b',mid_utc=mid.isoformat(),mid_local=mid.isoformat(),category=cat,
                        quality_class=cat,score=score,cycle=cycle,logistics_class='P1')
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
        # Non-P1 events are excluded from the operational pool.
        self.assertNotIn('Y b',compute_selection([dict(ev(20,0,99.0),name='Y b',logistics_class='P3')],p))


if __name__=='__main__': unittest.main()
