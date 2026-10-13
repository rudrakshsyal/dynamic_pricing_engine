import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None
import test_rca_evidence as fixtures

@unittest.skipIf(AppTest is None, 'optional Streamlit dependency absent')
class AppTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        env = patch.dict(os.environ, {'DPE_REPO_ROOT': str(self.fixture.root), 'OPENAI_API_KEY': 'test-only'})
        env.start()
        self.addCleanup(env.stop)
        self.mock = AsyncMock(return_value={'explanation': {'findings': [
            {'explanation': 'No remaining capacity is forecast.', 'evidence_refs': ['recommendation.od_supply']}],
            'unresolved_questions': []}, 'tool_calls': ['read_supply_evidence', 'read_demand_evidence', 'read_solver_evidence']})
        patcher = patch('src.rca_agent.explain_with_agent', self.mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20)

    def test_no_key_and_dnq(self):
        os.environ.pop('OPENAI_API_KEY')
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.button[0].disabled)
        self.assertEqual(self.app.metric[0].value, 'Do not quote')
        self.mock.assert_not_called()

    def test_on_demand_and_model_change(self):
        self.app.run()
        self.assertFalse(self.app.exception)
        self.mock.assert_not_called()
        self.app.button[0].click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.mock.await_count, 1)
        self.assertIn('narrative', self.app.session_state)
        self.app.run()
        self.assertEqual(self.mock.await_count, 1)
        self.app.text_input[0].set_value('different-model').run()
        self.assertNotIn('narrative', self.app.session_state)
        self.assertEqual(self.mock.await_count, 1)

    def test_error_is_sanitized(self):
        self.mock.side_effect = RuntimeError('SECRET_PROVIDER_ERROR')
        self.app.run().button[0].click().run()
        self.assertFalse(self.app.exception)
        self.assertNotIn('SECRET_PROVIDER_ERROR', self.app.error[0].value)
        self.assertIn('RuntimeError', self.app.error[0].value)

    def test_failed_checks_block_agent(self):
        self.fixture.write_case(7.35, 12000, 'solved', 6.02)
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertEqual(len(self.app.button), 0)
        self.mock.assert_not_called()

    def test_validation_error_explains_rejection(self):
        from src.rca_agent import ExplanationValidationError
        self.mock.side_effect = ExplanationValidationError("The AI cited missing or unrecognized evidence, so its explanation was withheld. Click Explain to retry.")
        self.app.run().button[0].click().run()
        self.assertIn("unrecognized evidence", self.app.error[0].value)
        self.assertNotIn("billing", self.app.error[0].value)
        self.assertNotIn("narrative", self.app.session_state)
