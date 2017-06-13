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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import script


REQUIREMENTS = ['fuzzywuzzy==0.15.0']

ATTR_TEXT = 'text'
ATTR_SENTENCE = 'sentence'
DOMAIN = 'conversation'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

SERVICE_PROCESS = 'process'

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): vol.All(cv.string, vol.Lower),
})

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({
    cv.string: vol.Schema({
        vol.Required(ATTR_SENTENCE): cv.string,
        vol.Required('action'): cv.SCRIPT_SCHEMA,
    })
})}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')
    from fuzzywuzzy import process as fuzzyExtract

    logger = logging.getLogger(__name__)
    config = config.get(DOMAIN, {})

    choices = {attrs[ATTR_SENTENCE]: script.Script(
        hass,
        attrs['action'],
        name)
               for name, attrs in config.items()}

    def process(service):
        """Parse text into commands."""
        # if actually configured
        if choices:
            text = service.data[ATTR_TEXT]
            match = fuzzyExtract.extractOne(text, choices.keys())
            scorelimit = 60  # arbitrary value
            logging.info(
                'matched up text %s and found %s',
                text,
                [match[0] if match[1] > scorelimit else 'nothing']
                )
            if match[1] > scorelimit:
                choices[match[0]].run()  # run respective script
                return

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

    hass.services.register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    return True
