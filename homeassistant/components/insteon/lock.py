"""Support for INSTEON locks."""

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon locks from a config entry."""

    @callback
    def async_add_insteon_lock_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, Platform.LOCK, InsteonLockEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.LOCK}"
    async_dispatcher_connect(hass, signal, async_add_insteon_lock_entities)
    async_add_insteon_devices(
        hass,
        Platform.LOCK,
        InsteonLockEntity,
        async_add_entities,
    )


class InsteonLockEntity(InsteonEntity, LockEntity):
    """A Class for an Insteon lock entity."""

    @property
    def is_locked(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self._insteon_device_group.value)

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self._insteon_device.async_lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._insteon_device.async_unlock()
