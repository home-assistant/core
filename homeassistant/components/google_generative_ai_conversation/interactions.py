"""Interactions API support for the Google Generative AI Conversation integration."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from google.genai import interactions
from google.genai.types import HarmCategory, SafetySetting
import probatio

from homeassistant.helpers import llm

from .const import (
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_LEVEL,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)


def format_tools_for_interactions(
    tools: list[llm.Tool] | None = None,
    *,
    custom_serializer: Callable[[Any], Any] | None = None,
    enable_google_search: bool = False,
) -> list[interactions.Tool]:
    """Format tools for the Gemini Interactions API."""
    formatted_tools: list[interactions.Tool] = []

    if tools:
        serializer = custom_serializer or llm.selector_serializer
        formatted_tools.extend(
            interactions.Function(
                name=tool.name,
                description=tool.description,
                parameters=probatio.to_openapi(
                    tool.parameters,
                    custom_serializer=serializer,
                ),
            )
            for tool in tools
        )

    if enable_google_search:
        formatted_tools.append(interactions.GoogleSearch())

    return formatted_tools


def format_response_format(
    structure: probatio.Schema | None,
    *,
    custom_serializer: Callable[[Any], Any] | None = None,
) -> interactions.TextResponseFormat | None:
    """Format structured output response_format for the Gemini Interactions API."""
    if not structure:
        return None

    serializer = custom_serializer or llm.selector_serializer
    return interactions.TextResponseFormat(
        type="text",
        mime_type="application/json",
        schema_=probatio.to_openapi(
            structure,
            custom_serializer=serializer,
        ),
    )


def create_safety_settings(options: Mapping[str, Any]) -> list[SafetySetting]:
    """Create safety settings from integration options."""
    return [
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=options.get(
                CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
            ),
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=options.get(
                CONF_HARASSMENT_BLOCK_THRESHOLD,
                RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ),
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=options.get(
                CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
            ),
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=options.get(
                CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
            ),
        ),
    ]


def build_interaction_request(
    *,
    model: str,
    input_content: Any,
    options: Mapping[str, Any] | None = None,
    system_instruction: str | None = None,
    tools: Sequence[interactions.Tool] | None = None,
    response_format: interactions.TextResponseFormat | None = None,
    safety_settings: list[SafetySetting] | None = None,
    default_max_tokens: int | None = None,
    stream: bool = True,
    store: bool = False,
) -> dict[str, Any]:
    """Build the request dictionary for a Gemini Interactions API call.

    Guarantees that store is always False for stateless conversation handling.
    """
    if store:
        raise ValueError("Home Assistant interactions must be stateless (store=False)")

    options = options or {}

    request: dict[str, Any] = {
        "model": model,
        "input": input_content,
        "stream": stream,
        "store": False,
    }

    if system_instruction:
        request["system_instruction"] = system_instruction

    if tools:
        request["tools"] = tools

    if response_format:
        request["response_format"] = response_format

    if safety_settings:
        request["safety_settings"] = safety_settings

    generation_config: dict[str, Any] = {
        "temperature": options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
        "top_p": options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
        "top_k": options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
        "max_output_tokens": options.get(
            CONF_MAX_TOKENS,
            default_max_tokens
            if default_max_tokens is not None
            else RECOMMENDED_MAX_TOKENS,
        ),
    }

    thinking_level = options.get(CONF_THINKING_LEVEL, RECOMMENDED_THINKING_LEVEL)
    if thinking_level and thinking_level != "auto":
        generation_config["thinking_level"] = thinking_level

    request["generation_config"] = generation_config

    return request
