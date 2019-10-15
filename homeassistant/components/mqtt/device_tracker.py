"""Support for tracking MQTT enabled devices."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_DEVICES, STATE_NOT_HOME, STATE_HOME

from . import CONF_QOS

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
    }
)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]
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
                async_see(dev_id=dev_id, location_name=location_name)
            )

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True
