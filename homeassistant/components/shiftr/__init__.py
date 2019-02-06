"""
Support for Shiftr.io.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/shiftr/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, EVENT_STATE_CHANGED,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import state as state_helper

REQUIREMENTS = ['paho-mqtt==1.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'shiftr'

SHIFTR_BROKER = 'broker.shiftr.io'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Initialize the Shiftr.io MQTT consumer."""
    import paho.mqtt.client as mqtt
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    client_id = 'HomeAssistant'
    port = 1883
    keepalive = 600

    mqttc = mqtt.Client(client_id, protocol=mqtt.MQTTv311)
    mqttc.username_pw_set(username, password=password)
    mqttc.connect(SHIFTR_BROKER, port=port, keepalive=keepalive)

    def stop_shiftr(event):
        """Stop the Shiftr.io MQTT component."""
        mqttc.disconnect()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_shiftr)

    def shiftr_event_listener(event):
        """Listen for new messages on the bus and sends them to Shiftr.io."""
        state = event.data.get('new_state')
        topic = state.entity_id.replace('.', '/')

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        try:
            mqttc.publish(topic, _state, qos=0, retain=False)

            if state.attributes:
                for attribute, data in state.attributes.items():
                    mqttc.publish(
                        '/{}/{}'.format(topic, attribute), str(data), qos=0,
                        retain=False)
        except RuntimeError:
            pass

    hass.bus.listen(EVENT_STATE_CHANGED, shiftr_event_listener)

    return True
