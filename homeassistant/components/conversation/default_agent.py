"""Standard conversation implementation for Home Assistant."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import IO, Any

from hassil.intents import Intents, ResponseType, SlotList, TextSlotList
from hassil.recognize import recognize
from hassil.util import merge_dict
from home_assistant_intents import get_intents
import yaml

from homeassistant import core, setup
from homeassistant.helpers import area_registry, entity_registry, intent, template
from homeassistant.helpers.json import json_loads

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_DEFAULT_ERROR_TEXT = "Sorry, I couldn't understand that"

REGEX_TYPE = type(re.compile(""))


def json_load(fp: IO[str]) -> dict[str, Any]:
    """Wrap json_loads for get_intents."""
    return json_loads(fp.read())


@dataclass
class LanguageIntents:
    """Loaded intents for a language."""

    intents: Intents
    intents_dict: dict[str, Any]
    intent_responses: dict[str, Any]
    error_responses: dict[str, Any]
    loaded_components: set[str]


def _get_language_variations(language: str) -> Iterable[str]:
    """Generate language codes with and without region."""
    yield language

    parts = re.split(r"([-_])", language)
    if len(parts) == 3:
        lang, sep, region = parts
        if sep == "_":
            # en_US -> en-US
            yield f"{lang}-{region}"

        # en-US -> en
        yield lang


class DefaultAgent(AbstractConversationAgent):
    """Default agent for conversation agent."""

    def __init__(self, hass: core.HomeAssistant) -> None:
        """Initialize the default agent."""
        self.hass = hass
        self._lang_intents: dict[str, LanguageIntents] = {}
        self._lang_lock: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # intent -> [sentences]
        self._config_intents: dict[str, Any] = {}

    async def async_initialize(self, config_intents):
        """Initialize the default agent."""
        if "intent" not in self.hass.config.components:
            await setup.async_setup_component(self.hass, "intent", {})

        # Intents from config may only contains sentences for HA config's language
        if config_intents:
            self._config_intents = config_intents

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""
        language = user_input.language or self.hass.config.language
        lang_intents = self._lang_intents.get(language)
        conversation_id = None  # Not supported

        # Reload intents if missing or new components
        if lang_intents is None or (
            lang_intents.loaded_components - self.hass.config.components
        ):
            # Load intents in executor
            lang_intents = await self.async_get_or_load_intents(language)

        if lang_intents is None:
            # No intents loaded
            _LOGGER.warning("No intents were loaded for language: %s", language)
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                _DEFAULT_ERROR_TEXT,
                conversation_id,
            )

        slot_lists: dict[str, SlotList] = {
            "area": self._make_areas_list(),
            "name": self._make_names_list(),
        }

        result = recognize(user_input.text, lang_intents.intents, slot_lists=slot_lists)
        if result is None:
            _LOGGER.debug("No intent was matched for '%s'", user_input.text)
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                self._get_error_text(ResponseType.NO_INTENT, lang_intents),
                conversation_id,
            )

        try:
            intent_response = await intent.async_handle(
                self.hass,
                DOMAIN,
                result.intent.name,
                {
                    entity.name: {"value": entity.value}
                    for entity in result.entities_list
                },
                user_input.text,
                user_input.context,
                language,
            )
        except intent.IntentHandleError:
            _LOGGER.exception("Intent handling error")
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                self._get_error_text(ResponseType.HANDLE_ERROR, lang_intents),
                conversation_id,
            )
        except intent.IntentUnexpectedError:
            _LOGGER.exception("Unexpected intent error")
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.UNKNOWN,
                self._get_error_text(ResponseType.HANDLE_ERROR, lang_intents),
                conversation_id,
            )

        if (
            (not intent_response.speech)
            and (intent_response.intent is not None)
            and (response_key := result.response)
        ):
            # Use response template, if available
            response_str = lang_intents.intent_responses.get(
                result.intent.name, {}
            ).get(response_key)
            if response_str:
                response_template = template.Template(response_str, self.hass)
                intent_response.async_set_speech(
                    response_template.async_render(
                        {
                            "slots": {
                                entity_name: entity_value.text or entity_value.value
                                for entity_name, entity_value in result.entities.items()
                            }
                        }
                    )
                )

        return ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    async def async_reload(self, language: str | None = None):
        """Clear cached intents for a language."""
        if language is None:
            language = self.hass.config.language

        self._lang_intents.pop(language, None)
        _LOGGER.debug("Cleared intents for language: %s", language)

    async def async_prepare(self, language: str | None = None):
        """Load intents for a language."""
        if language is None:
            language = self.hass.config.language

        lang_intents = await self.async_get_or_load_intents(language)

        if lang_intents is None:
            # No intents loaded
            _LOGGER.warning("No intents were loaded for language: %s", language)

    async def async_get_or_load_intents(self, language: str) -> LanguageIntents | None:
        """Load all intents of a language with lock."""
        async with self._lang_lock[language]:
            return await self.hass.async_add_executor_job(
                self._get_or_load_intents,
                language,
            )

    def _get_or_load_intents(self, language: str) -> LanguageIntents | None:
        """Load all intents for language (run inside executor)."""
        lang_intents = self._lang_intents.get(language)

        if lang_intents is None:
            intents_dict: dict[str, Any] = {}
            loaded_components: set[str] = set()
        else:
            intents_dict = lang_intents.intents_dict
            loaded_components = lang_intents.loaded_components

        # Check if any new components have been loaded
        intents_changed = False
        for component in self.hass.config.components:
            if component in loaded_components:
                continue

            # Don't check component again
            loaded_components.add(component)

            # Check for intents for this component with the target language.
            # Try en-US, en, etc.
            for language_variation in _get_language_variations(language):
                component_intents = get_intents(
                    component, language_variation, json_load=json_load
                )
                if component_intents:
                    # Merge sentences into existing dictionary
                    merge_dict(intents_dict, component_intents)

                    # Will need to recreate graph
                    intents_changed = True
                    _LOGGER.debug(
                        "Loaded intents component=%s, language=%s", component, language
                    )
                    break

        # Check for custom sentences in <config>/custom_sentences/<language>/
        if lang_intents is None:
            # Only load custom sentences once, otherwise they will be re-loaded
            # when components change.
            custom_sentences_dir = Path(
                self.hass.config.path("custom_sentences", language)
            )
            if custom_sentences_dir.is_dir():
                for custom_sentences_path in custom_sentences_dir.rglob("*.yaml"):
                    with custom_sentences_path.open(
                        encoding="utf-8"
                    ) as custom_sentences_file:
                        # Merge custom sentences
                        merge_dict(intents_dict, yaml.safe_load(custom_sentences_file))

                    # Will need to recreate graph
                    intents_changed = True
                    _LOGGER.debug(
                        "Loaded custom sentences language=%s, path=%s",
                        language,
                        custom_sentences_path,
                    )

            # Load sentences from HA config for default language only
            if self._config_intents and (language == self.hass.config.language):
                merge_dict(
                    intents_dict,
                    {
                        "intents": {
                            intent_name: {"data": [{"sentences": sentences}]}
                            for intent_name, sentences in self._config_intents.items()
                        }
                    },
                )
                intents_changed = True
                _LOGGER.debug(
                    "Loaded intents from configuration.yaml",
                )

        if not intents_dict:
            return None

        if not intents_changed and lang_intents is not None:
            return lang_intents

        # This can be made faster by not re-parsing existing sentences.
        # But it will likely only be called once anyways, unless new
        # components with sentences are often being loaded.
        intents = Intents.from_dict(intents_dict)

        # Load responses
        responses_dict = intents_dict.get("responses", {})
        intent_responses = responses_dict.get("intents", {})
        error_responses = responses_dict.get("errors", {})

        if lang_intents is None:
            lang_intents = LanguageIntents(
                intents,
                intents_dict,
                intent_responses,
                error_responses,
                loaded_components,
            )
            self._lang_intents[language] = lang_intents
        else:
            lang_intents.intents = intents
            lang_intents.intent_responses = intent_responses
            lang_intents.error_responses = error_responses

        return lang_intents

    def _make_areas_list(self) -> TextSlotList:
        """Create slot list mapping area names/aliases to area ids."""
        registry = area_registry.async_get(self.hass)
        areas = []
        for entry in registry.async_list_areas():
            areas.append((entry.name, entry.id))
            if entry.aliases:
                for alias in entry.aliases:
                    areas.append((alias, entry.id))

        return TextSlotList.from_tuples(areas)

    def _make_names_list(self) -> TextSlotList:
        """Create slot list mapping entity names/aliases to entity ids."""
        states = self.hass.states.async_all()
        registry = entity_registry.async_get(self.hass)
        names = []
        for state in states:
            domain = state.entity_id.split(".", maxsplit=1)[0]
            context = {"domain": domain}

            entry = registry.async_get(state.entity_id)
            if entry is not None:
                if entry.entity_category:
                    # Skip configuration/diagnostic entities
                    continue

                if entry.aliases:
                    for alias in entry.aliases:
                        names.append((alias, state.entity_id, context))

            # Default name
            names.append((state.name, state.entity_id, context))

        return TextSlotList.from_tuples(names)

    def _get_error_text(
        self, response_type: ResponseType, lang_intents: LanguageIntents
    ) -> str:
        """Get response error text by type."""
        response_key = response_type.value
        response_str = lang_intents.error_responses.get(response_key)
        return response_str or _DEFAULT_ERROR_TEXT


def _make_error_result(
    language: str,
    error_code: intent.IntentResponseErrorCode,
    response_text: str,
    conversation_id: str | None = None,
) -> ConversationResult:
    """Create conversation result with error code and text."""
    response = intent.IntentResponse(language=language)
    response.async_set_error(error_code, response_text)

    return ConversationResult(response, conversation_id)
