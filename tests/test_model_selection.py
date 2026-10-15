import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from src.model_selection import Experiment, COMPONENTS, CANDIDATES, ORIGINS, FINAL_ORIGIN, HORIZON, features, forecast
from src.model_selection_agent import make_agent

class SelectionTests(unittest.TestCase):
    def test_temporal_separation(self):
        self.assertLess(max(pd.Timestamp(d)+pd.Timedelta(days=HORIZON) for d in ORIGINS),pd.Timestamp(FINAL_ORIGIN)+pd.Timedelta(days=1))
    def test_past_features(self):
        f=features(range(28),pd.Timestamp('2025-01-01'))
        self.assertEqual(f[:4],[27,21,14,0])
        self.assertEqual(f[4],24)
        with self.assertRaises(ValueError):features(range(27),pd.Timestamp('2025-01-01'))
    def test_all_forecasters(self):
        idx=pd.date_range('2024-01-01',periods=400)
        train=pd.DataFrame({'aog_rate':.1+.03*np.sin(np.arange(400)/7)},index=idx)
        before=train.copy(deep=True)
        dates=pd.date_range(idx[-1]+pd.Timedelta(days=1),periods=5)
        current=pd.DataFrame({'aog_rate':[.1]*5},index=dates)
        for model in CANDIDATES:
            with self.subTest(model=model):
                values=forecast(train,dates,'aog_rate',model,current)
                self.assertEqual(len(values),5)
                self.assertTrue(np.isfinite(values).all())
                self.assertTrue(((values>=0)&(values<=1)).all())
        pd.testing.assert_frame_equal(train,before)
    def test_freeze_guards(self):
        e=Experiment.__new__(Experiment);e.selections=None;e.scores={};e.audit=[];e.manifest={}
        with self.assertRaises(ValueError):e.final_test()
        with self.assertRaises(ValueError):e.freeze_selection()
        e.scores={c:{'winner':'current','candidates':[{'failures':[]}]} for c in COMPONENTS}
        e.scores[COMPONENTS[0]]['candidates'][0]['failures']=['failed']
        with self.assertRaises(ValueError):e.freeze_selection()
        e.scores[COMPONENTS[0]]['candidates'][0]['failures']=[]
        with tempfile.TemporaryDirectory() as d:
            e.out=Path(d);e.freeze_selection()
            self.assertTrue((e.out/'frozen_selection.json').exists())
            with self.assertRaises(ValueError):e.evaluate_component(COMPONENTS[0])
    def test_maturity_and_cutoff(self):
        e=Experiment.__new__(Experiment)
        e.daily=pd.DataFrame({'x':1},index=pd.date_range('2024-01-01','2025-11-30'))
        e.quotes=pd.DataFrame({'quote_date':pd.to_datetime(['2025-10-01','2025-10-02','2025-11-02']), 'dep_date':pd.to_datetime(['2025-10-05','2025-12-01','2025-11-05'])})
        train,actual,mature,hold=e.split(FINAL_ORIGIN)
        self.assertEqual(train.index.max(),pd.Timestamp(FINAL_ORIGIN))
        self.assertEqual(len(actual),28);self.assertEqual(len(mature),1);self.assertEqual(len(hold),1)
    def test_agent_has_only_validation_tools(self):
        agent=make_agent(None,'not-called')
        self.assertEqual({t.name for t in agent.tools},{'evaluate_component','freeze_selection'})

if __name__=='__main__':unittest.main()
