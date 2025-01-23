"""Conversation support for OpenAI."""

from collections.abc import Callable
import json
from typing import Any, Literal, cast

import openai
from openai._types import NOT_GIVEN
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_message_tool_call_param import Function
from openai.types.shared_params import FunctionDefinition
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.json import JsonObjectType

from . import OpenAIConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenAIConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = OpenAIConversationEntity(config_entry)
    async_add_entities([agent])


class OpenAIChatMessageConverter(
    conversation.ChatMessageConverter[
        ChatCompletionMessageParam, ChatCompletionToolParam, ChatCompletionMessage
    ]
):
    """Class to convert chat messages to the native format."""

    def convert(
        self, message: conversation.ChatMessage[ChatCompletionMessageParam]
    ) -> ChatCompletionMessageParam:
        """Convert a chat message to the native format."""
        return cast(
            ChatCompletionMessageParam,
            {"role": message.role, "content": message.content},
        )

    def convert_tool(
        self, tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
    ) -> ChatCompletionToolParam:
        """Convert a tool to the native format."""
        tool_spec = FunctionDefinition(
            name=tool.name,
            parameters=convert(tool.parameters, custom_serializer=custom_serializer),
        )
        if tool.description:
            tool_spec["description"] = tool.description
        return ChatCompletionToolParam(type="function", function=tool_spec)

    def convert_response(
        self, agent_id: str | None, response: ChatCompletionMessage
    ) -> tuple[
        conversation.ChatMessage[ChatCompletionMessageParam], list[llm.ToolInput]
    ]:
        """Convert a native response to the Home Assistant LLM format."""
        response_message = _message_convert(response)
        chat_message = conversation.ChatMessage[ChatCompletionMessageParam](
            role=response.role,
            agent_id=agent_id,
            content=response.content or "",
            native=response_message,
        )
        tool_inputs: list[llm.ToolInput] = [
            llm.ToolInput(
                tool_name=tool_call.function.name,
                tool_args=json.loads(tool_call.function.arguments),
                tool_call_id=tool_call.id,
            )
            for tool_call in response.tool_calls or ()
        ]
        return chat_message, tool_inputs

    def convert_tool_response(
        self, tool_call_id: str | None, tool_response: JsonObjectType
    ) -> ChatCompletionMessageParam:
        """Convert a Home Assistant tool call response to the native format."""
        if tool_call_id is None:
            raise ValueError("tool_call_id is required")
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=tool_call_id,
            content=json.dumps(tool_response),
        )


def _message_convert(message: ChatCompletionMessage) -> ChatCompletionMessageParam:
    """Convert from class to TypedDict."""
    tool_calls: list[ChatCompletionMessageToolCallParam] = []
    if message.tool_calls:
        tool_calls = [
            ChatCompletionMessageToolCallParam(
                id=tool_call.id,
                function=Function(
                    arguments=tool_call.function.arguments,
                    name=tool_call.function.name,
                ),
                type=tool_call.type,
            )
            for tool_call in message.tool_calls
        ]
    param = ChatCompletionAssistantMessageParam(
        role=message.role,
        content=message.content,
    )
    if tool_calls:
        param["tool_calls"] = tool_calls
    return param


class OpenAIConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """OpenAI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: OpenAIConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenAI",
            model="ChatGPT",
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
        assist_pipeline.async_migrate_engine(
            self.hass, "conversation", self.entry.entry_id, self.entity_id
        )
        conversation.async_set_agent(self.hass, self.entry, self)
        self.entry.async_on_unload(
            self.entry.add_update_listener(self._async_entry_update_listener)
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        async with conversation.async_get_chat_session(
            self.hass,
            user_input,
        ) as session:
            options = self.entry.options

            try:
                await session.async_update_llm_data(
                    DOMAIN,
                    user_input,
                    options.get(CONF_LLM_HASS_API),
                    options.get(CONF_PROMPT),
                )
            except conversation.ConverseError as err:
                return err.as_conversation_result()

            return await session.async_model_loop(
                user_input, self._async_call_native_api, OpenAIChatMessageConverter()
            )

    async def _async_call_native_api(
        self,
        user_input: conversation.ConversationInput,
        conversation_id: str,
        messages: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionToolParam] | None,
    ) -> ChatCompletionMessage:
        """Send a message to the agent."""
        options = self.entry.options
        client = self.entry.runtime_data
        try:
            result = await client.chat.completions.create(
                model=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
                messages=messages,
                tools=tools or NOT_GIVEN,
                max_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
                top_p=options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
                temperature=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
                user=conversation_id,
            )
        except openai.OpenAIError as err:
            LOGGER.error("Error talking to OpenAI: %s", err)
            raise conversation.ConversationAgentError(
                "Sorry, I had a problem talking to OpenAI",
                conversation_id,
                user_input.language,
            ) from err

        return result.choices[0].message

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
