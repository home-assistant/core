"""Representation of Z-Wave switches."""
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave lock from config entry."""

    @callback
    def async_add_lock(value):
        """Add Z-Wave Lock."""
        lock = ZWaveLock(value)

        async_add_entities([lock])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{LOCK_DOMAIN}", async_add_lock)
    )


class ZWaveLock(ZWaveDeviceEntity, LockEntity):
    """Representation of a Z-Wave lock."""

    @property
    def is_locked(self):
        """Return a boolean for the state of the switch."""
        return bool(self.values.primary.value)

    async def async_lock(self, **kwargs):
        """Turn the switch on."""
        self.values.primary.send_value(True)

    async def async_unlock(self, **kwargs):
        """Turn the switch off."""
        self.values.primary.send_value(False)
