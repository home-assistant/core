"""Support for tracking MQTT enabled devices."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.const import (
    SOURCE_TYPE_ALL,
    SOURCE_TYPE_GPS,
)
from homeassistant.const import CONF_DEVICES
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_DEVICES, STATE_NOT_HOME, STATE_HOME

from . import CONF_QOS, CONF_SOURCE_TYPE

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
        vol.Optional(CONF_SOURCE_TYPE, default=SOURCE_TYPE_GPS): vol.In(
            SOURCE_TYPE_ALL
        ),
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
    }
)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]
    source_type = config[CONF_SOURCE_TYPE]
    payload_home = config[CONF_PAYLOAD_HOME]
    payload_not_home = config[CONF_PAYLOAD_NOT_HOME]

    for dev_id, topic in devices.items():

        @callback
        def async_message_received(msg, dev_id=dev_id):
            """Handle received MQTT message."""

            if msg.payload == payload_home:
                location_name = STATE_HOME
            elif msg.payload == payload_not_home:
                location_name = STATE_NOT_HOME
            else:
                location_name = msg.payload

            hass.async_create_task(
                async_see(
                    dev_id=dev_id, location_name=location_name, source_type=source_type
                )
            )

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True
