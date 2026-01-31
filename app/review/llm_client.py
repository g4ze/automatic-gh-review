from __future__ import annotations

import json
import logging
import re

from litellm import acompletion
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMParseError(Exception):
    """Raised when LLM output cannot be parsed as valid JSON."""


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output.

    Handles both raw JSON and markdown-fenced JSON blocks.
    """
    text = text.strip()

    # Try direct parse first
    if text.startswith("{"):
        return json.loads(text)

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())

    raise LLMParseError(f"Could not extract JSON from LLM output: {text[:200]}")


@retry(
    retry=retry_if_exception_type(LLMParseError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def call_llm_json(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    last_error: str | None = None,
) -> dict:
    """Call the LLM and parse the response as JSON.

    Retries up to 2 additional times if JSON parsing fails,
    appending the validation error to help the model self-correct.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if last_error:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your previous response had a JSON parsing error: {last_error}\n"
                    "Please respond with valid JSON only."
                ),
            }
        )

    logger.debug("Calling LLM model=%s", settings.litellm_model)

    response = await acompletion(
        model=settings.litellm_model,
        messages=messages,
        max_tokens=settings.litellm_max_tokens,
        temperature=settings.litellm_temperature,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    if not raw:
        raise LLMParseError("LLM returned empty response")

    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, LLMParseError) as exc:
        logger.warning("JSON parse failed, will retry: %s", exc)
        raise LLMParseError(str(exc)) from exc
