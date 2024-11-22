"""Support for GPS tracking MQTT enabled devices."""

from __future__ import annotations

import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
)
from homeassistant.components.mqtt import CONF_QOS
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICES,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

GPS_JSON_PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LATITUDE): vol.Coerce(float),
        vol.Required(ATTR_LONGITUDE): vol.Coerce(float),
        vol.Optional(ATTR_GPS_ACCURACY): vol.Coerce(int),
        vol.Optional(ATTR_BATTERY_LEVEL): vol.Coerce(str),
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(mqtt.config.SCHEMA_BASE).extend(
    {vol.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic}}
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the MQTT JSON tracker."""
    # Make sure MQTT integration is enabled and the client is available
    # We cannot count on dependencies as the device_tracker platform setup
    # also will be triggered when mqtt is loading the `device_tracker` platform
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]

    for dev_id, topic in devices.items():

        @callback
        def async_message_received(msg, dev_id=dev_id):
            """Handle received MQTT message."""
            try:
                data = GPS_JSON_PAYLOAD_SCHEMA(json.loads(msg.payload))
            except vol.MultipleInvalid:
                _LOGGER.error(
                    (
                        "Skipping update for following data "
                        "because of missing or malformatted data: %s"
                    ),
                    msg.payload,
                )
                return
            except ValueError:
                _LOGGER.error("Error parsing JSON payload: %s", msg.payload)
                return

            kwargs = _parse_see_args(dev_id, data)
            hass.async_create_task(async_see(**kwargs))

        await mqtt.async_subscribe(hass, topic, async_message_received, qos)

    return True


def _parse_see_args(dev_id, data):
    """Parse the payload location parameters, into the format see expects."""
    kwargs = {"gps": (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]), "dev_id": dev_id}

    if ATTR_GPS_ACCURACY in data:
        kwargs[ATTR_GPS_ACCURACY] = data[ATTR_GPS_ACCURACY]
    if ATTR_BATTERY_LEVEL in data:
        kwargs["battery"] = data[ATTR_BATTERY_LEVEL]
    return kwargs
