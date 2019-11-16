"""
Shared functions and classes for Rhasspy integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import logging
from typing import Dict, Iterable, Set

import attr

from homeassistant.core import State
from homeassistant.helpers.template import Template

from .const import (
    KEY_COMMAND,
    KEY_COMMAND_TEMPLATE,
    KEY_COMMAND_TEMPLATES,
    KEY_COMMANDS,
    KEY_DATA,
    KEY_DATA_TEMPLATE,
    KEY_DOMAINS,
    KEY_ENTITIES,
    KEY_EXCLUDE,
    KEY_INCLUDE,
)

# -----------------------------------------------------------------------------

_LOGGER = logging.getLogger("rhasspy")


@attr.s
class EntityCommandInfo:
    """Information used to generate a voice command for an entity."""

    entity_id: str = attr.ib()
    friendly_name: str = attr.ib()
    speech_name: str = attr.ib()
    state: State = attr.ib()


# -----------------------------------------------------------------------------
# Voice Command Functions
# -----------------------------------------------------------------------------


def command_to_sentences(
    hass,
    command,
    entities: Dict[str, EntityCommandInfo],
    intent_filters=None,
    template_dict=None,
) -> Iterable[str]:
    """Transform an intent command to one or more Rhasspy sentence templates."""
    if isinstance(command, str):
        # Literal sentence
        yield command
    elif isinstance(command, Template):
        # Template sentence
        command.hass = hass
        yield command.async_render(template_dict or {})
    else:
        # Handle complex command object
        for sentence in _command_object_to_sentences(
            hass,
            command,
            entities,
            intent_filters=intent_filters,
            template_dict=template_dict,
        ):
            yield sentence


def _command_object_to_sentences(
    hass,
    command,
    entities: Dict[str, EntityCommandInfo],
    intent_filters=None,
    template_dict=None,
) -> Iterable[str]:
    """Transform a complex command object to Rhasspy sentences."""
    template_dict = template_dict or {}

    # Command object
    # - command
    #   command_template
    #   commands
    #   command_templates
    #   data
    #   data_template
    #   include:
    #     domains
    #     entities
    #   exclude:
    #     domains
    #     entities
    commands = []
    have_templates = False
    intent_filters = intent_filters or {}

    if KEY_COMMAND in command:
        commands = [command[KEY_COMMAND]]
    elif KEY_COMMANDS in command:
        commands = command[KEY_COMMANDS]
    elif KEY_COMMAND_TEMPLATE in command:
        commands = [command[KEY_COMMAND_TEMPLATE]]
        have_templates = True
    elif KEY_COMMAND_TEMPLATES in command:
        commands = command[KEY_COMMAND_TEMPLATES]
        have_templates = True

    # Entities to include
    possible_entity_ids: Set[str] = set()

    # Lower-cased speech names already used.
    # Avoids duplicate entities.
    used_names: Set[str] = set()

    if have_templates:
        # Intent-level include/exclude settings
        if KEY_INCLUDE in intent_filters:
            include_filters = intent_filters[KEY_INCLUDE]
            intent_include_domains = set(include_filters.get(KEY_DOMAINS, []))

            # Include intent-level entiies
            possible_entity_ids.update(include_filters.get(KEY_ENTITIES, []))
        else:
            # No inclusions
            intent_include_domains = set()

        if KEY_EXCLUDE in intent_filters:
            exclude_filters = intent_filters[KEY_EXCLUDE]
            intent_exclude_domains = set(exclude_filters.get(KEY_DOMAINS, []))
            intent_exclude_entities = set(exclude_filters.get(KEY_ENTITIES, []))
        else:
            # No exclusions
            intent_exclude_domains = set()
            intent_exclude_entities = set()

        # Gather all entities to be used in command templates
        include_domains = set(intent_include_domains)
        if KEY_INCLUDE in command:
            # Include command-specific domains
            include_domains.update(command[KEY_INCLUDE].get(KEY_DOMAINS, []))

        for entity_id, info in entities.items():
            if (len(include_domains) == 0) or (info.state.domain in include_domains):
                if info.state.domain not in intent_exclude_domains:
                    speech_name_lower = info.speech_name.lower()
                    if speech_name_lower not in used_names:
                        possible_entity_ids.add(entity_id)
                        used_names.add(speech_name_lower)

        if KEY_INCLUDE in command:
            # Include command-specific entities
            possible_entity_ids.update(command[KEY_INCLUDE].get(KEY_ENTITIES, []))

        exclude_entities = set(intent_exclude_entities)
        if KEY_EXCLUDE in command:
            # Exclude command-specific entities
            exclude_entities.update(command[KEY_EXCLUDE][KEY_ENTITIES])

        # Exclude intent-level entities
        possible_entity_ids.difference_update(exclude_entities)

    # Generate Rhasspy sentences for each command (template)
    for sub_command in commands:
        if not have_templates:
            # Literal sentence
            command_strs = [sub_command]
        elif len(possible_entity_ids) == 0:
            # Assume template doesn't refer to entities
            command_strs = command_to_sentences(hass, sub_command, entities)
        else:
            # Render template for each possible entity (state)
            command_strs = []
            for entity_id in possible_entity_ids:
                if entity_id not in entities:
                    continue

                info = entities.get(entity_id)
                template_dict = {
                    "entity": info.state,
                    "speech_name": info.speech_name,
                    "friendly_name": info.friendly_name,
                }
                command_strs.extend(
                    command_to_sentences(
                        hass, sub_command, entities, template_dict=template_dict
                    )
                )

        # Extra data to attach to command
        command_data = dict(command.get(KEY_DATA, {}))
        command_data_template = command.get(KEY_DATA_TEMPLATE, {})

        # Render templates
        for data_key, data_template in command_data_template.items():
            data_template.hass = hass
            command_data[data_key] = data_template.render()

        # Append to sentences.
        # Use special form "(:){key:value}" to carry
        # information with the voice command without
        # changing to wording.
        for command_str in command_strs:
            for data_key, data_value in command_data.items():
                data_value = str(data_value)
                command_str = f"{command_str} (:){{{data_key}:{data_value}}}"

            yield command_str
