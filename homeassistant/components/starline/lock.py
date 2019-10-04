"""Support for StarLine lock."""
from homeassistant.components.lock import LockDevice
from .api import StarlineApi, StarlineDevice
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine lock."""

    api: StarlineApi = hass.data[DOMAIN]
    entities = []
    for device_id, device in api.devices.items():
        if device.support_state:
            entities.append(StarlineLock(api, device))
    async_add_entities(entities)
    return True


class StarlineLock(LockDevice):
    """Representation of a StarLine lock."""
    def __init__(self, api: StarlineApi, device: StarlineDevice):
        """Initialize the lock."""
        self._api = api
        self._device = device

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the lock."""
        return f"starline-lock-{self._device.device_id}"

    @property
    def name(self):
        """Return the name of the lock."""
        return f"{self._device.name} Security"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.online

    @property
    def device_state_attributes(self):
        """Return the state attributes of the lock."""
        return self._device.alarm_state

    @property
    def icon(self):
        return "mdi:shield-check-outline" if self.is_locked else "mdi:shield-alert-outline"

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._device.car_state["arm"]

    async def async_lock(self, **kwargs):
        """Lock the car."""
        await self._api.set_car_state(self._device.device_id, "arm", True)

    async def async_unlock(self, **kwargs):
        """Unlock the car."""
        await self._api.set_car_state(self._device.device_id, "arm", False)

    @property
    def device_info(self):
        """Return the device info."""
        return self._device.device_info

    def update(self):
        """Update state of the lock."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._api.add_update_listener(self.update)
