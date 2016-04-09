"""
Support for tracking MQTT enabled devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mqtt/
"""
import logging

import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.components.mqtt import CONF_QOS
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

CONF_DEVICES = 'devices'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
})


def setup_scanner(hass, config, see):
    """Setup the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]

    dev_id_lookup = {}

    def device_tracker_message_received(topic, payload, qos):
        """MQTT message received."""
        see(dev_id=dev_id_lookup[topic], location_name=payload)

    for dev_id, topic in devices.items():
        dev_id_lookup[topic] = dev_id
        mqtt.subscribe(hass, topic, device_tracker_message_received, qos)

    return True
