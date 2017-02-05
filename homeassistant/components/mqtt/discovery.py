"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import asyncio
import json
import logging

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.mqtt import DOMAIN
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_SENSOR_CLASS,
    CONF_PAYLOAD_ON, CONF_PAYLOAD_OFF, CONF_PLATFORM)
from homeassistant.components.mqtt import CONF_STATE_TOPIC, CONF_QOS
from homeassistant.components.binary_sensor.mqtt import (
    DEFAULT_PAYLOAD_OFF, DEFAULT_PAYLOAD_ON)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_COMPONENTS = ['binary_sensor']


def start(hass, discovery_config):
    """Initialization of MQTT Discovery."""

    @asyncio.coroutine
    def async_device_message_received(topic, payload, qos):
        """Process the received message."""
        try:
            main, component, object_id, msg_type = topic.split('/')
        except ValueError:
            return

        if msg_type != 'config':
            return

        try:
            payload = json.loads(payload)
        except ValueError:
            _LOGGER.warning(
                "Unable to parse configuration for %s: %s", object_id, payload)
            return

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Component %s is not supported", component)
            return

        entity_id = hass.states.get('{}.{}'.format(
            component, payload.get(CONF_NAME, object_id)))
        if entity_id is not None:
            _LOGGER.warning("Configuration update for %s is not supported",
                            entity_id.attributes[CONF_FRIENDLY_NAME])
            return

        if component == 'binary_sensor':
            payload[CONF_PLATFORM] = component
            payload[CONF_STATE_TOPIC] = '{}/{}/{}/state'.format(
                main, component, object_id)

        yield from async_load_platform(
           hass, component, DOMAIN, payload, discovery_config)

    mqtt.subscribe(hass, discovery_config, async_device_message_received, 0)

    return True
