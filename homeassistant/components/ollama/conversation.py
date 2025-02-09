"""The conversation platform for the Ollama integration."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any, Literal

import ollama
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, intent, llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MAX_HISTORY,
    DEFAULT_NUM_CTX,
    DOMAIN,
)
from .models import MessageHistory, MessageRole

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = OllamaConversationEntity(config_entry)
    async_add_entities([agent])


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    """Format tool specification."""
    tool_spec = {
        "name": tool.name,
        "parameters": convert(tool.parameters, custom_serializer=custom_serializer),
    }
    if tool.description:
        tool_spec["description"] = tool.description
    return {"type": "function", "function": tool_spec}


def _fix_invalid_arguments(value: Any) -> Any:
    """Attempt to repair incorrectly formatted json function arguments.

    Small models (for example llama3.1 8B) may produce invalid argument values
    which we attempt to repair here.
    """
    if not isinstance(value, str):
        return value
    if (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        try:
            return json.loads(value)
        except json.decoder.JSONDecodeError:
            pass
    return value


def _parse_tool_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Rewrite ollama tool arguments.

    This function improves tool use quality by fixing common mistakes made by
    small local tool use models. This will repair invalid json arguments and
    omit unnecessary arguments with empty values that will fail intent parsing.
    """
    return {k: _fix_invalid_arguments(v) for k, v in arguments.items() if v}


def _convert_content(
    chat_content: conversation.Content
    | conversation.ToolResultContent
    | conversation.AssistantContent,
) -> ollama.Message:
    """Create tool response content."""
    if isinstance(chat_content, conversation.ToolResultContent):
        return ollama.Message(
            role=MessageRole.TOOL.value,
            content=json.dumps(chat_content.tool_result),
        )
    if isinstance(chat_content, conversation.AssistantContent):
        return ollama.Message(
            role=MessageRole.ASSISTANT.value,
            content=chat_content.content,
            tool_calls=[
                ollama.Message.ToolCall(
                    function=ollama.Message.ToolCall.Function(
                        name=tool_call.tool_name,
                        arguments=tool_call.tool_args,
                    )
                )
                for tool_call in chat_content.tool_calls or ()
            ],
        )
    if isinstance(chat_content, conversation.UserContent):
        return ollama.Message(
            role=MessageRole.USER.value,
            content=chat_content.content,
        )
    if isinstance(chat_content, conversation.SystemContent):
        return ollama.Message(
            role=MessageRole.SYSTEM.value,
            content=chat_content.content,
        )
    raise ValueError(f"Unexpected content type: {type(chat_content)}")


class OllamaConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Ollama conversation agent."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry

        # conversation id -> message history
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id
        if self.entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

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

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

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
        settings = {**self.entry.data, **self.entry.options}

        client = self.hass.data[DOMAIN][self.entry.entry_id]
        model = settings[CONF_MODEL]

        try:
            await chat_log.async_update_llm_data(
                DOMAIN,
                user_input,
                settings.get(CONF_LLM_HASS_API),
                settings.get(CONF_PROMPT),
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        tools: list[dict[str, Any]] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        message_history: MessageHistory = MessageHistory(
            [_convert_content(content) for content in chat_log.content]
        )
        max_messages = int(settings.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY))
        self._trim_history(message_history, max_messages)

        # Get response
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                response = await client.chat(
                    model=model,
                    # Make a copy of the messages because we mutate the list later
                    messages=list(message_history.messages),
                    tools=tools,
                    stream=False,
                    # keep_alive requires specifying unit. In this case, seconds
                    keep_alive=f"{settings.get(CONF_KEEP_ALIVE, DEFAULT_KEEP_ALIVE)}s",
                    options={CONF_NUM_CTX: settings.get(CONF_NUM_CTX, DEFAULT_NUM_CTX)},
                )
            except (ollama.RequestError, ollama.ResponseError) as err:
                _LOGGER.error("Unexpected error talking to Ollama server: %s", err)
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to the Ollama server: {err}"
                ) from err

            response_message = response["message"]
            content = response_message.get("content")
            tool_calls = response_message.get("tool_calls")
            message_history.messages.append(
                ollama.Message(
                    role=response_message["role"],
                    content=content,
                    tool_calls=tool_calls,
                )
            )
            tool_inputs = [
                llm.ToolInput(
                    tool_name=tool_call["function"]["name"],
                    tool_args=_parse_tool_args(tool_call["function"]["arguments"]),
                )
                for tool_call in tool_calls or ()
            ]

            message_history.messages.extend(
                [
                    ollama.Message(
                        role=MessageRole.TOOL.value,
                        content=json.dumps(tool_response.tool_result),
                    )
                    async for tool_response in chat_log.async_add_assistant_content(
                        conversation.AssistantContent(
                            agent_id=user_input.agent_id,
                            content=content,
                            tool_calls=tool_inputs or None,
                        )
                    )
                ]
            )

            if not tool_calls:
                break

        # Create intent response
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_message["content"])
        return conversation.ConversationResult(
            response=intent_response, conversation_id=chat_log.conversation_id
        )

    def _trim_history(self, message_history: MessageHistory, max_messages: int) -> None:
        """Trims excess messages from a single history.

        This sets the max history to allow a configurable size history may take
        up in the context window.

        Note that some messages in the history may not be from ollama only, and
        may come from other anents, so the assumptions here may not strictly hold,
        but generally should be effective.
        """
        if max_messages < 1:
            # Keep all messages
            return

        # Ignore the in progress user message
        num_previous_rounds = message_history.num_user_messages - 1
        if num_previous_rounds >= max_messages:
            # Trim history but keep system prompt (first message).
            # Every other message should be an assistant message, so keep 2x
            # message objects. Also keep the last in progress user message
            num_keep = 2 * max_messages + 1
            drop_index = len(message_history.messages) - num_keep
            message_history.messages = [
                message_history.messages[0]
            ] + message_history.messages[drop_index:]

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
