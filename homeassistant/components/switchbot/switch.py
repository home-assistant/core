"""Support for Switchbot bot."""
from __future__ import annotations

import logging
from typing import Any

import switchbot

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitchBotSwitch(coordinator)])


class SwitchBotSwitch(SwitchbotEntity, SwitchEntity, RestoreEntity):
    """Representation of a Switchbot switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _device: switchbot.Switchbot

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
        self._last_run_success = last_state.attributes.get("last_run_success")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.info("Turn Switchbot bot on %s", self._address)

        self._last_run_success = bool(await self._device.turn_on())
        if self._last_run_success:
            self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.info("Turn Switchbot bot off %s", self._address)

        self._last_run_success = bool(await self._device.turn_off())
        if self._last_run_success:
            self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return not self._device.switch_mode()

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if not self._device.switch_mode():
            return self._attr_is_on
        return self._device.is_on()

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            **super().extra_state_attributes,
            "switch_mode": self._device.switch_mode(),
        }
