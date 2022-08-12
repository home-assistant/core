"""Support for Volvo On Call locks."""

from __future__ import annotations

from typing import Any

from volvooncall.dashboard import Lock

from homeassistant import config_entries
from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VolvoEntity, VolvoUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure locks from a config entry created in the integrations UI."""
    volvo_data = hass.data[DOMAIN][config_entry.entry_id].volvo_data
    for instrument in volvo_data.instruments:
        if instrument.component == "lock":
            discovery_info = (
                instrument.vehicle.vin,
                instrument.component,
                instrument.attr,
                instrument.slug_attr,
            )

            async_add_entities(
                [VolvoLock(hass.data[DOMAIN][config_entry.entry_id], *discovery_info)]
            )


class VolvoLock(VolvoEntity, LockEntity):
    """Represents a car lock."""

    instrument: Lock

    def __init__(
        self,
        coordinator: VolvoUpdateCoordinator,
        vin: str,
        component: str,
        attribute: str,
        slug_attr: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(vin, component, attribute, slug_attr, coordinator)

    @property
    def is_locked(self) -> bool | None:
        """Determine if car is locked."""
        return self.instrument.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        await self.instrument.lock()
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        await self.instrument.unlock()
        await self.coordinator.async_request_refresh()
