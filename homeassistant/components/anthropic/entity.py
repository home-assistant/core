"""Base entity for Anthropic."""

from collections.abc import AsyncGenerator, Callable, Iterable
import json
from typing import Any

import anthropic
from anthropic import AsyncStream
from anthropic.types import (
    CitationsDelta,
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
    TextDelta,
    ThinkingBlock,
    ThinkingBlockParam,
    ThinkingConfigDisabledParam,
    ThinkingConfigEnabledParam,
    ThinkingDelta,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
    ToolUseBlockParam,
    Usage,
    WebSearchToolResultBlock,
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
    CONF_WEB_SEARCH_MAX_USES,
    DOMAIN,
    LOGGER,
    MIN_THINKING_BUDGET,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_BUDGET,
    RECOMMENDED_WEB_SEARCH_MAX_USES,
    THINKING_MODELS,
    WEB_SEARCH_MODELS,
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
            tool_result_block = ToolResultBlockParam(
                type="tool_result",
                tool_use_id=content.tool_call_id,
                content=json.dumps(content.tool_result),
            )
            if not messages or messages[-1]["role"] != "user":
                messages.append(
                    MessageParam(
                        role="user",
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
            elif isinstance(content.native, WebSearchToolResultBlock):
                # Web search results must be preceded by their corresponding server_tool_use block
                # Find the matching tool call by tool_use_id
                if content.tool_calls:
                    for tool_call in content.tool_calls:
                        if (
                            tool_call.external
                            and tool_call.id == content.native.tool_use_id
                        ):
                            # Add the server_tool_use block first
                            messages[-1]["content"].append(  # type: ignore[union-attr]
                                ServerToolUseBlockParam(
                                    type="server_tool_use",
                                    id=tool_call.id,
                                    name=tool_call.tool_name,  # type: ignore[typeddict-item]
                                    input=tool_call.tool_args,
                                )
                            )
                            break
                # Then add the web_search_tool_result block
                messages[-1]["content"].append(  # type: ignore[union-attr]
                    content.native
                )
            elif isinstance(content.native, CitationsDelta):
                # Citations are handled as part of text blocks during reconstruction
                # They don't need to be explicitly added as separate blocks
                pass
            if content.content:
                messages[-1]["content"].append(  # type: ignore[union-attr]
                    TextBlockParam(type="text", text=content.content)
                )
            if content.tool_calls:
                for tool_call in content.tool_calls:
                    # Skip external tool calls that were already added with WebSearchToolResultBlock
                    if (
                        tool_call.external
                        and isinstance(content.native, WebSearchToolResultBlock)
                        and tool_call.id == content.native.tool_use_id
                    ):
                        continue
                    if tool_call.external:
                        # External tools (like web_search) use ServerToolUseBlockParam
                        messages[-1]["content"].append(  # type: ignore[union-attr]
                            ServerToolUseBlockParam(
                                type="server_tool_use",
                                id=tool_call.id,
                                name=tool_call.tool_name,  # type: ignore[typeddict-item]
                                input=tool_call.tool_args,
                            )
                        )
                    else:
                        # Regular tools use ToolUseBlockParam
                        messages[-1]["content"].append(  # type: ignore[union-attr]
                            ToolUseBlockParam(
                                type="tool_use",
                                id=tool_call.id,
                                name=tool_call.tool_name,
                                input=tool_call.tool_args,
                            )
                        )
        else:
            # Note: We don't pass SystemContent here as its passed to the API as the prompt
            raise TypeError(f"Unexpected content type: {type(content)}")

    return messages


async def _transform_stream(  # noqa: C901
    chat_log: conversation.ChatLog,
    stream: AsyncStream[MessageStreamEvent],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
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

    current_tool_block: ToolUseBlockParam | None = None
    current_tool_args: str = ""
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
            if isinstance(response.content_block, ToolUseBlock | ServerToolUseBlock):
                current_tool_block = ToolUseBlockParam(
                    type="tool_use",
                    id=response.content_block.id,
                    name=response.content_block.name,
                    input="",
                )
                current_tool_args = ""
            elif isinstance(response.content_block, WebSearchToolResultBlock):
                if has_native:
                    yield {"role": "assistant"}
                    has_native = False
                    has_content = False
                yield {"native": response.content_block}
                has_native = True
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
        elif isinstance(response, RawContentBlockDeltaEvent):
            if isinstance(response.delta, InputJSONDelta):
                current_tool_args += response.delta.partial_json
            elif isinstance(response.delta, TextDelta):
                yield {"content": response.delta.text}
            elif isinstance(response.delta, ThinkingDelta):
                yield {"thinking_content": response.delta.thinking}
            elif isinstance(response.delta, CitationsDelta):
                # Citations after WebSearchToolResultBlock need a new assistant message
                # because native content can only be set once per message
                if has_native:
                    yield {"role": "assistant"}
                    has_native = False
                    has_content = False
                yield {"native": response.delta}
                has_native = True
            elif isinstance(response.delta, SignatureDelta):
                yield {
                    "native": ThinkingBlock(
                        type="thinking",
                        thinking="",
                        signature=response.delta.signature,
                    )
                }
                has_native = True
        elif isinstance(response, RawContentBlockStopEvent):
            if current_tool_block is not None:
                tool_args = json.loads(current_tool_args) if current_tool_args else {}
                current_tool_block["input"] = tool_args
                # Check if this is a web search tool (external tool)
                is_external_tool = current_tool_block["name"] == "web_search"

                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_tool_block["id"],
                            tool_name=current_tool_block["name"],
                            tool_args=tool_args,
                            external=is_external_tool,
                        )
                    ]
                }
                current_tool_block = None
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

        tools: list[ToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        # Add web search tool if enabled and model supports it
        if options.get(CONF_WEB_SEARCH, False):
            model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
            if model in WEB_SEARCH_MODELS:
                web_search_tool = {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": int(
                        options.get(
                            CONF_WEB_SEARCH_MAX_USES, RECOMMENDED_WEB_SEARCH_MAX_USES
                        )
                    ),
                }
                if tools is None:
                    tools = []
                tools.append(web_search_tool)  # type: ignore[arg-type]

        system = chat_log.content[0]
        if not isinstance(system, conversation.SystemContent):
            raise TypeError("First message must be a system message")
        messages = _convert_content(chat_log.content[1:])

        client = self.entry.runtime_data

        thinking_budget = options.get(CONF_THINKING_BUDGET, RECOMMENDED_THINKING_BUDGET)
        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        model_args = MessageCreateParamsStreaming(
            model=model,
            messages=messages,
            max_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            system=system.content,
            stream=True,
        )
        if tools:
            model_args["tools"] = tools
        if (
            model.startswith(tuple(THINKING_MODELS))
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
