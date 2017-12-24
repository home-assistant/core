"""
Support for Snips on-device ASR and NLU.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/snips/
"""
import asyncio
import json
import logging
import voluptuous as vol
from homeassistant.helpers import intent, config_validation as cv

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

        intent_type = request['intent']['intentName'].split('__')[-1]
        slots = {}
        for slot in request.get('slots', []):
            if 'value' in slot['value']:
                slots[slot['slotName']] = {'value': slot['value']['value']}
            else:
                slots[slot['slotName']] = {'value': slot['rawValue']}

        try:
            yield from intent.async_handle(
                hass, DOMAIN, intent_type, slots, request['input'])
        except intent.IntentError:
            _LOGGER.exception("Error while handling intent: %s.", intent_type)

    yield from hass.components.mqtt.async_subscribe(
        INTENT_TOPIC, message_received)

    return True
