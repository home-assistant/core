import logging

from homeassistant.components.lock import SUPPORT_OPEN, LockEntity

from . import DroneMobileEntity
from .const import DOMAIN, LOCKS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Lock Entities from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    for key, value in LOCKS.items():
        async_add_entities([Lock(entry, key)], True)


class Lock(DroneMobileEntity, LockEntity):
    def __init__(self, coordinator, lock):
        """Initialize."""
        super().__init__(
            device_id="dronemobile_" + lock,
            name=coordinator.data["vehicle_name"] + "_" + lock,
            coordinator=coordinator,
        )
        self._lock = lock
        self._state = self.is_locked

    async def async_lock(self, **kwargs):
        """Locks the vehicle device."""
        if self.is_locked:
            return
        _LOGGER.debug("Locking %s", self.coordinator.data["vehicle_name"])
        command_call = None
        if self._lock == "doorLock":
            command_call = self.coordinator.vehicle.lock
        else:
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.is_locked
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlocks the vehicle device."""
        if not self.is_locked:
            return
        _LOGGER.debug("Unlocking %s", self.coordinator.data["vehicle_name"])
        command_call = None
        if self._lock == "doorLock":
            command_call = self.coordinator.vehicle.unlock
        elif self._lock == "trunk":
            command_call = self.coordinator.vehicle.trunk
        else:
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.is_locked
        self.async_write_ha_state()

    async def async_open(self, **kwargs):
        """Opens the trunk."""
        if not self.is_locked:
            return
        _LOGGER.debug("Opening %s trunk", self.coordinator.data["vehicle_name"])
        command_call = None
        if self._lock == "trunk":
            command_call = self.coordinator.vehicle.trunk
        else:
            return
        response = await self.coordinator.hass.async_add_executor_job(
            command_call, self.coordinator.data["device_key"]
        )
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.update_data_from_response, self.coordinator, response
        )
        self._state = self.is_locked
        self.async_write_ha_state()

    @property
    def is_locked(self):
        """Determine if the lock is locked."""
        if self._lock == "doorLock":
            if (
                self.coordinator.data is None
                or self.coordinator.data["last_known_state"]["controller"]["armed"]
                is None
            ):
                return None
            return (
                self.coordinator.data["last_known_state"]["controller"]["armed"] == True
            )
        elif self._lock == "trunk":
            if (
                self.coordinator.data is None
                or self.coordinator.data["last_known_state"]["controller"]["trunk_open"]
                is None
            ):
                return None
            return (
                self.coordinator.data["last_known_state"]["controller"]["trunk_open"]
                == False
            )
        else:
            _LOGGER.error("Entry not found in LOCKS: " + self._lock)

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._lock == "trunk":
            return SUPPORT_OPEN

    @property
    def icon(self):
        return LOCKS[self._lock]["icon"]
