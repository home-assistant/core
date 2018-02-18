"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import asyncio
import logging
import re

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http
from homeassistant.components.http.data_validator import (
    RequestDataValidator)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = 'text'

DEPENDENCIES = ['http']
DOMAIN = 'conversation'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')
REGEX_TYPE = type(re.compile(''))

SERVICE_PROCESS = 'process'

SERVICE_PROCESS_SCHEMA = vol.Schema({
    vol.Required(ATTR_TEXT): cv.string,
})

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({
    vol.Optional('intents'): vol.Schema({
        cv.string: vol.All(cv.ensure_list, [cv.string])
    })
})}, extra=vol.ALLOW_EXTRA)


@core.callback
@bind_hass
def async_register(hass, intent_type, utterances):
    """Register utterances and any custom intents.

    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    conf = intents.get(intent_type)

    if conf is None:
        conf = intents[intent_type] = []

    for utterance in utterances:
        if isinstance(utterance, REGEX_TYPE):
            conf.append(utterance)
        else:
            conf.append(_create_matcher(utterance))


@asyncio.coroutine
def async_setup(hass, config):
    """Register the process service."""
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

    async_register(hass, intent.INTENT_TURN_ON,
                   ['Turn {name} on', 'Turn on {name}'])
    async_register(hass, intent.INTENT_TURN_OFF,
                   ['Turn {name} off', 'Turn off {name}'])
    async_register(hass, intent.INTENT_TOGGLE,
                   ['Toggle {name}', '{name} toggle'])

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

            response = yield from hass.helpers.intent.async_handle(
                DOMAIN, intent_type,
                {key: {'value': value} for key, value
                 in match.groupdict().items()}, text)
            return response


class ConversationProcessView(http.HomeAssistantView):
    """View to retrieve shopping list content."""

    url = '/api/conversation/process'
    name = "api:conversation:process"

    @RequestDataValidator(vol.Schema({
        vol.Required('text'): str,
    }))
    @asyncio.coroutine
    def post(self, request, data):
        """Send a request for processing."""
        hass = request.app['hass']

        intent_result = yield from _process(hass, data['text'])

        if intent_result is None:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech("Sorry, I didn't understand that")

        return self.json(intent_result)
