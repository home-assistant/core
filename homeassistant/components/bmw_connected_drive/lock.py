"""Support for BMW car locks with BMW ConnectedDrive."""
import logging

from bimmer_connected.state import LockState

from homeassistant.components.lock import LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

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
        self._name = f"{self._vehicle.name} {self._attribute}"
        self._unique_id = f"{self._vehicle.vin}-{self._attribute}"
        self._sensor_name = sensor_name
        self._state = None
        self.door_lock_state_available = (
            DOOR_LOCK_STATE in self._vehicle.available_attributes
        )

    @property
    def unique_id(self):
        """Return the unique ID of the lock."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the lock."""
        vehicle_state = self._vehicle.state
        result = self._attrs.copy()

        if self.door_lock_state_available:
            result["door_lock_state"] = vehicle_state.door_lock_state.value
            result["last_update_reason"] = vehicle_state.last_update_reason
        return result

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        if self.door_lock_state_available:
            result = self._state == STATE_LOCKED
        else:
            result = None
        return result

    def lock(self, **kwargs):
        """Lock the car."""
        _LOGGER.debug("%s: locking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._state = STATE_LOCKED
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_lock()

    def unlock(self, **kwargs):
        """Unlock the car."""
        _LOGGER.debug("%s: unlocking doors", self._vehicle.name)
        # Optimistic state set here because it takes some time before the
        # update callback response
        self._state = STATE_UNLOCKED
        self.schedule_update_ha_state()
        self._vehicle.remote_services.trigger_remote_door_unlock()

    def update(self):
        """Update state of the lock."""
        _LOGGER.debug("%s: updating data for %s", self._vehicle.name, self._attribute)
        vehicle_state = self._vehicle.state

        # Possible values: LOCKED, SECURED, SELECTIVE_LOCKED, UNLOCKED
        self._state = (
            STATE_LOCKED
            if vehicle_state.door_lock_state in [LockState.LOCKED, LockState.SECURED]
            else STATE_UNLOCKED
        )
