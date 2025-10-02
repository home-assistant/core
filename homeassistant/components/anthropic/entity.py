"""Base entity for Anthropic."""

from collections.abc import AsyncGenerator, Callable, Iterable
import json
from typing import Any

import anthropic
from anthropic import AsyncStream
from anthropic.types import (
    CitationsDelta,
    CitationsWebSearchResultLocation,
    CitationWebSearchResultLocationParam,
    ContentBlockParam,
    InputJSONDelta,
    MessageDeltaUsage,
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    RedactedThinkingBlock,
    RedactedThinkingBlockParam,
    ServerToolUseBlock,
    ServerToolUseBlockParam,
    SignatureDelta,
    TextBlock,
    TextBlockParam,
    TextCitation,
    TextCitationParam,
    TextDelta,
    ThinkingBlock,
    ThinkingBlockParam,
    ThinkingConfigDisabledParam,
    ThinkingConfigEnabledParam,
    ThinkingDelta,
    ToolParam,
    ToolResultBlockParam,
    ToolUnionParam,
    ToolUseBlock,
    ToolUseBlockParam,
    Usage,
    WebSearchResultBlockParam,
    WebSearchTool20250305Param,
    WebSearchToolRequestErrorParam,
    WebSearchToolResultBlock,
    WebSearchToolResultBlockParam,
    WebSearchToolResultError,
)
from anthropic.types.message_create_params import MessageCreateParamsStreaming
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from . import AnthropicConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DOMAIN,
    LOGGER,
    MIN_THINKING_BUDGET,
    NON_THINKING_MODELS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_BUDGET,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> ToolParam:
    """Format tool specification."""
    return ToolParam(
        name=tool.name,
        description=tool.description or "",
        input_schema=convert(tool.parameters, custom_serializer=custom_serializer),
    )


def _convert_content(
    chat_content: Iterable[conversation.Content],
) -> list[MessageParam]:
    """Transform HA chat_log content into Anthropic API format."""
    messages: list[MessageParam] = []

    for content in chat_content:
        if isinstance(content, conversation.ToolResultContent):
            if content.tool_name == "web_search":
                tool_result_block: ContentBlockParam = WebSearchToolResultBlockParam(
                    type="web_search_tool_result",
                    tool_use_id=content.tool_call_id,
                    content=[
                        WebSearchResultBlockParam(
                            type="web_search_result",
                            encrypted_content=result.get("encrypted_content", ""),
                            page_age=result.get("page_age", ""),
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                        )
                        for result in content.tool_result["content"]
                    ]
                    if isinstance(content.tool_result, list)
                    else WebSearchToolRequestErrorParam(
                        type="web_search_tool_result_error",
                        error_code=content.tool_result.get("error_code", "unavailable"),  # type: ignore[typeddict-item]
                    ),
                )
                external_tool = True
            else:
                tool_result_block = ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=content.tool_call_id,
                    content=json.dumps(content.tool_result),
                )
                external_tool = False
            if (
                not messages or messages[-1]["role"] != "assistant"
                if external_tool
                else "user"
            ):
                messages.append(
                    MessageParam(
                        role="assistant" if external_tool else "user",
                        content=[tool_result_block],
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    tool_result_block,
                ]
            else:
                messages[-1]["content"].append(tool_result_block)  # type: ignore[attr-defined]
        elif isinstance(content, conversation.UserContent):
            # Combine consequent user messages
            if not messages or messages[-1]["role"] != "user":
                messages.append(
                    MessageParam(
                        role="user",
                        content=content.content,
                    )
                )
            elif isinstance(messages[-1]["content"], str):
                messages[-1]["content"] = [
                    TextBlockParam(type="text", text=messages[-1]["content"]),
                    TextBlockParam(type="text", text=content.content),
                ]
            else:
                messages[-1]["content"].append(  # type: ignore[attr-defined]
                    TextBlockParam(type="text", text=content.content)
                )
        elif isinstance(content, conversation.AssistantContent):
            # Combine consequent assistant messages
            if not messages or messages[-1]["role"] != "assistant":
                messages.append(
                    MessageParam(
                        role="assistant",
                        content=[],
                    )
                )

            if isinstance(content.native, ThinkingBlock):
                messages[-1]["content"].append(  # type: ignore[union-attr]
                    ThinkingBlockParam(
                        type="thinking",
                        thinking=content.thinking_content or "",
                        signature=content.native.signature,
                    )
                )
            elif isinstance(content.native, RedactedThinkingBlock):
                redacted_thinking_block = RedactedThinkingBlockParam(
                    type="redacted_thinking",
                    data=content.native.data,
                )
                if isinstance(messages[-1]["content"], str):
                    messages[-1]["content"] = [
                        TextBlockParam(type="text", text=messages[-1]["content"]),
                        redacted_thinking_block,
                    ]
                else:
                    messages[-1]["content"].append(  # type: ignore[attr-defined]
                        redacted_thinking_block
                    )
            if content.content:
                citations: list[TextCitationParam] = []
                if isinstance(content.native, list):
                    citations.extend(
                        CitationWebSearchResultLocationParam(
                            type="web_search_result_location",
                            title=citation.title,
                            url=citation.url,
                            cited_text=citation.cited_text,
                            encrypted_index=citation.encrypted_index,
                        )
                        for citation in content.native
                        if isinstance(citation, CitationsWebSearchResultLocation)
                    )
                messages[-1]["content"].append(  # type: ignore[union-attr]
                    TextBlockParam(
                        type="text",
                        text=content.content,
                        citations=citations if citations else None,
                    )
                )
            if content.tool_calls:
                messages[-1]["content"].extend(  # type: ignore[union-attr]
                    [
                        ServerToolUseBlockParam(
                            type="server_tool_use",
                            id=tool_call.id,
                            name="web_search",
                            input=tool_call.tool_args,
                        )
                        if tool_call.external and tool_call.tool_name == "web_search"
                        else ToolUseBlockParam(
                            type="tool_use",
                            id=tool_call.id,
                            name=tool_call.tool_name,
                            input=tool_call.tool_args,
                        )
                        for tool_call in content.tool_calls
                    ]
                )
        else:
            # Note: We don't pass SystemContent here as its passed to the API as the prompt
            raise TypeError(f"Unexpected content type: {type(content)}")

    return messages


async def _transform_stream(  # noqa: C901 - This is complex, but better to have it in one place
    chat_log: conversation.ChatLog,
    stream: AsyncStream[MessageStreamEvent],
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform the response stream into HA format.

    A typical stream of responses might look something like the following:
    - RawMessageStartEvent with no content
    - RawContentBlockStartEvent with an empty ThinkingBlock (if extended thinking is enabled)
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - RawContentBlockDeltaEvent with a ThinkingDelta
    - ...
    - RawContentBlockDeltaEvent with a SignatureDelta
    - RawContentBlockStopEvent
    - RawContentBlockStartEvent with a RedactedThinkingBlock (occasionally)
    - RawContentBlockStopEvent (RedactedThinkingBlock does not have a delta)
    - RawContentBlockStartEvent with an empty TextBlock
    - RawContentBlockDeltaEvent with a TextDelta
    - RawContentBlockDeltaEvent with a TextDelta
    - RawContentBlockDeltaEvent with a TextDelta
    - ...
    - RawContentBlockStopEvent
    - RawContentBlockStartEvent with ToolUseBlock specifying the function name
    - RawContentBlockDeltaEvent with a InputJSONDelta
    - RawContentBlockDeltaEvent with a InputJSONDelta
    - ...
    - RawContentBlockStopEvent
    - RawMessageDeltaEvent with a stop_reason='tool_use'
    - RawMessageStopEvent(type='message_stop')

    Each message could contain multiple blocks of the same type.
    """
    if stream is None:
        raise TypeError("Expected a stream of messages")

    current_tool_block: ToolUseBlockParam | ServerToolUseBlockParam | None = None
    current_tool_args: str
    citations: list[TextCitation] = []
    input_usage: Usage | None = None
    has_content = False
    has_native = False

    async for response in stream:
        LOGGER.debug("Received response: %s", response)

        if isinstance(response, RawMessageStartEvent):
            if response.message.role != "assistant":
                raise ValueError("Unexpected message role")
            input_usage = response.message.usage
        elif isinstance(response, RawContentBlockStartEvent):
            if isinstance(response.content_block, ToolUseBlock):
                current_tool_block = ToolUseBlockParam(
                    type="tool_use",
                    id=response.content_block.id,
                    name=response.content_block.name,
                    input="",
                )
                current_tool_args = ""
            elif isinstance(response.content_block, TextBlock):
                if has_content:
                    yield {"role": "assistant"}
                    has_native = False
                has_content = True
                if response.content_block.text:
                    yield {"content": response.content_block.text}
            elif isinstance(response.content_block, ThinkingBlock):
                if has_native:
                    yield {"role": "assistant"}
                    has_native = False
                    has_content = False
            elif isinstance(response.content_block, RedactedThinkingBlock):
                LOGGER.debug(
                    "Some of Claude’s internal reasoning has been automatically "
                    "encrypted for safety reasons. This doesn’t affect the quality of "
                    "responses"
                )
                if has_native:
                    yield {"role": "assistant"}
                    has_native = False
                    has_content = False
                yield {"native": response.content_block}
                has_native = True
            elif isinstance(response.content_block, ServerToolUseBlock):
                current_tool_block = ServerToolUseBlockParam(
                    type="server_tool_use",
                    id=response.content_block.id,
                    name=response.content_block.name,
                    input="",
                )
                current_tool_args = ""
            elif isinstance(response.content_block, WebSearchToolResultBlock):
                yield {
                    "role": "tool_result",
                    "tool_call_id": response.content_block.tool_use_id,
                    "tool_name": "web_search",
                    "tool_result": {
                        "type": "web_search_tool_result_error",
                        "error_code": response.content_block.content.error_code,
                    }
                    if isinstance(
                        response.content_block.content, WebSearchToolResultError
                    )
                    else {
                        "content": [
                            {
                                "type": "web_search_result",
                                "encrypted_content": block.encrypted_content,
                                "page_age": block.page_age,
                                "title": block.title,
                                "url": block.url,
                            }
                            for block in response.content_block.content
                        ]
                    },
                }
        elif isinstance(response, RawContentBlockDeltaEvent):
            if isinstance(response.delta, InputJSONDelta):
                current_tool_args += response.delta.partial_json
            elif isinstance(response.delta, TextDelta):
                yield {"content": response.delta.text}
            elif isinstance(response.delta, ThinkingDelta):
                yield {"thinking_content": response.delta.thinking}
            elif isinstance(response.delta, SignatureDelta):
                yield {
                    "native": ThinkingBlock(
                        type="thinking",
                        thinking="",
                        signature=response.delta.signature,
                    )
                }
                has_native = True
            elif isinstance(response.delta, CitationsDelta):
                citations.append(response.delta.citation)
        elif isinstance(response, RawContentBlockStopEvent):
            if current_tool_block is not None:
                tool_args = json.loads(current_tool_args) if current_tool_args else {}
                current_tool_block["input"] = tool_args
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_tool_block["id"],
                            tool_name=current_tool_block["name"],
                            tool_args=tool_args,
                            external=current_tool_block["type"] == "server_tool_use",
                        )
                    ]
                }
                current_tool_block = None
            if citations:
                if not has_native:
                    yield {"native": citations}
                citations = []
        elif isinstance(response, RawMessageDeltaEvent):
            if (usage := response.usage) is not None:
                chat_log.async_trace(_create_token_stats(input_usage, usage))
            if response.delta.stop_reason == "refusal":
                raise HomeAssistantError("Potential policy violation detected")


def _create_token_stats(
    input_usage: Usage | None, response_usage: MessageDeltaUsage
) -> dict[str, Any]:
    """Create token stats for conversation agent tracing."""
    input_tokens = 0
    cached_input_tokens = 0
    if input_usage:
        input_tokens = input_usage.input_tokens
        cached_input_tokens = input_usage.cache_creation_input_tokens or 0
    output_tokens = response_usage.output_tokens
    return {
        "stats": {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
        }
    }


class AnthropicBaseLLMEntity(Entity):
    """Anthropic base LLM entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: AnthropicConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Anthropic",
            model="Claude",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data

        system = chat_log.content[0]
        if not isinstance(system, conversation.SystemContent):
            raise TypeError("First message must be a system message")
        messages = _convert_content(chat_log.content[1:])

        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        model_args = MessageCreateParamsStreaming(
            model=model,
            messages=messages,
            max_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            system=system.content,
            stream=True,
        )

        thinking_budget = options.get(CONF_THINKING_BUDGET, RECOMMENDED_THINKING_BUDGET)
        if (
            not model.startswith(tuple(NON_THINKING_MODELS))
            and thinking_budget >= MIN_THINKING_BUDGET
        ):
            model_args["thinking"] = ThinkingConfigEnabledParam(
                type="enabled", budget_tokens=thinking_budget
            )
        else:
            model_args["thinking"] = ThinkingConfigDisabledParam(type="disabled")
            model_args["temperature"] = options.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            )

        tools: list[ToolUnionParam] = []
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if options.get(CONF_WEB_SEARCH):
            web_search = WebSearchTool20250305Param(
                name="web_search",
                type="web_search_20250305",
                max_uses=options.get(CONF_WEB_SEARCH_MAX_USES),
            )
            if options.get(CONF_WEB_SEARCH_USER_LOCATION):
                web_search["user_location"] = {
                    "type": "approximate",
                    "city": options.get(CONF_WEB_SEARCH_CITY, ""),
                    "region": options.get(CONF_WEB_SEARCH_REGION, ""),
                    "country": options.get(CONF_WEB_SEARCH_COUNTRY, ""),
                    "timezone": options.get(CONF_WEB_SEARCH_TIMEZONE, ""),
                }
            tools.append(web_search)

        if tools:
            model_args["tools"] = tools

        client = self.entry.runtime_data

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                stream = await client.messages.create(**model_args)

                messages.extend(
                    _convert_content(
                        [
                            content
                            async for content in chat_log.async_add_delta_content_stream(
                                self.entity_id,
                                _transform_stream(chat_log, stream),
                            )
                        ]
                    )
                )
            except anthropic.AnthropicError as err:
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to Anthropic: {err}"
                ) from err

            if not chat_log.unresponded_tool_results:
                break
