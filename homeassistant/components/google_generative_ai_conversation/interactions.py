"""Interactions API support for the Google Generative AI Conversation integration."""

import base64
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping
import json
from typing import Any

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
) -> list[dict[str, Any]]:
    """Format tools for the Gemini Interactions API."""
    formatted_tools: list[dict[str, Any]] = []

    if tools:
        serializer = custom_serializer or llm.selector_serializer
        formatted_tools.extend(
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": probatio.to_openapi(
                    tool.parameters,
                    custom_serializer=serializer,
                ),
            }
            for tool in tools
        )

    if enable_google_search:
        formatted_tools.append({"type": "google_search"})

    return formatted_tools


def format_response_format(
    structure: probatio.Schema | None,
    *,
    custom_serializer: Callable[[Any], Any] | None = None,
) -> dict[str, Any] | None:
    """Format structured output response_format for the Gemini Interactions API."""
    if not structure:
        return None

    serializer = custom_serializer or llm.selector_serializer
    return {
        "type": "text",
        "mime_type": "application/json",
        "schema": probatio.to_openapi(
            structure,
            custom_serializer=serializer,
        ),
    }


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
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
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


def _trace_usage(chat_log: conversation.ChatLog, event: Any) -> None:
    """Extract and trace token usage from an event."""
    metadata = getattr(event, "metadata", None)
    total_usage = getattr(metadata, "total_usage", None) if metadata else None
    interaction = getattr(event, "interaction", None)
    interaction_usage = getattr(interaction, "usage", None) if interaction else None
    step_usage = getattr(event, "step_usage", None)
    usage = total_usage or interaction_usage or step_usage
    if usage is None:
        return

    prompt_tokens = getattr(usage, "total_input_tokens", None)
    if prompt_tokens is None:
        prompt_tokens = getattr(usage, "prompt_token_count", None)
    cached_tokens = (
        getattr(usage, "total_cached_tokens", 0)
        or getattr(usage, "cached_content_token_count", 0)
        or 0
    )
    output_tokens = getattr(usage, "total_output_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "candidates_token_count", None)

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


def _check_event_error(event: Any) -> None:
    """Check for error conditions in an interactions event."""
    event_type = getattr(event, "event_type", None)

    if event_type == "error":
        error_obj = getattr(event, "error", None)
        message = (
            getattr(error_obj, "message", "Unknown error")
            if error_obj
            else "Unknown error"
        )
        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}")

    if event_type == "interaction.status_update":
        status = getattr(event, "status", None)
        if status in ("failed", "cancelled"):
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE} Status: {status}")

    if event_type == "interaction.completed":
        interaction = getattr(event, "interaction", None)
        status = getattr(interaction, "status", None) if interaction else None
        if status in ("failed", "cancelled"):
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE} Status: {status}")


async def transform_interactions_stream(
    chat_log: conversation.ChatLog,
    result: AsyncIterator[Any],
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

            match getattr(event, "event_type", None):
                case "step.start":
                    step = event.step
                    if step.type == "function_call":
                        current_tool_id = getattr(step, "id", None)
                        current_tool_name = getattr(step, "name", None)
                        current_tool_args_str = ""
                        current_tool_args_dict = None
                        if sig := getattr(step, "signature", None):
                            sig_str = (
                                base64.b64encode(sig).decode("utf-8")
                                if isinstance(sig, bytes)
                                else sig
                            )
                            part_details.append(
                                PartDetails(
                                    part_type="function_call",
                                    index=tool_call_index,
                                    thought_signature=sig_str,
                                )
                            )
                        if (
                            isinstance(args := getattr(step, "arguments", None), dict)
                            and args
                        ):
                            current_tool_args_dict = args

                case "step.delta":
                    delta = event.delta
                    match delta.type:
                        case "text":
                            if text := getattr(delta, "text", ""):
                                yield {"content": text}
                                content_index += len(text)

                        case "thought" | "thought_summary":
                            thought_text = getattr(delta, "text", None)
                            if not thought_text and hasattr(delta, "content"):
                                thought_text = getattr(delta.content, "text", None)
                            if thought_text:
                                yield {"thinking_content": thought_text}
                                thinking_content_index += len(thought_text)

                        case "thought_signature":
                            if sig := getattr(delta, "signature", None):
                                sig_str = (
                                    base64.b64encode(sig).decode("utf-8")
                                    if isinstance(sig, bytes)
                                    else sig
                                )
                                part_details.append(
                                    PartDetails(
                                        part_type="thought",
                                        index=thinking_content_index,
                                        length=0,
                                        thought_signature=sig_str,
                                    )
                                )

                        case "arguments_delta":
                            current_tool_args_str += (
                                getattr(delta, "arguments", "") or ""
                            )

                case "step.stop":
                    if current_tool_name:
                        tool_args: dict[str, Any]
                        if current_tool_args_str:
                            try:
                                tool_args = json.loads(current_tool_args_str)
                            except json.JSONDecodeError as err:
                                LOGGER.error("Error decoding tool args JSON: %s", err)
                                tool_args = {}
                        elif current_tool_args_dict is not None:
                            tool_args = current_tool_args_dict
                        else:
                            tool_args = {}

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
