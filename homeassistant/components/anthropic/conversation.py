"""Conversation support for Anthropic."""

from collections.abc import Callable
import json
from typing import Any, Literal, cast

import anthropic
from anthropic._types import NOT_GIVEN
from anthropic.types import (
    Message,
    MessageParam,
    TextBlock,
    TextBlockParam,
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
from homeassistant.helpers import chat_session, device_registry as dr, intent, llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AnthropicConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthropicConfigEntry,
    async_add_entities: AddEntitiesCallback,
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


def _message_convert(
    message: Message,
) -> MessageParam:
    """Convert from class to TypedDict."""
    param_content: list[TextBlockParam | ToolUseBlockParam] = []

    for message_content in message.content:
        if isinstance(message_content, TextBlock):
            param_content.append(TextBlockParam(type="text", text=message_content.text))
        elif isinstance(message_content, ToolUseBlock):
            param_content.append(
                ToolUseBlockParam(
                    type="tool_use",
                    id=message_content.id,
                    name=message_content.name,
                    input=message_content.input,
                )
            )

    return MessageParam(role=message.role, content=param_content)


def _convert_content(chat_content: conversation.Content) -> MessageParam:
    """Create tool response content."""
    if isinstance(chat_content, conversation.ToolResultContent):
        return MessageParam(
            role="user",
            content=[
                ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=chat_content.tool_call_id,
                    content=json.dumps(chat_content.tool_result),
                )
            ],
        )
    if isinstance(chat_content, conversation.AssistantContent):
        return MessageParam(
            role="assistant",
            content=[
                TextBlockParam(type="text", text=chat_content.content or ""),
                *[
                    ToolUseBlockParam(
                        type="tool_use",
                        id=tool_call.id,
                        name=tool_call.tool_name,
                        input=json.dumps(tool_call.tool_args),
                    )
                    for tool_call in chat_content.tool_calls or ()
                ],
            ],
        )
    if isinstance(chat_content, conversation.UserContent):
        return MessageParam(
            role="user",
            content=chat_content.content,
        )
    # Note: We don't pass SystemContent here as its passed to the API as the prompt
    raise ValueError(f"Unexpected content type: {type(chat_content)}")


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

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        with (
            chat_session.async_get_chat_session(
                self.hass, user_input.conversation_id
            ) as session,
            conversation.async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            return await self._async_handle_message(user_input, chat_log)

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
        messages = [_convert_content(content) for content in chat_log.content[1:]]

        client = self.entry.runtime_data

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                response = await client.messages.create(
                    model=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
                    messages=messages,
                    tools=tools or NOT_GIVEN,
                    max_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
                    system=system.content,
                    temperature=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
                )
            except anthropic.AnthropicError as err:
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to Anthropic: {err}"
                ) from err

            LOGGER.debug("Response %s", response)

            messages.append(_message_convert(response))

            text = "".join(
                [
                    content.text
                    for content in response.content
                    if isinstance(content, TextBlock)
                ]
            )
            tool_inputs = [
                llm.ToolInput(
                    id=tool_call.id,
                    tool_name=tool_call.name,
                    tool_args=cast(dict[str, Any], tool_call.input),
                )
                for tool_call in response.content
                if isinstance(tool_call, ToolUseBlock)
            ]

            tool_results = [
                ToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=tool_response.tool_call_id,
                    content=json.dumps(tool_response.tool_result),
                )
                async for tool_response in chat_log.async_add_assistant_content(
                    conversation.AssistantContent(
                        agent_id=user_input.agent_id,
                        content=text,
                        tool_calls=tool_inputs or None,
                    )
                )
            ]
            if tool_results:
                messages.append(MessageParam(role="user", content=tool_results))

            if not tool_inputs:
                break

        response_content = chat_log.content[-1]
        if not isinstance(response_content, conversation.AssistantContent):
            raise TypeError("Last message must be an assistant message")
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_content.content or "")
        return conversation.ConversationResult(
            response=intent_response, conversation_id=chat_log.conversation_id
        )

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
