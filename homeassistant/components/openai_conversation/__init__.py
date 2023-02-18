"""The OpenAI Conversation integration."""
from __future__ import annotations

from functools import partial
import logging

import openai
from openai import error

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers import area_registry, intent, template
from homeassistant.util import ulid

from .const import (
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    openai.api_key = entry.data[CONF_API_KEY]

    try:
        await hass.async_add_executor_job(
            partial(openai.Engine.list, request_timeout=10)
        )
    except error.AuthenticationError as err:
        _LOGGER.error("Invalid API key: %s", err)
        return False
    except error.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    conversation.async_set_agent(hass, entry, OpenAIAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    openai.api_key = None
    conversation.async_unset_agent(hass, entry)
    return True


class OpenAIAgent(conversation.AbstractConversationAgent):
    """OpenAI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, str] = {}

    @property
    def attribution(self):
        """Return the attribution."""
        return {"name": "Powered by OpenAI", "url": "https://www.openai.com"}

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        model = self.entry.options.get(CONF_MODEL, DEFAULT_MODEL)
        max_tokens = self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            prompt = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid()
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

        user_name = "User"
        if (
            user_input.context.user_id
            and (
                user := await self.hass.auth.async_get_user(user_input.context.user_id)
            )
            and user.name
        ):
            user_name = user.name

        prompt += f"\n{user_name}: {user_input.text}\nSmart home: "

        _LOGGER.debug("Prompt for %s: %s", model, prompt)

        try:
            result = await openai.Completion.acreate(
                engine=model,
                prompt=prompt,
                max_tokens=max_tokens,
                top_p=top_p,
                temperature=temperature,
                user=conversation_id,
            )
        except error.OpenAIError as err:
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Sorry, I had a problem talking to OpenAI: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        _LOGGER.debug("Response %s", result)
        response = result["choices"][0]["text"].strip()
        self.history[conversation_id] = prompt + response

        stripped_response = response
        if response.startswith("Smart home:"):
            stripped_response = response[11:].strip()

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(stripped_response)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(self, raw_prompt: str) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "areas": list(area_registry.async_get(self.hass).areas.values()),
            },
            parse_result=False,
        )
