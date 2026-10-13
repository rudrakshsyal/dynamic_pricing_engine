"""SDK wiring tests use a mocked runner: no API requests or credentials needed."""
import asyncio
import importlib.util
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.rca_agent import explain_with_agent


@unittest.skipUnless(importlib.util.find_spec('agents'), 'Optional openai-agents SDK not installed')
class AgentWiringTests(unittest.TestCase):
    def test_sdk_tools_and_structured_result(self):
        report = {'status': 'ok', 'departure_date': '2026-01-01', 'snapshot_id': 'test',
                  'facts': {'recommendation.solver_status': 'DNQ_zero_supply'}, 'notes': []}
        async def fake_run(agent, prompt, **kwargs):
            self.assertEqual(kwargs['max_turns'], 8)
            self.assertTrue(kwargs['run_config'].tracing_disabled)
            self.assertEqual(len(agent.tools), 3)
            from agents.tool_context import ToolContext
            for tool in agent.tools:
                self.assertEqual(tool.params_json_schema['properties'], {})
                result = await tool.on_invoke_tool(ToolContext(context=None, tool_name=tool.name, tool_call_id='test', tool_arguments='{}'), '{}')
                self.assertIn('test', result)
            result = agent.output_type(findings=[{'explanation': text, 'evidence_refs': ['recommendation.solver_status']} for text in ['Do not quote: no capacity remains.', 'No remaining capacity is forecast.', 'No selling price was selected.']], unresolved_questions=[])
            return SimpleNamespace(final_output=result)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-not-a-real-key'}), patch('agents.Runner.run', side_effect=fake_run):
            result = asyncio.run(explain_with_agent(report, 'test-model'))
        self.assertEqual(len(result['tool_calls']), 3)

    def test_inconsistent_evidence_never_calls_runner(self):
        with patch('agents.Runner.run') as runner:
            with self.assertRaises(ValueError):
                asyncio.run(explain_with_agent({'status': 'needs_review'}, 'test-model'))
            runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class BriefValidationTests(unittest.TestCase):
    def test_all_outcomes_and_known_failures(self):
        import copy
        from src.rca_agent import validate_explanation, ExplanationValidationError
        tools = ['read_supply_evidence', 'read_demand_evidence', 'read_solver_evidence']
        for status, sentence in [('solved', 'Forecast demand matches remaining capacity.'),
                                 ('DNQ_zero_supply', 'Do not quote: no capacity remains.'),
                                 ('demand_below_floor', 'The price floor applies because demand is below capacity.'),
                                 ('demand_above_ceiling', 'The price ceiling applies because demand still exceeds capacity.')]:
            report = {'facts': {'recommendation.solver_status': status, 'supply.remaining': 1.22, 'demand.bookings': 1.22}}
            payload = {'findings': [
                {'explanation': sentence, 'evidence_refs': ['recommendation.solver_status']},
                {'explanation': 'Remaining capacity is 1.22 legs.', 'evidence_refs': ['supply.remaining']},
                {'explanation': 'Forecast demand is 1.22 bookings.', 'evidence_refs': ['demand.bookings']}], 'unresolved_questions': []}
            with self.subTest(status=status):
                self.assertEqual(validate_explanation(payload, report, tools), payload)
            for bad in ['Capacity is supply.remaining.', 'Remaining capacity is 1.22 hours.',
                        'Remaining capacity is 9.99 legs.', 'Guaranteed bookings fill capacity.', 'word ' * 19]:
                mutated = copy.deepcopy(payload)
                mutated['findings'][1]['explanation'] = bad
                with self.subTest(status=status, bad=bad), self.assertRaises(ExplanationValidationError):
                    validate_explanation(mutated, report, tools)
            mutated = copy.deepcopy(payload)
            mutated['findings'][0]['explanation'] = 'A different price was selected.'
            with self.assertRaises(ExplanationValidationError):
                validate_explanation(mutated, report, tools)
