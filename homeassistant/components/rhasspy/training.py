"""
Methods for training a remove Rhasspy server profile.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
from collections import defaultdict
import io
import logging
from typing import Dict, List

from homeassistant.components.shopping_list import INTENT_ADD_ITEM
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_INTENT_COMMANDS,
    CONF_INTENT_FILTERS,
    CONF_MAKE_INTENT_COMMANDS,
    CONF_SHOPPING_LIST_ITEMS,
    CONF_SLOTS,
    EVENT_RHASSPY_TRAINED,
    KEY_COMMAND_TEMPLATE,
    KEY_COMMAND_TEMPLATES,
    KEY_EXCLUDE,
    KEY_INCLUDE,
)
from .core import command_to_sentences
from .default_settings import (
    DEFAULT_INTENT_COMMANDS,
    DEFAULT_INTENT_FILTERS,
    DEFAULT_LANGUAGE,
    DEFAULT_MAKE_INTENT_COMMANDS,
    DEFAULT_SHOPPING_LIST_ITEMS,
    DEFAULT_SLOTS,
)

# -----------------------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)


async def train_rhasspy(provider):
    """Generate voice commands and train a remote Rhasspy server."""
    session = async_get_clientsession(provider.hass)

    sentences_by_intent: Dict[str, List[str]] = defaultdict(list)
    make_default_commands = provider.config.get(
        CONF_MAKE_INTENT_COMMANDS, DEFAULT_MAKE_INTENT_COMMANDS
    )

    if make_default_commands:
        # Use default commands
        intent_commands = dict(
            DEFAULT_INTENT_COMMANDS.get(
                provider.language, DEFAULT_INTENT_COMMANDS[DEFAULT_LANGUAGE]
            )
        )

        # Determine if intents should be included or excluded
        if isinstance(make_default_commands, dict):
            if KEY_INCLUDE in make_default_commands:
                include_intents = set(make_default_commands[KEY_INCLUDE])
                intent_commands = {
                    intent_name: commands
                    for intent_name, commands in intent_commands.items()
                    if intent_name in include_intents
                }
            elif KEY_EXCLUDE in make_default_commands:
                for intent_name in make_default_commands[KEY_EXCLUDE]:
                    del intent_commands[intent_name]
    else:
        # No default commands
        intent_commands = {}

    # Override defaults with user commands
    for intent_type, commands in provider.config.get(CONF_INTENT_COMMANDS, {}).items():
        intent_commands[intent_type] = commands

    # Include/exclude domains/entities per intent for auto-generated commands
    intent_filters = dict(DEFAULT_INTENT_FILTERS)

    # Override defaults with user filters
    for intent_type, filters in provider.config.get(CONF_INTENT_FILTERS, {}).items():
        intent_filters[intent_type] = filters

    # Generate commands
    for intent_type, commands in intent_commands.items():
        if intent_type == INTENT_ADD_ITEM:
            # Special case for shopping list
            sentences_by_intent[intent_type].extend(
                get_shopping_list_commands(
                    provider, intent_commands.get(INTENT_ADD_ITEM, [])
                )
            )
        else:
            # All other intents
            for command in commands:
                for sentence in command_to_sentences(
                    provider.hass,
                    command,
                    provider.entities,
                    intent_filters=intent_filters.get(intent_type, {}),
                ):
                    sentences_by_intent[intent_type].append(sentence)

    # Prune empty intents
    for intent_type in list(sentences_by_intent):
        sentences = [s for s in sentences_by_intent[intent_type] if len(s.strip()) > 0]
        if len(sentences) > 0:
            sentences_by_intent[intent_type] = sentences
        else:
            del sentences_by_intent[intent_type]

    # Check for custom sentences
    num_sentences = sum(len(s) for s in sentences_by_intent.values())
    if num_sentences > 0:
        _LOGGER.debug("Writing sentences (%s)", provider.sentences_url)

        # Generate custom sentences.ini
        with io.StringIO() as sentences_file:
            for intent_type in sorted(sentences_by_intent):
                print(f"[{intent_type}]", file=sentences_file)

                # Write in sorted order so Rhasspy can avoid re-training.
                for sentence in sorted(sentences_by_intent[intent_type]):
                    if sentence.startswith("["):
                        # Escape "[" at start
                        sentence = f"\\{sentence}"

                    print(sentence, file=sentences_file)

                print("", file=sentences_file)

            # POST sentences.ini
            async with session.post(
                provider.sentences_url, data=sentences_file.getvalue()
            ) as res:
                _LOGGER.debug("Sentences result: %s", await res.text())
    else:
        _LOGGER.warning("No commands generated. Not overwriting sentences.")

    # Check for custom words
    custom_words = provider.config.get("custom_words", {})
    if len(custom_words) > 0:
        _LOGGER.debug("Writing custom words (%s)", provider.custom_words_url)

        with io.StringIO() as custom_words_file:
            for word in sorted(custom_words):
                pronunciations = custom_words[word]

                # Accept either string or list of strings
                if isinstance(pronunciations, str):
                    pronunciations = [pronunciations]

                # word P1 P2 P3...
                for pronunciation in sorted(pronunciations):
                    print(word.strip(), pronunciation.strip(), file=custom_words_file)

            # POST custom_words.txt
            async with session.post(
                provider.custom_words_url, data=custom_words_file.getvalue()
            ) as res:
                _LOGGER.debug("Custom words result: %s", await res.text())

    # Check for slots
    slots = dict(DEFAULT_SLOTS)
    for slot_name, slot_values in provider.config.get(CONF_SLOTS, {}).items():
        slots[slot_name] = slot_values

    if len(slots) > 0:
        _LOGGER.debug("Writing slots (%s)", provider.slots_url)
        for slot_name, slot_values in list(slots.items()):
            # Accept either string or list of strings
            if isinstance(slot_values, str):
                slots[slot_name] = [slot_values]

        # POST slots (JSON)
        async with session.post(provider.slots_url, json=slots) as res:
            _LOGGER.debug("Slots result: %s", await res.text())

    # Train profile
    _LOGGER.debug("Training profile (%s)", provider.train_url)
    async with session.post(provider.train_url) as res:
        _LOGGER.debug("Training result: %s", await res.text())

    # Fire event
    provider.hass.bus.async_fire(EVENT_RHASSPY_TRAINED, {})


def get_shopping_list_commands(provider, commands):
    """Generate voice commands for possible shopping list items."""
    possible_items = provider.config.get(
        CONF_SHOPPING_LIST_ITEMS, DEFAULT_SHOPPING_LIST_ITEMS
    )

    # Generate clean item names
    item_names = {
        item_name: provider.clean_name(item_name) for item_name in possible_items
    }

    for command in commands:
        if KEY_COMMAND_TEMPLATE in command:
            templates = [command[KEY_COMMAND_TEMPLATE]]
        elif KEY_COMMAND_TEMPLATES in command:
            templates = command[KEY_COMMAND_TEMPLATES]
        else:
            # No templates
            continue

        for item_name, clean_item_name in item_names.items():
            for template in templates:
                template.hass = provider.hass
                yield template.async_render(
                    {"item_name": item_name, "clean_item_name": clean_item_name}
                )
