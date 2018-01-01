"""
Support for Snips on-device ASR and NLU.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/snips/
"""
import asyncio
import json
import logging
import voluptuous as vol
from homeassistant.helpers import intent, template, config_validation as cv
import homeassistant.components.mqtt as mqtt

DOMAIN = 'snips'
DEPENDENCIES = ['mqtt']
CONF_INTENTS = 'intents'
CONF_ACTION = 'action'

INTENT_TOPIC = 'hermes/intent/#'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
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
            vol.Optional('value'): cv.match_all,
            vol.Optional('rawValue'): cv.match_all
        }
    }]
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Activate Snips component."""
    @asyncio.coroutine
    def message_received(topic, payload, qos):
        """Handle new messages on MQTT."""
        _LOGGER.debug("New intent: %s", payload)

        try:
            request = json.loads(payload)
        except TypeError:
            _LOGGER.error('Received invalid JSON: %s', payload)
            return

        try:
            request = INTENT_SCHEMA(request)
        except vol.Invalid as err:
            _LOGGER.error('Intent has invalid schema: %s. %s', err, request)
            return

        snips_response = SnipsResponse(hass, request.get('siteId', 'default'))

        if request['intent']['intentName'].startswith('user'):
            intent_type = request['intent']['intentName'].split('__')[-1]
        else:
            intent_type = request['intent']['intentName'].split(':')[-1]
        slots = {}
        for slot in request.get('slots', []):
            if 'value' in slot['value']:
                slots[slot['slotName']] = {'value': slot['value']['value']}
            else:
                slots[slot['slotName']] = {'value': slot['rawValue']}

        try:
            intent_response = yield from intent.async_handle(
                hass, DOMAIN, intent_type, slots, request['input'])
        except intent.UnknownIntent as err:
            _LOGGER.warning("Received unknown intent %s",
                            request['intent']['intentName'])
            snips_response.add_speech(
                "This intent is not yet configured within Home Assistant.")
        except intent.IntentError:
            _LOGGER.exception("Error while handling intent: %s.", intent_type)

        if 'plain' in intent_response.speech:
            snips_response.add_speech(
                intent_response.speech['plain']['speech'])

        if intent_response.speech:
            snips_response.send_response()

    yield from hass.components.mqtt.async_subscribe(
        INTENT_TOPIC, message_received)

    return True

class SnipsResponse(object):
    """Help generating the response for Snips."""

    def __init__(self, hass, siteid):
        """Initialize the Snips response."""
        self.hass = hass
        self.text = None
        self.siteid = siteid

    def add_speech(self, text):
        """Add speech to the response."""
        assert self.text is None

        if isinstance(text, template.Template):
            text = text.async_render()

        self.text = text

    def as_dict(self):
        """Return response in a Snips valid dictionary."""
        return {
            'siteId': self.siteid,
            'init': {'type': 'notification', 'text': self.text}
        }

    def send_response(self):
        """ Send response as TTS. """
        _LOGGER.debug("send_response %s", json.dumps(self.as_dict()))
        mqtt.async_publish(self.hass, 'hermes/dialogueManager/startSession',
                           json.dumps(self.as_dict()))
