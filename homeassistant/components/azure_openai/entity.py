"""Base entity for OpenAI."""

import base64
from collections.abc import AsyncGenerator, Callable, Iterable
import json
from mimetypes import guess_file_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

import openai
from openai._streaming import AsyncStream
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseCodeInterpreterToolCall,
    ResponseCodeInterpreterToolCallParam,
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
    ResponseTextDoneEvent,
    ToolChoiceTypesParam,
    ToolParam,
    WebSearchToolParam,
)
from openai.types.responses.response_code_interpreter_tool_call_param import (
    Output as CodeInterpreterOutputParam,
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
from openai.types.shared_params.reasoning import Reasoning
import probatio

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import json_dumps
from homeassistant.util import slugify

from .capabilities import RECOMMENDED_IMAGE_MODEL, get_capabilities
from .const import (
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_DEPLOYMENT,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_MODEL_FAMILY,
    CONF_PRO_MODE,
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
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_PRO_MODE,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_VERBOSITY,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
)
from .schema import adjust_schema

if TYPE_CHECKING:
    from . import OpenAIConfigEntry


MAX_TOOL_ITERATIONS = 10

SUPPORTED_ATTACHMENT_MIME_TYPES = {
    "application/pdf",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
_CITATION_OPENERS = (" ([", "([")
_CITATION_SCHEMES = ("http://", "https://")


def _citation_end(text: str, start: int) -> int | None:
    """Return the end of a complete citation, or None if it may be incomplete."""
    label_end = text.find("](", start + 2)
    if label_end in (-1, start + 2):
        return None

    url_start = label_end + 2
    remaining = text[url_start:]
    if not remaining.startswith(_CITATION_SCHEMES):
        if any(scheme.startswith(remaining) for scheme in _CITATION_SCHEMES):
            return None
        return -1

    depth = 0
    index = url_start
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth:
                depth -= 1
            elif index + 1 == len(text):
                return None
            elif text[index + 1] == ")":
                return index + 2
            else:
                return -1
        index += 1
    return None


def _filter_citations(text: str, *, final: bool = False) -> tuple[str, str]:
    """Remove complete citations and retain a possible incomplete suffix."""
    output: list[str] = []
    position = 0
    search_from = 0
    while (start := text.find("([", search_from)) != -1:
        citation_start = start - 1 if start and text[start - 1] == " " else start
        if (end := _citation_end(text, start)) == -1:
            search_from = start + 2
            continue
        if end is None:
            if not final:
                return "".join(output) + text[position:citation_start], text[
                    citation_start:
                ]
            search_from = start + 2
            continue
        output.append(text[position:citation_start])
        position = end
        search_from = end
    text = "".join(output) + text[position:]
    if final:
        return text, ""

    if (start := text.find("([")) != -1:
        if start and text[start - 1] == " ":
            start -= 1
        return text[:start], text[start:]

    pending = ""
    for opener in _CITATION_OPENERS:
        for length in range(1, len(opener)):
            prefix = opener[:length]
            if len(prefix) > len(pending) and text.endswith(prefix):
                pending = prefix
    if pending:
        return text[: -len(pending)], pending
    return text, ""


def _format_structured_output(
    schema: probatio.Schema, llm_api: llm.APIInstance | None
) -> dict[str, Any]:
    """Format the schema to be compatible with OpenAI API."""
    result: dict[str, Any] = probatio.to_openapi(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
        openapi_version="3.1.0",
    )

    adjust_schema(result)

    return result


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> FunctionToolParam:
    """Format tool specification."""
    unsupported_keys = {"oneOf", "anyOf", "allOf", "enum", "not"}
    schema = probatio.to_openapi(
        tool.parameters, custom_serializer=custom_serializer, openapi_version="3.1.0"
    )
    if unsupported_keys.intersection(schema):
        schema = {k: v for k, v in schema.items() if k not in unsupported_keys}

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
    """Convert any native chat message for this agent to the native format."""
    messages: ResponseInputParam = []
    reasoning_summary: list[str] = []
    web_search_calls: dict[str, ResponseFunctionWebSearchParam] = {}
    code_interpreter_calls: dict[str, llm.ToolInput] = {}

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            if (
                content.tool_name == "web_search_call"
                and content.tool_call_id in web_search_calls
            ):
                web_search_call = web_search_calls.pop(content.tool_call_id)
                web_search_call["status"] = content.result.data.get(  # type: ignore[typeddict-item]
                    "status", "completed"
                )
                messages.append(web_search_call)
            elif (
                content.tool_name == "code_interpreter"
                and content.tool_call_id in code_interpreter_calls
            ):
                tool_call = code_interpreter_calls.pop(content.tool_call_id)
                messages.append(
                    ResponseCodeInterpreterToolCallParam(
                        type="code_interpreter_call",
                        id=tool_call.id,
                        code=tool_call.tool_args["code"],
                        container_id=cast(str, content.result.data["container_id"]),
                        outputs=cast(
                            list[CodeInterpreterOutputParam] | None,
                            content.result.data["output"],
                        ),
                        status=content.result.data["status"],  # type: ignore[typeddict-item]
                    )
                )
            else:
                messages.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=content.tool_call_id,
                        output=json_dumps(
                            {
                                "data": content.result.data,
                                "error": content.result.error,
                            }
                        ),
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
                    elif (
                        tool_call.external and tool_call.tool_name == "code_interpreter"
                    ):
                        code_interpreter_calls[tool_call.id] = tool_call
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
    tool_calls: dict[str, ResponseFunctionToolCall] = {}
    citation_buffers: dict[tuple[str, int], str] = {}

    async for event in stream:
        LOGGER.debug("Received event: %s", event.type)

        if isinstance(event, ResponseOutputItemAddedEvent):
            if isinstance(event.item, ResponseFunctionToolCall):
                # HA embeds tool calls in assistant content, unlike OpenAI's separate
                # events, so emit assistant content as soon as each call arrives.
                yield {"role": "assistant"}
                last_role = "assistant"
                last_summary_index = None
                if event.item.id is None:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="provider_error",
                    )
                tool_calls[event.item.id] = event.item
            elif (
                isinstance(event.item, ResponseOutputMessage)
                or (
                    isinstance(event.item, ResponseReasoningItem)
                    and last_summary_index is not None
                )
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
            elif isinstance(event.item, ResponseCodeInterpreterToolCall):
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="code_interpreter",
                            tool_args={"code": event.item.code},
                            external=True,
                        )
                    ]
                }
                yield {
                    "role": "tool_result",
                    "tool_call_id": event.item.id,
                    "tool_name": "code_interpreter",
                    "result": llm.ToolResult(
                        data={
                            "container_id": event.item.container_id,
                            "output": (
                                [output.to_dict() for output in event.item.outputs]  # type: ignore[misc]
                                if event.item.outputs is not None
                                else None
                            ),
                            "status": event.item.status,
                        },
                        error=event.item.status == "failed",
                    ),
                }
                last_role = "tool_result"
            elif isinstance(event.item, ResponseFunctionWebSearch):
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=event.item.id,
                            tool_name="web_search_call",
                            tool_args={
                                "action": event.item.action.to_dict()
                                if event.item.action
                                else None,
                            },
                            external=True,
                        )
                    ]
                }
                yield {
                    "role": "tool_result",
                    "tool_call_id": event.item.id,
                    "tool_name": "web_search_call",
                    "result": llm.ToolResult(
                        data={"status": event.item.status},
                        error=event.item.status == "failed",
                    ),
                }
                last_role = "tool_result"
            elif isinstance(event.item, ImageGenerationCall):
                if last_summary_index is not None:
                    yield {"role": "assistant"}
                    last_role = "assistant"
                    last_summary_index = None
                yield {"native": event.item}
                last_summary_index = -1  # Trigger new assistant message on next turn
        elif isinstance(event, ResponseTextDeltaEvent):
            data = event.delta
            if remove_citations:
                key = (event.item_id, event.content_index)
                data, pending = _filter_citations(citation_buffers.pop(key, "") + data)
                if pending:
                    citation_buffers[key] = pending
            if data:
                yield {"content": data}
        elif isinstance(event, ResponseTextDoneEvent):
            if remove_citations:
                key = (event.item_id, event.content_index)
                if pending := citation_buffers.pop(key, ""):
                    data, _ = _filter_citations(pending, final=True)
                    if data:
                        yield {"content": data}
        elif isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            # Split multiple OpenAI summaries into separate assistant messages; only
            # the final summary carries the native reasoning item.
            if (
                last_summary_index is not None
                and event.summary_index != last_summary_index
            ):
                yield {"role": "assistant"}
                last_role = "assistant"
            last_summary_index = event.summary_index
            yield {"thinking_content": event.delta}
        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
            tool_calls[event.item_id].arguments += event.delta
        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
            tool_call = tool_calls.pop(event.item_id)
            tool_call.status = "completed"
            yield {
                "tool_calls": [
                    llm.ToolInput(
                        id=tool_call.call_id,
                        tool_name=tool_call.name,
                        tool_args=json.loads(tool_call.arguments),
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

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="response_incomplete",
                translation_placeholders={"reason": reason},
            )
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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="response_failed",
                translation_placeholders={"reason": reason},
            )
        elif isinstance(event, ResponseErrorEvent):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="response_error",
                translation_placeholders={"error": event.message},
            )

    for pending in citation_buffers.values():
        if data := _filter_citations(pending, final=True)[0]:
            yield {"content": data}


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
            manufacturer="Azure OpenAI",
            model=subentry.data[CONF_CHAT_MODEL],
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    def _raise_openai_error(self, err: openai.OpenAIError) -> NoReturn:
        """Raise a translated Home Assistant error for an OpenAI error."""
        if isinstance(err, openai.AuthenticationError):
            self.entry.async_start_reauth(self.hass)
            LOGGER.error("Authentication failed for Azure OpenAI: %s", err)
            translation_key = "provider_error"
        elif isinstance(err, openai.RateLimitError):
            LOGGER.error("Rate limited by Azure OpenAI: %s", err)
            translation_key = "rate_limited"
        elif isinstance(err, openai.APIError) and err.type == "insufficient_quota":
            LOGGER.error("Insufficient funds for Azure OpenAI: %s", err)
            translation_key = "insufficient_quota"
        else:
            LOGGER.error("Error talking to Azure OpenAI: %s", err)
            translation_key = "provider_error"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
        ) from err

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: probatio.Schema | None = None,
        force_image: bool = False,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data
        capabilities = get_capabilities(options.get(CONF_MODEL_FAMILY, ""))

        messages = _convert_content_to_param(chat_log.content)

        model_args = ResponseCreateParamsStreaming(
            model=options[CONF_CHAT_MODEL],
            input=messages,
            max_output_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            prompt_cache_key=self.subentry.subentry_id,
            store=False,
            stream=True,
        )

        effort = None
        if capabilities.reasoning:
            effort = capabilities.reasoning_effort(
                options.get(CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT)
            )
            reasoning: Reasoning = {
                "effort": effort,
            }

            reasoning_summary = options.get(
                CONF_REASONING_SUMMARY, RECOMMENDED_REASONING_SUMMARY
            )
            if (
                reasoning_summary != "off"
                and reasoning_summary in capabilities.reasoning_summary
            ):
                reasoning["summary"] = reasoning_summary

            if "pro" in capabilities.features and options.get(
                CONF_PRO_MODE, RECOMMENDED_PRO_MODE
            ):
                reasoning["mode"] = "pro"

            model_args["reasoning"] = reasoning
            model_args["include"] = ["reasoning.encrypted_content"]

        if capabilities.supports_sampling(effort):
            model_args["top_p"] = options.get(CONF_TOP_P, RECOMMENDED_TOP_P)
            model_args["temperature"] = options.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            )

        if "verbosity" in capabilities.features:
            model_args["text"] = {
                "verbosity": options.get(CONF_VERBOSITY, RECOMMENDED_VERBOSITY)
            }

        if "cache30" in capabilities.features:
            model_args["prompt_cache_options"] = {"ttl": "30m"}
        elif "cache24" in capabilities.features:
            model_args["prompt_cache_retention"] = "24h"

        tools: list[ToolParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        remove_citations = False
        if (
            "web" in capabilities.features
            and effort != "minimal"
            and options.get(CONF_WEB_SEARCH)
        ):
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

                if not capabilities.reasoning or "verbosity" in capabilities.features:
                    # o-series models handle this correctly with just a prompt
                    remove_citations = True

            tools.append(web_search)

        if (
            "code" in capabilities.features
            and effort != "minimal"
            and options.get(CONF_CODE_INTERPRETER)
        ):
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
            tools.append(
                ImageGeneration(
                    type="image_generation",
                    model=options.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL),
                    output_format="png",
                )
            )
            # Store the generated image so follow-up requests can reference its
            # image-generation call ID without resending the image data.
            model_args["store"] = True
            model_args["tool_choice"] = ToolChoiceTypesParam(type="image_generation")
            # Azure routes the image generation tool to a deployment via this
            # header; the tool's "model" field only selects the base model.
            model_args["extra_headers"] = {  # type: ignore[typeddict-unknown-key]
                "x-ms-oai-image-generation-deployment": cast(
                    str, options[CONF_IMAGE_DEPLOYMENT]
                )
            }

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
            last_message["content"] = [
                {"type": "input_text", "text": last_message["content"]},
                *files,
            ]

        if structure and structure_name:
            model_args.setdefault("text", {})["format"] = {
                "type": "json_schema",
                "name": slugify(structure_name),
                "schema": _format_structured_output(structure, chat_log.llm_api),
                "strict": True,
            }

        client = self.entry.runtime_data

        for _iteration in range(max_iterations):
            try:
                stream = await client.responses.create(**model_args)

                content_stream = chat_log.async_add_delta_content_stream(
                    self.entity_id,
                    _transform_stream(chat_log, stream, remove_citations),
                )
                messages.extend(
                    _convert_content_to_param(
                        [content async for content in content_stream]
                    )
                )
            except openai.OpenAIError as err:
                self._raise_openai_error(err)

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
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="attachment_missing",
                    translation_placeholders={"file_path": str(file_path)},
                )

            if mime_type is None:
                mime_type = guess_file_type(file_path)[0]

            if mime_type not in SUPPORTED_ATTACHMENT_MIME_TYPES:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="attachment_unsupported",
                    translation_placeholders={"file_path": str(file_path)},
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
            else:
                content.append(
                    ResponseInputFileParam(
                        type="input_file",
                        filename=file_path.name,
                        file_data=f"data:{mime_type};base64,{base64_file}",
                    )
                )

        return content

    return await hass.async_add_executor_job(append_files_to_content)
