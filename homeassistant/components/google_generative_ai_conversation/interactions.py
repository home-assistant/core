"""Interactions API support for the Google Generative AI Conversation integration."""

from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
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
    usage: interactions.Usage | None = None
    match event:
        case interactions.StepDelta(metadata=metadata) if (
            metadata and metadata.total_usage
        ):
            usage = metadata.total_usage
        case interactions.StepStop(step_usage=step_usage, usage=stop_usage):
            usage = step_usage or stop_usage
        case interactions.InteractionCompletedEvent(interaction=interaction) if (
            interaction
        ):
            usage = interaction.usage

    if usage is None:
        return

    prompt_tokens = usage.total_input_tokens
    cached_tokens = usage.total_cached_tokens or 0
    output_tokens = usage.total_output_tokens

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
    match event:
        case interactions.ErrorEvent(error=error_obj):
            message = (
                error_obj.message
                if error_obj and error_obj.message
                else "Unknown error"
            )
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}")
        case interactions.InteractionStatusUpdate(status=status):
            if status in ("failed", "cancelled"):
                raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE} Status: {status}")
        case interactions.InteractionCompletedEvent(interaction=interaction):
            if interaction and interaction.status in ("failed", "cancelled"):
                raise HomeAssistantError(
                    f"{ERROR_GETTING_RESPONSE} Status: {interaction.status}"
                )


@dataclass
class _StreamState:
    """State tracked while streaming an interaction."""

    part_details: list[PartDetails] = field(default_factory=list)
    content_index: int = 0
    thinking_content_index: int = 0
    tool_call_index: int = 0

    current_tool_id: str | None = None
    current_tool_name: str | None = None
    current_tool_args_str: str = ""
    current_tool_args_dict: dict[str, Any] | None = None

    current_search_call_id: str | None = None
    current_search_queries: list[str] | None = None
    current_search_signature: str | None = None


def _handle_step_start(step: interactions.Step, state: _StreamState) -> None:
    """Handle step start events."""
    match step:
        case interactions.FunctionCallStep(id=call_id, name=name, arguments=args):
            state.current_tool_id = call_id
            state.current_tool_name = name
            state.current_tool_args_str = ""
            state.current_tool_args_dict = (
                args if isinstance(args, dict) and args else None
            )
        case interactions.GoogleSearchCallStep(
            id=call_id, signature=sig, arguments=args
        ):
            state.current_search_call_id = call_id
            state.current_search_signature = sig or None
            state.current_search_queries = (
                list(args.queries) if args and args.queries is not None else None
            )


def _handle_step_delta(
    delta: interactions.StepDeltaData, state: _StreamState
) -> conversation.AssistantContentDeltaDict | None:
    """Handle step delta events."""
    match delta:
        case interactions.TextDelta(text=text):
            if text:
                state.content_index += len(text)
                return {"content": text}

        case interactions.ThoughtSummaryDelta(
            content=interactions.TextContent(text=text)
        ):
            if text:
                state.thinking_content_index += len(text)
                return {"thinking_content": text}

        case interactions.ThoughtSignatureDelta(signature=sig):
            if sig:
                state.part_details.append(
                    PartDetails(
                        part_type="thought",
                        index=state.thinking_content_index,
                        length=0,
                        thought_signature=sig,
                    )
                )

        case interactions.GoogleSearchCallDelta(signature=sig, arguments=args):
            if sig:
                state.current_search_signature = sig
            if args and args.queries is not None:
                state.current_search_queries = list(args.queries)

        case interactions.ArgumentsDelta(arguments=args):
            if args:
                state.current_tool_args_str += args

    return None


def _handle_step_stop(
    state: _StreamState,
) -> conversation.AssistantContentDeltaDict | None:
    """Handle step stop events."""
    if state.current_tool_name:
        tool_args = _parse_tool_args(
            state.current_tool_args_str, state.current_tool_args_dict
        )
        delta: conversation.AssistantContentDeltaDict = {
            "tool_calls": [
                llm.ToolInput(
                    tool_name=state.current_tool_name,
                    tool_args=tool_args,
                    id=state.current_tool_id or "",
                )
            ]
        }
        state.current_tool_id = None
        state.current_tool_name = None
        state.current_tool_args_str = ""
        state.current_tool_args_dict = None
        state.tool_call_index += 1
        return delta

    if state.current_search_call_id:
        search_delta: conversation.AssistantContentDeltaDict = {
            "tool_calls": [
                llm.ToolInput(
                    tool_name="google_search",
                    tool_args={"queries": state.current_search_queries or []},
                    id=state.current_search_call_id,
                    external=True,
                )
            ]
        }
        if state.current_search_signature:
            state.part_details.append(
                PartDetails(
                    part_type="google_search_call",
                    index=state.tool_call_index,
                    length=0,
                    thought_signature=state.current_search_signature,
                )
            )
        state.current_search_call_id = None
        state.current_search_queries = None
        state.current_search_signature = None
        state.tool_call_index += 1
        return search_delta

    return None


async def transform_interactions_stream(
    chat_log: conversation.ChatLog,
    result: AsyncIterator[interactions.InteractionSSEEvent],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform Gemini Interactions SSE stream into AssistantContentDeltaDict chunks."""
    new_message = True
    state = _StreamState()

    try:
        async for event in result:
            LOGGER.debug("Received interactions event: %s", event)

            _trace_usage(chat_log, event)
            _check_event_error(event)

            if new_message:
                yield {"role": "assistant"}
                new_message = False

            match event:
                case interactions.StepStart(step=step):
                    _handle_step_start(step, state)
                case interactions.StepDelta(delta=delta):
                    if out_delta := _handle_step_delta(delta, state):
                        yield out_delta
                case interactions.StepStop():
                    if out_delta := _handle_step_stop(state):
                        yield out_delta

        if state.part_details:
            yield {"native": ContentDetails(part_details=state.part_details)}

    except (APIError, ClientError, ValueError) as err:
        LOGGER.error("Error processing interactions stream: %s %s", type(err), err)
        message = err.message if isinstance(err, APIError) else type(err).__name__
        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}") from err
