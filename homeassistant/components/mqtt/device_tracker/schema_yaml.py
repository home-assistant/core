"""Support for tracking MQTT enabled devices defined in YAML."""

import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA, SOURCE_TYPES
from homeassistant.const import CONF_DEVICES, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from ... import mqtt
from ..const import CONF_QOS

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

PLATFORM_SCHEMA_YAML = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
        vol.Optional(CONF_SOURCE_TYPE): vol.In(SOURCE_TYPES),
    }
)


async def async_setup_scanner_from_yaml(hass, config, async_see, discovery_info=None):
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]
    payload_home = config[CONF_PAYLOAD_HOME]
    payload_not_home = config[CONF_PAYLOAD_NOT_HOME]
    source_type = config.get(CONF_SOURCE_TYPE)

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

            see_args = {"dev_id": dev_id, "location_name": location_name}
            if source_type:
                see_args["source_type"] = source_type

            hass.async_create_task(async_see(**see_args))

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True
