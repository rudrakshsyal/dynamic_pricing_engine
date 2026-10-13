import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from src.rca_chat import ask_about_date, validate_answer
from src.rca_agent import ExplanationValidationError

class ChatTests(unittest.TestCase):
    def test_validation(self):
        report = {'facts': {'supply.od_supply': 1.22}}
        payload = {'status':'answered', 'answer':'Remaining capacity is 1.22 legs.', 'evidence_refs':['supply.od_supply'], 'data_team_question':''}
        self.assertEqual(validate_answer(payload, report, True), payload)
        for override in [{'evidence_refs':['invented']}, {'evidence_refs':[]}, {'answer':'word '*81}, {'status':'needs_data'}]:
            with self.assertRaises(ExplanationValidationError):
                validate_answer({**payload, **override}, report, True)
        with self.assertRaises(ExplanationValidationError): validate_answer(payload, report, False)

    def test_tool_and_bounded_history(self):
        report={'status':'ok','departure_date':'2026-01-05','snapshot_id':'test','facts':{'supply.od_supply':1.22},'notes':[]}
        async def runner(agent, prompt, **kwargs):
            import json
            from agents.tool_context import ToolContext
            self.assertEqual(len(json.loads(prompt)['recent_conversation']),4)
            self.assertEqual(len(agent.tools),1)
            tool=agent.tools[0]
            self.assertEqual(tool.params_json_schema['properties'],{})
            result=await tool.on_invoke_tool(ToolContext(context=None,tool_name=tool.name,tool_call_id='test',tool_arguments='{}'),'{}')
            self.assertIn('2026-01-05',result)
            self.assertTrue(kwargs['run_config'].tracing_disabled)
            return SimpleNamespace(final_output=agent.output_type(status='answered',answer='Remaining capacity is 1.22 legs.',evidence_refs=['supply.od_supply'],data_team_question=''))
        history=[{'question':'Why?', 'response':{'answer':'Previous answer'}}]*6
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake'}), patch('agents.Runner.run',side_effect=runner):
            result=asyncio.run(ask_about_date(report,'How much capacity?',history,'test'))
        self.assertEqual(result['snapshot_id'],'test')

    def test_invalid_evidence_blocks_call(self):
        with patch('agents.Runner.run') as runner:
            with self.assertRaises(ExplanationValidationError):
                asyncio.run(ask_about_date({'status':'needs_review'},'Why?',[],'test'))
            runner.assert_not_called()
