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

REQUIREMENTS = ['fuzzywuzzy==0.14.0']

ATTR_TEXT = 'text'

DOMAIN = 'conversation'

COMMANDS = {'en': {'turn_on':r'(?P<command>turn on|activ\w+|enable|open|launch|start) (?P<name>(?: |\w)+)',
                  'turn_off':r'(?P<command>turn off|disactiv\w+|disable|close) (?P<name>(?: |\w)+)',
                  },
            'fr': {'turn_on':r'(?P<command>allum\w+|lanc\w+|activ\w+|ouvr\w+) (?P<name>(?: |\w)+)',
                  'turn_off':r'(?P<command>étein\w+|ferm\w+|stop|arrêt\w+|désactiv\w+) (?P<name>(?: |\w)+)',
                  },
            'es': {'turn_on':r'(?P<command>enciend\w+) (?P<name>(?: |\w)+)',
                  'turn_off':r'(?P<command>apag\w+) (?P<name>(?: |\w)+)',
                  },
            }

SERVICE_PROCESS = 'process'

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): vol.All(cv.string,
                                     vol.Lower),
})

CONF_LANG = 'language'

DEFAULT_LANG = 'en'

SUPPORT_LANGUAGES = ['en', 'fr', 'es']


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
                        vol.Optional(CONF_LANG,default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
                        }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')
    from fuzzywuzzy import process as fuzzyExtract

    logger = logging.getLogger(__name__)
    language = config[DOMAIN].get(CONF_LANG, DEFAULT_LANG)
    commands = COMMANDS[language]
    for c in commands:
        commands[c] = re.compile(commands[c])

    def process(service):
        """Parse text into commands."""
        
        text = service.data[ATTR_TEXT]
        match = None
        for command in commands:
            match = commands[command].match(text)
            if match:
                break
            
        if not match:
            logger.error("Unable to process: %s", text)
            return

        name = match.group('name')
        entities = {state.entity_id: state.name for state in hass.states.all()}
        entity_ids = fuzzyExtract.extractOne(
            name, entities, score_cutoff=65)[2]

        if not entity_ids:
            logger.error(
                "Could not find entity id %s from text %s", name, text)
            return

        if command == 'turn_on':
            hass.services.call(core.DOMAIN, SERVICE_TURN_ON, {
                ATTR_ENTITY_ID: entity_ids,
            }, blocking=True)
        elif command == 'turn_off':
            hass.services.call(core.DOMAIN, SERVICE_TURN_OFF, {
                ATTR_ENTITY_ID: entity_ids,
            }, blocking=True)
        else:
            logger.error('Got unsupported command %s from text %s',
                         command, text)

    hass.services.register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    return True
