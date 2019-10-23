"""Support for StarLine lock."""
from homeassistant.components.lock import LockDevice
from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine lock."""

    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        if device.support_state:
            entities.append(StarlineLock(account, device))
    async_add_entities(entities)
    return True


class StarlineLock(StarlineEntity, LockDevice):
    """Representation of a StarLine lock."""

    def __init__(self, account: StarlineAccount, device: StarlineDevice):
        """Initialize the lock."""
        super().__init__(account, device, "lock", "Security")

    @property
    def available(self):
        """Return True if entity is available."""
        return super().available and self._device.online

    @property
    def device_state_attributes(self):
        """Return the state attributes of the lock."""
        return self._device.alarm_state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return (
            "mdi:shield-check-outline" if self.is_locked else "mdi:shield-alert-outline"
        )

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._device.car_state["arm"]

    def lock(self, **kwargs):
        """Lock the car."""
        self._account.api.set_car_state(self._device.device_id, "arm", True)

    def unlock(self, **kwargs):
        """Unlock the car."""
        self._account.api.set_car_state(self._device.device_id, "arm", False)
