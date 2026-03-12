"""Base entity for OpenAI."""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator, Callable, Iterable
import json
from mimetypes import guess_file_type
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Literal, cast

import openai
from openai._streaming import AsyncStream
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseCodeInterpreterToolCall,
    ResponseCompletedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseFunctionWebSearch,
    ResponseFunctionWebSearchParam,
    ResponseIncompleteEvent,
    ResponseInputFileParam,
    ResponseInputImageParam,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseInputTextParam,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseReasoningItem,
    ResponseReasoningItemParam,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ToolChoiceTypesParam,
    ToolParam,
    WebSearchToolParam,
)
from openai.types.responses.response_create_params import ResponseCreateParamsStreaming
from openai.types.responses.response_input_param import (
    FunctionCallOutput,
    ImageGenerationCall as ImageGenerationCallParam,
)
from openai.types.responses.response_output_item import ImageGenerationCall
from openai.types.responses.tool_param import (
    CodeInterpreter,
    CodeInterpreterContainerCodeInterpreterToolAuto,
    ImageGeneration,
)
from openai.types.responses.web_search_tool_param import UserLocation
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir, llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import json_dumps
from homeassistant.util import slugify

from .const import (
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_VERBOSITY,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
    UNSUPPORTED_EXTENDED_CACHE_RETENTION_MODELS,
)

if TYPE_CHECKING:
    from . import OpenAIConfigEntry


# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


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

    _adjust_schema(result)

    return result


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> FunctionToolParam:
    """Format tool specification."""
    return FunctionToolParam(
        type="function",
        name=tool.name,
        parameters=convert(tool.parameters, custom_serializer=custom_serializer),
        description=tool.description,
        strict=False,
    )


def _convert_content_to_param(
    chat_content: Iterable[conversation.Content],
) -> ResponseInputParam:
    """Convert any native chat message for this agent to the native format."""
    messages: ResponseInputParam = []
    reasoning_summary: list[str] = []
    web_search_calls: dict[str, ResponseFunctionWebSearchParam] = {}

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            if (
                content.tool_name == "web_search_call"
                and content.tool_call_id in web_search_calls
            ):
                web_search_call = web_search_calls.pop(content.tool_call_id)
                web_search_call["status"] = content.tool_result.get(  # type: ignore[typeddict-item]
                    "status", "completed"
                )
                messages.append(web_search_call)
            else:
                messages.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=content.tool_call_id,
                        output=json_dumps(content.tool_result),
                    )
                )
            continue

        if content.content:
            role: Literal["user", "assistant", "system", "developer"] = content.role
            if role == "system":
                role = "developer"
            messages.append(
                EasyInputMessageParam(
                    type="message", role=role, content=content.content
                )
            )

        if isinstance(content, conversation.AssistantContent):
            if content.tool_calls:
                for tool_call in content.tool_calls:
                    if (
                        tool_call.external
                        and tool_call.tool_name == "web_search_call"
                        and "action" in tool_call.tool_args
                    ):
                        web_search_calls[tool_call.id] = ResponseFunctionWebSearchParam(
                            type="web_search_call",
                            id=tool_call.id,
                            action=tool_call.tool_args["action"],
                            status="completed",
                        )
                    else:
                        messages.append(
                            ResponseFunctionToolCallParam(
                                type="function_call",
                                name=tool_call.tool_name,
                                arguments=json_dumps(tool_call.tool_args),
                                call_id=tool_call.id,
                            )
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
                    )
                )
                reasoning_summary = []
            elif isinstance(content.native, ImageGenerationCall):
                messages.append(
                    cast(ImageGenerationCallParam, content.native.to_dict())
                )

    return messages


async def _transform_stream(  # noqa: C901 - This is complex, but better to have it in one place
    chat_log: conversation.ChatLog,
    stream: AsyncStream[ResponseStreamEvent],
    remove_citations: bool = False,
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform an OpenAI delta stream into HA format."""
    last_summary_index = None
    last_role: Literal["assistant", "tool_result"] | None = None

    # Non-reasoning models don't follow our request to remove citations, so we remove
    # them manually here. They always follow the same pattern: the citation is always
    # in parentheses in Markdown format, the citation is always in a single delta event,
    # and sometimes the closing parenthesis is split into a separate delta event.
    remove_parentheses: bool = False
    citation_regexp = re.compile(r"\(\[([^\]]+)\]\((https?:\/\/[^\)]+)\)")

    async for event in stream:
        LOGGER.debug("Received event: %s", event)

        if isinstance(event, ResponseOutputItemAddedEvent):
            if isinstance(event.item, ResponseFunctionToolCall):
                # OpenAI has tool calls as individual events
                # while HA puts tool calls inside the assistant message.
                # We turn them into individual assistant content for HA
                # to ensure that tools are called as soon as possible.
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                current_tool_call = event.item
            elif (
                isinstance(event.item, ResponseOutputMessage)
                or (
                    isinstance(event.item, ResponseReasoningItem)
                    and last_summary_index is not None
                )  # Subsequent ResponseReasoningItem
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
                        summary=[],  # Remove summaries
                        encrypted_content=event.item.encrypted_content,
                    )
                }
                last_summary_index = len(event.item.summary) - 1
            elif isinstance(event.item, ResponseCodeInterpreterToolCall):
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="code_interpreter",
                            tool_args={
                                "code": event.item.code,
                                "container": event.item.container_id,
                            },
                            external=True,
                        )
                    ]
                }
                yield {
                    "role": "tool_result",
                    "tool_call_id": event.item.id,
                    "tool_name": "code_interpreter",
                    "tool_result": {
                        "output": (
                            [output.to_dict() for output in event.item.outputs]  # type: ignore[misc]
                            if event.item.outputs is not None
                            else None
                        )
                    },
                }
                last_role = "tool_result"
            elif isinstance(event.item, ResponseFunctionWebSearch):
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="web_search_call",
                            tool_args={
                                "action": event.item.action.to_dict(),
                            },
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
            elif isinstance(event.item, ImageGenerationCall):
                yield {"native": event.item}
                last_summary_index = -1  # Trigger new assistant message on next turn
        elif isinstance(event, ResponseTextDeltaEvent):
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
        elif isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
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
        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
            current_tool_call.arguments += event.delta
        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
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
        elif isinstance(event, ResponseCompletedEvent):
            if event.response.usage is not None:
                chat_log.async_trace(
                    {
                        "stats": {
                            "input_tokens": event.response.usage.input_tokens,
                            "output_tokens": event.response.usage.output_tokens,
                        }
                    }
                )
        elif isinstance(event, ResponseIncompleteEvent):
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
        elif isinstance(event, ResponseFailedEvent):
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
        elif isinstance(event, ResponseErrorEvent):
            raise HomeAssistantError(f"OpenAI response error: {event.message}")


class OpenAIBaseLLMEntity(Entity):
    """OpenAI conversation agent."""

    _attr_has_entity_name = True
    _attr_name: str | None = None

    def __init__(self, entry: OpenAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="OpenAI",
            model=subentry.data.get(
                CONF_CHAT_MODEL,
                RECOMMENDED_CHAT_MODEL
                if subentry.subentry_type != "stt"
                else RECOMMENDED_STT_MODEL,
            ),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
        force_image: bool = False,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data

        messages = _convert_content_to_param(chat_log.content)

        model_args = ResponseCreateParamsStreaming(
            model=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
            input=messages,
            max_output_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            user=chat_log.conversation_id,
            store=False,
            stream=True,
        )

        if model_args["model"].startswith(("o", "gpt-5")):
            model_args["reasoning"] = {
                "effort": options.get(
                    CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                )
                if not model_args["model"].startswith("gpt-5-pro")
                else "high",  # GPT-5 pro only supports reasoning.effort: high
                "summary": options.get(
                    CONF_REASONING_SUMMARY, RECOMMENDED_REASONING_SUMMARY
                ),
            }
            model_args["include"] = ["reasoning.encrypted_content"]

        if (
            not model_args["model"].startswith("gpt-5")
            or model_args["reasoning"]["effort"] == "none"  # type: ignore[index]
        ):
            model_args["top_p"] = options.get(CONF_TOP_P, RECOMMENDED_TOP_P)
            model_args["temperature"] = options.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            )

        if model_args["model"].startswith("gpt-5"):
            model_args["text"] = {
                "verbosity": options.get(CONF_VERBOSITY, RECOMMENDED_VERBOSITY)
            }

        if not model_args["model"].startswith(
            tuple(UNSUPPORTED_EXTENDED_CACHE_RETENTION_MODELS)
        ):
            model_args["prompt_cache_retention"] = "24h"

        tools: list[ToolParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        remove_citations = False
        if options.get(CONF_WEB_SEARCH):
            web_search = WebSearchToolParam(
                type="web_search",
                search_context_size=options.get(
                    CONF_WEB_SEARCH_CONTEXT_SIZE, RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE
                ),
            )
            if options.get(CONF_WEB_SEARCH_USER_LOCATION):
                web_search["user_location"] = UserLocation(
                    type="approximate",
                    city=options.get(CONF_WEB_SEARCH_CITY, ""),
                    region=options.get(CONF_WEB_SEARCH_REGION, ""),
                    country=options.get(CONF_WEB_SEARCH_COUNTRY, ""),
                    timezone=options.get(CONF_WEB_SEARCH_TIMEZONE, ""),
                )
            if not options.get(
                CONF_WEB_SEARCH_INLINE_CITATIONS,
                RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
            ):
                system_message = cast(EasyInputMessageParam, messages[0])
                content = system_message["content"]
                if isinstance(content, str):
                    system_message["content"] = [
                        ResponseInputTextParam(type="input_text", text=content)
                    ]
                system_message["content"].append(  # type: ignore[union-attr]
                    ResponseInputTextParam(
                        type="input_text",
                        text="When doing a web search, do not include source citations",
                    )
                )

                if "reasoning" not in model_args:
                    # Reasoning models handle this correctly with just a prompt
                    remove_citations = True

            tools.append(web_search)

        if options.get(CONF_CODE_INTERPRETER):
            tools.append(
                CodeInterpreter(
                    type="code_interpreter",
                    container=CodeInterpreterContainerCodeInterpreterToolAuto(
                        type="auto"
                    ),
                )
            )
            model_args.setdefault("include", []).append("code_interpreter_call.outputs")  # type: ignore[union-attr]

        if force_image:
            image_model = options.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL)
            image_tool = ImageGeneration(
                type="image_generation",
                model=image_model,
                output_format="png",
            )
            if image_model != "gpt-image-1-mini":
                image_tool["input_fidelity"] = "high"
            tools.append(image_tool)
            model_args["tool_choice"] = ToolChoiceTypesParam(type="image_generation")
            model_args["store"] = True  # Avoid sending image data back and forth

        if tools:
            model_args["tools"] = tools

        last_content = chat_log.content[-1]

        # Handle attachments by adding them to the last user message
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
            last_message["content"] = [
                {"type": "input_text", "text": last_message["content"]},  # type: ignore[list-item]
                *files,  # type: ignore[list-item]
            ]

        if structure and structure_name:
            model_args["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": slugify(structure_name),
                    "schema": _format_structured_output(structure, chat_log.llm_api),
                },
            }

        client = self.entry.runtime_data

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(max_iterations):
            try:
                stream = await client.responses.create(**model_args)

                messages.extend(
                    _convert_content_to_param(
                        [
                            content
                            async for content in chat_log.async_add_delta_content_stream(
                                self.entity_id,
                                _transform_stream(chat_log, stream, remove_citations),
                            )
                        ]
                    )
                )
            except openai.RateLimitError as err:
                LOGGER.error("Rate limited by OpenAI: %s", err)
                raise HomeAssistantError("Rate limited or insufficient funds") from err
            except openai.OpenAIError as err:
                if (
                    isinstance(err, openai.APIError)
                    and err.type == "insufficient_quota"
                ):
                    LOGGER.error("Insufficient funds for OpenAI: %s", err)
                    raise HomeAssistantError("Insufficient funds for OpenAI") from err
                if "Verify Organization" in str(err):
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        "organization_verification_required",
                        is_fixable=False,
                        is_persistent=False,
                        learn_more_url="https://help.openai.com/en/articles/10910291-api-organization-verification",
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="organization_verification_required",
                        translation_placeholders={
                            "platform_settings": "https://platform.openai.com/settings/organization/general"
                        },
                    )

                LOGGER.error("Error talking to OpenAI: %s", err)
                raise HomeAssistantError("Error talking to OpenAI") from err

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
                    "Only images and PDF are supported by the OpenAI API,"
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
