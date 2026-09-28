"""Base entity for Open Responses."""

from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterable
import json
from typing import TYPE_CHECKING, Any

from openresponses_client import (
    APIConnectionError,
    AuthenticationError,
    ErrorEvent,
    FunctionCall,
    OpenResponsesError,
    PermissionDeniedError,
    StreamingEvent,
)
from openresponses_client.models import (
    ResponseCompletedEvent,
    ResponseFailedEvent,
    ResponseIncompleteEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputTextDeltaEvent,
    ResponseReasoningDeltaEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)
from openresponses_client.params import FunctionToolParam, InputItemParam
import probatio

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import json_dumps

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import OpenResponsesConfigEntry

MAX_TOOL_ITERATIONS = 10

# Function parameters must be a plain object schema
UNSUPPORTED_SCHEMA_KEYS = {"oneOf", "anyOf", "allOf", "enum", "not"}


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> FunctionToolParam:
    """Format a tool specification."""
    schema = probatio.to_openapi(
        tool.parameters, custom_serializer=custom_serializer, openapi_version="3.1.0"
    )
    return FunctionToolParam(
        type="function",
        name=tool.name,
        description=tool.description,
        parameters={
            k: v for k, v in schema.items() if k not in UNSUPPORTED_SCHEMA_KEYS
        },
        strict=False,
    )


def _convert_content_to_input(
    chat_content: Iterable[conversation.Content],
) -> list[InputItemParam]:
    """Convert chat log content to Open Responses input items."""
    items: list[InputItemParam] = []
    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": content.tool_call_id,
                    "output": json_dumps(
                        {"data": content.result.data, "error": content.result.error}
                    ),
                }
            )
            continue

        if content.content:
            match content.role:
                case "system":
                    items.append({"role": "system", "content": content.content})
                case "user":
                    items.append({"role": "user", "content": content.content})
                case "assistant":
                    items.append({"role": "assistant", "content": content.content})

        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            items.extend(
                {
                    "type": "function_call",
                    "call_id": tool_call.id,
                    "name": tool_call.tool_name,
                    "arguments": json_dumps(tool_call.tool_args),
                }
                for tool_call in content.tool_calls
            )
    return items


def _parse_function_call(function_call: FunctionCall) -> llm.ToolInput:
    """Convert a function call of the model to a tool input."""
    try:
        tool_args = function_call.parse_arguments()
    except json.JSONDecodeError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_tool_arguments",
            translation_placeholders={"error": str(err)},
        ) from err
    return llm.ToolInput(
        id=function_call.call_id,
        tool_name=function_call.name,
        tool_args=tool_args,
    )


async def _transform_stream(
    chat_log: conversation.ChatLog,
    stream: AsyncIterator[StreamingEvent],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform an Open Responses event stream into chat log deltas."""
    yield {"role": "assistant"}
    async for event in stream:
        match event:
            case ResponseOutputTextDeltaEvent(delta=delta):
                yield {"content": delta}
            case (
                ResponseReasoningDeltaEvent(delta=delta)
                | ResponseReasoningSummaryTextDeltaEvent(delta=delta)
            ):
                yield {"thinking_content": delta}
            case ResponseOutputItemDoneEvent(item=FunctionCall() as function_call):
                yield {"tool_calls": [_parse_function_call(function_call)]}
            case ResponseCompletedEvent(response=response):
                if response.usage is not None:
                    chat_log.async_trace(
                        {
                            "stats": {
                                "input_tokens": response.usage.input_tokens,
                                "output_tokens": response.usage.output_tokens,
                            }
                        }
                    )
            case ResponseIncompleteEvent(response=response):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="response_incomplete",
                    translation_placeholders={
                        "reason": (
                            response.incomplete_details
                            and response.incomplete_details.reason
                        )
                        or "unknown"
                    },
                )
            case ResponseFailedEvent(response=response):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="response_failed",
                    translation_placeholders={
                        "error": (response.error and response.error.message)
                        or "unknown"
                    },
                )
            case ErrorEvent(error=error):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="response_failed",
                    translation_placeholders={"error": error.message or "unknown"},
                )


class OpenResponsesBaseLLMEntity(Entity):
    """Base entity for Open Responses."""

    _attr_has_entity_name = True
    _attr_name = None

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
            model=subentry.data[CONF_MODEL],
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(self, chat_log: conversation.ChatLog) -> None:
        """Generate an answer for the chat log."""
        client = self.entry.runtime_data
        items = _convert_content_to_input(chat_log.content)
        tools: list[FunctionToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                async with client.stream(
                    model=self.subentry.data[CONF_MODEL],
                    input=[*items],
                    tools=tools,
                    store=False,
                    safety_identifier=chat_log.conversation_id,
                    prompt_cache_key=self.subentry.subentry_id,
                ) as stream:
                    items.extend(
                        _convert_content_to_input(
                            [
                                content
                                async for content in chat_log.async_add_delta_content_stream(
                                    self.entity_id, _transform_stream(chat_log, stream)
                                )
                            ]
                        )
                    )
            except (AuthenticationError, PermissionDeniedError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            except APIConnectionError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                ) from err
            except OpenResponsesError as err:
                LOGGER.debug("Error talking to the Open Responses server: %s", err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={"error": str(err)},
                ) from err

            if not chat_log.unresponded_tool_results:
                break
