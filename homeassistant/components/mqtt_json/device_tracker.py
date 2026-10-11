"""Support for GPS tracking MQTT enabled devices."""

import json
import logging

import probatio

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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

GPS_JSON_PAYLOAD_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_LATITUDE): probatio.Coerce(float),
        probatio.Required(ATTR_LONGITUDE): probatio.Coerce(float),
        probatio.Optional(ATTR_GPS_ACCURACY): probatio.Coerce(int),
        probatio.Optional(ATTR_BATTERY_LEVEL): probatio.Coerce(str),
    },
    extra=probatio.ALLOW_EXTRA,
)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(mqtt.config.SCHEMA_BASE).extend(
    {probatio.Required(CONF_DEVICES): {cv.string: mqtt.valid_subscribe_topic}}
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
            except probatio.MultipleInvalid:
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
