import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from src.research_budget import BudgetedResponses, BudgetStop


class BudgetTests(unittest.TestCase):
    def setup_guard(self, budget=4, count=1000, fail=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calls = 0

        async def tokens(**kw):
            return SimpleNamespace(input_tokens=count)

        async def create(**kw):
            self.calls += 1
            if fail:
                raise TimeoutError()
            self.assertEqual(kw["service_tier"], "default")
            return SimpleNamespace(
                usage=SimpleNamespace(input_tokens=count, output_tokens=100),
                id="synthetic",
                output=[],
                status="completed",
            )

        return BudgetedResponses(
            SimpleNamespace(create=create, input_tokens=SimpleNamespace(count=tokens)),
            Path(tmp.name),
            budget,
        )

    def call(self, g):
        return asyncio.run(
            g.create(model="gpt-5.5", max_output_tokens=1000, tools=[], input="test")
        )

    def test_blocks_before_spending(self):
        g = self.setup_guard(0.001)
        with self.assertRaises(BudgetStop):
            self.call(g)
        self.assertEqual(self.calls, 0)

    def test_reconciles_actual(self):
        g = self.setup_guard()
        self.call(g)
        self.assertEqual(float(g.charged), 0.008)

    def test_failed_request_keeps_reservation_and_stops(self):
        g = self.setup_guard(fail=True)
        with self.assertRaises(TimeoutError):
            self.call(g)
        self.assertEqual(float(g.charged), 0.035)
        with self.assertRaises(BudgetStop):
            self.call(g)
        self.assertEqual(self.calls, 1)

    def test_long_context_blocked(self):
        g = self.setup_guard(count=272001)
        with self.assertRaises(BudgetStop):
            self.call(g)
        self.assertEqual(self.calls, 0)

    def test_wrong_model_blocked(self):
        g = self.setup_guard()
        with self.assertRaises(BudgetStop):
            asyncio.run(g.create(model="other", max_output_tokens=1000))
        self.assertEqual(self.calls, 0)

    def test_cap_cannot_exceed_four(self):
        with self.assertRaises(ValueError):
            self.setup_guard(4.01)
