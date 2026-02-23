from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.query import StepResult, ActionTaken

logger = logging.getLogger(__name__)
settings = get_settings()

SYNTHESIS_PROMPT = """You are a helpful assistant that summarizes the results of Google Workspace operations.

Given the user's original query and the results of various operations, generate a clear, concise natural language response.

Guidelines:
- Use checkmarks (✓) for successful operations
- Use warnings (⚠) for failed or partial operations
- Include specific details (email subjects, event titles, file names, dates, times)
- If actions were drafted but not sent, ask for confirmation
- If there were ambiguities or failures, explain what happened and suggest next steps
- Keep the response conversational and helpful
- Format dates and times in a human-readable way

User query: {query}

Operation results:
{results}

Generate a natural language response:"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def _format_results(step_results: list[StepResult]) -> str:
    parts = []
    for r in step_results:
        data_str = json.dumps(r.data, default=str, indent=2) if r.data else "no data"
        parts.append(
            f"Step: {r.step_id} | Agent: {r.agent} | Action: {r.action} | "
            f"Status: {r.status}\n"
            f"Data: {data_str[:2000]}\n"
            f"Error: {r.error or 'none'}"
        )
    return "\n---\n".join(parts)


async def synthesize_response(
    query: str,
    step_results: list[StepResult],
) -> tuple[str, list[ActionTaken]]:
    """Generate a natural language response from step results."""
    actions_taken = [
        ActionTaken(
            service=r.agent,
            action=r.action,
            status=r.status,
            detail=r.error if r.status == "failed" else _summarize_data(r.data),
        )
        for r in step_results
    ]

    # If all steps failed, provide a graceful fallback
    if all(r.status == "failed" for r in step_results):
        return (
            "I wasn't able to complete your request. "
            + " ".join(f"The {r.agent} service reported: {r.error}" for r in step_results)
            + "\nPlease try again or rephrase your query.",
            actions_taken,
        )

    prompt = SYNTHESIS_PROMPT.format(
        query=query,
        results=_format_results(step_results),
    )

    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    return response.choices[0].message.content or "", actions_taken


def _summarize_data(data) -> str | None:
    if data is None:
        return None
    if isinstance(data, str):
        return data[:200]
    if isinstance(data, list):
        return f"{len(data)} result(s)"
    if isinstance(data, dict):
        if "subject" in data:
            return f"Email: {data['subject']}"
        if "title" in data:
            return f"Event: {data['title']}"
        if "name" in data:
            return f"File: {data['name']}"
    return str(data)[:200]
