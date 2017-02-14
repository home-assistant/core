"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import logging
import re
import warnings

import voluptuous as vol

from homeassistant import core
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.helpers import script, config_validation as cv

REQUIREMENTS = ['fuzzywuzzy==0.14.0']

ATTR_TEXT = 'text'

CONF_ACTION = 'action'

DOMAIN = 'conversation'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

SERVICE_PROCESS = 'process'

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): vol.All(cv.string, vol.Lower),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')
    from fuzzywuzzy import process as fuzzyExtract

    logger = logging.getLogger(__name__)

    # Get action entity if defined
    action = config[DOMAIN].get(CONF_ACTION, None)

    def process_action(service):
        """Calls an action for processing of the text."""
        text = service.data[ATTR_TEXT]

        if not text.strip():
            return

        logger.info("Conversation query: %s", (text))

        parameters = {'text': text}
        si = script.Script(hass, action,
                           "Conversation action: {}".format(action))

        hass.async_add_job(si.async_run(parameters))

    def process_fuzzy(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        match = REGEX_TURN_COMMAND.match(text)

        if not match:
            logger.error("Unable to process: %s", text)
            return

        name, command = match.groups()
        entities = {state.entity_id: state.name for state in hass.states.all()}
        entity_ids = fuzzyExtract.extractOne(
            name, entities, score_cutoff=65)[2]

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
            logger.error('Got unsupported command %s from text %s',
                         command, text)

    # Use action if configured, otherwise use fuzzy "turn on/off" matching
    process = process_action if action else process_fuzzy

    # Register the service call ("conversation.process")
    hass.services.register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    return True
