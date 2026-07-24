"""Base entity for Open Responses."""

import base64
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Iterable
import json
from mimetypes import guess_file_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import json_dumps
from homeassistant.util import slugify

from .const import (
    CONF_MAX_OUTPUT_TOKENS,
    CONF_STORE_RESPONSES,
    DOMAIN,
    LOGGER,
    RECOMMENDED_MAX_OUTPUT_TOKENS,
    RECOMMENDED_STORE_RESPONSES,
)
from .exceptions import (
    AuthenticationError,
    BadRequestError,
    OpenResponsesError,
    RateLimitError,
)

if TYPE_CHECKING:
    from . import OpenResponsesConfigEntry


MAX_TOOL_ITERATIONS = 10

type ResponseInputParam = list[dict[str, Any]]
type ResponseInputMessageContentListParam = list[dict[str, Any]]
type FunctionToolParam = dict[str, Any]
type ToolParam = dict[str, Any]


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the output schema to the Open Responses JSON schema subset."""
    if schema["type"] == "object":
        schema.setdefault("strict", True)
        schema.setdefault("additionalProperties", False)
        if "properties" not in schema:
            return

        if "required" not in schema:
            schema["required"] = []

        for prop, prop_info in schema["properties"].items():
            _adjust_schema(prop_info)
            if prop not in schema["required"]:
                prop_info["type"] = [prop_info["type"], "null"]
                schema["required"].append(prop)

    elif schema["type"] == "array":
        if "items" not in schema:
            return

        _adjust_schema(schema["items"])


def _format_structured_output(
    schema: vol.Schema, llm_api: llm.APIInstance | None
) -> dict[str, Any]:
    """Format the schema for Open Responses structured output."""
    result: dict[str, Any] = convert(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )

    _adjust_schema(result)

    return result


def _strip_unsupported_tool_schema_keys(schema: Any) -> None:
    """Strip JSON Schema keywords unsupported for Open Responses tools."""
    unsupported_keys = {"oneOf", "anyOf", "allOf", "enum", "not"}

    if isinstance(schema, dict):
        for key in unsupported_keys:
            schema.pop(key, None)
        for value in schema.values():
            _strip_unsupported_tool_schema_keys(value)
    elif isinstance(schema, list):
        for item in schema:
            _strip_unsupported_tool_schema_keys(item)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> FunctionToolParam:
    """Format Home Assistant LLM tool metadata for Open Responses."""
    schema = convert(tool.parameters, custom_serializer=custom_serializer)
    _strip_unsupported_tool_schema_keys(schema)

    return {
        "type": "function",
        "name": tool.name,
        "parameters": schema,
        "description": tool.description,
        "strict": False,
    }


def _convert_content_to_param(
    chat_content: Iterable[conversation.Content],
) -> ResponseInputParam:
    """Convert native Home Assistant chat content to Open Responses input items."""
    messages: ResponseInputParam = []

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            messages.append(
                {
                    "type": "function_call_output",
                    "call_id": content.tool_call_id,
                    "output": json_dumps(content.tool_result),
                }
            )
            continue

        if (
            isinstance(content, conversation.AssistantContent)
            and isinstance(content.native, dict)
            and content.native.get("type")
        ):
            messages.append(cast(Any, content.native))
            continue

        if content.content or (
            isinstance(content, conversation.UserContent) and content.attachments
        ):
            messages.append(
                {
                    "type": "message",
                    "role": content.role,
                    "content": content.content or "",
                }
            )

        if isinstance(content, conversation.AssistantContent):
            if content.tool_calls:
                messages.extend(
                    {
                        "type": "function_call",
                        "name": tool_call.tool_name,
                        "arguments": json_dumps(tool_call.tool_args),
                        "call_id": tool_call.id,
                        "status": "completed",
                    }
                    for tool_call in content.tool_calls
                )

    return messages


async def _async_prepare_message_attachments(
    hass: HomeAssistant,
    chat_content: Iterable[conversation.Content],
    messages: ResponseInputParam,
) -> None:
    """Attach files to all matching user messages."""
    message_index = 0

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            message_index += 1
            continue

        if (
            isinstance(content, conversation.AssistantContent)
            and isinstance(content.native, dict)
            and content.native.get("type")
        ):
            message_index += 1
            continue

        if content.content or (
            isinstance(content, conversation.UserContent) and content.attachments
        ):
            if isinstance(content, conversation.UserContent) and content.attachments:
                files = await async_prepare_files_for_prompt(
                    hass,
                    [
                        (attachment.path, attachment.mime_type)
                        for attachment in content.attachments
                    ],
                )
                message = messages[message_index]
                assert (
                    message["type"] == "message"
                    and message["role"] == "user"
                    and isinstance(message["content"], str)
                )
                message_content: ResponseInputMessageContentListParam = []
                if message["content"]:
                    message_content.append(
                        {"type": "input_text", "text": message["content"]}
                    )
                message_content.extend(files)
                message["content"] = message_content

            message_index += 1

        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            message_index += len(content.tool_calls)


async def _transform_stream(
    chat_log: conversation.ChatLog,
    stream: AsyncIterable[Any],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform an Open Responses stream into Home Assistant chat deltas."""
    current_tool_calls: dict[str, dict[str, Any]] = {}
    last_summary_index: int | None = None
    last_role: Literal["assistant"] | None = None

    async for raw_event in stream:
        event = _event_to_dict(raw_event)
        LOGGER.debug("Received event: %s", event)

        event_type = event.get("type")

        if event_type == "response.output_item.added":
            item = cast(dict[str, Any], event.get("item") or {})
            item_type = item.get("type")
            if item_type == "function_call":
                if item.get("id") is None:
                    raise HomeAssistantError("Received tool call without an item ID")
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                current_tool_calls[item["id"]] = item.copy()
            elif item_type in ("reasoning", "message") or last_role != "assistant":
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
        elif event_type == "response.output_item.done":
            item = cast(dict[str, Any], event.get("item") or {})
            item_type = item.get("type")
            if item_type == "reasoning":
                yield {
                    "native": {
                        "type": "reasoning",
                        "id": item.get("id"),
                        "summary": item.get("summary") or [],
                        "encrypted_content": item.get("encrypted_content"),
                    }
                }
                last_summary_index = len(item.get("summary") or []) - 1
            elif item_type != "function_call":
                yield {"native": item}
        elif event_type in (
            "response.output_text.delta",
            "response.refusal.delta",
            "response.text.delta",
        ):
            yield {"content": event["delta"]}
        elif event_type in (
            "response.reasoning.delta",
            "response.reasoning_summary.delta",
            "response.reasoning_summary_text.delta",
        ):
            summary_index = cast(int, event.get("summary_index", 0))
            if last_summary_index is not None and summary_index != last_summary_index:
                yield {"role": "assistant"}
                last_role = "assistant"
            last_summary_index = summary_index
            yield {"thinking_content": event["delta"]}
        elif event_type == "response.function_call_arguments.delta":
            if current_tool_call := current_tool_calls.get(event["item_id"]):
                current_tool_call["arguments"] = (
                    current_tool_call.get("arguments", "") + event["delta"]
                )
        elif event_type == "response.function_call_arguments.done":
            if (
                current_tool_call := current_tool_calls.pop(event["item_id"], None)
            ) is None:
                raise HomeAssistantError("Received tool arguments without a tool call")
            current_tool_call["arguments"] = event["arguments"]
            current_tool_call["status"] = "completed"
            yield {
                "tool_calls": [
                    llm.ToolInput(
                        id=current_tool_call["call_id"],
                        tool_name=current_tool_call["name"],
                        tool_args=json.loads(current_tool_call["arguments"]),
                    )
                ]
            }
        elif event_type in (
            "response.completed",
            "response.incomplete",
            "response.failed",
        ):
            response = cast(dict[str, Any], event.get("response") or {})
            if usage := response.get("usage"):
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": usage["input_tokens"],
                            "output_tokens": usage["output_tokens"],
                        }
                    }
                )
            if event_type == "response.incomplete":
                reason = "unknown reason"
                if incomplete_details := response.get("incomplete_details"):
                    reason = incomplete_details.get("reason") or reason
                raise HomeAssistantError(
                    f"Open Responses response incomplete: {reason}"
                )
            if event_type == "response.failed":
                reason = "unknown reason"
                if error := response.get("error"):
                    reason = error.get("message") or reason
                raise HomeAssistantError(f"Open Responses response failed: {reason}")
        elif event_type in ("error", "response.error"):
            error = cast(dict[str, Any], event.get("error") or {})
            reason = error.get("message") or event.get("message") or "unknown reason"
            raise HomeAssistantError(f"Open Responses response error: {reason}")


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Convert stream events to plain Open Responses event dictionaries."""
    if isinstance(event, dict):
        return event
    if hasattr(event, "event") and hasattr(event, "data"):
        data = cast(dict[str, Any], event.data.copy())
        data.setdefault("type", event.event)
        return data
    if hasattr(event, "model_dump"):
        return cast(dict[str, Any], event.model_dump(mode="json", exclude_none=True))
    if hasattr(event, "to_dict"):
        return cast(dict[str, Any], event.to_dict())
    raise HomeAssistantError("Received unknown Open Responses stream event")


class OpenResponsesEntity(Entity):
    """Base Open Responses entity."""

    _attr_has_entity_name = True
    _attr_name: str | None = None

    def __init__(
        self, entry: OpenResponsesConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Open Responses",
            model=subentry.data.get(CONF_MODEL, entry.data[CONF_MODEL]),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data
        chat_content = list(chat_log.content)
        messages = _convert_content_to_param(chat_content)
        await _async_prepare_message_attachments(self.hass, chat_content, messages)

        model_args: dict[str, Any] = {
            "model": options.get(CONF_MODEL, self.entry.data[CONF_MODEL]),
            "input": messages,
            "max_output_tokens": options.get(
                CONF_MAX_OUTPUT_TOKENS, RECOMMENDED_MAX_OUTPUT_TOKENS
            ),
            "user": chat_log.conversation_id,
            "store": options.get(CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES),
        }

        tools: list[ToolParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if tools:
            model_args["tools"] = tools

        if structure and structure_name:
            model_args["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": slugify(structure_name),
                    "schema": _format_structured_output(structure, chat_log.llm_api),
                },
            }

        client = self.entry.runtime_data

        for _iteration in range(max_iterations):
            try:
                stream = await client.create(**model_args, stream=True)
                new_contents = [
                    content
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        _transform_stream(chat_log, stream),
                    )
                ]
            except AuthenticationError as err:
                self.entry.async_start_reauth(self.hass)
                raise ConfigEntryAuthFailed(
                    "Authentication failed with Open Responses endpoint"
                ) from err
            except RateLimitError as err:
                LOGGER.error("Rate limited by Open Responses endpoint: %s", err)
                raise HomeAssistantError(
                    "Rate limited by Open Responses endpoint"
                ) from err
            except BadRequestError as err:
                LOGGER.error("Open Responses endpoint rejected request: %s", err)
                raise HomeAssistantError(
                    "Open Responses endpoint rejected request"
                ) from err
            except OpenResponsesError as err:
                LOGGER.error("Error talking to Open Responses endpoint: %s", err)
                raise HomeAssistantError(
                    "Error talking to Open Responses endpoint"
                ) from err

            messages.extend(_convert_content_to_param(new_contents))
            if not chat_log.unresponded_tool_results:
                break


async def async_prepare_files_for_prompt(
    hass: HomeAssistant, files: list[tuple[Path, str | None]]
) -> ResponseInputMessageContentListParam:
    """Append files to a prompt.

    Caller needs to ensure that the files are allowed.
    """

    def append_files_to_content() -> ResponseInputMessageContentListParam:
        content: ResponseInputMessageContentListParam = []

        for file_path, mime_type in files:
            if not file_path.exists():
                raise HomeAssistantError(f"`{file_path}` does not exist")

            if mime_type is None:
                mime_type = guess_file_type(file_path)[0]

            if not mime_type or not mime_type.startswith(("image/", "application/pdf")):
                raise HomeAssistantError(
                    "Only images and PDF are supported by the Open Responses API, "
                    f"`{file_path}` is not an image file or PDF"
                )

            base64_file = base64.b64encode(file_path.read_bytes()).decode("utf-8")

            if mime_type.startswith("image/"):
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{base64_file}",
                        "detail": "auto",
                    }
                )
            elif mime_type.startswith("application/pdf"):
                content.append(
                    {
                        "type": "input_file",
                        "filename": file_path.name,
                        "file_data": f"data:{mime_type};base64,{base64_file}",
                    }
                )

        return content

    return await hass.async_add_executor_job(append_files_to_content)
