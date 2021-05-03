"""Support for Rituals Perfume Genie switches."""
from __future__ import annotations

from typing import Any, Callable

from pyrituals import Diffuser

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTES, COORDINATORS, DEVICES, DOMAIN
from .entity import DiffuserEntity

FAN = "fanc"
SPEED = "speedc"
ROOM = "roomc"

ON_STATE = "1"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
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

    def __init__(self, diffuser: Diffuser, coordinator: CoordinatorEntity) -> None:
        """Initialize the diffuser switch."""
        super().__init__(diffuser, coordinator, "")
        self._is_on = self._diffuser.is_on

    @property
    def icon(self) -> str:
        """Return the icon of the device."""
        return "mdi:fan"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attributes = {
            "fan_speed": self._diffuser.hub_data[ATTRIBUTES][SPEED],
            "room_size": self._diffuser.hub_data[ATTRIBUTES][ROOM],
        }
        return attributes

    @property
    def is_on(self) -> bool:
        """If the device is currently on or off."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._diffuser.turn_on()
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._diffuser.turn_off()
        self._is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._is_on = self._diffuser.is_on
        self.async_write_ha_state()
