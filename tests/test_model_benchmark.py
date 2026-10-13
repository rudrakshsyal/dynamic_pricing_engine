import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.model_benchmark import metrics, validate_llm, TARGETS, GRID, llm_forecast, make_request, solve

class BenchmarkTests(unittest.TestCase):
    def bundle(self):
        return {'daily':[{'date':'2025-07-01',**{c:.1 if c.endswith('_rate') else 10 for c in TARGETS}}],
                'curve':[{'yield_usd':p,'quote_multiplier':1.,'conversion_probability':.05} for p in GRID]}

    def test_metrics_zeros_and_nonfinite(self):
        self.assertIsNone(metrics([0,0],[1,0])['wape'])
        self.assertEqual(metrics([1,3],[2,2])['mae'],1)
        with self.assertRaises(ValueError):metrics([1],[np.nan])

    def test_llm_schema_validation(self):
        request={'forecast_dates':['2025-07-01']}
        df,curve=validate_llm(self.bundle(),request)
        self.assertEqual(len(df),1)
        self.assertEqual(np.interp(10784,curve['x'],curve['multiplier']),1)
        for change in ['date','rate','negative','nan','grid']:
            b=self.bundle()
            if change=='date':b['daily'][0]['date']='2025-07-02'
            if change=='rate':b['daily'][0]['aog_rate']=2
            if change=='negative':b['daily'][0]['daily_quote_count']=-1
            if change=='nan':b['curve'][0]['conversion_probability']=float('nan')
            if change=='grid':b['curve'].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):validate_llm(b,request)

    def test_no_paid_calls_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp, patch('openai.OpenAI') as client:
            with self.assertRaises(ValueError):llm_forecast({'forecast_dates':[]},Path(tmp),'test',False,1000)
            client.assert_not_called()

    def test_request_does_not_contain_holdout(self):
        train=pd.DataFrame({c:[.1,.2] for c in TARGETS},index=pd.to_datetime(['2025-06-29','2025-06-30']))
        train.index.name='date'
        # Binning is independent; ensure prompt receives history only and future dates without labels.
        qc=pd.Series([10,11,12],index=[7250,7750,8250]);cv=pd.DataFrame({'mean':[.1,.08,.05],'size':[20]*3},index=[7500,8500,9500])
        with patch('src.model_benchmark.curve_bins',return_value=(qc,cv)):
            r=make_request(train,pd.date_range('2025-07-01',periods=2),None)
        self.assertEqual(max(x['date'] for x in r['daily_history']),'2025-06-30')
        self.assertEqual(r['forecast_dates'],['2025-07-01','2025-07-02'])
        self.assertNotIn('actual',r)

    @unittest.skipUnless(importlib.util.find_spec('scipy'),'scipy required')
    def test_solver_all_branches(self):
        c={'x':GRID,'multiplier':[1.]*len(GRID),'a':1.,'b':.1}
        self.assertEqual(solve(c,100,0),(None,'DNQ_zero_supply'))
        self.assertEqual(solve(c,100,90)[1],'demand_below_floor')
        self.assertEqual(solve(c,100,1)[1],'demand_above_ceiling')
        price,status=solve(c,100,30)
        self.assertEqual(status,'solved')
        self.assertAlmostEqual(100*np.exp(-.1*price/1000),30,places=2)

    def test_mocked_llm_response_cached_and_reused(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from src.model_benchmark import ForecastBundle
        request={'forecast_dates':['2025-07-01']}
        response=SimpleNamespace(id='fake-response',usage=SimpleNamespace(model_dump=lambda:{'input_tokens':100,'output_tokens':50}),
                                 output_parsed=ForecastBundle(**self.bundle()))
        with tempfile.TemporaryDirectory() as tmp, patch('openai.OpenAI') as client:
            client.return_value.__enter__.return_value.responses.parse.return_value=response
            first=llm_forecast(request,Path(tmp),'test',True,1000)
            self.assertEqual(first[2]['usage']['input_tokens'],100)
            client.assert_called_once()
            client.reset_mock()
            second=llm_forecast(request,Path(tmp),'test',False,1000)
            client.assert_not_called()
            self.assertEqual(second[2]['response_id'],'fake-response')
