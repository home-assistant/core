"""Support for Switchbot humidifier."""
from __future__ import annotations

import logging

import switchbot

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotSwitchedEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitchBotHumidifier(coordinator)])


class SwitchBotHumidifier(SwitchbotSwitchedEntity, HumidifierEntity):
    """Representation of a Switchbot humidifier."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_min_humidity = 0
    _attr_max_humidity = 100
    _device: switchbot.SwitchbotHumidifier

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._attr_is_on = False

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._device.set_level(humidity)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._device.is_on()
