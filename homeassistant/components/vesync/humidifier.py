"""Support for VeSync humidifiers."""
from __future__ import annotations

import logging

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LUH-A602S-WUS": "humidifier",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

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
        if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type)) == "humidifier":
            entities.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    def __init__(self, humidifier):
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.smarthumidifier = humidifier

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.smarthumidifier.config["auto_target_humidity"]

    @property
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes."""
        return self.smarthumidifier.mist_modes

    @property
    def mode(self) -> str | None:
        """Return current modes."""
        return self.smarthumidifier.details["mode"]

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return 40

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return 80

    @property
    def supported_features(self) -> HumidifierEntityFeature:
        """Return the list of supported features."""
        return HumidifierEntityFeature.MODES

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        return self.smarthumidifier.set_humidity(humidity)

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        return self.smarthumidifier.set_humidity_mode(mode)

    def turn_on(self, **kwargs):
        """Turn the device on."""
        return self.smarthumidifier.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        return self.smarthumidifier.turn_off()
