"""Support for deCONZ locks."""
from homeassistant.components.lock import DOMAIN, LockEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import LOCKS, NEW_LIGHT
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up locks for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_lock(lights=gateway.api.lights.values()):
        """Add lock from deCONZ."""
        entities = []

        for light in lights:

            if light.type in LOCKS and light.uniqueid not in gateway.entities[DOMAIN]:
                entities.append(DeconzLock(light, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_lock
        )
    )

    async_add_lock()


class DeconzLock(DeconzDevice, LockEntity):
    """Representation of a deCONZ lock."""

    TYPE = DOMAIN

    @property
    def is_locked(self):
        """Return true if lock is on."""
        return self._device.is_locked

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        await self._device.lock()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        await self._device.unlock()
