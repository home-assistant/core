"""The Ollama conversation integration."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

import httpx
import ollama

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers import config_validation as cv, intent, template
from homeassistant.util import ulid

from .const import (
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_MODEL_OPTIONS,
    CONF_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    KEEP_ALIVE_FOREVER,
    MAX_HISTORY_NO_LIMIT,
    MAX_HISTORY_SECONDS,
)
from .models import MessageHistory, MessageRole

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONF_URL",
    "CONF_PROMPT",
    "CONF_MODEL",
    "CONF_MODEL_OPTIONS",
    "CONF_MAX_HISTORY",
    "MAX_HISTORY_NO_LIMIT",
    "DOMAIN",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ollama conversation from a config entry."""
    settings = {**entry.data, **entry.options}
    client = ollama.AsyncClient(host=settings[CONF_URL])
    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.list()
    except (TimeoutError, httpx.ConnectError) as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    conversation.async_set_agent(hass, entry, OllamaAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ollama conversation."""
    hass.data[DOMAIN].pop(entry.entry_id)
    conversation.async_unset_agent(hass, entry)
    return True


class OllamaAgent(conversation.AbstractConversationAgent):
    """Ollama conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry

        # conversation id -> message history
        self._history: dict[str, MessageHistory] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        settings = {**self.entry.data, **self.entry.options}

        client = self.hass.data[DOMAIN][self.entry.entry_id]
        conversation_id = user_input.conversation_id or ulid.ulid_now()
        raw_prompt = settings[CONF_PROMPT]

        # Render prompt and error out early if there's a problem
        try:
            prompt = self._async_generate_prompt(raw_prompt)
        except TemplateError as err:
            _LOGGER.error("Error rendering prompt: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem with my template: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        model = settings[CONF_MODEL]
        model_options = settings.get(CONF_MODEL_OPTIONS, {})

        # Look up message history
        message_history: MessageHistory | None = None
        message_history = self._history.get(conversation_id)
        if message_history is None:
            # New history
            message_history = MessageHistory(
                timestamp=time.monotonic(),
                messages=[
                    ollama.Message(role=MessageRole.SYSTEM.value, content=prompt)
                ],
            )
            self._history[conversation_id] = message_history
        else:
            # Bump timestamp so this conversation won't get cleaned up
            message_history.timestamp = time.monotonic()

        # Clean up old histories
        self._prune_old_histories()

        # Trim this message history to keep a maximum number of *user* messages
        max_messages = int(settings.get(CONF_MAX_HISTORY, MAX_HISTORY_NO_LIMIT))
        self._trim_history(message_history, max_messages)

        # Add new user message
        message_history.messages.append(
            ollama.Message(role=MessageRole.USER.value, content=user_input.text)
        )

        # Get response
        try:
            response = await client.chat(
                model=model,
                messages=list(message_history.messages),
                stream=False,
                keep_alive=KEEP_ALIVE_FOREVER,
                options={**model_options},
            )
        except (ollama.RequestError, ollama.ResponseError) as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to the Ollama server: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        response_message = response["message"]
        message_history.messages.append(
            ollama.Message(
                role=response_message["role"], content=response_message["content"]
            )
        )

        # Create intent response
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_message["content"])
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _prune_old_histories(self) -> None:
        """Remove old message histories."""
        now = time.monotonic()
        self._history = {
            conversation_id: message_history
            for conversation_id, message_history in self._history.items()
            if (now - message_history.timestamp) <= MAX_HISTORY_SECONDS
        }

    def _trim_history(self, message_history: MessageHistory, max_messages: int) -> None:
        """Trims excess messages from a single history."""
        if max_messages < 1:
            # Keep all messages
            return

        if message_history.num_user_messages >= max_messages:
            # Trim history but keep system prompt (first message).
            # Every other message should be an assistant message, so keep 2x
            # message objects.
            num_keep = 2 * max_messages
            drop_index = len(message_history.messages) - num_keep
            message_history.messages = [
                message_history.messages[0]
            ] + message_history.messages[drop_index:]

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
