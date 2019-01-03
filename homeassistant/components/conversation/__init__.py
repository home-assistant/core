"""
Support for functionality to have conversations with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/conversation/
"""
import logging
import re

import voluptuous as vol

from homeassistant import core
from homeassistant.components import http
from homeassistant.components.conversation.util import create_matcher
from homeassistant.components.http.data_validator import (
    RequestDataValidator)
from homeassistant.components.cover import (INTENT_OPEN_COVER,
                                            INTENT_CLOSE_COVER)
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.loader import bind_hass
from homeassistant.setup import (ATTR_COMPONENT)

_LOGGER = logging.getLogger(__name__)

ATTR_TEXT = 'text'

DEPENDENCIES = ['http']
DOMAIN = 'conversation'

REGEX_TURN_COMMAND = re.compile(r'turn (?P<name>(?: |\w)+) (?P<command>\w+)')
REGEX_TYPE = type(re.compile(''))

UTTERANCES = {
    'cover': {
        INTENT_OPEN_COVER: ['Open [the] [a] [an] {name}[s]'],
        INTENT_CLOSE_COVER: ['Close [the] [a] [an] {name}[s]']
    }
}

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
            conf.append(create_matcher(utterance))


async def async_setup(hass, config):
    """Register the process service."""
    config = config.get(DOMAIN, {})
    intents = hass.data.get(DOMAIN)

    if intents is None:
        intents = hass.data[DOMAIN] = {}

    for intent_type, utterances in config.get('intents', {}).items():
        conf = intents.get(intent_type)

        if conf is None:
            conf = intents[intent_type] = []

        conf.extend(create_matcher(utterance) for utterance in utterances)

    async def process(service):
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug('Processing: <%s>', text)
        try:
            await _process(hass, text)
        except intent.IntentHandleError as err:
            _LOGGER.error('Error processing %s: %s', text, err)

    hass.services.async_register(
        DOMAIN, SERVICE_PROCESS, process, schema=SERVICE_PROCESS_SCHEMA)

    hass.http.register_view(ConversationProcessView)

    # We strip trailing 's' from name because our state matcher will fail
    # if a letter is not there. By removing 's' we can match singular and
    # plural names.

    async_register(hass, intent.INTENT_TURN_ON, [
        'Turn [the] [a] {name}[s] on',
        'Turn on [the] [a] [an] {name}[s]',
    ])
    async_register(hass, intent.INTENT_TURN_OFF, [
        'Turn [the] [a] [an] {name}[s] off',
        'Turn off [the] [a] [an] {name}[s]',
    ])
    async_register(hass, intent.INTENT_TOGGLE, [
        'Toggle [the] [a] [an] {name}[s]',
        '[the] [a] [an] {name}[s] toggle',
    ])

    @callback
    def register_utterances(component):
        """Register utterances for a component."""
        if component not in UTTERANCES:
            return
        for intent_type, sentences in UTTERANCES[component].items():
            async_register(hass, intent_type, sentences)

    @callback
    def component_loaded(event):
        """Handle a new component loaded."""
        register_utterances(event.data[ATTR_COMPONENT])

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded)

    # Check already loaded components.
    for component in hass.config.components:
        register_utterances(component)

    return True


async def _process(hass, text):
    """Process a line of text."""
    intents = hass.data.get(DOMAIN, {})

    for intent_type, matchers in intents.items():
        for matcher in matchers:
            match = matcher.match(text)

            if not match:
                continue

            response = await hass.helpers.intent.async_handle(
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
    async def post(self, request, data):
        """Send a request for processing."""
        hass = request.app['hass']

        try:
            intent_result = await _process(hass, data['text'])
        except intent.IntentHandleError as err:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech(str(err))

        if intent_result is None:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech("Sorry, I didn't understand that")

        return self.json(intent_result)
