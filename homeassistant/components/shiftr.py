"""
Support for Shiftr.io.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/shiftr/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.mqtt as mqtt
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, EVENT_STATE_CHANGED,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import state as state_helper

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'shiftr'

SHIFTR_BROKER = 'broker.shiftr.io'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Shiftr.io MQTT consumer."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    client_id = 'HomeAssistant'
    port = 1883
    keepalive = 600

    shiftr_mqtt = mqtt.MQTT(
        hass, SHIFTR_BROKER, port, client_id, keepalive, username,
        password, certificate=None, client_key=None, client_cert=None,
        tls_insecure=False, protocol='3.1.1', will_message=None,
        birth_message=None, tls_version=1.2)

    success = yield from shiftr_mqtt.async_connect()
    if not success:
        return False

    @asyncio.coroutine
    def async_stop_shiftr(event):
        """Stop the Shiftr.io MQTT component."""
        yield from shiftr_mqtt.async_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_shiftr)

    @asyncio.coroutine
    def async_shiftr_event_listener(event):
        """Listen for new messages on the bus and sends them to Shiftr.io."""
        state = event.data.get('new_state')
        topic = state.entity_id.replace('.', '/')

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        yield from shiftr_mqtt.async_publish(topic, _state, 0, False)

        if state.attributes:
            for k, v in state.attributes.items():
                yield from shiftr_mqtt.async_publish(
                    '/{}/{}'.format(topic, k), str(v), 0, False)

    hass.bus.async_listen(EVENT_STATE_CHANGED, async_shiftr_event_listener)

    return True
