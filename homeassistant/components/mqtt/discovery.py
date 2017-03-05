"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import asyncio
import json
import logging
import re

import homeassistant.components.mqtt as mqtt
from homeassistant.components.mqtt import DOMAIN
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import CONF_PLATFORM
from homeassistant.components.mqtt import CONF_STATE_TOPIC

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r'(?P<prefix_topic>\w+)/(?P<component>\w+)/(?P<object_id>\w+)/config')

SUPPORTED_COMPONENTS = ['binary_sensor', 'sensor']


@asyncio.coroutine
def async_start(hass, discovery_topic, hass_config):
    """Initialization of MQTT Discovery."""
    # pylint: disable=unused-variable
    @asyncio.coroutine
    def async_device_message_received(topic, payload, qos):
        """Process the received message."""
        match = TOPIC_MATCHER.match(topic)

        if not match:
            return

        prefix_topic, component, object_id = match.groups()

        try:
            payload = json.loads(payload)
        except ValueError:
            _LOGGER.warning("Unable to parse JSON %s: %s", object_id, payload)
            return

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Component %s is not supported", component)
            return

        payload = dict(payload)
        payload[CONF_PLATFORM] = 'mqtt'
        if CONF_STATE_TOPIC not in payload:
            payload[CONF_STATE_TOPIC] = '{}/{}/{}/state'.format(
                discovery_topic, component, object_id)

        yield from async_load_platform(
            hass, component, DOMAIN, payload, hass_config)

    yield from mqtt.async_subscribe(
        hass, discovery_topic + '/#', async_device_message_received, 0)

    return True
