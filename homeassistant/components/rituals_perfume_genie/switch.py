"""Support for Rituals Perfume Genie switches."""
from __future__ import annotations

from typing import Any

from pyrituals import Diffuser

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RitualsDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import DiffuserEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser switch."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserSwitch(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserSwitch(SwitchEntity, DiffuserEntity):
    """Representation of a diffuser switch."""

    _attr_icon = "mdi:fan"

    def __init__(
        self, diffuser: Diffuser, coordinator: RitualsDataUpdateCoordinator
    ) -> None:
        """Initialize the diffuser switch."""
        super().__init__(diffuser, coordinator, "")
        self._attr_is_on = self._diffuser.is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {
            "fan_speed": self._diffuser.perfume_amount,
            "room_size": self._diffuser.room_size,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._diffuser.turn_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._diffuser.turn_off()
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._diffuser.is_on
        self.async_write_ha_state()
