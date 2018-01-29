"""
Support for wit.ai webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wit/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, template
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']
DOMAIN = 'wit'

INTENTS_API_ENDPOINT = '/api/wit'

SOURCE = "Home Assistant Wit"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
}, extra=vol.ALLOW_EXTRA)


class WitError(HomeAssistantError):
    """Raised when a Wit error happens."""


@asyncio.coroutine
def async_setup(hass, config):
    """Set up Wit component."""
    hass.http.register_view(WitIntentsView)

    return True


class WitIntentsView(HomeAssistantView):
    """Handle Wit requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:wit'

    @asyncio.coroutine
    def post(self, request):
        """Handle Wit."""
        hass = request.app['hass']
        message = yield from request.json()

        _LOGGER.debug("Received Wit request: %s", message)

        try:
            response = yield from async_handle_message(hass, message)
            return b'' if response is None else self.json(response)

        except WitError as err:
            _LOGGER.warning(str(err))
            return self.json(wit_error_response(
                hass, message, str(err)))

        except intent.UnknownIntent as err:
            _LOGGER.warning(str(err))
            return self.json(wit_error_response(
                hass, message,
                "This intent is not yet configured within Home Assistant."))

        except intent.InvalidSlotInfo as err:
            _LOGGER.warning(str(err))
            return self.json(wit_error_response(
                hass, message,
                "Invalid slot information received for this intent."))

        except intent.IntentError as err:
            _LOGGER.warning(str(err))
            return self.json(wit_error_response(
                hass, message, "Error handling intent."))


def wit_error_response(hass, message, error):
    """Return a response saying the error message."""
    wit_response = WitResponse()
    wit_response.add_speech(error)
    return wit_response.as_dict()


@asyncio.coroutine
def async_handle_message(hass, message):
    """Handle a Wit message."""
    req = message['entities']

    if not 'intent' in req:
        raise WitError(
            "Message does not contain intent parameter.")

    action = req['intent'][0]['value']

    if action == "":
        raise WitError(
            "You have not defined an intent in your Wit request.")

    slots = {key: {'value': value[0]['value']} for key,value
             in req.items() if key != 'intent'}
    wit_response = WitResponse()

    intent_response = yield from intent.async_handle(
        hass, DOMAIN, action, slots)

    if 'plain' in intent_response.speech:
        wit_response.add_speech(
            intent_response.speech['plain']['speech'])

    return wit_response.as_dict()


class WitResponse(object):
    """Help generating the response for Wit."""

    def __init__(self):
        """Initialize the Wit response."""
        self.speech = None

    def add_speech(self, text):
        """Add speech to the response."""
        assert self.speech is None

        if isinstance(text, template.Template):
            text = text.async_render(self.parameters)

        self.speech = text

    def as_dict(self):
        """Return response in a Wit valid dictionary."""
        return {
            'speech': self.speech,
            'displayText': self.speech,
            'source': SOURCE,
        }
