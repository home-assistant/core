"""Interactions API support for the Google Generative AI Conversation integration."""

import base64
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from google.genai import interactions
from google.genai.errors import APIError, ClientError
from google.genai.types import File
import probatio

# The google-genai SDK's interactions module has a name collision:
# google.genai.interactions exports both triggers.Interaction (a Request/Union typealias)
# and interactions.interaction.Interaction (the response model class).
# At static analysis time, mypy resolves interactions.Interaction to the trigger union,
# causing attribute errors on response fields (steps, output_image, output_audio).
# We import the concrete response model under TYPE_CHECKING for type checkers while
# using the public interactions.Interaction export at runtime.
# Tracked upstream: https://github.com/googleapis/python-genai/issues/3013
if TYPE_CHECKING:
    from google.genai._gaos.types.interactions.interaction import Interaction
else:
    Interaction = interactions.Interaction
from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .const import (
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    ERROR_GETTING_RESPONSE,
    LOGGER,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_LEVEL,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)
from .helpers import ContentDetails, PartDetails


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


def format_image_content(
    *,
    uri: str | None = None,
    data: bytes | str | None = None,
    file: File | None = None,
    mime_type: str | None = None,
    resolution: str | None = None,
) -> interactions.ImageContent:
    """Format image content for the Gemini Interactions API.

    Supports both Files API references (via URI or File object) and inline bytes/base64 strings.
    """
    effective_uri = file.uri if file is not None else uri
    effective_mime_type = (file.mime_type if file is not None else None) or mime_type

    if effective_uri is not None and data is not None:
        raise ValueError("Cannot provide both uri/file and data for image content")
    if effective_uri is None and data is None:
        raise ValueError("Must provide either uri, file, or data for image content")

    b64_data: str | None = None
    if data is not None:
        b64_data = (
            base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else data
        )

    return interactions.ImageContent(
        type="image",
        uri=effective_uri,
        data=b64_data,
        mime_type=cast(interactions.ImageContentMimeType, effective_mime_type)
        if effective_mime_type is not None
        else None,
        resolution=cast(interactions.MediaResolution, resolution)
        if resolution is not None
        else None,
    )


def format_image_response_format(
    *,
    mime_type: Literal["image/jpeg"] | None = None,
    aspect_ratio: interactions.ImageResponseFormatAspectRatio | None = None,
    image_size: interactions.ImageResponseFormatImageSize | None = None,
    delivery: interactions.ImageResponseFormatDelivery | None = "inline",
) -> interactions.ImageResponseFormat:
    """Format image output response_format for the Gemini Interactions API."""
    return interactions.ImageResponseFormat(
        type="image",
        mime_type=mime_type,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        delivery=delivery,
    )


def format_audio_response_format(
    *,
    mime_type: interactions.AudioResponseFormatMimeType | None = None,
    delivery: interactions.AudioResponseFormatDelivery | None = "inline",
    sample_rate: int | None = None,
    bit_rate: int | None = None,
) -> interactions.AudioResponseFormat:
    """Format audio output response_format for the Gemini Interactions API."""
    return interactions.AudioResponseFormat(
        type="audio",
        mime_type=mime_type,
        delivery=delivery,
        sample_rate=sample_rate,
        bit_rate=bit_rate,
    )


def extract_output_image(
    interaction: Interaction,
) -> tuple[bytes, str]:
    """Extract raw image bytes and MIME type from an Interaction.

    Checks both interaction.output_image and ModelOutputStep parts.
    """
    if (
        interaction.output_image is not None
        and interaction.output_image.data is not None
    ):
        return (
            base64.b64decode(interaction.output_image.data),
            interaction.output_image.mime_type or "image/jpeg",
        )

    if interaction.steps:
        for step in interaction.steps:
            if isinstance(step, interactions.ModelOutputStep) and step.content:
                for content_part in step.content:
                    if (
                        isinstance(content_part, interactions.ImageContent)
                        and content_part.data is not None
                    ):
                        return (
                            base64.b64decode(content_part.data),
                            content_part.mime_type or "image/jpeg",
                        )

    raise ValueError("Interaction did not contain an output image")


def extract_output_audio(
    interaction: Interaction,
) -> tuple[bytes, str]:
    """Extract raw audio bytes and MIME type from an Interaction.

    Checks both interaction.output_audio and ModelOutputStep parts.
    """
    if (
        interaction.output_audio is not None
        and interaction.output_audio.data is not None
    ):
        return (
            base64.b64decode(interaction.output_audio.data),
            interaction.output_audio.mime_type or "audio/wav",
        )

    if interaction.steps:
        for step in interaction.steps:
            if isinstance(step, interactions.ModelOutputStep) and step.content:
                for content_part in step.content:
                    if (
                        isinstance(content_part, interactions.AudioContent)
                        and content_part.data is not None
                    ):
                        return (
                            base64.b64decode(content_part.data),
                            content_part.mime_type or "audio/wav",
                        )

    raise ValueError("Interaction did not contain output audio")


def build_interaction_request(
    *,
    model: str,
    input_content: (
        str
        | Sequence[interactions.Step]
        | Sequence[interactions.StepParam]
        | Sequence[interactions.Content]
        | Sequence[interactions.ContentParam]
    ),
    options: Mapping[str, Any] | None = None,
    system_instruction: str | None = None,
    tools: Sequence[interactions.Tool] | None = None,
    response_format: (
        interactions.InteractionResponseFormat
        | interactions.ResponseFormat
        | Sequence[interactions.ResponseFormat]
        | None
    ) = None,
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

    model_name = model.removeprefix("models/")
    thinking_level = options.get(CONF_THINKING_LEVEL, RECOMMENDED_THINKING_LEVEL)
    if (
        thinking_level
        and thinking_level != "auto"
        and model_name.startswith("gemini-3")
        and not ("pro" in model_name and thinking_level == "minimal")
    ):
        generation_config["thinking_level"] = thinking_level

    request["generation_config"] = generation_config

    return request


def _validate_tool_results(value: Any) -> Any:
    """Recursively convert non-json-serializable types."""
    if isinstance(value, (datetime.time, datetime.date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_validate_tool_results(item) for item in value]
    if isinstance(value, dict):
        return {k: _validate_tool_results(v) for k, v in value.items()}
    return value


def _read_attachment_file(path: Path) -> bytes:
    """Read attachment bytes from disk, failing fast if not found or on I/O error."""
    if not path.exists():
        raise HomeAssistantError(f"Attachment file not found: {path}")
    try:
        return path.read_bytes()
    except OSError as err:
        raise HomeAssistantError(
            f"Error reading attachment file {path}: {err}"
        ) from err


def _format_attachment_content(
    raw_data: bytes,
    mime_type: str,
) -> interactions.Content:
    """Format raw attachment data into the appropriate Interactions Content part."""
    b64_data = base64.b64encode(raw_data).decode("ascii")

    if mime_type.startswith("image/"):
        return format_image_content(data=raw_data, mime_type=mime_type)

    if mime_type.startswith("audio/"):
        return interactions.AudioContent(data=b64_data, mime_type=cast(Any, mime_type))

    if mime_type.startswith("video/"):
        return interactions.VideoContent(data=b64_data, mime_type=cast(Any, mime_type))

    if mime_type in ("application/pdf", "text/csv"):
        return interactions.DocumentContent(
            data=b64_data, mime_type=cast(Any, mime_type)
        )

    if mime_type.startswith("text/"):
        return interactions.TextContent(text=raw_data.decode("utf-8", errors="replace"))

    raise HomeAssistantError(f"Unsupported attachment type: {mime_type}")


async def async_prepare_attachment_for_interactions(
    hass: HomeAssistant,
    attachment: conversation.Attachment,
) -> interactions.Content:
    """Prepare a single conversation attachment asynchronously for Interactions API."""
    if not attachment.path:
        raise HomeAssistantError(
            f"Attachment missing file path: {attachment.media_content_id}"
        )
    raw_data = await hass.async_add_executor_job(_read_attachment_file, attachment.path)
    return _format_attachment_content(raw_data, attachment.mime_type)


async def async_prepare_chat_log_attachments(
    hass: HomeAssistant,
    chat_log: conversation.ChatLog,
) -> dict[str, interactions.Content]:
    """Prepare all attachments in a chat log asynchronously for Interactions API."""
    prepared: dict[str, interactions.Content] = {}
    for content in chat_log.content:
        if isinstance(content, conversation.UserContent) and content.attachments:
            for attachment in content.attachments:
                if attachment.media_content_id not in prepared:
                    prepared[
                        attachment.media_content_id
                    ] = await async_prepare_attachment_for_interactions(
                        hass, attachment
                    )
    return prepared


def _convert_user_content_step(
    content: conversation.UserContent,
    attachment_cache: dict[str | Path, interactions.Content] | None = None,
) -> interactions.UserInputStep:
    """Convert UserContent into a UserInputStep, including any attachments."""
    step_content: list[interactions.Content] = []

    if content.attachments:
        for attachment in content.attachments:
            cached_part: interactions.Content | None = None
            if attachment_cache is not None:
                cached_part = attachment_cache.get(attachment.media_content_id) or (
                    attachment_cache.get(attachment.path) if attachment.path else None
                )

            if cached_part is not None:
                step_content.append(cached_part)
                continue

            if not attachment.path:
                raise HomeAssistantError(
                    f"Attachment missing file path: {attachment.media_content_id}"
                )

            raw_data = _read_attachment_file(attachment.path)
            part = _format_attachment_content(raw_data, attachment.mime_type)
            if attachment_cache is not None:
                attachment_cache[attachment.media_content_id] = part
                attachment_cache[attachment.path] = part
            step_content.append(part)

    if content.content:
        step_content.append(interactions.TextContent(text=content.content))
    elif not step_content:
        step_content.append(interactions.TextContent(text=" "))

    return interactions.UserInputStep(content=step_content)


def _create_thought_step(
    detail: PartDetails,
    thinking_content: str | None,
    single_thought: bool,
) -> interactions.ThoughtStep:
    """Create a ThoughtStep from PartDetails and thinking content."""
    thought_text = ""
    if thinking_content:
        if detail.length > 0:
            thought_text = thinking_content[detail.index : detail.index + detail.length]
        elif single_thought:
            thought_text = thinking_content
        else:
            thought_text = thinking_content[detail.index :]

    summary: list[interactions.ThoughtSummaryContent] | None = (
        [interactions.TextContent(text=thought_text)] if thought_text else None
    )
    return interactions.ThoughtStep(
        signature=detail.thought_signature,
        summary=summary,
    )


def _create_google_search_step(
    tool_call: llm.ToolInput,
    signature: str | None,
) -> interactions.GoogleSearchCallStep:
    """Create a GoogleSearchCallStep from ToolInput."""
    queries = (
        list(tool_call.tool_args["queries"])
        if isinstance(tool_call.tool_args, dict)
        and "queries" in tool_call.tool_args
        and tool_call.tool_args["queries"] is not None
        else None
    )
    return interactions.GoogleSearchCallStep(
        id=tool_call.id,
        arguments=interactions.GoogleSearchCallArguments(queries=queries),
        signature=signature,
        search_type="web_search",
    )


def _create_function_call_step(
    tool_call: llm.ToolInput,
) -> interactions.FunctionCallStep:
    """Create a FunctionCallStep from ToolInput."""
    args = tool_call.tool_args if isinstance(tool_call.tool_args, dict) else {}
    return interactions.FunctionCallStep(
        id=tool_call.id,
        name=tool_call.tool_name,
        arguments=args,
    )


def _find_tool_call(
    tool_calls: list[llm.ToolInput] | None,
    index: int,
    is_search: bool,
    handled_indices: set[int],
) -> tuple[int, llm.ToolInput] | tuple[None, None]:
    """Find matching tool call by index or next available."""
    if not tool_calls:
        return None, None

    if 0 <= index < len(tool_calls):
        cand = tool_calls[index]
        if (cand.tool_name == "google_search") == is_search:
            handled_indices.add(index)
            return index, cand

    for idx, cand in enumerate(tool_calls):
        if (
            idx not in handled_indices
            and (cand.tool_name == "google_search") == is_search
        ):
            handled_indices.add(idx)
            return idx, cand

    return None, None


def _convert_assistant_content_steps(
    content: conversation.AssistantContent,
) -> list[interactions.Step]:
    """Convert AssistantContent into the corresponding interaction steps."""
    steps: list[interactions.Step] = []
    part_details = (
        content.native.part_details
        if isinstance(content.native, ContentDetails)
        else []
    )
    handled_tool_indices: set[int] = set()
    single_thought = len([d for d in part_details if d.part_type == "thought"]) == 1

    for detail in part_details:
        match detail.part_type:
            case "thought":
                steps.append(
                    _create_thought_step(
                        detail, content.thinking_content, single_thought
                    )
                )
            case "google_search_call":
                _, search_tool = _find_tool_call(
                    content.tool_calls, detail.index, True, handled_tool_indices
                )
                if search_tool:
                    steps.append(
                        _create_google_search_step(
                            search_tool, detail.thought_signature
                        )
                    )
            case "function_call":
                _, func_tool = _find_tool_call(
                    content.tool_calls, detail.index, False, handled_tool_indices
                )
                if func_tool:
                    steps.append(_create_function_call_step(func_tool))

    if content.thinking_content and not any(
        isinstance(s, interactions.ThoughtStep) for s in steps
    ):
        fallback_summary: list[interactions.ThoughtSummaryContent] = [
            interactions.TextContent(text=content.thinking_content)
        ]
        steps.append(interactions.ThoughtStep(summary=fallback_summary))

    if content.tool_calls:
        for idx, tool_call in enumerate(content.tool_calls):
            if idx in handled_tool_indices:
                continue
            if tool_call.tool_name == "google_search":
                steps.append(_create_google_search_step(tool_call, None))
            else:
                steps.append(_create_function_call_step(tool_call))
            handled_tool_indices.add(idx)

    if content.content:
        steps.append(
            interactions.ModelOutputStep(
                content=[interactions.TextContent(text=content.content)]
            )
        )

    return steps


def _convert_tool_result_step(
    content: conversation.ToolResultContent,
) -> interactions.FunctionResultStep:
    """Convert ToolResultContent into a FunctionResultStep."""
    result_data = (
        _validate_tool_results(content.result.data)
        if content.result.data is not None
        else {}
    )
    return interactions.FunctionResultStep(
        call_id=content.tool_call_id,
        result=result_data,
        is_error=True if content.result.error else None,
        name=content.tool_name,
    )


def convert_chat_log_to_interactions_steps(
    chat_log: conversation.ChatLog,
    prepared_attachments: Mapping[str | Path, interactions.Content] | None = None,
) -> list[interactions.Step]:
    """Convert Home Assistant ChatLog history into a sequence of interaction steps."""
    steps: list[interactions.Step] = []
    cache: dict[str | Path, interactions.Content] = (
        dict(prepared_attachments) if prepared_attachments is not None else {}
    )

    for content in chat_log.content:
        match content:
            case conversation.UserContent():
                steps.append(_convert_user_content_step(content, cache))
            case conversation.AssistantContent():
                steps.extend(_convert_assistant_content_steps(content))
            case conversation.ToolResultContent():
                steps.append(_convert_tool_result_step(content))

    return steps


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

    in_thought: bool = False
    current_thought_start: int = 0
    current_thought_length: int = 0
    current_thought_signature: str | None = None


def _flush_active_thought(state: _StreamState) -> None:
    """Flush active thought part to part_details if any."""
    if state.in_thought:
        if state.current_thought_signature:
            state.part_details.append(
                PartDetails(
                    part_type="thought",
                    index=state.current_thought_start,
                    length=state.current_thought_length,
                    thought_signature=state.current_thought_signature,
                )
            )
        state.in_thought = False
        state.current_thought_signature = None
        state.current_thought_length = 0


def _handle_step_start(step: interactions.Step, state: _StreamState) -> None:
    """Handle step start events."""
    _flush_active_thought(state)

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
        case interactions.ThoughtStep(signature=sig):
            state.in_thought = True
            state.current_thought_start = state.thinking_content_index
            state.current_thought_length = 0
            state.current_thought_signature = sig or None


def _handle_step_delta(
    delta: interactions.StepDeltaData, state: _StreamState
) -> conversation.AssistantContentDeltaDict | None:
    """Handle step delta events."""
    match delta:
        case interactions.TextDelta(text=text):
            if text:
                _flush_active_thought(state)
                state.content_index += len(text)
                return {"content": text}

        case interactions.ThoughtSummaryDelta(
            content=interactions.TextContent(text=text)
        ):
            if text:
                if not state.in_thought:
                    state.in_thought = True
                    state.current_thought_start = state.thinking_content_index
                    state.current_thought_length = 0
                    state.current_thought_signature = None
                state.current_thought_length += len(text)
                state.thinking_content_index += len(text)
                return {"thinking_content": text}

        case interactions.ThoughtSignatureDelta(signature=sig):
            if sig:
                if not state.in_thought:
                    state.in_thought = True
                    state.current_thought_start = state.thinking_content_index
                    state.current_thought_length = 0
                state.current_thought_signature = sig

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
    _flush_active_thought(state)

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

        _flush_active_thought(state)
        if state.part_details:
            yield {"native": ContentDetails(part_details=state.part_details)}

    except (APIError, ClientError, ValueError) as err:
        LOGGER.error("Error processing interactions stream: %s %s", type(err), err)
        message = err.message if isinstance(err, APIError) else type(err).__name__
        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {message}") from err
