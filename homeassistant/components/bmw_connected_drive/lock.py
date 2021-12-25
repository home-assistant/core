"""Support for BMW car locks with BMW ConnectedDrive."""
import logging
from typing import Any

from bimmer_connected.vehicle import ConnectedDriveVehicle
from bimmer_connected.vehicle_status import LockState

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    DOMAIN as BMW_DOMAIN,
    BMWConnectedDriveAccount,
    BMWConnectedDriveBaseEntity,
)
from .const import CONF_ACCOUNT, DATA_ENTRIES

DOOR_LOCK_STATE = "door_lock_state"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    account: BMWConnectedDriveAccount = hass.data[BMW_DOMAIN][DATA_ENTRIES][
        config_entry.entry_id
    ][CONF_ACCOUNT]

    if not account.read_only:
        entities = [
            BMWLock(account, vehicle, "lock", "BMW lock")
            for vehicle in account.account.vehicles
        ]
        async_add_entities(entities, True)


class BMWLock(BMWConnectedDriveBaseEntity, LockEntity):
    """Representation of a BMW vehicle lock."""

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
        attribute: str,
        sensor_name: str,
    ) -> None:
        """Initialize the lock."""
        super().__init__(account, vehicle)

        self._attribute = attribute
        self._attr_name = f"{vehicle.name} {attribute}"
        self._attr_unique_id = f"{vehicle.vin}-{attribute}"
        self._sensor_name = sensor_name
        self.door_lock_state_available = DOOR_LOCK_STATE in vehicle.available_attributes

    def lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._attr_is_locked = True
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_lock()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._attr_is_locked = False
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_unlock()

    def update(self) -> None:
        """Update state of the lock."""
        _LOGGER.debug(
            "Updating lock data for '%s' of %s", self._attribute, self._vehicle.name
        )
        vehicle_state = self._vehicle.status
        if not self.door_lock_state_available:
            self._attr_is_locked = None
        else:
            self._attr_is_locked = vehicle_state.door_lock_state in {
                LockState.LOCKED,
                LockState.SECURED,
            }

        result = self._attrs.copy()
        if self.door_lock_state_available:
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        self._attr_extra_state_attributes = result
