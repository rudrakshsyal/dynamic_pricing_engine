import unittest
import numpy as np
import pandas as pd
from src.synthetic_data import simulate_daily, simulate_quotes, quote_distribution, evaluation_plan,TARGETS

class SyntheticTests(unittest.TestCase):
    def setUp(self):
        dates=pd.date_range('2024-01-01','2025-12-31');r=np.random.default_rng(7)
        self.source=pd.DataFrame({c:np.maximum(0,r.normal(.08,.02,len(dates))) if c.endswith('_rate') else r.integers(1,50,len(dates)) for c in TARGETS},index=dates)
        self.source['num_tails']=43
        self.dates=pd.date_range('2032-01-01','2034-12-31')
    def test_reproducible_and_distinct_seeds(self):
        a,_=simulate_daily(self.source,self.dates,42);b,_=simulate_daily(self.source,self.dates,42);c,_=simulate_daily(self.source,self.dates,43)
        pd.testing.assert_frame_equal(a,b);self.assertFalse(a.equals(c))
    def test_constraints_and_source_untouched(self):
        before=self.source.copy();a,_=simulate_daily(self.source,self.dates,42,'maintenance_stress')
        self.assertTrue((a[TARGETS]>=0).all().all());self.assertTrue((a[TARGETS[:4]].sum(axis=1)<=1+1e-12).all())
        self.assertTrue((a[TARGETS[4:]]%1==0).all().all());pd.testing.assert_frame_equal(before,self.source)
    def test_paired_stress_intervention(self):
        a,_=simulate_daily(self.source,self.dates,42);b,_=simulate_daily(self.source,self.dates,42,'demand_shift')
        pd.testing.assert_frame_equal(a.loc[:'2032-12-31'],b.loc[:'2032-12-31'])
        self.assertGreater(b.loc['2034','daily_quote_count'].mean(),a.loc['2034','daily_quote_count'].mean())
    def test_quotes_align_and_no_identifiers(self):
        q=pd.DataFrame({'quote_date':pd.to_datetime(['2024-01-01','2024-02-02']), 'dep_date':pd.to_datetime(['2024-01-11','2024-02-01']), 'yield_per_eft':[10000.,np.nan],'final_yield':[10000.,np.nan],'booked':[1,0]})
        daily,_=simulate_daily(self.source,self.dates[:10],42)
        result=simulate_quotes(daily,quote_distribution(q),42,'baseline')
        self.assertEqual(len(result),daily.daily_quote_count.sum());self.assertTrue((result.dep_date>=result.quote_date).all())
        self.assertTrue(result.is_synthetic.all());self.assertNotIn('QUOTE_LEG_ID',result.columns)
    def test_plan_separates_validation_test(self):
        plan=pd.DataFrame(evaluation_plan())
        self.assertEqual(len(plan),48)
        self.assertLess(plan[plan.split=='validation'].forecast_end.max(),plan[plan.split=='test'].forecast_start.min())
        self.assertTrue((pd.to_datetime(plan.origin)<pd.to_datetime(plan.forecast_start)).all())
        for (_,h),group in plan.groupby(['split','horizon']):
            self.assertTrue((pd.to_datetime(group.forecast_start).iloc[1:].to_numpy()>pd.to_datetime(group.forecast_end).iloc[:-1].to_numpy()).all())
    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):simulate_daily(self.source,self.dates,42,'invented')

if __name__=='__main__':unittest.main()
