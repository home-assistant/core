"""
Support for Dialogflow webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/dialogflow/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.helpers import intent, template
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

CONF_INTENTS = 'intents'
CONF_SPEECH = 'speech'
CONF_ACTION = 'action'
CONF_ASYNC_ACTION = 'async_action'

DEFAULT_CONF_ASYNC_ACTION = False
DEPENDENCIES = ['http']
DOMAIN = 'dialogflow'

INTENTS_API_ENDPOINT = '/api/dialogflow'

SOURCE = "Home Assistant Dialogflow"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up Dialogflow component."""
    hass.http.register_view(DialogflowIntentsView)

    return True


class DialogflowIntentsView(HomeAssistantView):
    """Handle Dialogflow requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:dialogflow'

    @asyncio.coroutine
    def post(self, request):
        """Handle Dialogflow."""
        hass = request.app['hass']
        data = yield from request.json()

        _LOGGER.debug("Received Dialogflow request: %s", data)

        req = data.get('result')

        if req is None:
            _LOGGER.error("Received invalid data from Dialogflow: %s", data)
            return self.json_message(
                "Expected result value not received", HTTP_BAD_REQUEST)

        action_incomplete = req['actionIncomplete']

        if action_incomplete:
            return None

        action = req.get('action')
        parameters = req.get('parameters')
        dialogflow_response = DialogflowResponse(parameters)

        if action == "":
            _LOGGER.warning("Received intent with empty action")
            dialogflow_response.add_speech(
                "You have not defined an action in your Dialogflow intent.")
            return self.json(dialogflow_response)

        try:
            intent_response = yield from intent.async_handle(
                hass, DOMAIN, action,
                {key: {'value': value} for key, value
                 in parameters.items()})

        except intent.UnknownIntent as err:
            _LOGGER.warning("Received unknown intent %s", action)
            dialogflow_response.add_speech(
                "This intent is not yet configured within Home Assistant.")
            return self.json(dialogflow_response)

        except intent.InvalidSlotInfo as err:
            _LOGGER.error("Received invalid slot data: %s", err)
            return self.json_message('Invalid slot data received',
                                     HTTP_BAD_REQUEST)
        except intent.IntentError:
            _LOGGER.exception("Error handling request for %s", action)
            return self.json_message('Error handling intent', HTTP_BAD_REQUEST)

        if 'plain' in intent_response.speech:
            dialogflow_response.add_speech(
                intent_response.speech['plain']['speech'])

        return self.json(dialogflow_response)


class DialogflowResponse(object):
    """Help generating the response for Dialogflow."""

    def __init__(self, parameters):
        """Initialize the Dialogflow response."""
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
        """Return response in a Dialogflow valid dictionary."""
        return {
            'speech': self.speech,
            'displayText': self.speech,
            'source': SOURCE,
        }
