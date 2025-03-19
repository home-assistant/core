"""Switches of a smart control stove."""

from typing import Any

from pystove import DATA_NIGHT_LOWERING

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StoveDataUpdateCoordinator


class NightLoweringSwitch(CoordinatorEntity[StoveDataUpdateCoordinator], SwitchEntity):
    """A switch to enable of disable night lowering.

    This switch enables the night lowering that will happen between configures times.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-time-nine-outline"

    def __init__(self, coordinator: StoveDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.key = DATA_NIGHT_LOWERING
        self.translation_key = DATA_NIGHT_LOWERING
        self._attr_unique_id = f"{coordinator.device_id}_{DATA_NIGHT_LOWERING}"
        self._attr_device_info = coordinator.device_info()

    @property
    def is_on(self) -> bool:
        """Return true if night lowering is enabled."""
        return self.coordinator.data[self.key] != "Disabled"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn night lowering on."""
        await self.coordinator.api.set_night_lowering(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn ight lowering off."""
        await self.coordinator.api.set_night_lowering(False)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure the switches."""
    coordinator: StoveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NightLoweringSwitch(coordinator)])
