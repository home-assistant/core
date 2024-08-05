"""Support for Switchbot humidifier."""

from __future__ import annotations

import switchbot

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SwitchbotConfigEntry
from .entity import SwitchbotSwitchedEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    async_add_entities([SwitchBotHumidifier(entry.runtime_data)])


class SwitchBotHumidifier(SwitchbotSwitchedEntity, HumidifierEntity):
    """Representation of a Switchbot humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_available_modes = [MODE_NORMAL, MODE_AUTO]
    _device: switchbot.SwitchbotHumidifier
    _attr_min_humidity = 1
    _attr_translation_key = "humidifier"
    _attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._device.is_on()

    @property
    def mode(self) -> str:
        """Return the humidity we try to reach."""
        return MODE_AUTO if self._device.is_auto() else MODE_NORMAL

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._device.get_target_humidity()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self._last_run_success = bool(await self._device.set_level(humidity))
        self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set new target humidity."""
        if mode == MODE_AUTO:
            self._last_run_success = await self._device.async_set_auto()
        else:
            self._last_run_success = await self._device.async_set_manual()
        self.async_write_ha_state()
