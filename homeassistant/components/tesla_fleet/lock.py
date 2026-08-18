"""Lock platform for Tesla Fleet integration."""

from typing import Any, override

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

    @override
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_is_locked = self._value

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.door_lock())
        self._attr_is_locked = True
        self.async_write_ha_state()

    @override
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

    @override
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        if self._value is None:
            self._attr_is_locked = None
            return
        self._attr_is_locked = self._value == ENGAGED

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Charge cable Lock cannot be manually locked."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_cable",
        )

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charge cable lock."""
        self.raise_for_read_only(Scope.VEHICLE_CMDS)
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.charge_port_door_open())
        self._attr_is_locked = False
        self.async_write_ha_state()
