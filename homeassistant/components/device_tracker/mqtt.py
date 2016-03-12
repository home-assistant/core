"""
Support for tracking MQTT enabled devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mqtt/
"""
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant import util

DEPENDENCIES = ['mqtt']

CONF_QOS = 'qos'
CONF_DEVICES = 'devices'

DEFAULT_QOS = 0

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see):
    """Setup the MQTT tracker."""
    devices = config.get(CONF_DEVICES)
    qos = util.convert(config.get(CONF_QOS), int, DEFAULT_QOS)

    if not isinstance(devices, dict):
        _LOGGER.error('Expected %s to be a dict, found %s', CONF_DEVICES,
                      devices)
        return False

    dev_id_lookup = {}

    def device_tracker_message_received(topic, payload, qos):
        """MQTT message received."""
        see(dev_id=dev_id_lookup[topic], location_name=payload)

    for dev_id, topic in devices.items():
        dev_id_lookup[topic] = dev_id
        mqtt.subscribe(hass, topic, device_tracker_message_received, qos)

    return True
