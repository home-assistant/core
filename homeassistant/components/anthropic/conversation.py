"""Conversation support for Anthropic."""

from collections.abc import AsyncGenerator, Callable, Iterable
import json
from typing import Any, Literal, cast

import anthropic
from anthropic import AsyncStream
from anthropic._types import NOT_GIVEN
from anthropic.types import (
    InputJSONDelta,
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
    RedactedThinkingBlock,
    RedactedThinkingBlockParam,
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
)
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnthropicConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    DOMAIN,
    LOGGER,
    MIN_THINKING_BUDGET,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_BUDGET,
    THINKING_MODELS,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthropicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = AnthropicConversationEntity(config_entry)
    async_add_entities([agent])


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

            if content.content:
                messages[-1]["content"].append(  # type: ignore[union-attr]
                    TextBlockParam(type="text", text=content.content)
                )
            if content.tool_calls:
                messages[-1]["content"].extend(  # type: ignore[union-attr]
                    [
                        ToolUseBlockParam(
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


async def _transform_stream(
    result: AsyncStream[MessageStreamEvent],
    messages: list[MessageParam],
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
    if result is None:
        raise TypeError("Expected a stream of messages")

    current_message: MessageParam | None = None
    current_block: (
        TextBlockParam
        | ToolUseBlockParam
        | ThinkingBlockParam
        | RedactedThinkingBlockParam
        | None
    ) = None
    current_tool_args: str

    async for response in result:
        LOGGER.debug("Received response: %s", response)

        if isinstance(response, RawMessageStartEvent):
            if response.message.role != "assistant":
                raise ValueError("Unexpected message role")
            current_message = MessageParam(role=response.message.role, content=[])
        elif isinstance(response, RawContentBlockStartEvent):
            if isinstance(response.content_block, ToolUseBlock):
                current_block = ToolUseBlockParam(
                    type="tool_use",
                    id=response.content_block.id,
                    name=response.content_block.name,
                    input="",
                )
                current_tool_args = ""
            elif isinstance(response.content_block, TextBlock):
                current_block = TextBlockParam(
                    type="text", text=response.content_block.text
                )
                yield {"role": "assistant"}
                if response.content_block.text:
                    yield {"content": response.content_block.text}
            elif isinstance(response.content_block, ThinkingBlock):
                current_block = ThinkingBlockParam(
                    type="thinking",
                    thinking=response.content_block.thinking,
                    signature=response.content_block.signature,
                )
            elif isinstance(response.content_block, RedactedThinkingBlock):
                current_block = RedactedThinkingBlockParam(
                    type="redacted_thinking", data=response.content_block.data
                )
                LOGGER.debug(
                    "Some of Claude’s internal reasoning has been automatically "
                    "encrypted for safety reasons. This doesn’t affect the quality of "
                    "responses"
                )
        elif isinstance(response, RawContentBlockDeltaEvent):
            if current_block is None:
                raise ValueError("Unexpected delta without a block")
            if isinstance(response.delta, InputJSONDelta):
                current_tool_args += response.delta.partial_json
            elif isinstance(response.delta, TextDelta):
                text_block = cast(TextBlockParam, current_block)
                text_block["text"] += response.delta.text
                yield {"content": response.delta.text}
            elif isinstance(response.delta, ThinkingDelta):
                thinking_block = cast(ThinkingBlockParam, current_block)
                thinking_block["thinking"] += response.delta.thinking
            elif isinstance(response.delta, SignatureDelta):
                thinking_block = cast(ThinkingBlockParam, current_block)
                thinking_block["signature"] += response.delta.signature
        elif isinstance(response, RawContentBlockStopEvent):
            if current_block is None:
                raise ValueError("Unexpected stop event without a current block")
            if current_block["type"] == "tool_use":
                # tool block
                tool_args = json.loads(current_tool_args) if current_tool_args else {}
                current_block["input"] = tool_args
                yield {
                    "tool_calls": [
                        llm.ToolInput(
                            id=current_block["id"],
                            tool_name=current_block["name"],
                            tool_args=tool_args,
                        )
                    ]
                }
            elif current_block["type"] == "thinking":
                # thinking block
                LOGGER.debug("Thinking: %s", current_block["thinking"])

            if current_message is None:
                raise ValueError("Unexpected stop event without a current message")
            current_message["content"].append(current_block)  # type: ignore[union-attr]
            current_block = None
        elif isinstance(response, RawMessageStopEvent):
            if current_message is not None:
                messages.append(current_message)
                current_message = None


class AnthropicConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Anthropic conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: AnthropicConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Anthropic",
            model="Claude",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if self.entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.entry.async_on_unload(
            self.entry.add_update_listener(self._async_entry_update_listener)
        )

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
        options = self.entry.options

        try:
            await chat_log.async_update_llm_data(
                DOMAIN,
                user_input,
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        tools: list[ToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        system = chat_log.content[0]
        if not isinstance(system, conversation.SystemContent):
            raise TypeError("First message must be a system message")
        messages = _convert_content(chat_log.content[1:])

        client = self.entry.runtime_data

        thinking_budget = options.get(CONF_THINKING_BUDGET, RECOMMENDED_THINKING_BUDGET)
        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            model_args = {
                "model": model,
                "messages": messages,
                "tools": tools or NOT_GIVEN,
                "max_tokens": options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
                "system": system.content,
                "stream": True,
            }
            if model in THINKING_MODELS and thinking_budget >= MIN_THINKING_BUDGET:
                model_args["thinking"] = ThinkingConfigEnabledParam(
                    type="enabled", budget_tokens=thinking_budget
                )
            else:
                model_args["thinking"] = ThinkingConfigDisabledParam(type="disabled")
                model_args["temperature"] = options.get(
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                )

            try:
                stream = await client.messages.create(**model_args)
            except anthropic.AnthropicError as err:
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to Anthropic: {err}"
                ) from err

            messages.extend(
                _convert_content(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            user_input.agent_id, _transform_stream(stream, messages)
                        )
                        if not isinstance(content, conversation.AssistantContent)
                    ]
                )
            )

            if not chat_log.unresponded_tool_results:
                break

        response_content = chat_log.content[-1]
        if not isinstance(response_content, conversation.AssistantContent):
            raise TypeError("Last message must be an assistant message")
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_content.content or "")
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=chat_log.continue_conversation,
        )

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
