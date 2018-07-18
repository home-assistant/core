"""
Support for tracking MQTT enabled devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mqtt/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.const import CONF_DEVICES
from homeassistant.components.mqtt import CONF_QOS
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['mqtt']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend({
    vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
})


@asyncio.coroutine
def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]

    for dev_id, topic in devices.items():
        @callback
        def async_message_received(topic, payload, qos, dev_id=dev_id):
            """Handle received MQTT message."""
            hass.async_add_job(
                async_see(dev_id=dev_id, location_name=payload))

        yield from mqtt.async_subscribe(
            hass, topic, async_message_received, qos)

    return True
