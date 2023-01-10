"""Standard conversation implementation for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any

from hassil.intents import Intents, SlotList, TextSlotList
from hassil.recognize import recognize
from hassil.util import merge_dict
from home_assistant_intents import get_intents
import yaml

from homeassistant import core, setup
from homeassistant.helpers import area_registry, entity_registry, intent

from .agent import AbstractConversationAgent, ConversationResult
from .const import DOMAIN
from .util import create_matcher

_LOGGER = logging.getLogger(__name__)

REGEX_TYPE = type(re.compile(""))


@core.callback
def async_register(hass, intent_type, utterances):
    """Register utterances and any custom intents for the default agent.

    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.setdefault(DOMAIN, {})
    conf = intents.setdefault(intent_type, [])

    for utterance in utterances:
        if isinstance(utterance, REGEX_TYPE):
            conf.append(utterance)
        else:
            conf.append(create_matcher(utterance))


@dataclass
class LanguageIntents:
    """Loaded intents for a language."""

    intents: Intents
    intents_dict: dict[str, Any]
    loaded_components: set[str]


class DefaultAgent(AbstractConversationAgent):
    """Default agent for conversation agent."""

    def __init__(self, hass: core.HomeAssistant) -> None:
        """Initialize the default agent."""
        self.hass = hass
        self._lang_intents: dict[str, LanguageIntents] = {}

    async def async_initialize(self, config):
        """Initialize the default agent."""
        if "intent" not in self.hass.config.components:
            await setup.async_setup_component(self.hass, "intent", {})

        config = config.get(DOMAIN, {})
        self.hass.data.setdefault(DOMAIN, {})

        if config:
            _LOGGER.warning(
                "Custom intent sentences have been moved to config/custom_sentences"
            )

    async def async_process(
        self,
        text: str,
        context: core.Context,
        conversation_id: str | None = None,
        language: str | None = None,
    ) -> ConversationResult | None:
        """Process a sentence."""
        language = language or self.hass.config.language
        lang_intents = self._lang_intents.get(language)

        # Reload intents if missing or new components
        if lang_intents is None or (
            lang_intents.loaded_components - self.hass.config.components
        ):
            # Load intents in executor
            lang_intents = await self.hass.async_add_executor_job(
                self.get_or_load_intents,
                language,
            )

        if lang_intents is None:
            # No intents loaded
            _LOGGER.warning("No intents were loaded for language: %s", language)
            return None

        slot_lists: dict[str, SlotList] = {
            "area": self._make_areas_list(),
            "name": self._make_names_list(),
        }

        result = recognize(text, lang_intents.intents, slot_lists=slot_lists)
        if result is None:
            return None

        intent_response = await intent.async_handle(
            self.hass,
            DOMAIN,
            result.intent.name,
            {entity.name: {"value": entity.value} for entity in result.entities_list},
            text,
            context,
            language,
        )

        return ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def get_or_load_intents(self, language: str) -> LanguageIntents | None:
        """Load all intents for language."""
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

            # Check for intents for this component with the target language
            component_intents = get_intents(component, language)
            if component_intents:
                # Merge sentences into existing dictionary
                merge_dict(intents_dict, component_intents)

                # Will need to recreate graph
                intents_changed = True
                _LOGGER.debug(
                    "Loaded intents component=%s, language=%s", component, language
                )

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

        if not intents_dict:
            return None

        if not intents_changed and lang_intents is not None:
            return lang_intents

        # This can be made faster by not re-parsing existing sentences.
        # But it will likely only be called once anyways, unless new
        # components with sentences are often being loaded.
        intents = Intents.from_dict(intents_dict)

        if lang_intents is None:
            lang_intents = LanguageIntents(intents, intents_dict, loaded_components)
            self._lang_intents[language] = lang_intents
        else:
            lang_intents.intents = intents

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
            entry = registry.async_get(state.entity_id)
            if entry is not None:
                if entry.entity_category:
                    # Skip configuration/diagnostic entities
                    continue

                if entry.aliases:
                    for alias in entry.aliases:
                        names.append((alias, state.entity_id))

            # Default name
            names.append((state.name, state.entity_id))

        return TextSlotList.from_tuples(names)
