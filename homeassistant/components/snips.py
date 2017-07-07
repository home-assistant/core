"""
Support for Snips on-device ASR and NLU.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/snips/
"""
import asyncio
import copy
import json
import logging
import voluptuous as vol
from homeassistant.helpers import template, script, config_validation as cv
import homeassistant.loader as loader

DOMAIN = 'snips'
DEPENDENCIES = ['mqtt']
CONF_INTENTS = 'intents'
CONF_ACTION = 'action'

INTENT_TOPIC = 'hermes/nlu/intentParsed'

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        CONF_INTENTS: {
            cv.string: {
                vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
            }
        }
    }
}, extra=vol.ALLOW_EXTRA)

INTENT_SCHEMA = vol.Schema({
    vol.Required('input'): str,
    vol.Required('intent'): {
        vol.Required('intentName'): str
    },
    vol.Optional('slots'): [{
        vol.Required('slotName'): str,
        vol.Required('value'): {
            vol.Required('kind'): str,
            vol.Required('value'): cv.match_all
        }
    }]
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Activate Snips component."""
    mqtt = loader.get_component('mqtt')
    intents = config[DOMAIN].get(CONF_INTENTS, {})
    handler = IntentHandler(hass, intents)

    @asyncio.coroutine
    def message_received(topic, payload, qos):
        """Handle new messages on MQTT."""
        LOGGER.debug("New intent: %s", payload)
        yield from handler.handle_intent(payload)

    yield from mqtt.async_subscribe(hass, INTENT_TOPIC, message_received)

    return True


class IntentHandler(object):
    """Help handling intents."""

    def __init__(self, hass, intents):
        """Initialize the intent handler."""
        self.hass = hass
        intents = copy.deepcopy(intents)
        template.attach(hass, intents)

        for name, intent in intents.items():
            if CONF_ACTION in intent:
                intent[CONF_ACTION] = script.Script(
                    hass, intent[CONF_ACTION], "Snips intent {}".format(name))

        self.intents = intents

    @asyncio.coroutine
    def handle_intent(self, payload):
        """Handle an intent."""
        try:
            response = json.loads(payload)
        except TypeError:
            LOGGER.error('Received invalid JSON: %s', payload)
            return

        try:
            response = INTENT_SCHEMA(response)
        except vol.Invalid as err:
            LOGGER.error('Intent has invalid schema: %s. %s', err, response)
            return

        intent = response['intent']['intentName'].split('__')[-1]
        config = self.intents.get(intent)

        if config is None:
            LOGGER.warning("Received unknown intent %s. %s", intent, response)
            return

        action = config.get(CONF_ACTION)

        if action is not None:
            slots = self.parse_slots(response)
            yield from action.async_run(slots)

    # pylint: disable=no-self-use
    def parse_slots(self, response):
        """Parse the intent slots."""
        parameters = {}

        for slot in response.get('slots', []):
            key = slot['slotName']
            value = slot['value']['value']
            if value is not None:
                parameters[key] = value

        return parameters
