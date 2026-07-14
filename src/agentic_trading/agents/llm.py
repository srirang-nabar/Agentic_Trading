"""LLM trading agents (Stage 3).

The harness turns a polled AgentView into a rendered prompt, sends it to an
LLM over an OpenAI-compatible API, parses the reply through a strict
pydantic schema, validates it semantically against the trader's own state,
and converts it to an engine action. Invalid replies get error feedback and
a bounded number of retries (then a forced pass).

Guarantees the Stage 3 gate tests enforce:
- Full capture: exactly one JSONL-able record per API call — rendered
  messages, raw response, parsed decision, error, model ID, temperature,
  prompt-template hash, token usage, timestamp. A session missing a record
  is invalid by construction (the recorder counts calls).
- No malformed model output can crash the harness or corrupt the book:
  parsing is total, semantic validation precedes submission, and the engine
  itself rejects anything that slips through.
- Determinism given responses: the agent adds no randomness of its own, so
  a session replays bit-exactly from its event log regardless of the model.

API access: base URL and key come from the environment only
(TRADING_LLM_BASE_URL, TRADING_LLM_API_KEY) — never from files.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from agentic_trading.exchange import Side
from agentic_trading.runner import Action, AgentView, CancelAction, SubmitAction

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


# ---- decision schema (strict) ----


class OrderDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["bid", "ask", "cancel", "pass"]
    price: int | None = None

    @model_validator(mode="after")
    def _price_matches_action(self) -> "OrderDecision":
        if self.action in ("bid", "ask") and self.price is None:
            raise ValueError("a price is required for bid/ask")
        if self.action in ("cancel", "pass") and self.price is not None:
            raise ValueError("price must be null for cancel/pass")
        return self


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_decision(text: str) -> tuple[OrderDecision | None, str | None]:
    """Total parser: returns (decision, None) or (None, error message)."""
    candidate = text.strip()
    fence = _FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()
    try:
        obj = json.loads(candidate)
    except (json.JSONDecodeError, RecursionError):
        return None, "reply was not a single valid JSON object"
    if not isinstance(obj, dict):
        return None, "reply must be a JSON object, not a list or scalar"
    try:
        return OrderDecision.model_validate(obj), None
    except ValidationError as exc:
        first = exc.errors()[0]
        return None, f"invalid order: {first['loc']}: {first['msg']}"


def validate_decision(
    decision: OrderDecision, view: AgentView, *, max_price: int
) -> str | None:
    """Semantic check against the trader's own state; None means valid."""
    if decision.action == "bid":
        if not view.remaining_values:
            return "you cannot buy any more units this period"
        if not (1 <= decision.price <= max_price):
            return f"price must be a whole number between 1 and {max_price}"
        if decision.price > view.cash_available:
            return f"you only have {view.cash_available} francs available"
    elif decision.action == "ask":
        if not view.remaining_costs:
            return "you cannot sell any more units this period"
        if not (1 <= decision.price <= max_price):
            return f"price must be a whole number between 1 and {max_price}"
        if view.inventory_available < 1:
            return "you have no unit available to sell"
    elif decision.action == "cancel":
        if not view.open_orders:
            return "you have no resting offer to cancel"
    return None


def decision_to_action(decision: OrderDecision, view: AgentView) -> Action:
    if decision.action == "bid":
        return SubmitAction(side=Side.BUY, price=decision.price)
    if decision.action == "ask":
        return SubmitAction(side=Side.SELL, price=decision.price)
    if decision.action == "cancel":
        return CancelAction(order_id=view.open_orders[0][0])
    return None


# ---- transports ----


@dataclass(frozen=True)
class ChatResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int


class ChatClient(Protocol):
    call_count: int

    def complete(
        self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int
    ) -> ChatResponse: ...


class OpenAICompatClient:
    """Any OpenAI-compatible endpoint: vLLM, Ollama, or a hosted provider."""

    def __init__(self, model: str, *, base_url: str | None = None, api_key: str | None = None):
        import openai

        self.model = model
        self.call_count = 0
        self._client = openai.OpenAI(
            base_url=base_url or os.environ["TRADING_LLM_BASE_URL"],
            api_key=api_key or os.environ.get("TRADING_LLM_API_KEY", "none"),
            timeout=120,
            max_retries=3,
        )

    def complete(self, messages, *, temperature, max_tokens) -> ChatResponse:
        self.call_count += 1
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = response.usage
        return ChatResponse(
            text=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )


class AnthropicChatClient:
    """Frontier transport via the official Anthropic SDK (Stage 4 frontier cell).

    Restricted to models that accept an explicit temperature (Haiku 4.5,
    Sonnet 4.6) — the pre-registered T=0.7 cannot be expressed on models that
    reject sampling parameters (Opus 4.7+/Sonnet 5), which are also outside
    the budget projection anyway. Reads ANTHROPIC_API_KEY from the
    environment only.
    """

    def __init__(self, model: str):
        import anthropic

        self.model = model
        self.call_count = 0
        self._client = anthropic.Anthropic(timeout=120, max_retries=3)

    def complete(self, messages, *, temperature, max_tokens) -> ChatResponse:
        self.call_count += 1
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        chat = [m for m in messages if m["role"] != "system"]
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=chat,
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return ChatResponse(
            text=text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )


class ScriptedClient:
    """Test transport: replays a fixed list of responses (then passes)."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.call_count = 0

    def complete(self, messages, *, temperature, max_tokens) -> ChatResponse:
        self.call_count += 1
        text = self.responses.pop(0) if self.responses else '{"action": "pass", "price": null}'
        return ChatResponse(text=text, prompt_tokens=len(str(messages)) // 4,
                            completion_tokens=len(text) // 4)


# ---- full-capture recorder ----


class SessionRecorder:
    """Accumulates one record per LLM call; attached to the session log."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, entry: dict[str, Any]) -> None:
        self.records.append(entry)

    def validity_stats(self) -> dict[str, Any]:
        polls: dict[tuple, dict] = {}
        for r in self.records:
            key = (r["trader_id"], r["period"], r["step"])
            poll = polls.setdefault(key, {"attempts": 0, "resolved": False})
            poll["attempts"] += 1
            if r["error"] is None:
                poll["resolved"] = True
        n_polls = len(polls)
        resolved = sum(1 for p in polls.values() if p["resolved"])
        first_try = sum(1 for p in polls.values() if p["attempts"] == 1 and p["resolved"])
        return {
            "n_llm_polls": n_polls,
            "n_llm_calls": len(self.records),
            "validity_rate": resolved / n_polls if n_polls else None,
            "first_attempt_rate": first_try / n_polls if n_polls else None,
            "forced_passes": n_polls - resolved,
        }


# ---- prompt templates ----


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    text: str
    sha256: str

    @classmethod
    def load(cls, name: str) -> "PromptTemplate":
        path = PROMPTS_DIR / f"{name}.md"
        data = path.read_bytes()
        return cls(name=name, text=data.decode(), sha256=hashlib.sha256(data).hexdigest())


def render_role_block(view: AgentView, persona: str = "neutral") -> str:
    lines = [PERSONAS[persona]] if PERSONAS[persona] else []
    if view.remaining_values:
        lines.append(
            f"Your role: you can still buy {len(view.remaining_values)} unit(s) this "
            f"period. When you buy your next unit, you will redeem it for "
            f"{view.remaining_values[0]} francs (profit = redemption value minus the "
            f"price you paid). You have {view.cash_available} francs available."
        )
    if view.remaining_costs:
        lines.append(
            f"Your role: you can still sell {len(view.remaining_costs)} unit(s) this "
            f"period. Producing your next unit costs you {view.remaining_costs[0]} "
            f"francs (profit = the price you receive minus that cost)."
        )
    if not lines:
        lines.append("You have no units left to trade this period.")
    return "\n".join(lines)


def render_state(view: AgentView, feedback: str | None, memory: str = "none") -> str:
    best_bid = view.best_bid if view.best_bid is not None else "none"
    best_ask = view.best_ask if view.best_ask is not None else "none"
    last = view.last_trade_price if view.last_trade_price is not None else "none yet"
    open_orders = (
        "; ".join(f"{side} at {price} (id {oid})" for oid, side, price in view.open_orders)
        or "none"
    )
    memory_line = ""
    if memory == "recent" and view.recent_trade_prices:
        memory_line = (
            "Recent trade prices, oldest first: "
            + ", ".join(str(p) for p in view.recent_trade_prices) + ".\n"
        )
    text = (
        f"Trading period {view.period}, turn {view.step + 1}.\n"
        f"Highest standing bid: {best_bid}. Lowest standing ask: {best_ask}.\n"
        f"Most recent trade price: {last}.\n"
        + memory_line
        + f"Your resting offers: {open_orders}.\n"
        f"Your reply (JSON only):"
    )
    if feedback:
        text = f"Your previous reply was invalid: {feedback}. Try again.\n\n" + text
    return text


# ---- the agent ----


# Exploratory persona variants (HYPOTHESES A2.v) — appended to the role block.
PERSONAS = {
    "neutral": "",
    "risk_averse": (
        "You are a cautious trader: you strongly prefer safe, certain profits "
        "and avoid any trade that could reduce your profit."
    ),
    "aggressive": (
        "You are an aggressive trader: you push to trade as often as possible "
        "and accept slim profit margins to get deals done."
    ),
}


@dataclass
class LLMTraderConfig:
    model: str
    template: str
    temperature: float = 0.7
    max_tokens: int = 80
    max_price: int = 200
    k_retries: int = 3
    persona: str = "neutral"
    memory: str = "none"  # "none" (best quotes + last trade) | "recent" (adds price list)

    def __post_init__(self) -> None:
        if self.persona not in PERSONAS:
            raise ValueError(f"unknown persona: {self.persona!r}")
        if self.memory not in ("none", "recent"):
            raise ValueError(f"unknown memory window: {self.memory!r}")


class LLMTrader:
    def __init__(
        self,
        trader_id: str,
        client: ChatClient,
        recorder: SessionRecorder,
        config: LLMTraderConfig,
    ):
        self.trader_id = trader_id
        self.client = client
        self.recorder = recorder
        self.config = config
        self.template = PromptTemplate.load(config.template)

    def act(self, view: AgentView) -> Action:
        feedback: str | None = None
        for attempt in range(self.config.k_retries + 1):
            system = self.template.text.format(
                role_block=render_role_block(view, self.config.persona),
                max_price=self.config.max_price,
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": render_state(view, feedback, self.config.memory)},
            ]
            try:
                response = self.client.complete(
                    messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
            except Exception as exc:  # transport fault: record, then pass
                self._record(view, attempt, messages, None, f"transport error: {exc}")
                return None

            decision, error = parse_decision(response.text)
            if decision is not None and error is None:
                error = validate_decision(decision, view, max_price=self.config.max_price)
            self._record(view, attempt, messages, response, error,
                         decision if error is None else None)
            if error is None:
                return decision_to_action(decision, view)
            feedback = error
        return None  # retries exhausted: forced pass

    def _record(self, view, attempt, messages, response, error, decision=None) -> None:
        self.recorder.record(
            {
                "kind": "llm_call",
                "trader_id": self.trader_id,
                "period": view.period,
                "step": view.step,
                "attempt": attempt,
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "template": self.template.name,
                "template_sha256": self.template.sha256,
                "messages": messages,
                "raw_response": response.text if response else None,
                "prompt_tokens": response.prompt_tokens if response else 0,
                "completion_tokens": response.completion_tokens if response else 0,
                "parsed": decision.model_dump() if decision else None,
                "error": error,
                "ts": time.time(),
            }
        )


# ---- contamination scan (in-session recognition, per protocol item c) ----

RECOGNITION_PATTERNS = (
    "vernon smith", "gode", "sunder", "double auction", "experimental economics",
    "zero intelligence", "zero-intelligence", "induced value", "induced-value",
    "smith 1962", "laboratory experiment", "classic experiment",
)


def scan_recognition(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag raw responses that verbalize recognition of the experimental design."""
    flags = []
    for r in records:
        text = (r.get("raw_response") or "").lower()
        hits = [p for p in RECOGNITION_PATTERNS if p in text]
        if hits:
            flags.append(
                {"trader_id": r["trader_id"], "period": r["period"], "step": r["step"],
                 "attempt": r["attempt"], "patterns": hits}
            )
    return flags
