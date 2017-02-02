"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import json
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.components.mqtt import DOMAIN
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_SENSOR_CLASS,
    CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF)
from homeassistant.components.mqtt import CONF_STATE_TOPIC, CONF_QOS
from homeassistant.components.binary_sensor.mqtt import (
    DEFAULT_PAYLOAD_OFF, DEFAULT_PAYLOAD_ON)

_LOGGER = logging.getLogger(__name__)


def start(hass, discovery_config):
    """Initialization of MQTT Discovery."""
    if discovery_config is None:
        _LOGGER.warning("Can't setup MQTT discovery")
        return False

    def device_message_received(topic, payload, qos):
        """Process the received message."""
        parts = topic.split('/')

        if parts[3] != 'config':
            return False

        entity_id = hass.states.get('{}.{}'.format(
            parts[1], json.loads(payload).get(CONF_NAME)))

        if entity_id is not None:
            _LOGGER.warning("Configuration update for %s is not supported",
                            entity_id.attributes[CONF_FRIENDLY_NAME])
            return False

        try:
            payload = json.loads(str(payload))
        except ValueError:
            _LOGGER.warning("Payload for is not valid JSON")

        if parts[1] == 'binary_sensor':
            config = {
                CONF_NAME: payload.get(CONF_NAME, parts[2]),
                CONF_STATE_TOPIC: '{}/{}/{}/state'.format(
                    parts[0], parts[1], parts[2]),
                CONF_VALUE_TEMPLATE: payload.get(CONF_VALUE_TEMPLATE),
                CONF_SENSOR_CLASS: payload.get(CONF_SENSOR_CLASS),
                CONF_QOS: qos,
                CONF_PAYLOAD_ON: payload.get(
                    CONF_PAYLOAD_ON, DEFAULT_PAYLOAD_ON),
                CONF_PAYLOAD_OFF: payload.get(
                    CONF_PAYLOAD_OFF, DEFAULT_PAYLOAD_OFF),
            }
            load_platform(hass, 'binary_sensor', DOMAIN, config)

    mqtt.subscribe(hass, discovery_config, device_message_received, 0)

    return True
