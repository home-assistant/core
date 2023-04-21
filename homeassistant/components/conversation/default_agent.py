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
from hassil.recognize import RecognizeResult, recognize_all
from hassil.util import merge_dict
from home_assistant_intents import get_domains_and_languages, get_intents
import yaml

from homeassistant import core, setup
from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
    template,
    translation,
)
from homeassistant.util.json import JsonObjectType, json_loads_object

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_DEFAULT_ERROR_TEXT = "Sorry, I couldn't understand that"
_ENTITY_REGISTRY_UPDATE_FIELDS = ["aliases", "name", "original_name"]

REGEX_TYPE = type(re.compile(""))


def json_load(fp: IO[str]) -> JsonObjectType:
    """Wrap json_loads for get_intents."""
    return json_loads_object(fp.read())


@dataclass(slots=True)
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
        self._slot_lists: dict[str, SlotList] | None = None

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return get_domains_and_languages()["homeassistant"]

    async def async_initialize(self, config_intents):
        """Initialize the default agent."""
        if "intent" not in self.hass.config.components:
            await setup.async_setup_component(self.hass, "intent", {})

        # Intents from config may only contains sentences for HA config's language
        if config_intents:
            self._config_intents = config_intents

        self.hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED,
            self._async_handle_area_registry_changed,
            run_immediately=True,
        )
        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._async_handle_entity_registry_changed,
            run_immediately=True,
        )
        async_listen_entity_updates(
            self.hass, DOMAIN, self._async_exposed_entities_updated
        )

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

        slot_lists = self._make_slot_lists()

        result = await self.hass.async_add_executor_job(
            self._recognize,
            user_input,
            lang_intents,
            slot_lists,
        )
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
            response_template_str = lang_intents.intent_responses.get(
                result.intent.name, {}
            ).get(response_key)
            if response_template_str:
                response_template = template.Template(response_template_str, self.hass)
                speech = await self._build_speech(
                    language, response_template, intent_response, result
                )
                intent_response.async_set_speech(speech)

        return ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _recognize(
        self,
        user_input: ConversationInput,
        lang_intents: LanguageIntents,
        slot_lists: dict[str, SlotList],
    ) -> RecognizeResult | None:
        """Search intents for a match to user input."""
        # Prioritize matches with entity names above area names
        maybe_result: RecognizeResult | None = None
        for result in recognize_all(
            user_input.text, lang_intents.intents, slot_lists=slot_lists
        ):
            if "name" in result.entities:
                return result

            # Keep looking in case an entity has the same name
            maybe_result = result

        return maybe_result

    async def _build_speech(
        self,
        language: str,
        response_template: template.Template,
        intent_response: intent.IntentResponse,
        recognize_result: RecognizeResult,
    ) -> str:
        # Make copies of the states here so we can add translated names for responses.
        matched: list[core.State] = []

        for state in intent_response.matched_states:
            state_copy = core.State.from_dict(state.as_dict())
            if state_copy is not None:
                matched.append(state_copy)

        unmatched: list[core.State] = []
        for state in intent_response.unmatched_states:
            state_copy = core.State.from_dict(state.as_dict())
            if state_copy is not None:
                unmatched.append(state_copy)

        all_states = matched + unmatched
        domains = {state.domain for state in all_states}
        translations = await translation.async_get_translations(
            self.hass, language, "state", domains
        )

        # Use translated state names
        for state in all_states:
            device_class = state.attributes.get("device_class", "_")
            key = f"component.{state.domain}.state.{device_class}.{state.state}"
            state.state = translations.get(key, state.state)

        # Get first matched or unmatched state.
        # This is available in the response template as "state".
        state1: core.State | None = None
        if intent_response.matched_states:
            state1 = matched[0]
        elif intent_response.unmatched_states:
            state1 = unmatched[0]

        # Render response template
        speech = response_template.async_render(
            {
                # Slots from intent recognizer
                "slots": {
                    entity_name: entity_value.text or entity_value.value
                    for entity_name, entity_value in recognize_result.entities.items()
                },
                # First matched or unmatched state
                "state": template.TemplateState(self.hass, state1)
                if state1 is not None
                else None,
                "query": {
                    # Entity states that matched the query (e.g, "on")
                    "matched": [
                        template.TemplateState(self.hass, state) for state in matched
                    ],
                    # Entity states that did not match the query
                    "unmatched": [
                        template.TemplateState(self.hass, state) for state in unmatched
                    ],
                },
            }
        )

        # Normalize whitespace
        if speech is not None:
            speech = str(speech)
            speech = " ".join(speech.strip().split())

        return speech

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
        hass_components = set(self.hass.config.components)
        async with self._lang_lock[language]:
            return await self.hass.async_add_executor_job(
                self._get_or_load_intents, language, hass_components
            )

    def _get_or_load_intents(
        self, language: str, hass_components: set[str]
    ) -> LanguageIntents | None:
        """Load all intents for language (run inside executor)."""
        lang_intents = self._lang_intents.get(language)

        if lang_intents is None:
            intents_dict: dict[str, Any] = {}
            loaded_components: set[str] = set()
        else:
            intents_dict = lang_intents.intents_dict
            loaded_components = lang_intents.loaded_components

        # en-US, en_US, en, ...
        language_variations = list(_get_language_variations(language))

        # Check if any new components have been loaded
        intents_changed = False
        for component in hass_components:
            if component in loaded_components:
                continue

            # Don't check component again
            loaded_components.add(component)

            # Check for intents for this component with the target language.
            # Try en-US, en, etc.
            for language_variation in language_variations:
                component_intents = get_intents(
                    component, language_variation, json_load=json_load
                )
                if component_intents:
                    # Merge sentences into existing dictionary
                    merge_dict(intents_dict, component_intents)

                    # Will need to recreate graph
                    intents_changed = True
                    _LOGGER.debug(
                        "Loaded intents component=%s, language=%s (%s)",
                        component,
                        language,
                        language_variation,
                    )
                    break

        # Check for custom sentences in <config>/custom_sentences/<language>/
        if lang_intents is None:
            # Only load custom sentences once, otherwise they will be re-loaded
            # when components change.
            for language_variation in language_variations:
                custom_sentences_dir = Path(
                    self.hass.config.path("custom_sentences", language_variation)
                )
                if custom_sentences_dir.is_dir():
                    for custom_sentences_path in custom_sentences_dir.rglob("*.yaml"):
                        with custom_sentences_path.open(
                            encoding="utf-8"
                        ) as custom_sentences_file:
                            # Merge custom sentences
                            merge_dict(
                                intents_dict, yaml.safe_load(custom_sentences_file)
                            )

                        # Will need to recreate graph
                        intents_changed = True
                        _LOGGER.debug(
                            "Loaded custom sentences language=%s (%s), path=%s",
                            language,
                            language_variation,
                            custom_sentences_path,
                        )

                    # Stop after first matched language variation
                    break

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

    @core.callback
    def _async_handle_area_registry_changed(self, event: core.Event) -> None:
        """Clear area area cache when the area registry has changed."""
        self._slot_lists = None

    @core.callback
    def _async_handle_entity_registry_changed(self, event: core.Event) -> None:
        """Clear names list cache when an entity registry entry has changed."""
        if event.data["action"] == "update" and not any(
            field in event.data["changes"] for field in _ENTITY_REGISTRY_UPDATE_FIELDS
        ):
            return
        self._slot_lists = None

    @core.callback
    def _async_exposed_entities_updated(self) -> None:
        """Handle updated preferences."""
        self._slot_lists = None

    def _make_slot_lists(self) -> dict[str, SlotList]:
        """Create slot lists with areas and entity names/aliases."""
        if self._slot_lists is not None:
            return self._slot_lists

        area_ids_with_entities: set[str] = set()
        all_entities = er.async_get(self.hass)
        entities = [
            entity
            for entity in all_entities.entities.values()
            if async_should_expose(self.hass, DOMAIN, entity.entity_id)
        ]
        devices = dr.async_get(self.hass)

        # Gather exposed entity names
        entity_names = []
        for entity in entities:
            # Checked against "requires_context" and "excludes_context" in hassil
            context = {"domain": entity.domain}
            if entity.device_class:
                context[ATTR_DEVICE_CLASS] = entity.device_class

            if entity.aliases:
                for alias in entity.aliases:
                    entity_names.append((alias, alias, context))

            # Default name
            name = entity.async_friendly_name(self.hass) or entity.entity_id.replace(
                "_", " "
            )
            entity_names.append((name, name, context))

            if entity.area_id:
                # Expose area too
                area_ids_with_entities.add(entity.area_id)
            elif entity.device_id:
                # Check device for area as well
                device = devices.async_get(entity.device_id)
                if (device is not None) and device.area_id:
                    area_ids_with_entities.add(device.area_id)

        # Gather areas from exposed entities
        areas = ar.async_get(self.hass)
        area_names = []
        for area_id in area_ids_with_entities:
            area = areas.async_get_area(area_id)
            if area is None:
                continue

            area_names.append((area.name, area.id))
            if area.aliases:
                for alias in area.aliases:
                    area_names.append((alias, area.id))

        _LOGGER.debug("Exposed areas: %s", area_names)
        _LOGGER.debug("Exposed entities: %s", entity_names)

        self._slot_lists = {
            "area": TextSlotList.from_tuples(area_names, allow_template=False),
            "name": TextSlotList.from_tuples(entity_names, allow_template=False),
        }

        return self._slot_lists

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
