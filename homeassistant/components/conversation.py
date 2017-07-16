"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import asyncio
import logging
import re
import warnings

import voluptuous as vol

from homeassistant import core
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['fuzzywuzzy==0.15.0']
DEPENDENCIES = ['intent']

ATTR_TEXT = 'text'
DOMAIN = 'conversation'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')

SERVICE_PROCESS = 'process'

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({
    vol.Optional('intents'): vol.Schema({
        cv.string: vol.All(cv.ensure_list, [cv.string])
    })
})}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')

    logger = logging.getLogger(__name__)
    config = config.get(DOMAIN, {})

    intents = {
        intent: [_create_matcher(sentence) for sentence in sentences]
        for intent, sentences in config.get('intents', {}).items()
    }

    @asyncio.coroutine
    def process(service):
        """Parse text into commands."""
        from fuzzywuzzy import process as fuzzyExtract

        text = service.data[ATTR_TEXT]

        for intent, matchers in intents.items():
            for matcher in matchers:
                match = matcher.match(text)

                if not match:
                    continue

                yield from hass.intent.async_handle(
                    DOMAIN, intent, {key: {'value': value} for key, value
                                     in match.groupdict().items()}, text)
                return

        text = text.lower()
        match = REGEX_TURN_COMMAND.match(text)

        if not match:
            logger.error("Unable to process: %s", text)
            return

        name, command = match.groups()
        entities = {state.entity_id: state.name for state
                    in hass.states.async_all()}
        entity_ids = fuzzyExtract.extractOne(
            name, entities, score_cutoff=65)[2]

        if not entity_ids:
            logger.error(
                "Could not find entity id %s from text %s", name, text)
            return

        if command == 'on':
            yield from hass.services.async_call(
                core.DOMAIN, SERVICE_TURN_ON, {
                    ATTR_ENTITY_ID: entity_ids,
                }, blocking=True)

        elif command == 'off':
            yield from hass.services.async_call(
                core.DOMAIN, SERVICE_TURN_OFF, {
                    ATTR_ENTITY_ID: entity_ids,
                }, blocking=True)

        else:
            logger.error('Got unsupported command %s from text %s',
                         command, text)

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    return True


def _create_matcher(utterance):
    """Create a regex that matches the utterance."""
    parts = re.split(r'({\w+})', utterance)
    group_matcher = re.compile(r'{(\w+)}')

    pattern = ['^']

    for part in parts:
        match = group_matcher.match(part)

        if match is None:
            pattern.append(part)
            continue

        pattern.append('(?P<{}>{})'.format(match.groups()[0], r'[\w ]+'))

    pattern.append('$')
    return re.compile(''.join(pattern), re.I)
