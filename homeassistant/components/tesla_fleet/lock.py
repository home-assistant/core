"""Lock platform for Tesla Fleet integration."""

from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import Scope

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .const import DOMAIN
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

ENGAGED = "Engaged"

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TeslaFleet lock platform from a config entry."""

    async_add_entities(
        klass(vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes)
        for klass in (
            TeslaFleetVehicleLockEntity,
            TeslaFleetCableLockEntity,
        )
        for vehicle in entry.runtime_data.vehicles
    )


class TeslaFleetVehicleLockEntity(TeslaFleetVehicleEntity, LockEntity):
    """Lock entity for TeslaFleet."""

    def __init__(self, data: TeslaFleetVehicleData, scoped: bool) -> None:
        """Initialize the lock."""
        super().__init__(data, "vehicle_state_locked")
        self.scoped = scoped

    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_is_locked = self._value

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.door_lock())
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.door_unlock())
        self._attr_is_locked = False
        self.async_write_ha_state()


class TeslaFleetCableLockEntity(TeslaFleetVehicleEntity, LockEntity):
    """Cable Lock entity for TeslaFleet."""

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        scoped: bool,
    ) -> None:
        """Initialize the lock."""
        super().__init__(data, "charge_state_charge_port_latch")
        self.scoped = scoped

    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        if self._value is None:
            self._attr_is_locked = None
        self._attr_is_locked = self._value == ENGAGED

    async def async_lock(self, **kwargs: Any) -> None:
        """Charge cable Lock cannot be manually locked."""
        raise ServiceValidationError(
            "Insert cable to lock",
            translation_domain=DOMAIN,
            translation_key="no_cable",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charge cable lock."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_locked = False
        self.async_write_ha_state()
