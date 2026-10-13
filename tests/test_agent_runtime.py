import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from src.agent_runtime import run_agent
from src.rca_agent import run_validated, ExplanationValidationError

class RuntimeTests(unittest.TestCase):
    def test_repeated_clicks_share_live_loop(self):
        async def identify():
            await asyncio.sleep(0)
            return asyncio.get_running_loop()
        first=run_agent(identify())
        self.assertIs(first,run_agent(identify()))
        self.assertFalse(first.is_closed())

    def test_one_correction_preserves_context(self):
        def result(payload):
            return SimpleNamespace(final_output=SimpleNamespace(model_dump=lambda:payload),
                                   to_input_list=lambda:[{'role':'assistant','content':'prior evidence'}])
        def validate(p):
            if p=='bad':raise ExplanationValidationError('Too long')
            return p
        with patch('agents.Runner.run',new_callable=AsyncMock,side_effect=[result('bad'),result('good')]) as runner:
            payload,count=asyncio.run(run_validated(None,'initial',validate,5))
            self.assertEqual((payload,count),('good',1))
            self.assertEqual(runner.await_count,2)
            self.assertIn('prior evidence',str(runner.call_args.args[1]))

    def test_repair_is_bounded(self):
        result=SimpleNamespace(final_output=SimpleNamespace(model_dump=lambda:{}),to_input_list=lambda:[])
        def invalid(p):raise ExplanationValidationError('bad')
        with patch('agents.Runner.run',new_callable=AsyncMock,return_value=result) as runner:
            with self.assertRaises(ExplanationValidationError):asyncio.run(run_validated(None,'initial',invalid,5))
            self.assertEqual(runner.await_count,2)

    def test_provider_failure_not_retried(self):
        with patch('agents.Runner.run',new_callable=AsyncMock,side_effect=RuntimeError('offline')) as runner:
            with self.assertRaises(RuntimeError):asyncio.run(run_validated(None,'initial',lambda p:p,5))
            self.assertEqual(runner.await_count,1)
