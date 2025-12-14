"""Helpers for cloud LLM chat handling."""

import base64
from collections.abc import AsyncGenerator, Callable, Iterable
from enum import Enum
import json
import logging
import re
from typing import Any, Literal, cast

from hass_nabucasa import Cloud, NabuCasaBaseError
from hass_nabucasa.llm import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
)
from litellm import (
    ResponseFunctionToolCall,
    ResponseInputParam,
    ResponsesAPIStreamEvents,
)
from openai.types.responses import (
    FunctionToolParam,
    ResponseInputItemParam,
    ResponseReasoningItem,
    ToolParam,
    WebSearchToolParam,
)
from openai.types.responses.response_input_param import (
    ImageGenerationCall as ImageGenerationCallParam,
)
from openai.types.responses.response_output_item import ImageGenerationCall
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .client import CloudClient

_LOGGER = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 10


class ResponseItemType(str, Enum):
    """Response item types."""

    FUNCTION_CALL = "function_call"
    MESSAGE = "message"
    REASONING = "reasoning"
    WEB_SEARCH_CALL = "web_search_call"
    IMAGE = "image"


def _convert_content_to_param(
    chat_content: Iterable[conversation.Content],
) -> ResponseInputParam:
    """Convert any native chat message for this agent to the native format."""
    messages: ResponseInputParam = []
    reasoning_summary: list[str] = []
    web_search_calls: dict[str, dict[str, Any]] = {}

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            if (
                content.tool_name == "web_search_call"
                and content.tool_call_id in web_search_calls
            ):
                web_search_call = web_search_calls.pop(content.tool_call_id)
                web_search_call["status"] = content.tool_result.get(
                    "status", "completed"
                )
                messages.append(cast("ResponseInputItemParam", web_search_call))
            else:
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": content.tool_call_id,
                        "output": json.dumps(content.tool_result),
                    }
                )
            continue

        if content.content:
            role: Literal["user", "assistant", "system", "developer"] = content.role
            if role == "system":
                role = "developer"
            messages.append(
                {"type": "message", "role": role, "content": content.content}
            )

        if isinstance(content, conversation.AssistantContent):
            if content.tool_calls:
                for tool_call in content.tool_calls:
                    if (
                        tool_call.external
                        and tool_call.tool_name == "web_search_call"
                        and "action" in tool_call.tool_args
                    ):
                        web_search_calls[tool_call.id] = {
                            "type": "web_search_call",
                            "id": tool_call.id,
                            "action": tool_call.tool_args["action"],
                            "status": "completed",
                        }
                    else:
                        messages.append(
                            {
                                "type": "function_call",
                                "name": tool_call.tool_name,
                                "arguments": json.dumps(tool_call.tool_args),
                                "call_id": tool_call.id,
                            }
                        )

            if content.thinking_content:
                reasoning_summary.append(content.thinking_content)

            if isinstance(content.native, ResponseReasoningItem):
                messages.append(
                    {
                        "type": "reasoning",
                        "id": content.native.id,
                        "summary": (
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
                        "encrypted_content": content.native.encrypted_content,
                    }
                )
                reasoning_summary = []

            elif isinstance(content.native, ImageGenerationCall):
                messages.append(
                    cast(ImageGenerationCallParam, content.native.to_dict())
                )

    return messages


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
) -> ToolParam:
    """Format a Home Assistant tool for the OpenAI Responses API."""
    parameters = convert(tool.parameters, custom_serializer=custom_serializer)

    spec: FunctionToolParam = {
        "type": "function",
        "name": tool.name,
        "strict": False,
        "description": tool.description,
        "parameters": parameters,
    }

    return spec


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the schema to be compatible with OpenAI API."""
    if schema["type"] == "object":
        schema.setdefault("strict", True)
        schema.setdefault("additionalProperties", False)
        if "properties" not in schema:
            return

        if "required" not in schema:
            schema["required"] = []

        # Ensure all properties are required
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
    """Format the schema to be compatible with OpenAI API."""
    result: dict[str, Any] = convert(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )

    _ensure_schema_constraints(result)

    return result


def _ensure_schema_constraints(schema: dict[str, Any]) -> None:
    """Ensure generated schemas match the Responses API expectations."""
    schema_type = schema.get("type")

    if schema_type == "object":
        schema.setdefault("additionalProperties", False)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for property_schema in properties.values():
                if isinstance(property_schema, dict):
                    _ensure_schema_constraints(property_schema)
    elif schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            _ensure_schema_constraints(items)


# Borrowed and adapted from openai_conversation component
async def _transform_stream(  # noqa: C901 - This is complex, but better to have it in one place
    chat_log: conversation.ChatLog,
    stream: Any,
    remove_citations: bool = False,
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform stream result into HA format."""
    last_summary_index = None
    last_role: Literal["assistant", "tool_result"] | None = None
    current_tool_call: ResponseFunctionToolCall | None = None

    # Non-reasoning models don't follow our request to remove citations, so we remove
    # them manually here. They always follow the same pattern: the citation is always
    # in parentheses in Markdown format, the citation is always in a single delta event,
    # and sometimes the closing parenthesis is split into a separate delta event.
    remove_parentheses: bool = False
    citation_regexp = re.compile(r"\(\[([^\]]+)\]\((https?:\/\/[^\)]+)\)")

    async for event in stream:
        event_type = getattr(event, "type", None)
        event_item = getattr(event, "item", None)
        event_item_type = getattr(event_item, "type", None) if event_item else None

        _LOGGER.debug(
            "Event[%s] | item: %s",
            event_type,
            event_item_type,
        )

        if event_type == ResponsesAPIStreamEvents.OUTPUT_ITEM_ADDED:
            # Detect function_call even when it's a BaseLiteLLMOpenAIResponseObject
            if event_item_type == ResponseItemType.FUNCTION_CALL:
                # OpenAI has tool calls as individual events
                # while HA puts tool calls inside the assistant message.
                # We turn them into individual assistant content for HA
                # to ensure that tools are called as soon as possible.
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                current_tool_call = cast(ResponseFunctionToolCall, event.item)
            elif (
                event_item_type == ResponseItemType.MESSAGE
                or (
                    event_item_type == ResponseItemType.REASONING
                    and last_summary_index is not None
                )  # Subsequent ResponseReasoningItem
                or last_role != "assistant"
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None

        elif event_type == ResponsesAPIStreamEvents.OUTPUT_ITEM_DONE:
            if event_item_type == ResponseItemType.REASONING:
                encrypted_content = getattr(event.item, "encrypted_content", None)
                summary = getattr(event.item, "summary", []) or []

                yield {
                    "native": ResponseReasoningItem(
                        type="reasoning",
                        id=event.item.id,
                        summary=[],
                        encrypted_content=encrypted_content,
                    )
                }

                last_summary_index = len(summary) - 1 if summary else None
            elif event_item_type == ResponseItemType.WEB_SEARCH_CALL:
                action = getattr(event.item, "action", None)
                if isinstance(action, dict):
                    action_dict = action
                elif action is not None:
                    action_dict = action.to_dict()
                else:
                    action_dict = {}
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="web_search_call",
                            tool_args={"action": action_dict},
                            external=True,
                        )
                    ]
                }
                yield {
                    "role": "tool_result",
                    "tool_call_id": event.item.id,
                    "tool_name": "web_search_call",
                    "tool_result": {"status": event.item.status},
                }
                last_role = "tool_result"
            elif event_item_type == ResponseItemType.IMAGE:
                yield {"native": event.item}
                last_summary_index = -1  # Trigger new assistant message on next turn

        elif event_type == ResponsesAPIStreamEvents.OUTPUT_TEXT_DELTA:
            data = event.delta
            if remove_parentheses:
                data = data.removeprefix(")")
                remove_parentheses = False
            elif remove_citations and (match := citation_regexp.search(data)):
                match_start, match_end = match.span()
                # remove leading space if any
                if data[match_start - 1 : match_start] == " ":
                    match_start -= 1
                # remove closing parenthesis:
                if data[match_end : match_end + 1] == ")":
                    match_end += 1
                else:
                    remove_parentheses = True
                data = data[:match_start] + data[match_end:]
            if data:
                yield {"content": data}

        elif event_type == ResponsesAPIStreamEvents.REASONING_SUMMARY_TEXT_DELTA:
            # OpenAI can output several reasoning summaries
            # in a single ResponseReasoningItem. We split them as separate
            # AssistantContent messages. Only last of them will have
            # the reasoning `native` field set.
            if (
                last_summary_index is not None
                and event.summary_index != last_summary_index
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
            last_summary_index = event.summary_index
            yield {"thinking_content": event.delta}

        elif event_type == ResponsesAPIStreamEvents.FUNCTION_CALL_ARGUMENTS_DELTA:
            if current_tool_call is not None:
                current_tool_call.arguments += event.delta

        elif event_type == ResponsesAPIStreamEvents.WEB_SEARCH_CALL_SEARCHING:
            yield {"role": "assistant"}

        elif event_type == ResponsesAPIStreamEvents.FUNCTION_CALL_ARGUMENTS_DONE:
            if current_tool_call is not None:
                current_tool_call.status = "completed"

                raw_args = json.loads(current_tool_call.arguments)
                for key in ("area", "floor"):
                    if key in raw_args and not raw_args[key]:
                        # Remove keys that are "" or None
                        raw_args.pop(key, None)

                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_tool_call.call_id,
                            tool_name=current_tool_call.name,
                            tool_args=raw_args,
                        )
                    ]
                }

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_COMPLETED:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_INCOMPLETE:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )

            if (
                event.response.incomplete_details
                and event.response.incomplete_details.reason
            ):
                reason: str = event.response.incomplete_details.reason
            else:
                reason = "unknown reason"

            if reason == "max_output_tokens":
                reason = "max output tokens reached"
            elif reason == "content_filter":
                reason = "content filter triggered"

            raise HomeAssistantError(f"OpenAI response incomplete: {reason}")

        elif event_type == ResponsesAPIStreamEvents.RESPONSE_FAILED:
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )
            reason = "unknown reason"
            if event.response.error is not None:
                reason = event.response.error.message
            raise HomeAssistantError(f"OpenAI response failed: {reason}")

        elif event_type == ResponsesAPIStreamEvents.ERROR:
            raise HomeAssistantError(f"OpenAI response error: {event.message}")


class BaseCloudLLMEntity(Entity):
    """Cloud LLM conversation agent."""

    def __init__(self, cloud: Cloud[CloudClient], config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._cloud = cloud
        self._entry = config_entry

    async def _prepare_chat_for_generation(
        self,
        chat_log: conversation.ChatLog,
        messages: ResponseInputParam,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Prepare kwargs for Cloud LLM from the chat log."""

        last_content: Any = chat_log.content[-1]
        if last_content.role == "user" and last_content.attachments:
            files = await self._async_prepare_files_for_prompt(last_content.attachments)
            current_content = last_content.content
            last_content = [*(current_content or []), *files]

        tools: list[ToolParam] = []
        tool_choice: str | None = None

        if chat_log.llm_api:
            ha_tools: list[ToolParam] = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

            if ha_tools:
                if not chat_log.unresponded_tool_results:
                    tools = ha_tools
                    tool_choice = "auto"
                else:
                    tools = []
                    tool_choice = "none"

        web_search = WebSearchToolParam(
            type="web_search",
            search_context_size="medium",
        )
        tools.append(web_search)

        response_kwargs: dict[str, Any] = {
            "messages": messages,
            "conversation_id": chat_log.conversation_id,
        }

        if response_format is not None:
            response_kwargs["response_format"] = response_format
        if tools is not None:
            response_kwargs["tools"] = tools
        if tool_choice is not None:
            response_kwargs["tool_choice"] = tool_choice

        response_kwargs["stream"] = True

        return response_kwargs

    async def _async_prepare_files_for_prompt(
        self,
        attachments: list[conversation.Attachment],
    ) -> list[dict[str, Any]]:
        """Prepare files for multimodal prompts."""

        def prepare() -> list[dict[str, Any]]:
            content: list[dict[str, Any]] = []
            for attachment in attachments:
                mime_type = attachment.mime_type
                path = attachment.path
                if not path.exists():
                    raise HomeAssistantError(f"`{path}` does not exist")

                data = base64.b64encode(path.read_bytes()).decode("utf-8")
                if mime_type and mime_type.startswith("image/"):
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{data}",
                            "detail": "auto",
                        }
                    )
                elif mime_type and mime_type.startswith("application/pdf"):
                    content.append(
                        {
                            "type": "input_file",
                            "filename": str(path.name),
                            "file_data": f"data:{mime_type};base64,{data}",
                        }
                    )
                else:
                    raise HomeAssistantError(
                        "Only images and PDF are currently supported as attachments"
                    )

            return content

        return await self.hass.async_add_executor_job(prepare)

    async def _async_handle_chat_log(
        self,
        type: Literal["ai_task", "conversation"],
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate a response for the chat log."""

        for _ in range(_MAX_TOOL_ITERATIONS):
            response_format: dict[str, Any] | None = None
            if structure and structure_name:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": slugify(structure_name),
                        "schema": _format_structured_output(
                            structure, chat_log.llm_api
                        ),
                        "strict": False,
                    },
                }

            messages = _convert_content_to_param(chat_log.content)

            response_kwargs = await self._prepare_chat_for_generation(
                chat_log,
                messages,
                response_format,
            )

            try:
                if type == "conversation":
                    raw_stream = await self._cloud.llm.async_process_conversation(
                        **response_kwargs,
                    )
                else:
                    raw_stream = await self._cloud.llm.async_generate_data(
                        **response_kwargs,
                    )

                messages.extend(
                    _convert_content_to_param(
                        [
                            content
                            async for content in chat_log.async_add_delta_content_stream(
                                self.entity_id,
                                _transform_stream(
                                    chat_log,
                                    raw_stream,
                                    True,
                                ),
                            )
                        ]
                    )
                )

            except LLMAuthenticationError as err:
                raise HomeAssistantError("Cloud LLM authentication failed") from err
            except LLMRateLimitError as err:
                raise HomeAssistantError("Cloud LLM is rate limited") from err
            except LLMResponseError as err:
                raise HomeAssistantError(str(err)) from err
            except LLMServiceError as err:
                raise HomeAssistantError("Error talking to Cloud LLM") from err
            except NabuCasaBaseError as err:
                raise HomeAssistantError(str(err)) from err

            if not chat_log.unresponded_tool_results:
                break
