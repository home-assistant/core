"""The Google Generative AI Conversation integration."""
from __future__ import annotations

from functools import partial
import logging
from typing import Literal

from google.api_core.exceptions import ClientError
import google.generativeai as palm
from google.generativeai.types.discuss_types import ChatResponse

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers import intent, template
from homeassistant.util import ulid

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Generative AI Conversation from a config entry."""
    palm.configure(api_key=entry.data[CONF_API_KEY])

    try:
        await hass.async_add_executor_job(
            partial(
                palm.get_model, entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
            )
        )
    except ClientError as err:
        if err.reason == "API_KEY_INVALID":
            _LOGGER.error("Invalid API key: %s", err)
            return False
        raise ConfigEntryNotReady(err) from err

    conversation.async_set_agent(hass, entry, GoogleGenerativeAIAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload GoogleGenerativeAI."""
    palm.configure(api_key=None)
    conversation.async_unset_agent(hass, entry)
    return True


class GoogleGenerativeAIAgent(conversation.AbstractConversationAgent):
    """Google Generative AI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        top_k = self.entry.options.get(CONF_TOP_K, DEFAULT_TOP_K)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
            messages = []

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

        messages.append({"author": "0", "content": user_input.text})

        _LOGGER.debug("Prompt for %s: %s", model, messages)

        try:
            chat_response: ChatResponse = await palm.chat_async(
                model=model,
                context=prompt,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )
        except ClientError as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to Google Generative AI: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        _LOGGER.debug("Response %s", chat_response)
        # For some queries the response is empty. In that case don't update history to avoid
        # "google.generativeai.types.discuss_types.AuthorError: Authors are not strictly alternating"
        if chat_response.last:
            self.history[conversation_id] = chat_response.messages

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(chat_response.last)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
            },
            parse_result=False,
        )
