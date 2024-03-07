"""Standard conversation implementation for Home Assistant."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
import functools
import logging
from pathlib import Path
import re
from typing import IO, Any

from hassil.expression import Expression, ListReference, Sequence
from hassil.intents import Intents, SlotList, TextSlotList, WildcardSlotList
from hassil.recognize import (
    MISSING_ENTITY,
    RecognizeResult,
    UnmatchedTextEntity,
    recognize_all,
)
from hassil.util import merge_dict
from home_assistant_intents import ErrorKey, get_intents, get_languages
import yaml

from homeassistant import core, setup
from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.const import EVENT_STATE_CHANGED, MATCH_ALL
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
    start,
    template,
    translation,
)
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_added_domain,
)
from homeassistant.helpers.typing import EventType
from homeassistant.util.json import JsonObjectType, json_loads_object

from .agent import AbstractConversationAgent, ConversationInput, ConversationResult
from .const import DEFAULT_EXPOSED_ATTRIBUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)
_DEFAULT_ERROR_TEXT = "Sorry, I couldn't understand that"
_ENTITY_REGISTRY_UPDATE_FIELDS = ["aliases", "name", "original_name"]

REGEX_TYPE = type(re.compile(""))
TRIGGER_CALLBACK_TYPE = Callable[[str, RecognizeResult], Awaitable[str | None]]
METADATA_CUSTOM_SENTENCE = "hass_custom_sentence"
METADATA_CUSTOM_FILE = "hass_custom_file"


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
    language_variant: str | None


@dataclass(slots=True)
class TriggerData:
    """List of sentences and the callback for a trigger."""

    sentences: list[str]
    callback: TRIGGER_CALLBACK_TYPE


@dataclass(slots=True)
class SentenceTriggerResult:
    """Result when matching a sentence trigger in an automation."""

    sentence: str
    sentence_template: str | None
    matched_triggers: dict[int, RecognizeResult]


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


@core.callback
def async_setup(hass: core.HomeAssistant) -> None:
    """Set up entity registry listener for the default agent."""
    entity_registry = er.async_get(hass)
    for entity_id in entity_registry.entities:
        async_should_expose(hass, DOMAIN, entity_id)

    @core.callback
    def async_entity_state_listener(event: EventType[EventStateChangedData]) -> None:
        """Set expose flag on new entities."""
        async_should_expose(hass, DOMAIN, event.data["entity_id"])

    @core.callback
    def async_hass_started(hass: core.HomeAssistant) -> None:
        """Set expose flag on all entities."""
        for state in hass.states.async_all():
            async_should_expose(hass, DOMAIN, state.entity_id)
        async_track_state_added_domain(hass, MATCH_ALL, async_entity_state_listener)

    start.async_at_started(hass, async_hass_started)


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

        # Sentences that will trigger a callback (skipping intent recognition)
        self._trigger_sentences: list[TriggerData] = []
        self._trigger_intents: Intents | None = None

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return get_languages()

    async def async_initialize(self, config_intents: dict[str, Any] | None) -> None:
        """Initialize the default agent."""
        if "intent" not in self.hass.config.components:
            await setup.async_setup_component(self.hass, "intent", {})

        # Intents from config may only contains sentences for HA config's language
        if config_intents:
            self._config_intents = config_intents

        self.hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED,
            self._async_handle_area_registry_changed,  # type: ignore[arg-type]
            run_immediately=True,
        )
        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._async_handle_entity_registry_changed,  # type: ignore[arg-type]
            run_immediately=True,
        )
        self.hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            self._async_handle_state_changed,  # type: ignore[arg-type]
            run_immediately=True,
        )
        async_listen_entity_updates(
            self.hass, DOMAIN, self._async_exposed_entities_updated
        )

    async def async_recognize(
        self, user_input: ConversationInput
    ) -> RecognizeResult | SentenceTriggerResult | None:
        """Recognize intent from user input."""
        if trigger_result := await self._match_triggers(user_input.text):
            return trigger_result

        language = user_input.language or self.hass.config.language
        lang_intents = self._lang_intents.get(language)

        # Reload intents if missing or new components
        if lang_intents is None:
            # Load intents in executor
            lang_intents = await self.async_get_or_load_intents(language)

        if lang_intents is None:
            # No intents loaded
            _LOGGER.warning("No intents were loaded for language: %s", language)
            return None

        slot_lists = self._make_slot_lists()
        intent_context = self._make_intent_context(user_input)

        result = await self.hass.async_add_executor_job(
            self._recognize,
            user_input,
            lang_intents,
            slot_lists,
            intent_context,
            language,
        )

        return result

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""
        language = user_input.language or self.hass.config.language
        conversation_id = None  # Not supported

        result = await self.async_recognize(user_input)

        # Check if a trigger matched
        if isinstance(result, SentenceTriggerResult):
            # Gather callback responses in parallel
            trigger_callbacks = [
                self._trigger_sentences[trigger_id].callback(
                    result.sentence, trigger_result
                )
                for trigger_id, trigger_result in result.matched_triggers.items()
            ]

            # Use last non-empty result as response.
            #
            # There may be multiple copies of a trigger running when editing in
            # the UI, so it's critical that we filter out empty responses here.
            response_text: str | None = None
            for trigger_future in asyncio.as_completed(trigger_callbacks):
                if trigger_response := await trigger_future:
                    response_text = trigger_response
                    break

            # Convert to conversation result
            response = intent.IntentResponse(language=language)
            response.response_type = intent.IntentResponseType.ACTION_DONE
            response.async_set_speech(response_text or "Done")

            return ConversationResult(response=response)

        # Intent match or failure
        lang_intents = self._lang_intents.get(language)

        if result is None:
            # Intent was not recognized
            _LOGGER.debug("No intent was matched for '%s'", user_input.text)
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                self._get_error_text(ErrorKey.NO_INTENT, lang_intents),
                conversation_id,
            )

        if result.unmatched_entities:
            # Intent was recognized, but not entity/area names, etc.
            _LOGGER.debug(
                "Recognized intent '%s' for template '%s' but had unmatched: %s",
                result.intent.name,
                (
                    result.intent_sentence.text
                    if result.intent_sentence is not None
                    else ""
                ),
                result.unmatched_entities_list,
            )
            error_response_type, error_response_args = _get_unmatched_response(result)
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                self._get_error_text(
                    error_response_type, lang_intents, **error_response_args
                ),
                conversation_id,
            )

        # Will never happen because result will be None when no intents are
        # loaded in async_recognize.
        assert lang_intents is not None

        # Slot values to pass to the intent
        slots = {
            entity.name: {"value": entity.value, "text": entity.text or entity.value}
            for entity in result.entities_list
        }

        try:
            intent_response = await intent.async_handle(
                self.hass,
                DOMAIN,
                result.intent.name,
                slots,
                user_input.text,
                user_input.context,
                language,
                assistant=DOMAIN,
            )
        except intent.NoStatesMatchedError as no_states_error:
            # Intent was valid, but no entities matched the constraints.
            error_response_type, error_response_args = _get_no_states_matched_response(
                no_states_error
            )
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                self._get_error_text(
                    error_response_type, lang_intents, **error_response_args
                ),
                conversation_id,
            )
        except intent.DuplicateNamesMatchedError as duplicate_names_error:
            # Intent was valid, but two or more entities with the same name matched.
            (
                error_response_type,
                error_response_args,
            ) = _get_duplicate_names_matched_response(duplicate_names_error)
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                self._get_error_text(
                    error_response_type, lang_intents, **error_response_args
                ),
                conversation_id,
            )
        except intent.IntentHandleError:
            # Intent was valid and entities matched constraints, but an error
            # occurred during handling.
            _LOGGER.exception("Intent handling error")
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                self._get_error_text(ErrorKey.HANDLE_ERROR, lang_intents),
                conversation_id,
            )
        except intent.IntentUnexpectedError:
            _LOGGER.exception("Unexpected intent error")
            return _make_error_result(
                language,
                intent.IntentResponseErrorCode.UNKNOWN,
                self._get_error_text(ErrorKey.HANDLE_ERROR, lang_intents),
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
        intent_context: dict[str, Any] | None,
        language: str,
    ) -> RecognizeResult | None:
        """Search intents for a match to user input."""
        # Prioritize matches with entity names above area names
        maybe_result: RecognizeResult | None = None
        for result in recognize_all(
            user_input.text,
            lang_intents.intents,
            slot_lists=slot_lists,
            intent_context=intent_context,
            language=language,
        ):
            if "name" in result.entities:
                return result

            # Keep looking in case an entity has the same name
            maybe_result = result

        if maybe_result is not None:
            # Successful strict match
            return maybe_result

        # Try again with missing entities enabled
        best_num_unmatched_entities = 0
        for result in recognize_all(
            user_input.text,
            lang_intents.intents,
            slot_lists=slot_lists,
            intent_context=intent_context,
            allow_unmatched_entities=True,
        ):
            if result.text_chunks_matched < 1:
                # Skip results that don't match any literal text
                continue

            # Don't count missing entities that couldn't be filled from context
            num_unmatched_entities = 0
            for entity in result.unmatched_entities_list:
                if isinstance(entity, UnmatchedTextEntity):
                    if entity.text != MISSING_ENTITY:
                        num_unmatched_entities += 1
                else:
                    num_unmatched_entities += 1

            if maybe_result is None:
                # First result
                maybe_result = result
                best_num_unmatched_entities = num_unmatched_entities
            elif num_unmatched_entities < best_num_unmatched_entities:
                # Fewer unmatched entities
                maybe_result = result
                best_num_unmatched_entities = num_unmatched_entities
            elif num_unmatched_entities == best_num_unmatched_entities:
                if (result.text_chunks_matched > maybe_result.text_chunks_matched) or (
                    (result.text_chunks_matched == maybe_result.text_chunks_matched)
                    and ("name" in result.unmatched_entities)  # prefer entities
                ):
                    # More literal text chunks matched, but prefer entities to areas, etc.
                    maybe_result = result

        if (maybe_result is not None) and maybe_result.unmatched_entities:
            # Failed to match, but we have more information about why in unmatched_entities
            return maybe_result

        # Complete match failure
        return None

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
            self.hass, language, "entity_component", domains
        )

        # Use translated state names
        for state in all_states:
            device_class = state.attributes.get("device_class", "_")
            key = f"component.{state.domain}.entity_component.{device_class}.state.{state.state}"
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
                "state": (
                    template.TemplateState(self.hass, state1)
                    if state1 is not None
                    else None
                ),
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

    async def async_reload(self, language: str | None = None) -> None:
        """Clear cached intents for a language."""
        if language is None:
            self._lang_intents.clear()
            _LOGGER.debug("Cleared intents for all languages")
        else:
            self._lang_intents.pop(language, None)
            _LOGGER.debug("Cleared intents for language: %s", language)

    async def async_prepare(self, language: str | None = None) -> None:
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
            language_variant: str | None = None
        else:
            intents_dict = lang_intents.intents_dict
            language_variant = lang_intents.language_variant

        supported_langs = set(get_languages())

        if not language_variant:
            # Choose a language variant upfront and commit to it for custom
            # sentences, etc.
            all_language_variants = {lang.lower(): lang for lang in supported_langs}

            # en-US, en_US, en, ...
            for maybe_variant in _get_language_variations(language):
                matching_variant = all_language_variants.get(maybe_variant.lower())
                if matching_variant:
                    language_variant = matching_variant
                    break

            if not language_variant:
                _LOGGER.warning(
                    "Unable to find supported language variant for %s", language
                )
                return None

            # Load intents for this language variant
            lang_variant_intents = get_intents(language_variant, json_load=json_load)

            if lang_variant_intents:
                # Merge sentences into existing dictionary
                merge_dict(intents_dict, lang_variant_intents)

                # Will need to recreate graph
                intents_changed = True
                _LOGGER.debug(
                    "Loaded intents  language=%s (%s)",
                    language,
                    language_variant,
                )

        # Check for custom sentences in <config>/custom_sentences/<language>/
        if lang_intents is None:
            # Only load custom sentences once, otherwise they will be re-loaded
            # when components change.
            custom_sentences_dir = Path(
                self.hass.config.path("custom_sentences", language_variant)
            )
            if custom_sentences_dir.is_dir():
                for custom_sentences_path in custom_sentences_dir.rglob("*.yaml"):
                    with custom_sentences_path.open(
                        encoding="utf-8"
                    ) as custom_sentences_file:
                        # Merge custom sentences
                        if isinstance(
                            custom_sentences_yaml := yaml.safe_load(
                                custom_sentences_file
                            ),
                            dict,
                        ):
                            # Add metadata so we can identify custom sentences in the debugger
                            custom_intents_dict = custom_sentences_yaml.get(
                                "intents", {}
                            )
                            for intent_dict in custom_intents_dict.values():
                                intent_data_list = intent_dict.get("data", [])
                                for intent_data in intent_data_list:
                                    sentence_metadata = intent_data.get("metadata", {})
                                    sentence_metadata[METADATA_CUSTOM_SENTENCE] = True
                                    sentence_metadata[METADATA_CUSTOM_FILE] = str(
                                        custom_sentences_path.relative_to(
                                            custom_sentences_dir.parent
                                        )
                                    )
                                    intent_data["metadata"] = sentence_metadata

                            merge_dict(intents_dict, custom_sentences_yaml)
                        else:
                            _LOGGER.warning(
                                "Custom sentences file does not match expected format path=%s",
                                custom_sentences_file.name,
                            )

                    # Will need to recreate graph
                    intents_changed = True
                    _LOGGER.debug(
                        "Loaded custom sentences language=%s (%s), path=%s",
                        language,
                        language_variant,
                        custom_sentences_path,
                    )

            # Load sentences from HA config for default language only
            if self._config_intents and (
                self.hass.config.language in (language, language_variant)
            ):
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
                language_variant,
            )
            self._lang_intents[language] = lang_intents
        else:
            lang_intents.intents = intents
            lang_intents.intent_responses = intent_responses
            lang_intents.error_responses = error_responses

        return lang_intents

    @core.callback
    def _async_handle_area_registry_changed(
        self, event: EventType[ar.EventAreaRegistryUpdatedData]
    ) -> None:
        """Clear area area cache when the area registry has changed."""
        self._slot_lists = None

    @core.callback
    def _async_handle_entity_registry_changed(
        self, event: EventType[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Clear names list cache when an entity registry entry has changed."""
        if event.data["action"] != "update" or not any(
            field in event.data["changes"] for field in _ENTITY_REGISTRY_UPDATE_FIELDS
        ):
            return
        self._slot_lists = None

    @core.callback
    def _async_handle_state_changed(
        self, event: EventType[EventStateChangedData]
    ) -> None:
        """Clear names list cache when a state is added or removed from the state machine."""
        if event.data["old_state"] and event.data["new_state"]:
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

        entity_registry = er.async_get(self.hass)
        states = [
            state
            for state in self.hass.states.async_all()
            if async_should_expose(self.hass, DOMAIN, state.entity_id)
        ]

        # Gather exposed entity names.
        #
        # NOTE: We do not pass entity ids in here because multiple entities may
        # have the same name. The intent matcher doesn't gather all matching
        # values for a list, just the first. So we will need to match by name no
        # matter what.
        entity_names = []
        for state in states:
            # Checked against "requires_context" and "excludes_context" in hassil
            context = {"domain": state.domain}
            if state.attributes:
                # Include some attributes
                for attr in DEFAULT_EXPOSED_ATTRIBUTES:
                    if attr not in state.attributes:
                        continue
                    context[attr] = state.attributes[attr]

            entity = entity_registry.async_get(state.entity_id)

            if not entity:
                # Default name
                entity_names.append((state.name, state.name, context))
                continue

            if entity.aliases:
                for alias in entity.aliases:
                    if not alias.strip():
                        continue

                    entity_names.append((alias, alias, context))

            # Default name
            entity_names.append((state.name, state.name, context))

        # Expose all areas.
        #
        # We pass in area id here with the expectation that no two areas will
        # share the same name or alias.
        areas = ar.async_get(self.hass)
        area_names = []
        for area in areas.async_list_areas():
            area_names.append((area.name, area.id))
            if area.aliases:
                for alias in area.aliases:
                    if not alias.strip():
                        continue

                    area_names.append((alias, area.id))

        _LOGGER.debug("Exposed entities: %s", entity_names)

        self._slot_lists = {
            "area": TextSlotList.from_tuples(area_names, allow_template=False),
            "name": TextSlotList.from_tuples(entity_names, allow_template=False),
        }

        return self._slot_lists

    def _make_intent_context(
        self, user_input: ConversationInput
    ) -> dict[str, Any] | None:
        """Return intent recognition context for user input."""
        if not user_input.device_id:
            return None

        devices = dr.async_get(self.hass)
        device = devices.async_get(user_input.device_id)
        if (device is None) or (device.area_id is None):
            return None

        areas = ar.async_get(self.hass)
        device_area = areas.async_get_area(device.area_id)
        if device_area is None:
            return None

        return {"area": {"value": device_area.id, "text": device_area.name}}

    def _get_error_text(
        self,
        error_key: ErrorKey,
        lang_intents: LanguageIntents | None,
        **response_args,
    ) -> str:
        """Get response error text by type."""
        if lang_intents is None:
            return _DEFAULT_ERROR_TEXT

        response_key = error_key.value
        response_str = (
            lang_intents.error_responses.get(response_key) or _DEFAULT_ERROR_TEXT
        )
        response_template = template.Template(response_str, self.hass)

        return response_template.async_render(response_args)

    def register_trigger(
        self,
        sentences: list[str],
        callback: TRIGGER_CALLBACK_TYPE,
    ) -> core.CALLBACK_TYPE:
        """Register a list of sentences that will trigger a callback when recognized."""
        trigger_data = TriggerData(sentences=sentences, callback=callback)
        self._trigger_sentences.append(trigger_data)

        # Force rebuild on next use
        self._trigger_intents = None

        unregister = functools.partial(self._unregister_trigger, trigger_data)
        return unregister

    def _rebuild_trigger_intents(self) -> None:
        """Rebuild the HassIL intents object from the current trigger sentences."""
        intents_dict = {
            "language": self.hass.config.language,
            "intents": {
                # Use trigger data index as a virtual intent name for HassIL.
                # This works because the intents are rebuilt on every
                # register/unregister.
                str(trigger_id): {"data": [{"sentences": trigger_data.sentences}]}
                for trigger_id, trigger_data in enumerate(self._trigger_sentences)
            },
        }

        self._trigger_intents = Intents.from_dict(intents_dict)

        # Assume slot list references are wildcards
        wildcard_names: set[str] = set()
        for trigger_intent in self._trigger_intents.intents.values():
            for intent_data in trigger_intent.data:
                for sentence in intent_data.sentences:
                    _collect_list_references(sentence, wildcard_names)

        for wildcard_name in wildcard_names:
            self._trigger_intents.slot_lists[wildcard_name] = WildcardSlotList()

        _LOGGER.debug("Rebuilt trigger intents: %s", intents_dict)

    def _unregister_trigger(self, trigger_data: TriggerData) -> None:
        """Unregister a set of trigger sentences."""
        self._trigger_sentences.remove(trigger_data)

        # Force rebuild on next use
        self._trigger_intents = None

    async def _match_triggers(self, sentence: str) -> SentenceTriggerResult | None:
        """Try to match sentence against registered trigger sentences.

        Calls the registered callbacks if there's a match and returns a sentence
        trigger result.
        """
        if not self._trigger_sentences:
            # No triggers registered
            return None

        if self._trigger_intents is None:
            # Need to rebuild intents before matching
            self._rebuild_trigger_intents()

        assert self._trigger_intents is not None

        matched_triggers: dict[int, RecognizeResult] = {}
        matched_template: str | None = None
        for result in recognize_all(sentence, self._trigger_intents):
            if result.intent_sentence is not None:
                matched_template = result.intent_sentence.text

            trigger_id = int(result.intent.name)
            if trigger_id in matched_triggers:
                # Already matched a sentence from this trigger
                break

            matched_triggers[trigger_id] = result

        if not matched_triggers:
            # Sentence did not match any trigger sentences
            return None

        _LOGGER.debug(
            "'%s' matched %s trigger(s): %s",
            sentence,
            len(matched_triggers),
            list(matched_triggers),
        )

        return SentenceTriggerResult(sentence, matched_template, matched_triggers)


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


def _get_unmatched_response(result: RecognizeResult) -> tuple[ErrorKey, dict[str, Any]]:
    """Get key and template arguments for error when there are unmatched intent entities/slots."""

    # Filter out non-text and missing context entities
    unmatched_text: dict[str, str] = {
        key: entity.text.strip()
        for key, entity in result.unmatched_entities.items()
        if isinstance(entity, UnmatchedTextEntity) and entity.text != MISSING_ENTITY
    }

    if unmatched_area := unmatched_text.get("area"):
        # area only
        return ErrorKey.NO_AREA, {"area": unmatched_area}

    # Area may still have matched
    matched_area: str | None = None
    if matched_area_entity := result.entities.get("area"):
        matched_area = matched_area_entity.text.strip()

    if unmatched_name := unmatched_text.get("name"):
        if matched_area:
            # device in area
            return ErrorKey.NO_ENTITY_IN_AREA, {
                "entity": unmatched_name,
                "area": matched_area,
            }

        # device only
        return ErrorKey.NO_ENTITY, {"entity": unmatched_name}

    # Default error
    return ErrorKey.NO_INTENT, {}


def _get_no_states_matched_response(
    no_states_error: intent.NoStatesMatchedError,
) -> tuple[ErrorKey, dict[str, Any]]:
    """Return key and template arguments for error when intent returns no matching states."""

    # Device classes should be checked before domains
    if no_states_error.device_classes:
        device_class = next(iter(no_states_error.device_classes))  # first device class
        if no_states_error.area:
            # device_class in area
            return ErrorKey.NO_DEVICE_CLASS_IN_AREA, {
                "device_class": device_class,
                "area": no_states_error.area,
            }

        # device_class only
        return ErrorKey.NO_DEVICE_CLASS, {"device_class": device_class}

    if no_states_error.domains:
        domain = next(iter(no_states_error.domains))  # first domain
        if no_states_error.area:
            # domain in area
            return ErrorKey.NO_DOMAIN_IN_AREA, {
                "domain": domain,
                "area": no_states_error.area,
            }

        # domain only
        return ErrorKey.NO_DOMAIN, {"domain": domain}

    # Default error
    return ErrorKey.NO_INTENT, {}


def _get_duplicate_names_matched_response(
    duplicate_names_error: intent.DuplicateNamesMatchedError,
) -> tuple[ErrorKey, dict[str, Any]]:
    """Return key and template arguments for error when intent returns duplicate matches."""

    if duplicate_names_error.area:
        return ErrorKey.DUPLICATE_ENTITIES_IN_AREA, {
            "entity": duplicate_names_error.name,
            "area": duplicate_names_error.area,
        }

    return ErrorKey.DUPLICATE_ENTITIES, {"entity": duplicate_names_error.name}


def _collect_list_references(expression: Expression, list_names: set[str]) -> None:
    """Collect list reference names recursively."""
    if isinstance(expression, Sequence):
        seq: Sequence = expression
        for item in seq.items:
            _collect_list_references(item, list_names)
    elif isinstance(expression, ListReference):
        # {list}
        list_ref: ListReference = expression
        list_names.add(list_ref.slot_name)
