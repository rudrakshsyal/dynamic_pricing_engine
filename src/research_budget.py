"""Reserve each request's maximum standard API cost before dispatch. No retries."""

from decimal import Decimal
import json
from pathlib import Path

COUNT_FIELDS = {
    "model",
    "input",
    "instructions",
    "tools",
    "tool_choice",
    "text",
    "reasoning",
    "parallel_tool_calls",
    "truncation",
}


class BudgetStop(RuntimeError):
    pass


class BudgetedResponses:
    def __init__(self, responses, out, dollars):
        self.responses = responses
        self.create_original = responses.create
        self.out = Path(out)
        self.cap = Decimal(str(dollars))
        if not self.cap.is_finite() or not 0 < self.cap <= Decimal("4"):
            raise ValueError("Budget must be positive and at most $4")
        self.charged = Decimal("0")
        self.entries = []
        self.stopped = False
        if (self.out / "budget.json").exists():
            raise ValueError("Existing budget ledger; use a fresh run")
        self.save()

    def save(self):
        (self.out / "budget.json").write_text(
            json.dumps(
                {
                    "cap_usd": str(self.cap),
                    "accounted_usd": str(self.charged),
                    "remaining_usd": str(self.cap - self.charged),
                    "pricing": "Standard GPT-5.5, uncached input $5/M, output $30/M; cached discounts ignored conservatively",
                    "stopped": self.stopped,
                    "requests": self.entries,
                },
                indent=2,
            )
        )

    async def create(self, **kwargs):
        if self.stopped:
            raise BudgetStop("Run stopped; no further requests")
        if kwargs.get("model") != "gpt-5.5":
            raise BudgetStop("Pricing guard supports gpt-5.5 only")
        if (
            kwargs.get("stream")
            or kwargs.get("previous_response_id")
            or kwargs.get("conversation")
        ):
            raise BudgetStop("Only independent nonstreamed requests supported")
        maximum = kwargs.get("max_output_tokens")
        if not isinstance(maximum, int) or not 1 <= maximum <= 4000:
            raise BudgetStop("Bounded output required")
        for tool in kwargs.get("tools", []):
            if tool.get("type") != "function":
                raise BudgetStop("Hosted billable tools not permitted")
        kwargs["service_tier"] = "default"
        count = await self.responses.input_tokens.count(
            **{k: v for k, v in kwargs.items() if k in COUNT_FIELDS}
        )
        n = count.input_tokens
        if not isinstance(n, int) or not 0 <= n <= 272000:
            raise BudgetStop("Invalid count or long-context pricing unsupported")
        reserve = (Decimal(n) * 5 + Decimal(maximum) * 30) / 1000000
        if self.charged + reserve > self.cap:
            self.stopped = True
            self.save()
            raise BudgetStop("Next request cannot fit remaining budget")
        entry = {
            "request": len(self.entries) + 1,
            "input_tokens_counted": n,
            "max_output_tokens": maximum,
            "reserved_usd": str(reserve),
            "status": "reserved",
        }
        self.entries.append(entry)
        self.charged += reserve
        self.save()
        # Retain only visible action/message payloads, never API credentials or hidden reasoning.
        try:
            response = await self.create_original(**kwargs)
            u = response.usage
            if u is None:
                raise BudgetStop("Usage unavailable; reservation retained")
            cost = (
                Decimal(u.input_tokens) * 5 + Decimal(u.output_tokens) * 30
            ) / 1000000
            if cost > reserve:
                raise BudgetStop("Reported usage exceeded reservation; stop for review")
            self.charged += cost - reserve
            entry.update(
                status="completed",
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                accounted_usd=str(cost),
                response_id=response.id,
            )
            actions = []
            for item in response.output:
                if item.type in ("function_call", "message"):
                    actions.append(item.model_dump())
            (self.out / f"response_{entry['request']:03d}.json").write_text(
                json.dumps(
                    {
                        "id": response.id,
                        "status": response.status,
                        "visible_output": actions,
                    },
                    indent=2,
                )
            )
            self.save()
            print(
                f"API response {len(self.entries)}: accounted ${self.charged:.4f} / ${self.cap}",
                flush=True,
            )
            return response
        except BaseException as exc:
            entry.update(status="uncertain_or_failed", error_type=type(exc).__name__)
            self.stopped = True
            self.save()
            raise
