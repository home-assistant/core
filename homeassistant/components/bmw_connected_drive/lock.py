"""Support for BMW car locks with BMW ConnectedDrive."""
import logging

from bimmer_connected.state import LockState

from homeassistant.components.lock import LockEntity

from . import DOMAIN as BMW_DOMAIN, BMWConnectedDriveBaseEntity
from .const import CONF_ACCOUNT, DATA_ENTRIES

DOOR_LOCK_STATE = "door_lock_state"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the BMW ConnectedDrive binary sensors from config entry."""
    account = hass.data[BMW_DOMAIN][DATA_ENTRIES][config_entry.entry_id][CONF_ACCOUNT]
    entities = []

    if not account.read_only:
        for vehicle in account.account.vehicles:
            device = BMWLock(account, vehicle, "lock", "BMW lock")
            entities.append(device)
    async_add_entities(entities, True)


class BMWLock(BMWConnectedDriveBaseEntity, LockEntity):
    """Representation of a BMW vehicle lock."""

    def __init__(self, account, vehicle, attribute: str, sensor_name):
        """Initialize the lock."""
        super().__init__(account, vehicle)

        self._attribute = attribute
        self._attr_name = f"{vehicle.name} {attribute}"
        self._attr_unique_id = f"{vehicle.vin}-{attribute}"
        self._sensor_name = sensor_name
        self.door_lock_state_available = DOOR_LOCK_STATE in vehicle.available_attributes

    def lock(self, **kwargs):
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._attr_is_locked = True
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_lock()

    def unlock(self, **kwargs):
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._attr_is_locked = False
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_unlock()

    def update(self):
        """Update state of the lock."""
        _LOGGER.debug("%s: updating data for %s", self._vehicle.name, self._attribute)
        if self._vehicle.state.door_lock_state in [LockState.LOCKED, LockState.SECURED]:
            self._attr_is_locked = True
        else:
            self._attr_is_locked = False
        if not self.door_lock_state_available:
            self._attr_is_locked = None

        vehicle_state = self._vehicle.state
        result = self._attrs.copy()
        if self.door_lock_state_available:
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        self._attr_extra_state_attributes = result
