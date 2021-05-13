"""Platform for Mazda lock integration."""
import datetime

from homeassistant.components.lock import LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.util import dt as dt_util

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN, LOCK_ASSUMED_STATE_PERIOD


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the lock platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaLock(client, coordinator, index))

    async_add_entities(entities)


class MazdaLock(MazdaEntity, LockEntity):
    """Class for the lock."""

    def __init__(self, client, coordinator, index):
        """Initialize the Mazda entity."""
        super().__init__(client, coordinator, index)
        self._assumed_lock_state = None
        self._assumed_lock_state_timestamp = None

    @property
    def name(self):
        """Return the name of the entity."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Lock"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return self.vin

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        api_last_updated_timestamp_str = self.data["status"]["lastUpdatedTimestamp"]
        api_last_updated_timestamp = datetime.datetime.strptime(
            api_last_updated_timestamp_str, "%Y%m%d%H%M%S"
        ).replace(tzinfo=datetime.timezone.utc)

        now_timestamp = dt_util.utcnow()

        # We need to do an optimistic update here because the API takes a few minutes to update after sending a lock/unlock request
        # This will use self._assumed_lock_state as long as it is less than 5 minutes old and is more current than the API response
        if (
            self._assumed_lock_state is not None
            and self._assumed_lock_state_timestamp is not None
            and self._assumed_lock_state_timestamp > api_last_updated_timestamp
            and (
                (now_timestamp - self._assumed_lock_state_timestamp)
                < datetime.timedelta(seconds=LOCK_ASSUMED_STATE_PERIOD)
            )
        ):
            return self._assumed_lock_state == STATE_LOCKED

        # We didn't use self._assumed_lock_state, so use the value from the most recent API response
        door_lock_status = self.data["status"]["doorLocks"]

        vehicle_is_unlocked = (
            door_lock_status["driverDoorUnlocked"]
            or door_lock_status["passengerDoorUnlocked"]
            or door_lock_status["rearLeftDoorUnlocked"]
            or door_lock_status["rearRightDoorUnlocked"]
        )

        return not vehicle_is_unlocked

    async def async_lock(self, **kwargs):
        """Lock the vehicle doors."""
        # Optimistically assume the door is locked, because the API takes a long time to reflect the update
        self._assumed_lock_state = STATE_LOCKED
        self._assumed_lock_state_timestamp = dt_util.utcnow()

        self.async_write_ha_state()

        await self.client.lock_doors(self.vehicle_id)

    async def async_unlock(self, **kwargs):
        """Unlock the vehicle doors."""
        # Optimistically assume the door is unlocked, because the API takes a long time to reflect the update
        self._assumed_lock_state = STATE_UNLOCKED
        self._assumed_lock_state_timestamp = dt_util.utcnow()

        self.async_write_ha_state()

        await self.client.unlock_doors(self.vehicle_id)
