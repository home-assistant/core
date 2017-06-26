"""
Support for Snips on-device ASR and NLU.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/snips/
"""
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


def setup(hass, config):
    """Activate Snips component."""
    mqtt = loader.get_component('mqtt')
    intents = config[DOMAIN].get(CONF_INTENTS, {})
    handler = IntentHandler(hass, intents)

    def message_received(topic, payload, qos):
        LOGGER.debug("New intent: {}".format(payload))
        handler.handle_intent(payload)

    mqtt.subscribe(hass, INTENT_TOPIC, message_received)

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

    def handle_intent(self, payload):
        """Handle an intent."""
        try:
            response = json.loads(payload)
        except TypeError:
            return

        if response is None:
            return

        name = self.get_name(response)
        if name is None:
            return

        config = self.intents.get(name)

        if config is None:
            LOGGER.warning("Received unknown intent %s", name)
            return

        action = config.get(CONF_ACTION)

        if action is not None:
            slots = self.parse_slots(response)
            action.run(slots)

    def get_name(self, response):
        """Extract the name of an intent."""
        try:
            return response['intent']['intent_name'].split('__')[-1]
        except KeyError:
            return None

    def parse_slots(self, response):
        """Parse the intent slots."""
        try:
            slots = iter(response["slots"])
        except KeyError:
            return {}

        parameters = {}

        for slot in slots:
            try:
                key = slot["slot_name"]
            except KeyError:
                continue
            value = self.get_value(slot)
            if (key is not None) and (value is not None):
                parameters[key] = value

        return parameters

    def get_value(self, slot):
        """Return the value of a given slot."""
        try:
            value = slot["value"]
            kind = value["kind"]
        except KeyError:
            return None

        if kind == "Custom":
            try:
                return value["value"]
            except KeyError:
                return None
        elif kind == "Builtin":
            try:
                return value["value"]["value"]
            except KeyError:
                return None
        return None
