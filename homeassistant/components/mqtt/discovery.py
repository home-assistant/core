"""
Support for MQTT discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#discovery
"""
import json
import logging
import re

from homeassistant.components import mqtt
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import CONF_PLATFORM
from homeassistant.components.mqtt import CONF_STATE_TOPIC

_LOGGER = logging.getLogger(__name__)

TOPIC_MATCHER = re.compile(
    r'(?P<prefix_topic>\w+)/(?P<component>\w+)/'
    r'(?:(?P<node_id>[a-zA-Z0-9_-]+)/)?(?P<object_id>[a-zA-Z0-9_-]+)/config')

SUPPORTED_COMPONENTS = [
    'binary_sensor', 'camera', 'cover', 'fan',
    'light', 'sensor', 'switch', 'lock', 'climate',
    'alarm_control_panel']

ALLOWED_PLATFORMS = {
    'binary_sensor': ['mqtt'],
    'camera': ['mqtt'],
    'cover': ['mqtt'],
    'fan': ['mqtt'],
    'light': ['mqtt', 'mqtt_json', 'mqtt_template'],
    'lock': ['mqtt'],
    'sensor': ['mqtt'],
    'switch': ['mqtt'],
    'climate': ['mqtt'],
    'alarm_control_panel': ['mqtt'],
}

ALREADY_DISCOVERED = 'mqtt_discovered_components'


async def async_start(hass, discovery_topic, hass_config):
    """Initialize of MQTT Discovery."""
    async def async_device_message_received(topic, payload, qos):
        """Process the received message."""
        match = TOPIC_MATCHER.match(topic)

        if not match:
            return

        _prefix_topic, component, node_id, object_id = match.groups()

        try:
            payload = json.loads(payload)
        except ValueError:
            _LOGGER.warning("Unable to parse JSON %s: %s", object_id, payload)
            return

        if component not in SUPPORTED_COMPONENTS:
            _LOGGER.warning("Component %s is not supported", component)
            return

        payload = dict(payload)
        platform = payload.get(CONF_PLATFORM, 'mqtt')
        if platform not in ALLOWED_PLATFORMS.get(component, []):
            _LOGGER.warning("Platform %s (component %s) is not allowed",
                            platform, component)
            return

        payload[CONF_PLATFORM] = platform
        if CONF_STATE_TOPIC not in payload:
            payload[CONF_STATE_TOPIC] = '{}/{}/{}{}/state'.format(
                discovery_topic, component, '%s/' % node_id if node_id else '',
                object_id)

        if ALREADY_DISCOVERED not in hass.data:
            hass.data[ALREADY_DISCOVERED] = set()

        # If present, the node_id will be included in the discovered object id
        discovery_id = '_'.join((node_id, object_id)) if node_id else object_id

        discovery_hash = (component, discovery_id)
        if discovery_hash in hass.data[ALREADY_DISCOVERED]:
            _LOGGER.info("Component has already been discovered: %s %s",
                         component, discovery_id)
            return

        hass.data[ALREADY_DISCOVERED].add(discovery_hash)

        _LOGGER.info("Found new component: %s %s", component, discovery_id)

        await async_load_platform(
            hass, component, platform, payload, hass_config)

    await mqtt.async_subscribe(
        hass, discovery_topic + '/#', async_device_message_received, 0)

    return True
