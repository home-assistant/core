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
from yaml import safe_load

from homeassistant import core, setup
from homeassistant.helpers import area_registry, entity_registry, intent
from homeassistant.loader import async_get_integration

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

    async def async_process(
        self,
        text: str,
        context: core.Context,
        conversation_id: str | None = None,
        language: str | None = None,
    ) -> ConversationResult | None:
        """Process a sentence."""
        language = language or self.hass.config.language
        lang_intents = await self.async_get_or_load_intents(language)
        if lang_intents is None:
            # No intents loaded
            return None

        slot_lists: dict[str, SlotList] = {
            "area": self._make_areas_list(),
            "name": self._make_names_list(),
        }

        result = recognize(text, lang_intents, slot_lists=slot_lists)
        if result is not None:
            intent_response = await intent.async_handle(
                self.hass,
                DOMAIN,
                result.intent.name,
                {
                    entity.name: {"value": entity.value}
                    for entity in result.entities_list
                },
                text,
                context,
                language,
            )

            return ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        return None

    async def async_get_or_load_intents(self, language: str) -> Intents | None:
        """Load all intents for language."""
        lang_intents = self._lang_intents.get(language)

        if lang_intents is None:
            # Load all sentences for language
            intents_dict: dict[str, Any] = {}
            for component in self.hass.config.components:
                # Check for sentences in this component with the target language
                sentences_dir = await self.async_get_sentences_dir(component)
                yaml_path = sentences_dir / f"{language}.yaml"
                if yaml_path.exists():
                    # Merge sentences into existing dictionary
                    _LOGGER.info("Loading intents YAML file %s", yaml_path)
                    with open(yaml_path, encoding="utf-8") as yaml_file:
                        merge_dict(intents_dict, safe_load(yaml_file))

            if not intents_dict:
                _LOGGER.warning("No intents loaded")
                return None

            lang_intents = LanguageIntents(
                intents=Intents.from_dict(intents_dict),
                intents_dict=intents_dict,
                loaded_components=set(self.hass.config.components),
            )
            self._lang_intents[language] = lang_intents
        else:
            # Check if any new components have been loaded
            components_change = False
            for component in self.hass.config.components:
                if component not in lang_intents.loaded_components:
                    # Check for sentences in this component with the target language
                    sentences_dir = await self.async_get_sentences_dir(component)
                    yaml_path = sentences_dir / f"{language}.yaml"
                    if yaml_path.exists():
                        # Merge sentences into existing dictionary
                        _LOGGER.info("Loading intents YAML file %s", yaml_path)
                        with open(yaml_path, encoding="utf-8") as yaml_file:
                            merge_dict(lang_intents.intents_dict, safe_load(yaml_file))

                        # Will need to recreate graph
                        lang_intents.loaded_components.add(component)
                        components_change = True

            if components_change:
                # This can be made faster by not re-parsing existing sentences.
                # But it will likely only be called once anyways, unless new
                # components with sentences are often being loaded.
                lang_intents.intents = Intents.from_dict(lang_intents.intents_dict)

        return lang_intents.intents

    async def async_get_sentences_dir(self, component: str) -> Path:
        """Get the sentences directory for a component."""
        domain = component.rpartition(".")[-1]
        integration = await async_get_integration(self.hass, domain)
        return integration.file_path / "sentences"

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
            names.append((state.name, state.entity_id))
            entry = registry.async_get(state.entity_id)
            if (entry is not None) and entry.aliases:
                for alias in entry.aliases:
                    names.append((alias, state.entity_id))

        return TextSlotList.from_tuples(names)
