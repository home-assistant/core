"""
Support for API.AI webhook.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/apiai/
"""
import asyncio
import copy
import logging

import voluptuous as vol

from homeassistant.const import PROJECT_NAME, HTTP_BAD_REQUEST
from homeassistant.helpers import template, script, config_validation as cv
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
    DOMAIN: {
        CONF_INTENTS: {
            cv.string: {
                vol.Optional(CONF_SPEECH): cv.template,
                vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
                vol.Optional(CONF_ASYNC_ACTION,
                             default=DEFAULT_CONF_ASYNC_ACTION): cv.boolean
            }
        }
    }
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Activate API.AI component."""
    intents = config[DOMAIN].get(CONF_INTENTS, {})

    hass.http.register_view(ApiaiIntentsView(hass, intents))

    return True


class ApiaiIntentsView(HomeAssistantView):
    """Handle API.AI requests."""

    url = INTENTS_API_ENDPOINT
    name = 'api:apiai'

    def __init__(self, hass, intents):
        """Initialize API.AI view."""
        super().__init__()

        self.hass = hass
        intents = copy.deepcopy(intents)
        template.attach(hass, intents)

        for name, intent in intents.items():
            if CONF_ACTION in intent:
                intent[CONF_ACTION] = script.Script(
                    hass, intent[CONF_ACTION], "Apiai intent {}".format(name))

        self.intents = intents

    @asyncio.coroutine
    def post(self, request):
        """Handle API.AI."""
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

        # use intent to no mix HASS actions with this parameter
        intent = req.get('action')
        parameters = req.get('parameters')
        # contexts = req.get('contexts')
        response = ApiaiResponse(parameters)

        # Default Welcome Intent
        # Maybe is better to handle this in api.ai directly?
        #
        # if intent == 'input.welcome':
        #     response.add_speech(
        #     "Hello, and welcome to the future. How may I help?")
        #     return self.json(response)

        if intent == "":
            _LOGGER.warning("Received intent with empty action")
            response.add_speech(
                "You have not defined an action in your api.ai intent.")
            return self.json(response)

        config = self.intents.get(intent)

        if config is None:
            _LOGGER.warning("Received unknown intent %s", intent)
            response.add_speech(
                "Intent '%s' is not yet configured within Home Assistant." %
                intent)
            return self.json(response)

        speech = config.get(CONF_SPEECH)
        action = config.get(CONF_ACTION)
        async_action = config.get(CONF_ASYNC_ACTION)

        if action is not None:
            # API.AI expects a response in less than 5s
            if async_action:
                # Do not wait for the action to be executed.
                # Needed if the action will take longer than 5s to execute
                self.hass.async_add_job(action.async_run(response.parameters))
            else:
                # Wait for the action to be executed so we can use results to
                # render the answer
                yield from action.async_run(response.parameters)

        # pylint: disable=unsubscriptable-object
        if speech is not None:
            response.add_speech(speech)

        return self.json(response)


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
