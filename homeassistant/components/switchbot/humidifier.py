"""Support for Switchbot humidifier."""

from __future__ import annotations

import logging
from typing import Any

import switchbot
from switchbot import HumidifierAction as SwitchbotHumidifierAction, HumidifierMode

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry
from .entity import SwitchbotSwitchedEntity, exception_handler

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0
EVAPORATIVE_HUMIDIFIER_ACTION_MAP: dict[int, HumidifierAction] = {
    SwitchbotHumidifierAction.OFF: HumidifierAction.OFF,
    SwitchbotHumidifierAction.HUMIDIFYING: HumidifierAction.HUMIDIFYING,
    SwitchbotHumidifierAction.DRYING: HumidifierAction.DRYING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator = entry.runtime_data
    if isinstance(coordinator.device, switchbot.SwitchbotEvaporativeHumidifier):
        async_add_entities([SwitchBotEvaporativeHumidifier(coordinator)])
    else:
        async_add_entities([SwitchBotHumidifier(coordinator)])


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

    @exception_handler
    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self._last_run_success = bool(await self._device.set_level(humidity))
        self.async_write_ha_state()

    @exception_handler
    async def async_set_mode(self, mode: str) -> None:
        """Set new target humidity."""
        if mode == MODE_AUTO:
            self._last_run_success = await self._device.async_set_auto()
        else:
            self._last_run_success = await self._device.async_set_manual()
        self.async_write_ha_state()


class SwitchBotEvaporativeHumidifier(SwitchbotSwitchedEntity, HumidifierEntity):
    """Representation of a Switchbot evaporative humidifier."""

    _device: switchbot.SwitchbotEvaporativeHumidifier
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = HumidifierMode.get_modes()
    _attr_min_humidity = 1
    _attr_max_humidity = 99
    _attr_translation_key = "evaporative_humidifier"
    _attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._device.is_on()

    @property
    def mode(self) -> str:
        """Return the evaporative humidifier current mode."""
        return self._device.get_mode().name.lower()

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._device.get_humidity()

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._device.get_target_humidity()

    @property
    def action(self) -> HumidifierAction | None:
        """Return the current action."""
        return EVAPORATIVE_HUMIDIFIER_ACTION_MAP.get(
            self._device.get_action(), HumidifierAction.IDLE
        )

    @exception_handler
    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        _LOGGER.debug("Setting target humidity to: %s %s", humidity, self._address)
        await self._device.set_target_humidity(humidity)
        self.async_write_ha_state()

    @exception_handler
    async def async_set_mode(self, mode: str) -> None:
        """Set new evaporative humidifier mode."""
        _LOGGER.debug("Setting mode to: %s %s", mode, self._address)
        await self._device.set_mode(HumidifierMode[mode.upper()])
        self.async_write_ha_state()

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the humidifier."""
        _LOGGER.debug("Turning on the humidifier %s", self._address)
        await self._device.turn_on()
        self.async_write_ha_state()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the humidifier."""
        _LOGGER.debug("Turning off the humidifier %s", self._address)
        await self._device.turn_off()
        self.async_write_ha_state()
