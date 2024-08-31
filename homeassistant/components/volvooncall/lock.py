"""Support for Volvo On Call locks."""

from __future__ import annotations

from typing import Any

from volvooncall.dashboard import Instrument, Lock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VolvoEntity, VolvoUpdateCoordinator
from .const import DOMAIN, VOLVO_DISCOVERY_NEW


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configure locks from a config entry created in the integrations UI."""
    coordinator: VolvoUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    volvo_data = coordinator.volvo_data

    @callback
    def async_discover_device(instruments: list[Instrument]) -> None:
        """Discover and add a discovered Volvo On Call lock."""
        entities: list[VolvoLock] = []

        for instrument in instruments:
            if instrument.component == "lock":
                entities.append(
                    VolvoLock(
                        coordinator,
                        instrument.vehicle.vin,
                        instrument.component,
                        instrument.attr,
                        instrument.slug_attr,
                    )
                )

        async_add_entities(entities)

    async_discover_device([*volvo_data.instruments])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VOLVO_DISCOVERY_NEW, async_discover_device)
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
