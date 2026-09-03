"""Aggregate parsed messages into per-agent and per-model token totals."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from claude_session_telemetry.parse import COORDINATOR_AGENT_NAME, ParsedMessage


@dataclass(frozen=True)
class TokenTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    api_calls: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )


def token_totals(messages: Sequence[ParsedMessage]) -> TokenTotals:
    """Sum usage counters across every message that has a usage record."""
    input_tokens = output_tokens = cache_write = cache_read = api_calls = 0
    for message in messages:
        if message.usage is None:
            continue
        api_calls += 1
        input_tokens += message.usage.input_tokens
        output_tokens += message.usage.output_tokens
        cache_write += message.usage.cache_creation_input_tokens
        cache_read += message.usage.cache_read_input_tokens
    return TokenTotals(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
        api_calls=api_calls,
    )


def group_by(messages: Sequence[ParsedMessage], key: str) -> dict[str, list[ParsedMessage]]:
    groups: dict[str, list[ParsedMessage]] = {}
    for message in messages:
        value = getattr(message, key)
        if value is None:
            continue
        groups.setdefault(value, []).append(message)
    return groups


def per_agent_token_totals(messages: Sequence[ParsedMessage]) -> dict[str, TokenTotals]:
    return {
        agent: token_totals(agent_messages)
        for agent, agent_messages in group_by(messages, "agent_name").items()
    }


def per_model_token_totals(messages: Sequence[ParsedMessage]) -> dict[str, TokenTotals]:
    return {
        model: token_totals(model_messages)
        for model, model_messages in group_by(messages, "model").items()
    }


def coordinator_messages(messages: Sequence[ParsedMessage]) -> list[ParsedMessage]:
    return [m for m in messages if m.agent_name == COORDINATOR_AGENT_NAME]


def subagent_messages(messages: Sequence[ParsedMessage]) -> list[ParsedMessage]:
    return [m for m in messages if m.agent_name != COORDINATOR_AGENT_NAME]
