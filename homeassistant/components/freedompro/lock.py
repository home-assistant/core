"""Support for Freedompro lock."""
import json

from homeassistant.components.lock import LockEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .utils import putState


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro lock."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    devices = [
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "lock"
    ]

    async_add_entities(devices, False)


class Device(CoordinatorEntity, LockEntity):
    """Representation of an Freedompro lock."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro lock."""
        super().__init__(coordinator)
        self._hass = hass
        self._api_key = api_key
        self._name = device["name"]
        self._uid = device["uid"]
        self._type = device["type"]
        self._characteristics = device["characteristics"]
        self._lock = 0

    @property
    def name(self):
        """Return the name of the Freedompro lock."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this lock."""
        return self._uid

    @property
    def supported_features(self):
        """Supported features for lock."""
        support = 0
        return support

    @property
    def is_locked(self):
        """Return the status of the lock."""
        device = next(
            (device for device in self.coordinator.data if device["uid"] == self._uid),
            None,
        )
        if device is not None:
            if "state" in device:
                state = device["state"]
                if "lock" in state:
                    self._lock = state["lock"]
        if self._lock == 0:
            return False
        else:
            return True

    async def async_lock(self, **kwargs):
        """Async function to lock the lock."""
        self._lock = 1
        payload = {"lock": self._lock}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs):
        """Async function to unlock the lock."""
        self._lock = 0
        payload = {"lock": self._lock}
        payload = json.dumps(payload)
        await putState(self._hass, self._api_key, self._uid, payload)
        await self.coordinator.async_request_refresh()
