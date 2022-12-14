"""Support for VeSync humidifiers."""
from __future__ import annotations

import logging

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "Classic300S": "humidifier",
}

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"

PRESET_MODES = {
    "Classic300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "humidifier":
            entities.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""
