"""Support for BMW car locks with BMW ConnectedDrive."""
from __future__ import annotations

import logging
from typing import Any

from bimmer_connected.vehicle import ConnectedDriveVehicle
from bimmer_connected.vehicle_status import LockState

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWConnectedDriveBaseEntity
from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

DOOR_LOCK_STATE = "door_lock_state"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWLock] = []

    for vehicle in coordinator.account.vehicles:
        if not coordinator.read_only:
            entities.append(BMWLock(coordinator, vehicle, "lock", "BMW lock"))
    async_add_entities(entities)


class BMWLock(BMWConnectedDriveBaseEntity, LockEntity):
    """Representation of a BMW vehicle lock."""

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: ConnectedDriveVehicle,
        attribute: str,
        sensor_name: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(coordinator, vehicle)

        self._attribute = attribute
        self._attr_name = f"{vehicle.name} {attribute}"
        self._attr_unique_id = f"{vehicle.vin}-{attribute}"
        self._sensor_name = sensor_name
        self.door_lock_state_available = DOOR_LOCK_STATE in vehicle.available_attributes

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        return {"door_lock_state": self.vehicle.status.door_lock_state.value}

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        _LOGGER.debug(
            "Updating lock data for '%s' of %s", self._attribute, self.vehicle.name
        )
        vehicle_state = self.vehicle.status
        if not self.door_lock_state_available:
            return None
        return vehicle_state.door_lock_state in {
            LockState.LOCKED,
            LockState.SECURED,
        }

    def lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self.vehicle.name)
        self.vehicle.remote_services.trigger_remote_door_lock()
        self.schedule_update_ha_state()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self.vehicle.name)
        self.vehicle.remote_services.trigger_remote_door_unlock()
        self.schedule_update_ha_state()
