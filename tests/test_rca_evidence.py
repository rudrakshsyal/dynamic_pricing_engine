import json
from pathlib import Path
import tempfile
import unittest

import polars as pl

from src.rca_evidence import EvidenceStore, render_report
from src.rca_agent import validate_explanation


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data/processed'
        self.data.mkdir(parents=True)
        (self.root / 'notebooks').mkdir()
        params = {'yield_floor': 6000, 'quote_count_elasticity': {
            'method': 'lowess', 'x': [7000, 15000], 'y_normalized': [1, 1]},
            'conversion_elasticity': {'method': 'exponential', 'a': .2, 'b': .1, 'b_unit': 'per_$k'}}
        (self.data/'elasticity_params.json').write_text(json.dumps(params))
        (self.root/'notebooks/09_solver.ipynb').write_text(json.dumps({'cells': [
            {'cell_type': 'code', 'source': ['YIELD_FLOOR=7000\nYIELD_CEILING=15000\nY_MEDIAN=10784']}
        ]}))
        self.write_case()

    def write_case(self, capacity=0, price=15000, status='DNQ_zero_supply', stored_demand=0):
        pl.DataFrame({'date': ['2026-01-01'], 'od_supply': [float(capacity)],
            'forecasted_quotes': [100.], 'optimal_yield': [float(price)],
            'd_at_yield': [float(stored_demand)], 'solver_status': [status]}).with_columns(
                pl.col('date').str.to_date()).write_parquet(self.data/'optimal_yield_per_date.parquet')
        pl.DataFrame({'date': ['2026-01-01'], 'raw_leg_supply_fc': [10.+capacity],
            'program_live_legs_fc': [8.], 'non_program_live_legs_fc': [2.],
            'current_od_adjusted': [0.], 'od_supply': [float(capacity)]}).with_columns(
                pl.col('date').str.to_date()).write_parquet(self.data/'jan2026_od_supply.parquet')
        pl.DataFrame({'date': ['2026-01-01'], 'forecasted_quotes': [100.],
            'yhat_lower': [-1.], 'yhat_upper': [120.]}).with_columns(
                pl.col('date').str.to_date()).write_parquet(self.data/'jan2026_may2026_quotes_forecast.parquet')

    def test_dnq_marker_not_zero_model_demand(self):
        r = EvidenceStore(self.root).explain('2026-01-01')
        self.assertEqual(r['status'], 'ok')
        self.assertGreater(r['demand']['points']['selected']['expected_bookings'], 0)
        self.assertIn('DNQ marker', render_report(r))
        self.assertTrue(any('6000' in x for x in r['notes']))

    def test_all_solver_branches(self):
        import math
        for capacity, price, status in [(12, 7000, 'demand_below_floor'),
            (2, 15000, 'demand_above_ceiling'), (20*math.exp(-1), 10000, 'solved')]:
            with self.subTest(status=status):
                self.write_case(capacity, price, status, round(20*math.exp(-price/10000), 2))
                self.assertEqual(EvidenceStore(self.root).explain('2026-01-01')['status'], 'ok')

    def test_false_solved_price_flagged(self):
        self.write_case(7.35, 12000, 'solved', 6.02)
        r = EvidenceStore(self.root).explain('2026-01-01')
        self.assertEqual(r['status'], 'needs_review')
        self.assertFalse(r['checks']['selected_yield_matches_branch'])

    def test_missing_and_invalid_dates(self):
        store = EvidenceStore(self.root)
        self.assertEqual(store.explain('2026-06-01')['status'], 'not_found')
        with self.assertRaises(ValueError): store.explain('20260101')

    def test_mismatch_and_nonfinite(self):
        path = self.data/'jan2026_may2026_quotes_forecast.parquet'
        df = pl.read_parquet(path)
        df.with_columns(pl.lit(99.).alias('forecasted_quotes')).write_parquet(path)
        self.assertEqual(EvidenceStore(self.root).explain('2026-01-01')['status'], 'needs_review')
        df.with_columns(pl.lit(float('nan')).alias('forecasted_quotes')).write_parquet(path)
        with self.assertRaises(ValueError): EvidenceStore(self.root).explain('2026-01-01')

    def test_duplicate_date(self):
        path = self.data/'optimal_yield_per_date.parquet'
        df = pl.read_parquet(path)
        pl.concat([df, df]).write_parquet(path)
        with self.assertRaises(ValueError): EvidenceStore(self.root).explain('2026-01-01')

    def test_snapshot_does_not_change_after_load(self):
        store = EvidenceStore(self.root)
        self.write_case(12, 7000, 'demand_below_floor', 9.93)
        self.assertEqual(store.explain('2026-01-01')['recommendation']['solver_status'], 'DNQ_zero_supply')
        self.assertNotEqual(store.snapshot_id, EvidenceStore(self.root).snapshot_id)

    def test_bad_curve(self):
        path = self.data/'elasticity_params.json'
        p = json.loads(path.read_text())
        p['quote_count_elasticity']['x'] = [7000, 7000]
        path.write_text(json.dumps(p))
        with self.assertRaises(ValueError): EvidenceStore(self.root)

    def test_unverified_agent_claim_rejected(self):
        report = EvidenceStore(self.root).explain('2026-01-01')
        names = ['read_supply_evidence', 'read_demand_evidence', 'read_solver_evidence']
        payload = {'findings': [{'explanation': 'x', 'evidence_refs': ['invented']}], 'unresolved_questions': []}
        with self.assertRaises(ValueError): validate_explanation(payload, report, names)
        payload['findings'][0]['evidence_refs'] = ['recommendation.solver_status']
        with self.assertRaises(ValueError): validate_explanation(payload, report, [])
        payload['findings'] = [{'explanation': text, 'evidence_refs': ['recommendation.solver_status']} for text in ['Do not quote: no capacity remains.', 'No remaining capacity is forecast.', 'No selling price was selected.']]
        self.assertEqual(validate_explanation(payload, report, names), payload)


if __name__ == '__main__':
    unittest.main()
