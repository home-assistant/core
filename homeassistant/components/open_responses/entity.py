"""Base entity for Open Responses."""

import base64
from collections.abc import AsyncGenerator, Callable, Iterable
import json
from mimetypes import guess_file_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import openai
from openai._streaming import AsyncStream
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseCompletedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseIncompleteEvent,
    ResponseInputFileParam,
    ResponseInputImageParam,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseReasoningItem,
    ResponseReasoningItemParam,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ToolParam,
)
from openai.types.responses.response_create_params import ResponseCreateParamsStreaming
from openai.types.responses.response_input_param import FunctionCallOutput
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

if TYPE_CHECKING:
    from . import OpenResponsesConfigEntry


MAX_TOOL_ITERATIONS = 10


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

    return FunctionToolParam(
        type="function",
        name=tool.name,
        parameters=schema,
        description=tool.description,
        strict=False,
    )


def _convert_content_to_param(
    chat_content: Iterable[conversation.Content],
) -> ResponseInputParam:
    """Convert native Home Assistant chat content to Open Responses input items."""
    messages: ResponseInputParam = []
    reasoning_summary: list[str] = []

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            messages.append(
                FunctionCallOutput(
                    type="function_call_output",
                    call_id=content.tool_call_id,
                    output=json_dumps(content.tool_result),
                )
            )
            continue

        if (
            isinstance(content, conversation.AssistantContent)
            and isinstance(content.native, dict)
            and content.native.get("type")
        ):
            messages.append(cast(Any, content.native))
            continue
        if isinstance(content, conversation.AssistantContent) and isinstance(
            content.native, ResponseOutputMessage
        ):
            messages.append(
                cast(
                    Any,
                    content.native.model_dump(exclude_none=True),
                )
            )
            continue
        if (
            isinstance(content, conversation.AssistantContent)
            and not isinstance(content.native, ResponseReasoningItem)
            and hasattr(content.native, "model_dump")
        ):
            messages.append(cast(Any, content.native.model_dump(exclude_none=True)))
            continue

        if content.content or (
            isinstance(content, conversation.UserContent) and content.attachments
        ):
            messages.append(
                EasyInputMessageParam(
                    type="message", role=content.role, content=content.content
                )
            )

        if isinstance(content, conversation.AssistantContent):
            if content.tool_calls:
                messages.extend(
                    ResponseFunctionToolCallParam(
                        type="function_call",
                        name=tool_call.tool_name,
                        arguments=json_dumps(tool_call.tool_args),
                        call_id=tool_call.id,
                        status="completed",
                    )
                    for tool_call in content.tool_calls
                )

            if content.thinking_content:
                reasoning_summary.append(content.thinking_content)

            if isinstance(content.native, ResponseReasoningItem):
                messages.append(
                    ResponseReasoningItemParam(
                        type="reasoning",
                        id=content.native.id,
                        summary=(
                            [
                                {
                                    "type": "summary_text",
                                    "text": summary,
                                }
                                for summary in reasoning_summary
                            ]
                            if content.thinking_content
                            else []
                        ),
                        encrypted_content=content.native.encrypted_content,
                        status="completed",
                    )
                )
                reasoning_summary = []

    return messages


async def _transform_stream(
    chat_log: conversation.ChatLog,
    stream: AsyncStream[ResponseStreamEvent],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform an Open Responses stream into Home Assistant chat deltas."""
    current_tool_calls: dict[str, ResponseFunctionToolCall] = {}
    last_summary_index: int | None = None
    last_role: Literal["assistant"] | None = None

    async for event in stream:
        LOGGER.debug("Received event: %s", event)

        if isinstance(event, ResponseOutputItemAddedEvent):
            if isinstance(event.item, ResponseFunctionToolCall):
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                current_tool_calls[event.item.id] = event.item
            elif (
                isinstance(event.item, (ResponseReasoningItem, ResponseOutputMessage))
                or last_role != "assistant"
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
        elif isinstance(event, ResponseOutputItemDoneEvent):
            if isinstance(event.item, ResponseReasoningItem):
                yield {
                    "native": ResponseReasoningItem(
                        type="reasoning",
                        id=event.item.id,
                        summary=[],
                        encrypted_content=event.item.encrypted_content,
                    )
                }
                last_summary_index = len(event.item.summary) - 1
            elif not isinstance(event.item, ResponseFunctionToolCall):
                yield {"native": event.item}
        elif isinstance(event, ResponseTextDeltaEvent):
            yield {"content": event.delta}
        elif isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            if (
                last_summary_index is not None
                and event.summary_index != last_summary_index
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
            last_summary_index = event.summary_index
            yield {"thinking_content": event.delta}
        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
            if current_tool_call := current_tool_calls.get(event.item_id):
                current_tool_call.arguments += event.delta
        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
            if (
                current_tool_call := current_tool_calls.pop(event.item_id, None)
            ) is None:
                raise HomeAssistantError("Received tool arguments without a tool call")
            current_tool_call.arguments = event.arguments
            current_tool_call.status = "completed"
            yield {
                "tool_calls": [
                    llm.ToolInput(
                        id=current_tool_call.call_id,
                        tool_name=current_tool_call.name,
                        tool_args=json.loads(current_tool_call.arguments),
                    )
                ]
            }
        elif isinstance(
            event,
            (ResponseCompletedEvent, ResponseIncompleteEvent, ResponseFailedEvent),
        ):
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )
            if isinstance(event, ResponseIncompleteEvent):
                reason = "unknown reason"
                if (
                    event.response.incomplete_details
                    and event.response.incomplete_details.reason
                ):
                    reason = event.response.incomplete_details.reason
                raise HomeAssistantError(
                    f"Open Responses response incomplete: {reason}"
                )
            if isinstance(event, ResponseFailedEvent):
                reason = "unknown reason"
                if event.response.error is not None:
                    reason = event.response.error.message
                raise HomeAssistantError(f"Open Responses response failed: {reason}")
        elif isinstance(event, ResponseErrorEvent):
            raise HomeAssistantError(f"Open Responses response error: {event.message}")


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
        messages = _convert_content_to_param(chat_log.content)

        model_args = ResponseCreateParamsStreaming(
            model=options.get(CONF_MODEL, self.entry.data[CONF_MODEL]),
            input=messages,
            max_output_tokens=options.get(
                CONF_MAX_OUTPUT_TOKENS, RECOMMENDED_MAX_OUTPUT_TOKENS
            ),
            user=chat_log.conversation_id,
            store=options.get(CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES),
            stream=True,
        )

        tools: list[ToolParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if tools:
            model_args["tools"] = tools

        last_content = chat_log.content[-1]
        if last_content.role == "user" and last_content.attachments:
            files = await async_prepare_files_for_prompt(
                self.hass,
                [(a.path, a.mime_type) for a in last_content.attachments],
            )
            last_message = messages[-1]
            assert (
                last_message["type"] == "message"
                and last_message["role"] == "user"
                and isinstance(last_message["content"], str)
            )
            last_message_content: ResponseInputMessageContentListParam = []
            if last_message["content"]:
                last_message_content.append(
                    {"type": "input_text", "text": last_message["content"]}
                )
            last_message_content.extend(files)
            last_message["content"] = last_message_content

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
                stream = await client.responses.create(**model_args)
            except openai.AuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    "Authentication failed with Open Responses endpoint"
                ) from err
            except openai.RateLimitError as err:
                LOGGER.error("Rate limited by Open Responses endpoint: %s", err)
                raise HomeAssistantError(
                    "Rate limited by Open Responses endpoint"
                ) from err
            except openai.OpenAIError as err:
                LOGGER.error("Error talking to Open Responses endpoint: %s", err)
                raise HomeAssistantError(
                    "Error talking to Open Responses endpoint"
                ) from err

            messages.extend(
                _convert_content_to_param(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            self.entity_id,
                            _transform_stream(chat_log, stream),
                        )
                    ]
                )
            )
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
                    ResponseInputImageParam(
                        type="input_image",
                        image_url=f"data:{mime_type};base64,{base64_file}",
                        detail="auto",
                    )
                )
            elif mime_type.startswith("application/pdf"):
                content.append(
                    ResponseInputFileParam(
                        type="input_file",
                        filename=str(file_path),
                        file_data=f"data:{mime_type};base64,{base64_file}",
                    )
                )

        return content

    return await hass.async_add_executor_job(append_files_to_content)
