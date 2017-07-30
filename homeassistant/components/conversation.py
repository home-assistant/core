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
from homeassistant.loader import bind_hass
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, HTTP_BAD_REQUEST)
from homeassistant.helpers import intent, config_validation as cv
from homeassistant.components import http


REQUIREMENTS = ['fuzzywuzzy==0.15.1']
DEPENDENCIES = ['http']

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

_LOGGER = logging.getLogger(__name__)


@core.callback
@bind_hass
def async_register(hass, intent_type, utterances):
    """Register an intent.

    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    conf = intents.get(intent_type)

    if conf is None:
        conf = intents[intent_type] = []

    conf.extend(_create_matcher(utterance) for utterance in utterances)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the process service."""
    warnings.filterwarnings('ignore', module='fuzzywuzzy')

    config = config.get(DOMAIN, {})
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    for intent_type, utterances in config.get('intents', {}).items():
        conf = intents.get(intent_type)

        if conf is None:
            conf = intents[intent_type] = []

        conf.extend(_create_matcher(utterance) for utterance in utterances)

    @asyncio.coroutine
    def process(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        yield from _process(hass, text)

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    hass.http.register_view(ConversationProcessView)

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


@asyncio.coroutine
def _process(hass, text):
    """Process a line of text."""
    intents = hass.data.get(DOMAIN, {})

    for intent_type, matchers in intents.items():
        for matcher in matchers:
            match = matcher.match(text)

            if not match:
                continue

            response = yield from intent.async_handle(
                hass, DOMAIN, intent_type,
                {key: {'value': value} for key, value
                 in match.groupdict().items()}, text)
            return response

    from fuzzywuzzy import process as fuzzyExtract
    text = text.lower()
    match = REGEX_TURN_COMMAND.match(text)

    if not match:
        _LOGGER.error("Unable to process: %s", text)
        return None

    name, command = match.groups()
    entities = {state.entity_id: state.name for state
                in hass.states.async_all()}
    entity_ids = fuzzyExtract.extractOne(
        name, entities, score_cutoff=65)[2]

    if not entity_ids:
        _LOGGER.error(
            "Could not find entity id %s from text %s", name, text)
        return None

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
        _LOGGER.error('Got unsupported command %s from text %s',
                      command, text)

    return None


class ConversationProcessView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/conversation/process'
    name = "api:conversation:process"

    @asyncio.coroutine
    def post(self, request):
        """Send a request for processing."""
        hass = request.app['hass']
        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message('Invalid JSON specified',
                                     HTTP_BAD_REQUEST)

        text = data.get('text')

        if text is None:
            return self.json_message('Missing "text" key in JSON.',
                                     HTTP_BAD_REQUEST)

        intent_result = yield from _process(hass, text)

        if intent_result is None:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech("Sorry, I didn't understand that")

        return self.json(intent_result)
