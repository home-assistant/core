"""Support for Volvo On Call locks."""
from __future__ import annotations

from typing import Any

from volvooncall.dashboard import Lock

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_KEY, VolvoEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Volvo On Call lock."""
    if discovery_info is None:
        return

    async_add_entities([VolvoLock(hass.data[DATA_KEY], *discovery_info)])


class VolvoLock(VolvoEntity, LockEntity):
    """Represents a car lock."""

    instrument: Lock

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        return self.instrument.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        await self.instrument.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        await self.instrument.unlock()
