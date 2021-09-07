"""Support for Rituals Perfume Genie switches."""
from __future__ import annotations

from typing import Any

from pypoolstation import Pool

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolstationDataUpdateCoordinator
from .const import COORDINATORS, DEVICES, DOMAIN
from .entity import PoolEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool relays."""
    pools = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for pool_id, pool in pools.items():
        coordinator = coordinators[pool_id]
        entities.append(PoolRelaySwitch(pool, coordinator))
        # for relay in pool.relays:

    async_add_entities(entities)


class PoolRelaySwitch(PoolEntity, SwitchEntity):
    """Representation of a diffuser switch."""

    def __init__(
        self, pool: Pool, coordinator: PoolstationDataUpdateCoordinator
    ) -> None:
        """Initialize the diffuser switch."""
        super().__init__(pool, coordinator, "")
        self.relay = pool.relays[0]
        self._attr_is_on = self.relay["active"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on."""

        self._attr_is_on = await self._pool.set_relay(self._pool.relays[0]["id"], True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off."""
        self._attr_is_on = await self._pool.set_relay(self._pool.relays[0]["id"], False)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._pool.relays[0]["active"]
        self.async_write_ha_state()
