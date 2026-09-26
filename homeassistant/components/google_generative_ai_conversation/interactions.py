"""Interactions API support for the Google Generative AI Conversation integration."""

import base64
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping, Sequence
import json
from typing import Any

from google.genai import interactions
from google.genai.errors import APIError, ClientError
from google.genai.types import HarmCategory, SafetySetting
import probatio

from homeassistant.components import conversation
from homeassistant.exceptions import HomeAssistantError
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
    LOGGER,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_LEVEL,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)
from .entity import ERROR_GETTING_RESPONSE, ContentDetails, PartDetails


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


def _decode_signature(sig: bytes | str) -> str:
    """Decode signature to base64 string if bytes."""
    if isinstance(sig, bytes):
        return base64.b64encode(sig).decode("utf-8")
    return sig


def _parse_tool_args(args_str: str, args_dict: dict[str, Any] | None) -> dict[str, Any]:
    """Parse tool arguments from json string or prepopulated dictionary."""
    if args_str:
        try:
            return json.loads(args_str)
        except json.JSONDecodeError as err:
            LOGGER.error("Error decoding tool args JSON: %s", err)
            return {}
    if args_dict is not None:
        return args_dict
    return {}


def _trace_usage(
    chat_log: conversation.ChatLog, event: interactions.InteractionSSEEvent
) -> None:
    """Extract and trace token usage from an event."""
    usage: Any = None
    match event.event_type:
        case "step.delta":
            if event.metadata and event.metadata.total_usage:
                usage = event.metadata.total_usage
        case "step.stop":
            usage = event.step_usage or event.usage
        case "interaction.completed":
            usage = event.interaction.usage
    if usage is None:
        return

    prompt_tokens = getattr(usage, "total_input_tokens", None) or getattr(
        usage, "prompt_token_count", None
    )
    cached_tokens = (
        getattr(usage, "total_cached_tokens", 0)
        or getattr(usage, "cached_content_token_count", 0)
        or 0
    )
    output_tokens = getattr(usage, "total_output_tokens", None) or getattr(
        usage, "candidates_token_count", None
    )

    if prompt_tokens is not None and output_tokens is not None:
        chat_log.async_trace(
            {
                "stats": {
                    "input_tokens": prompt_tokens,
                    "cached_input_tokens": cached_tokens,
                    "output_tokens": output_tokens,
                }
            }
        )


def _check_event_error(event: interactions.InteractionSSEEvent) -> None:
    """Check for error conditions in an interactions event."""
    match event.event_type:
        case "error":
            error_obj = event.error
            message = (
                error_obj.message
                if error_obj and error_obj.message
                else "Unknown error"
            )
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}")
        case "interaction.status_update":
            if event.status in ("failed", "cancelled"):
                raise HomeAssistantError(
                    f"{ERROR_GETTING_RESPONSE} Status: {event.status}"
                )
        case "interaction.completed":
            interaction = event.interaction
            if interaction and interaction.status in ("failed", "cancelled"):
                raise HomeAssistantError(
                    f"{ERROR_GETTING_RESPONSE} Status: {interaction.status}"
                )


async def transform_interactions_stream(
    chat_log: conversation.ChatLog,
    result: AsyncIterator[interactions.InteractionSSEEvent],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform Gemini Interactions SSE stream into AssistantContentDeltaDict chunks."""
    new_message = True
    part_details: list[PartDetails] = []
    content_index = 0
    thinking_content_index = 0
    tool_call_index = 0

    current_tool_id: str | None = None
    current_tool_name: str | None = None
    current_tool_args_str = ""
    current_tool_args_dict: dict[str, Any] | None = None

    try:
        async for event in result:
            LOGGER.debug("Received interactions event: %s", event)

            _trace_usage(chat_log, event)
            _check_event_error(event)

            if new_message:
                yield {"role": "assistant"}
                new_message = False

            match event.event_type:
                case "step.start":
                    step = event.step
                    match step.type:
                        case "function_call":
                            current_tool_id = step.id
                            current_tool_name = step.name
                            current_tool_args_str = ""
                            current_tool_args_dict = None
                            if isinstance(step.arguments, dict) and step.arguments:
                                current_tool_args_dict = step.arguments

                case "step.delta":
                    delta = event.delta
                    match delta.type:
                        case "text":
                            if text := delta.text:
                                yield {"content": text}
                                content_index += len(text)

                        case "thought":
                            if hasattr(delta, "text") and (thought_text := delta.text):
                                yield {"thinking_content": thought_text}
                                thinking_content_index += len(thought_text)

                        case "thought_summary":
                            if delta.content and hasattr(delta.content, "text"):
                                if thought_text := delta.content.text:
                                    yield {"thinking_content": thought_text}
                                    thinking_content_index += len(thought_text)

                        case "thought_signature":
                            if sig := delta.signature:
                                part_details.append(
                                    PartDetails(
                                        part_type="thought",
                                        index=thinking_content_index,
                                        length=0,
                                        thought_signature=_decode_signature(sig),
                                    )
                                )

                        case "arguments_delta":
                            current_tool_args_str += delta.arguments or ""

                case "step.stop":
                    if current_tool_name:
                        tool_args = _parse_tool_args(
                            current_tool_args_str, current_tool_args_dict
                        )
                        yield {
                            "tool_calls": [
                                llm.ToolInput(
                                    tool_name=current_tool_name,
                                    tool_args=tool_args,
                                    id=current_tool_id or "",
                                )
                            ]
                        }
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_args_str = ""
                        current_tool_args_dict = None
                        tool_call_index += 1

        if part_details:
            yield {"native": ContentDetails(part_details=part_details)}

    except (APIError, ClientError, ValueError) as err:
        LOGGER.error("Error processing interactions stream: %s %s", type(err), err)
        if isinstance(err, APIError):
            message = err.message
        else:
            message = type(err).__name__
        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}") from err
