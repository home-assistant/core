"""Support for Volvo On Call locks."""

from __future__ import annotations

from typing import Any

from volvooncall.dashboard import Lock

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Volvo On Call lock."""
    if discovery_info is None:
        return

    async_add_entities([VolvoLock(hass, *discovery_info)])


class VolvoLock(VolvoEntity, LockEntity):
    """Represents a car lock."""

    instrument: Lock

    def __init__(
        self, hass: HomeAssistant, vin, component, attribute, slug_attr, coordinator
    ):
        """Initialize the lock."""
        VolvoEntity.__init__(
            self, hass, vin, component, attribute, slug_attr, coordinator
        )

        self._attr_is_locked = self.instrument.is_locked

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._attr_is_locked = self.instrument.is_locked
        self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        await self.instrument.lock()
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        await self.instrument.unlock()
        await self.coordinator.async_request_refresh()
