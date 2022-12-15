"""Support for VeSync humidifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
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
    "Classic300S": "humidifier",
}

PRESET_MODES = {
    "Classic200S": [MODE_NORMAL, MODE_AUTO],
    "Classic300S": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
    "Dual200S": [MODE_NORMAL, MODE_AUTO],
    "LV600S": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
    "OASISMIST": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
}

MODE_MAP = {
    "manual": MODE_NORMAL,
    "humidity": MODE_AUTO,
    "auto": MODE_AUTO,
    "sleep": MODE_SLEEP,
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

    _attr_min_humidity = 30
    _attr_max_humidity = 80
    _attr_supported_features = HumidifierEntityFeature.MODES

    @property
    def available_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return PRESET_MODES[SKU_TO_BASE_DEVICE[self.device.device_type]]

    @property
    def mode(self) -> str:
        """Get the current preset mode."""
        return MODE_MAP[self.device.details["mode"]]

    @property
    def target_humidity(self) -> int:
        """Return the current target humidity."""
        return self.device.auto_humidity

    def set_humidity(self, humidity: int) -> None:
        """Set the humidity of device."""
        if not self.device.is_on:
            self.device.turn_on()

        self.device.set_humidity(humidity)

    def set_mode(self, mode: str) -> None:
        """Set the preset mode of device."""
        if mode not in self.available_modes:
            raise ValueError(
                f"{mode} is not one of the valid modes: " f"{self.available_modes}"
            )

        if not self.device.is_on:
            self.device.turn_on()

        if mode == MODE_NORMAL:
            self.device.set_manual_mode()
        elif mode == MODE_SLEEP:
            self.device.set_humidity_mode("sleep")
        elif mode == MODE_AUTO:
            self.device.set_auto_mode()

        self.schedule_update_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()
