"""Support for SwitchBot Fans."""

from __future__ import annotations

import logging
from typing import Any

import switchbot
from switchbot import FanMode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot fan based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([SwitchBotFanEntity(coordinator)])


class SwitchBotFanEntity(SwitchbotEntity, FanEntity, RestoreEntity):
    """Representation of a Switchbot."""

    _device: switchbot.SwitchbotFan
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = FanMode.get_modes()
    _attr_translation_key = "fan"
    _attr_name = None

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the switchbot."""
        super().__init__(coordinator)
        self._attr_is_on = False

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._device.is_on()

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._device.get_current_percentage()

    @property
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._device.get_oscillating_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._device.get_current_mode()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""

        _LOGGER.debug(
            "Switchbot fan to set preset mode %s %s", preset_mode, self._address
        )
        self._last_run_success = bool(await self._device.set_preset_mode(preset_mode))
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""

        _LOGGER.debug(
            "Switchbot fan to set percentage %d %s", percentage, self._address
        )
        self._last_run_success = bool(await self._device.set_percentage(percentage))
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""

        _LOGGER.debug(
            "Switchbot fan to set oscillating %s %s", oscillating, self._address
        )
        self._last_run_success = bool(await self._device.set_oscillation(oscillating))
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""

        _LOGGER.debug(
            "Switchbot fan to set turn on %s %s %s",
            percentage,
            preset_mode,
            self._address,
        )
        self._last_run_success = bool(await self._device.turn_on())
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""

        _LOGGER.debug("Switchbot fan to set turn off %s", self._address)
        self._last_run_success = bool(await self._device.turn_off())
        self.async_write_ha_state()
