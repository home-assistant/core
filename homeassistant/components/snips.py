"""
Support for Snips on-device ASR and NLU.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/snips/
"""
from homeassistant.helpers import template, script, config_validation as cv
import homeassistant.loader as loader
import voluptuous as vol
import asyncio
import copy
import json
import logging

DOMAIN = 'snips'
DEPENDENCIES = ['mqtt']
CONF_TOPIC = 'topic'
DEFAULT_TOPIC = '#'
CONF_INTENTS = 'intents'
CONF_ACTION = 'action'

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
    LOGGER.info("The 'snips' component is ready!")

    mqtt = loader.get_component('mqtt')
    topic = config[DOMAIN].get(CONF_TOPIC, DEFAULT_TOPIC)
    intents = config[DOMAIN].get(CONF_INTENTS, {})
    handler = IntentHandler(hass, intents)

    def message_received(topic, payload, qos):
        if topic == 'hermes/nlu/intentParsed':
            LOGGER.info("New intent: {}".format(payload))
            handler.handle_intent(payload)

    LOGGER.info("Subscribing to topic " + str(topic))
    mqtt.subscribe(hass, topic, message_received)

    return True

class IntentHandler(object):

    def __init__(self, hass, intents):
        self.hass = hass
        intents = copy.deepcopy(intents)
        template.attach(hass, intents)

        for name, intent in intents.items():
            if CONF_ACTION in intent:
                intent[CONF_ACTION] = script.Script(hass, intent[CONF_ACTION],
                    "Snips intent {}".format(name))

        self.intents = intents

    def handle_intent(self, payload):
        if not payload:
            return
        response = json.loads(payload)
        if not response:
            return

        name = self.get_name(response)
        if not name:
            return

        config = self.intents.get(name)

        if not config:
            LOGGER.warning("Received unknown intent %s", name)
            return

        action = config.get(CONF_ACTION)

        if action is not None:
            slots = self.parse_slots(response)
            action.run(slots)

    def get_name(self, response):
        try:
            return response['intent']['intentName'].split('__')[-1]
        except:
            return None

    def parse_slots(self, response):
        slots = response["slots"]
        if not slots:
            return {}
        parameters = {}
        for slot in slots:
            key = slot["slotName"]
            value = self.get_value(slot)
            parameters[key] = value
        return parameters

    def get_value(self, slot):
        try:
            return slot["value"]["value"]["value"]
        except:
            pass
        try:
            return slot["value"]["value"]
        except:
            pass
        try:
            return slot["value"]
        except:
            pass
        return None
