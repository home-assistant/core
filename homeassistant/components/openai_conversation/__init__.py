"""The OpenAI Conversation integration."""
from __future__ import annotations

from difflib import SequenceMatcher
from functools import partial
import logging

import openai
from openai import error

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers import area_registry, entity_registry, intent, template
from homeassistant.util import ulid

from .const import (
    CONF_CONTINUED_PROMPT,
    CONF_ENGINE,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
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
        raw_prompt = self.entry.options[CONF_PROMPT]
        raw_contprompt = self.entry.options[CONF_CONTINUED_PROMPT]
        engine = self.entry.options[CONF_ENGINE]
        max_tokens = self.entry.options[CONF_MAX_TOKENS]
        top_p = self.entry.options[CONF_TOP_P]
        temperature = self.entry.options[CONF_TEMPERATURE]
        template_variables = {
            "matched_areas": self._matching_areas(user_input.text),
            "matched_entities": self._matching_entities(user_input.text),
        }

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            prompt = self.history[conversation_id]
            prompt += self._async_generate_prompt(raw_contprompt, template_variables)
        else:
            conversation_id = ulid.ulid()
            try:
                prompt = self._async_generate_prompt(raw_prompt, template_variables)
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

        _LOGGER.debug("Prompt for %s: %s", engine, prompt)

        try:
            result = await openai.Completion.acreate(
                prompt=prompt,
                user=conversation_id,
                engine=engine,
                max_tokens=max_tokens,
                top_p=top_p,
                temperature=temperature,
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

    def _async_generate_prompt(self, raw_prompt: str, variables: dict) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "areas": list(area_registry.async_get(self.hass).areas.values()),
                **variables,
            }
        )

    @staticmethod
    def _process_words(sentence: str) -> list[str]:
        """Strip whitespace and normalises text to a list of words."""
        return sentence.replace(".", " ").replace("_", " ").split()

    @staticmethod
    def _match_strings(str1, str2, threshold) -> bool:
        """Compare two strings to determine likeness ratio."""
        ratio = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        if ratio > threshold:
            return True
        return False

    def similar_words(self, str1, str2, threshold=0.8):
        """Compare two sentences word by word to determine likeness."""
        word_list_1 = self._process_words(str1)
        word_list_2 = self._process_words(str2)
        for word1 in word_list_1:
            for word2 in word_list_2:
                if self._match_strings(word1, word2, threshold):
                    return True
        return False

    def _matching_areas(self, request_text) -> list:
        """Create a list of areas which share likeness with the requested text."""
        registry = area_registry.async_get(self.hass)
        areas = set()
        for entry in registry.async_list_areas():
            if self.similar_words(entry.name, request_text):
                areas.add(entry.id)
            if entry.aliases:
                for alias in entry.aliases:
                    if self.similar_words(alias, request_text):
                        areas.add(entry.id)
        return sorted(areas)

    def _matching_entities(self, request_text) -> list:
        """Create a list of areas which share likeness with the requested text."""
        states = self.hass.states.async_all()
        registry = entity_registry.async_get(self.hass)
        entities = set()
        for state in states:
            entry = registry.async_get(state.entity_id)
            if entry is not None:
                if entry.entity_category:
                    # Skip configuration/diagnostic entities
                    continue
                if entry.aliases:
                    for alias in entry.aliases:
                        if self.similar_words(alias, request_text):
                            entities.add(state.entity_id)
            # Default name
            if self.similar_words(state.name, request_text):
                entities.add(state.entity_id)
        return sorted(entities)
