"""
Support for API.AI webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/apiai/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import PROJECT_NAME, HTTP_BAD_REQUEST
from homeassistant.helpers import intent, template
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

INTENTS_API_ENDPOINT = '/api/apiai'

CONF_INTENTS = 'intents'
CONF_SPEECH = 'speech'
CONF_ACTION = 'action'
CONF_ASYNC_ACTION = 'async_action'

DEFAULT_CONF_ASYNC_ACTION = False

DOMAIN = 'apiai'
DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Activate API.AI component."""
    hass.http.register_view(ApiaiIntentsView)

    return True


class ApiaiIntentsView(HomeAssistantView):
    """Handle API.AI requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:apiai'

    @asyncio.coroutine
    def post(self, request):
        """Handle API.AI."""
        hass = request.app['hass']
        data = yield from request.json()

        _LOGGER.debug("Received api.ai request: %s", data)

        req = data.get('result')

        if req is None:
            _LOGGER.error("Received invalid data from api.ai: %s", data)
            return self.json_message(
                "Expected result value not received", HTTP_BAD_REQUEST)

        action_incomplete = req['actionIncomplete']

        if action_incomplete:
            return None

        action = req.get('action')
        parameters = req.get('parameters')
        apiai_response = ApiaiResponse(parameters)

        if action == "":
            _LOGGER.warning("Received intent with empty action")
            apiai_response.add_speech(
                "You have not defined an action in your api.ai intent.")
            return self.json(apiai_response)

        try:
            intent_response = yield from intent.async_handle(
                hass, DOMAIN, action,
                {key: {'value': value} for key, value
                 in parameters.items()})

        except intent.UnknownIntent as err:
            _LOGGER.warning('Received unknown intent %s', action)
            apiai_response.add_speech(
                "This intent is not yet configured within Home Assistant.")
            return self.json(apiai_response)

        except intent.InvalidSlotInfo as err:
            _LOGGER.error('Received invalid slot data: %s', err)
            return self.json_message('Invalid slot data received',
                                     HTTP_BAD_REQUEST)
        except intent.IntentError:
            _LOGGER.exception('Error handling request for %s', action)
            return self.json_message('Error handling intent', HTTP_BAD_REQUEST)

        if 'plain' in intent_response.speech:
            apiai_response.add_speech(
                intent_response.speech['plain']['speech'])

        return self.json(apiai_response)


class ApiaiResponse(object):
    """Help generating the response for API.AI."""

    def __init__(self, parameters):
        """Initialize the response."""
        self.speech = None
        self.parameters = {}
        # Parameter names replace '.' and '-' for '_'
        for key, value in parameters.items():
            underscored_key = key.replace('.', '_').replace('-', '_')
            self.parameters[underscored_key] = value

    def add_speech(self, text):
        """Add speech to the response."""
        assert self.speech is None

        if isinstance(text, template.Template):
            text = text.async_render(self.parameters)

        self.speech = text

    def as_dict(self):
        """Return response in an API.AI valid dict."""
        return {
            'speech': self.speech,
            'displayText': self.speech,
            'source': PROJECT_NAME,
        }
