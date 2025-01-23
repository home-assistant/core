"""Lock platform for Tessie integration."""

from __future__ import annotations

from typing import Any

from tessie_api import lock, open_unlock_charge_port, unlock

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TessieConfigEntry
from .const import DOMAIN, TessieChargeCableLockStates
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        klass(vehicle)
        for klass in (TessieLockEntity, TessieCableLockEntity)
        for vehicle in data.vehicles
    )


class TessieLockEntity(TessieEntity, LockEntity):
    """Lock entity for Tessie."""

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_locked")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value

    async def async_lock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(lock)
        self.set((self.key, True))

    async def async_unlock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(unlock)
        self.set((self.key, False))


class TessieCableLockEntity(TessieEntity, LockEntity):
    """Cable Lock entity for Tessie."""

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "charge_state_charge_port_latch")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value == TessieChargeCableLockStates.ENGAGED

    async def async_lock(self, **kwargs: Any) -> None:
        """Charge cable Lock cannot be manually locked."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_cable",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charge cable lock."""
        await self.run(open_unlock_charge_port)
        self.set((self.key, TessieChargeCableLockStates.DISENGAGED))
