"""KPI functions from docs/plan.md section 4.

Per CLAUDE.md rule 4, every KPI is exactly one function here, each with its
own unit test whose expected value is computed by hand in the test.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from importlib import resources

from claude_session_telemetry.attribute import (
    TokenTotals,
    coordinator_messages,
    per_agent_token_totals,
    per_model_token_totals,
    token_totals,
)
from claude_session_telemetry.parse import COORDINATOR_AGENT_NAME, ParsedMessage

PriceTable = dict


def load_price_table() -> PriceTable:
    """Load the versioned price table bundled with the package."""
    with resources.files("claude_session_telemetry").joinpath("prices.toml").open("rb") as f:
        return tomllib.load(f)


# --- 4.2 Tokens and cost -----------------------------------------------------


def output_tokens(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).output_tokens


def fresh_input_tokens(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).input_tokens


def cache_write_tokens(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).cache_creation_input_tokens


def cache_read_tokens(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).cache_read_input_tokens


def total_tokens(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).total_tokens


def api_calls(messages: Sequence[ParsedMessage]) -> int:
    return token_totals(messages).api_calls


def cache_read_share(messages: Sequence[ParsedMessage]) -> float:
    totals = token_totals(messages)
    if totals.total_tokens == 0:
        return 0.0
    return totals.cache_read_input_tokens / totals.total_tokens


def tokens_by_model(messages: Sequence[ParsedMessage]) -> dict[str, TokenTotals]:
    return per_model_token_totals(messages)


def cost_usd(messages: Sequence[ParsedMessage], price_table: PriceTable) -> float:
    """Sum tokens x price per type per model, from the repo's price table."""
    rates_by_model = price_table.get("models", {})
    total = 0.0
    for model, totals in per_model_token_totals(messages).items():
        rates = rates_by_model.get(model)
        if rates is None:
            continue
        total += (
            totals.input_tokens * rates["input"]
            + totals.output_tokens * rates["output"]
            + totals.cache_creation_input_tokens * rates["cache_write"]
            + totals.cache_read_input_tokens * rates["cache_read"]
        ) / 1_000_000
    return total


# --- 4.3 Orchestration efficiency --------------------------------------------


def coordinator_share_of_tokens(messages: Sequence[ParsedMessage]) -> float:
    overall = token_totals(messages).total_tokens
    if overall == 0:
        return 0.0
    return token_totals(coordinator_messages(messages)).total_tokens / overall


def coordinator_share_of_cost(messages: Sequence[ParsedMessage], price_table: PriceTable) -> float:
    overall = cost_usd(messages, price_table)
    if overall == 0:
        return 0.0
    return cost_usd(coordinator_messages(messages), price_table) / overall


def _coordinator_context_sizes(messages: Sequence[ParsedMessage]) -> list[int]:
    return [
        m.usage.input_tokens + m.usage.cache_read_input_tokens
        for m in coordinator_messages(messages)
        if m.usage is not None
    ]


def mean_context_per_coordinator_call(messages: Sequence[ParsedMessage]) -> float:
    sizes = _coordinator_context_sizes(messages)
    return sum(sizes) / len(sizes) if sizes else 0.0


def peak_context_per_coordinator_call(messages: Sequence[ParsedMessage]) -> int:
    sizes = _coordinator_context_sizes(messages)
    return max(sizes) if sizes else 0


def agents_spawned(messages: Sequence[ParsedMessage]) -> int:
    return len({m.agent_name for m in messages} - {COORDINATOR_AGENT_NAME})


def calls_per_agent(messages: Sequence[ParsedMessage]) -> dict[str, int]:
    return {agent: totals.api_calls for agent, totals in per_agent_token_totals(messages).items()}


def coordinator_model(messages: Sequence[ParsedMessage]) -> str | None:
    """The most frequently used model among coordinator assistant messages."""
    models = [m.model for m in coordinator_messages(messages) if m.model is not None]
    if not models:
        return None
    counts: dict[str, int] = {}
    order: list[str] = []
    for model in models:
        if model not in counts:
            order.append(model)
        counts[model] = counts.get(model, 0) + 1
    return max(order, key=lambda model: counts[model])
