"""Support for GPS tracking MQTT enabled devices."""
import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.mqtt import CONF_QOS
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICES,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_LATITUDE_FIELD_NAME = "latitude_field"
CONF_LONGITUDE_FIELD_NAME = "longitude_field"
CONF_GPS_ACCURACY_FIELD_NAME = "gps_accuracy_field"
CONF_BATTERY_LEVEL_FIELD_NAME = "battery_level_field"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(mqtt.SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic},
        vol.Optional(CONF_LATITUDE_FIELD_NAME, default=ATTR_LATITUDE): cv.string,
        vol.Optional(CONF_LONGITUDE_FIELD_NAME, default=ATTR_LONGITUDE): cv.string,
        vol.Optional(
            CONF_GPS_ACCURACY_FIELD_NAME, default=ATTR_GPS_ACCURACY
        ): cv.string,
        vol.Optional(
            CONF_BATTERY_LEVEL_FIELD_NAME, default=ATTR_BATTERY_LEVEL
        ): cv.string,
    }
)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MQTT JSON tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]

    for dev_id, topic in devices.items():

        @callback
        def async_message_received(msg, dev_id=dev_id):
            """Handle received MQTT message."""
            try:
                data = input_schema(config)(json.loads(msg.payload))
            except vol.MultipleInvalid:
                _LOGGER.error(
                    "Skipping update for following data "
                    "because of missing or malformatted data: %s",
                    msg.payload,
                )
                return
            except ValueError:
                _LOGGER.error("Error parsing JSON payload: %s", msg.payload)
                return

            kwargs = _parse_see_args(dev_id, config, data)
            hass.async_create_task(async_see(**kwargs))

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True


def input_schema(config):
    """Compute a JSON schema based on user defined property names."""
    return vol.Schema(
        {
            vol.Required(config[CONF_LATITUDE_FIELD_NAME]): vol.Coerce(float),
            vol.Required(config[CONF_LONGITUDE_FIELD_NAME]): vol.Coerce(float),
            vol.Optional(config[CONF_GPS_ACCURACY_FIELD_NAME]): vol.Coerce(int),
            vol.Optional(config[CONF_BATTERY_LEVEL_FIELD_NAME]): vol.Coerce(str),
        },
        extra=vol.ALLOW_EXTRA,
    )


def _parse_see_args(dev_id, config, data):
    """Parse the payload location parameters, into the format see expects."""
    kwargs = {
        "gps": (
            data[config[CONF_LATITUDE_FIELD_NAME]],
            data[config[CONF_LONGITUDE_FIELD_NAME]],
        ),
        "dev_id": dev_id,
    }

    if config[CONF_GPS_ACCURACY_FIELD_NAME] in data:
        kwargs[ATTR_GPS_ACCURACY] = data[config[CONF_GPS_ACCURACY_FIELD_NAME]]
    if config[CONF_BATTERY_LEVEL_FIELD_NAME] in data:
        kwargs["battery"] = data[config[CONF_BATTERY_LEVEL_FIELD_NAME]]
    return kwargs
