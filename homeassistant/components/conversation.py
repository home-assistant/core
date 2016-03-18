"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import logging
import re

from homeassistant import core
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)

DOMAIN = "conversation"

SERVICE_PROCESS = "process"

ATTR_TEXT = "text"

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

REQUIREMENTS = ['fuzzywuzzy==0.8.0']


def setup(hass, config):
    """Register the process service."""
    from fuzzywuzzy import process as fuzzyExtract

    logger = logging.getLogger(__name__)

    def process(service):
        """Parse text into commands."""
        if ATTR_TEXT not in service.data:
            logger.error("Received process service call without a text")
            return

        text = service.data[ATTR_TEXT].lower()
        match = REGEX_TURN_COMMAND.match(text)

        if not match:
            logger.error("Unable to process: %s", text)
            return

        name, command = match.groups()
        entities = {state.entity_id: state.name for state in hass.states.all()}
        entity_ids = fuzzyExtract.extractOne(name, entities,
                                             score_cutoff=65)[2]

        if not entity_ids:
            logger.error(
                "Could not find entity id %s from text %s", name, text)
            return

        if command == 'on':
            hass.services.call(core.DOMAIN, SERVICE_TURN_ON, {
                ATTR_ENTITY_ID: entity_ids,
            }, blocking=True)

        elif command == 'off':
            hass.services.call(core.DOMAIN, SERVICE_TURN_OFF, {
                ATTR_ENTITY_ID: entity_ids,
            }, blocking=True)

        else:
            logger.error(
                'Got unsupported command %s from text %s', command, text)

    hass.services.register(DOMAIN, SERVICE_PROCESS, process)

    return True
