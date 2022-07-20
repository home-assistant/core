"""Support for tracking MQTT enabled devices defined in YAML."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import dataclasses
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA, SOURCE_TYPES
from homeassistant.const import CONF_DEVICES, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from ... import mqtt
from ..client import async_subscribe
from ..config import SCHEMA_BASE
from ..const import CONF_QOS, MQTT_DATA_DEVICE_TRACKER_LEGACY
from ..util import mqtt_config_entry_enabled, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

PLATFORM_SCHEMA_YAML = PLATFORM_SCHEMA.extend(SCHEMA_BASE).extend(
    {
        vol.Required(CONF_DEVICES): {cv.string: valid_subscribe_topic},
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
        vol.Optional(CONF_SOURCE_TYPE): vol.In(SOURCE_TYPES),
    }
)


@dataclasses.dataclass
class MQTTLegacyDeviceTrackerData:
    """Class to hold device tracker data."""

    async_see: Callable[..., Awaitable[None]]
    config: ConfigType


async def async_setup_scanner_from_yaml(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: Callable[..., Awaitable[None]],
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the MQTT tracker."""
    devices = config[CONF_DEVICES]
    qos = config[CONF_QOS]
    payload_home = config[CONF_PAYLOAD_HOME]
    payload_not_home = config[CONF_PAYLOAD_NOT_HOME]
    source_type = config.get(CONF_SOURCE_TYPE)
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subscriptions: list[Callable] = []

    hass.data[MQTT_DATA_DEVICE_TRACKER_LEGACY] = MQTTLegacyDeviceTrackerData(
        async_see, config
    )
    if not mqtt_config_entry_enabled(hass):
        _LOGGER.info(
            "MQTT device trackers will be not available until the config entry is enabled",
        )
        return False

    @callback
    def _entry_unload(*_: Any) -> None:
        """Handle the unload of the config entry."""
        # Unsubscribe from mqtt
        for unsubscribe in subscriptions:
            unsubscribe()

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

        subscriptions.append(
            await async_subscribe(hass, topic, async_message_received, qos)
        )

    config_entry.async_on_unload(_entry_unload)

    return True
