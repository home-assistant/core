"""Conversation helpers for Mistral AI."""

from collections.abc import AsyncGenerator, Callable, Iterable
import json
from typing import Any

from mistralai.client import errors, models as mistral_models
from mistralai.client.models import (
    AssistantMessage,
    CompletionEvent,
    DeltaMessage,
    Function,
    FunctionCall,
    SystemMessage,
    Tool,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from mistralai.client.types import UNSET
from probatio import to_openapi

from homeassistant.components import conversation
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.json import json_dumps

from .api import is_unset
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT,
    LOGGER,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _extract_text(content: Any) -> str:
    """Extract plain text from a Mistral message content.

    Content can be a plain string or a list of content chunks.
    """
    if content is None or is_unset(content):
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                if chunk.get("type") == "text":
                    parts.append(chunk.get("text", ""))
            elif getattr(chunk, "type", None) == "text":
                parts.append(getattr(chunk, "text", "") or "")
        return "".join(parts)
    return str(content)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> Tool:
    """Format a Home Assistant LLM tool as a Mistral tool."""
    return Tool(
        function=Function(
            name=tool.name,
            description=tool.description or "",
            parameters=to_openapi(tool.parameters, custom_serializer=custom_serializer),
        )
    )


def convert_content_to_messages(
    chat_content: Iterable[conversation.Content],
) -> list[mistral_models.ChatCompletionRequestMessage]:
    """Convert conversation content to Mistral messages."""
    messages: list[mistral_models.ChatCompletionRequestMessage] = []

    for content in chat_content:
        if isinstance(content, conversation.SystemContent):
            messages.append(SystemMessage(content=content.content))
        elif isinstance(content, conversation.UserContent):
            messages.append(UserMessage(content=content.content))
        elif isinstance(content, conversation.ToolResultContent):
            messages.append(
                ToolMessage(
                    content=json_dumps(content.result.data),
                    tool_call_id=content.tool_call_id,
                    name=content.tool_name,
                )
            )
        elif isinstance(content, conversation.AssistantContent):
            if content.content or content.tool_calls:
                messages.append(
                    AssistantMessage(
                        content=content.content,
                        tool_calls=(
                            [
                                ToolCall(
                                    id=tool_call.id,
                                    function=FunctionCall(
                                        name=tool_call.tool_name,
                                        arguments=json_dumps(tool_call.tool_args),
                                    ),
                                )
                                for tool_call in content.tool_calls
                            ]
                            if content.tool_calls
                            else UNSET
                        ),
                    )
                )
        else:
            raise TypeError(f"Unexpected content type: {type(content)}")

    return messages


async def transform_stream(
    stream,
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform a Mistral event stream into conversation content deltas."""
    current_tool_calls: dict[int, dict[str, Any]] = {}
    message_started = False

    async for event in stream:
        LOGGER.debug("Received event: %s", event)
        if not isinstance(event, CompletionEvent):
            continue

        chunk = event.data
        for choice in chunk.choices:
            delta: DeltaMessage = choice.delta

            if (
                not is_unset(delta.role)
                and delta.role == "assistant"
                and not message_started
            ):
                yield {"role": "assistant"}
                message_started = True

            if not is_unset(delta.content) and delta.content:
                text = _extract_text(delta.content)
                if text:
                    if not message_started:
                        yield {"role": "assistant"}
                        message_started = True
                    yield {"content": text}

            if not is_unset(delta.tool_calls) and delta.tool_calls:
                if not message_started:
                    yield {"role": "assistant"}
                    message_started = True
                for tool_call in delta.tool_calls:
                    index = tool_call.index if tool_call.index is not None else 0
                    entry = current_tool_calls.setdefault(
                        index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tool_call.id and tool_call.id != "null":
                        entry["id"] = tool_call.id
                    if (
                        tool_call.function
                        and tool_call.function.name
                        and not is_unset(tool_call.function.name)
                    ):
                        entry["name"] += tool_call.function.name
                    if tool_call.function and tool_call.function.arguments:
                        entry["arguments"] += tool_call.function.arguments

            if choice.finish_reason == "tool_calls" and current_tool_calls:
                tool_inputs: list[llm.ToolInput] = []
                for entry in current_tool_calls.values():
                    try:
                        args = (
                            json.loads(entry["arguments"]) if entry["arguments"] else {}
                        )
                    except json.JSONDecodeError as err:
                        raise HomeAssistantError(
                            f"Unexpected tool argument response: {err}"
                        ) from err
                    tool_inputs.append(
                        llm.ToolInput(
                            id=entry["id"],
                            tool_name=entry["name"],
                            tool_args=args,
                        )
                    )
                yield {"tool_calls": tool_inputs}
                current_tool_calls = {}


async def handle_chat_log(entity, chat_log: conversation.ChatLog) -> None:
    """Stream the chat log through the Mistral API and update the log."""
    options = entity.subentry.data

    system = chat_log.content[0]
    if not isinstance(system, conversation.SystemContent):
        raise TypeError("First message must be a system message")

    messages = convert_content_to_messages(chat_log.content)

    model = options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL])

    model_args: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS]),
        "temperature": options.get(CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE]),
        "top_p": options.get(CONF_TOP_P, DEFAULT[CONF_TOP_P]),
    }

    tools: list[Tool] = []
    if chat_log.llm_api:
        tools = [
            _format_tool(tool, chat_log.llm_api.custom_serializer)
            for tool in chat_log.llm_api.tools
        ]

    if tools:
        model_args["tools"] = tools

    client = entity.entry.runtime_data

    # To prevent infinite loops, we limit the number of iterations
    for _iteration in range(MAX_TOOL_ITERATIONS):
        try:
            stream = await client.chat.stream_async(**model_args)
            messages.extend(
                convert_content_to_messages(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            entity.entity_id,
                            transform_stream(stream),
                        )
                    ]
                )
            )
        except errors.MistralError as err:
            if err.status_code in (401, 403):
                # Trigger the reauthentication flow for a revoked/expired key.
                entity.entry.async_start_reauth(entity.hass)
            LOGGER.error("Error talking to Mistral: %s", err)
            raise HomeAssistantError("Error talking to Mistral") from err
        except HomeAssistantError:
            raise
        except Exception as err:
            LOGGER.error("Error talking to Mistral: %s", err)
            raise HomeAssistantError("Error talking to Mistral") from err

        if not chat_log.unresponded_tool_results:
            break
