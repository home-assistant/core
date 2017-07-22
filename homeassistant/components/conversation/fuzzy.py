"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""

import logging
import re
import warnings

import asyncio
from homeassistant import core
from homeassistant.const import (SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                 ATTR_ENTITY_ID)
from homeassistant.components.conversation import (ConversationEngine,
                                                   PLATFORM_SCHEMA)
from homeassistant.helpers import script
import homeassistant.helpers.config_validation as cv
import voluptuous as vol


_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['fuzzywuzzy==0.15.0']

ATTR_SENTENCE = 'sentence'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    cv.string: vol.Schema({
        vol.Required(ATTR_SENTENCE): cv.string,
        vol.Required('action'): cv.SCRIPT_SCHEMA,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_get_engine(hass, config):
    """Set up a simple textfile conversation component."""
    return FuzzyProvider(hass, config)


class FuzzyProvider(ConversationEngine):
    """Textfile conversation component. Simply writes each text to a file."""

    def __init__(self, hass, config):
        """Init Textfile conversation provider."""
        super().__init__(hass)
        self.name = 'fuzzy'

        warnings.filterwarnings('ignore', module='fuzzywuzzy')
        from fuzzywuzzy import process as fuzzyExtract
        self._extract = fuzzyExtract.extractOne

        self.choices = {attrs[ATTR_SENTENCE]: script.Script(
            hass,
            attrs['action'],
            name)
            for name, attrs in config.items() if name != 'platform'}

    @asyncio.coroutine
    def process(self, text):
        """Parse text into commands."""
        # If choices are  configured
        if self.choices:
            match = self._extract(text, self.choices.keys())
            scorelimit = 60  # arbitrary value
            logging.info(
                'matched up text %s and found %s',
                text,
                [match[0] if match[1] > scorelimit else 'nothing']
                )
            if match[1] > scorelimit:
                self.hass.async_add_job(self.choices[match[0]].async_run())
                return

        # If choices not configured or text didn't match any choice, use regexp
        match = REGEX_TURN_COMMAND.match(text)

        if not match:
            _LOGGER.error("Unable to process: %s", text)
            return

        # Regexp was matched, try to find the entity referenced in the text
        name, command = match.groups()
        states = self.hass.states.async_all()
        entities = {state.entity_id: state.name
                    for state in states}
        entity_ids = self._extract(name, entities, score_cutoff=65)[2]

        if not entity_ids:
            _LOGGER.error(
                "Could not find entity id %s from text %s", name, text)
            return

        # Apply command to entity
        if command == 'on':
            yield from self.hass.services.async_call(
                core.DOMAIN, SERVICE_TURN_ON, {
                    ATTR_ENTITY_ID: entity_ids,
                }, blocking=True)

        elif command == 'off':
            yield from self.hass.services.async_call(
                core.DOMAIN, SERVICE_TURN_OFF, {
                    ATTR_ENTITY_ID: entity_ids,
                }, blocking=True)

        else:
            _LOGGER.error('Got unsupported command %s from text %s',
                          command, text)
