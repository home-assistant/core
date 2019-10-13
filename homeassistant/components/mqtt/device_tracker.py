"""Support for tracking MQTT enabled devices."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.const import (
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_ROUTER,
    SOURCE_TYPE_BLUETOOTH,
    SOURCE_TYPE_BLUETOOTH_LE,
)
from homeassistant.const import CONF_DEVICES
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import CONF_QOS, CONF_SOURCE_TYPE

_LOGGER = logging.getLogger(__name__)

_VALID_SOURCE_TYPE_SCHEMA = vol.In(
    [
        SOURCE_TYPE_GPS,
        SOURCE_TYPE_ROUTER,
        SOURCE_TYPE_BLUETOOTH,
        SOURCE_TYPE_BLUETOOTH_LE,
    ]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
        vol.Optional(
            CONF_SOURCE_TYPE, default=SOURCE_TYPE_GPS
        ): _VALID_SOURCE_TYPE_SCHEMA,
    }
)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]
    source_type = config[CONF_SOURCE_TYPE]

    for dev_id, topic in devices.items():

        @callback
        def async_message_received(msg, dev_id=dev_id):
            """Handle received MQTT message."""
            hass.async_create_task(
                async_see(
                    dev_id=dev_id, location_name=msg.payload, source_type=source_type
                )
            )

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True
