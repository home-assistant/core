"""Support for Rituals Perfume Genie switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser switch."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        DiffuserSwitch(coordinator) for coordinator in coordinators.values()
    )


class DiffuserSwitch(DiffuserEntity, SwitchEntity):
    """Representation of a diffuser switch."""

    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the diffuser switch."""
        super().__init__(coordinator, "")
        self._attr_is_on = self.coordinator.diffuser.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.diffuser.turn_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.diffuser.turn_off()
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.diffuser.is_on
        self.async_write_ha_state()
