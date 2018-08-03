"""
Support for Dialogflow webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/dialogflow/
"""
import logging

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
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


class DialogFlowError(HomeAssistantError):
    """Raised when a DialogFlow error happens."""


async def async_setup(hass, config):
    """Set up Dialogflow component."""
    hass.http.register_view(DialogflowIntentsView)

    return True


class DialogflowIntentsView(HomeAssistantView):
    """Handle Dialogflow requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:dialogflow'

    async def post(self, request):
        """Handle Dialogflow."""
        hass = request.app['hass']
        message = await request.json()

        _LOGGER.debug("Received Dialogflow request: %s", message)

        try:
            response = await async_handle_message(hass, message)
            return b'' if response is None else self.json(response)

        except DialogFlowError as err:
            _LOGGER.warning(str(err))
            return self.json(dialogflow_error_response(
                hass, message, str(err)))

        except intent.UnknownIntent as err:
            _LOGGER.warning(str(err))
            return self.json(dialogflow_error_response(
                hass, message,
                "This intent is not yet configured within Home Assistant."))

        except intent.InvalidSlotInfo as err:
            _LOGGER.warning(str(err))
            return self.json(dialogflow_error_response(
                hass, message,
                "Invalid slot information received for this intent."))

        except intent.IntentError as err:
            _LOGGER.warning(str(err))
            return self.json(dialogflow_error_response(
                hass, message, "Error handling intent."))


def dialogflow_error_response(hass, message, error):
    """Return a response saying the error message."""
    dialogflow_response = DialogflowResponse(message['result']['parameters'])
    dialogflow_response.add_speech(error)
    return dialogflow_response.as_dict()


async def async_handle_message(hass, message):
    """Handle a DialogFlow message."""
    req = message.get('result')
    action_incomplete = req['actionIncomplete']

    if action_incomplete:
        return None

    action = req.get('action', '')
    parameters = req.get('parameters').copy()
    parameters["dialogflow_query"] = message
    dialogflow_response = DialogflowResponse(parameters)

    if action == "":
        raise DialogFlowError(
            "You have not defined an action in your Dialogflow intent.")

    intent_response = await intent.async_handle(
        hass, DOMAIN, action,
        {key: {'value': value} for key, value
         in parameters.items()})

    if 'plain' in intent_response.speech:
        dialogflow_response.add_speech(
            intent_response.speech['plain']['speech'])

    return dialogflow_response.as_dict()


class DialogflowResponse:
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
