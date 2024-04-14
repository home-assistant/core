"""Support for SwitchBot lock platform."""

from typing import Any

import switchbot
from switchbot.const import LockStatus

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot lock based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([(SwitchBotLock(coordinator))])


# noinspection PyAbstractClass
class SwitchBotLock(SwitchbotEntity, LockEntity):
    """Representation of a Switchbot lock."""

    _attr_translation_key = "lock"
    _attr_name = None
    _device: switchbot.SwitchbotLock

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._async_update_attrs()
        if self._device.is_night_latch_enabled():
            self._attr_supported_features = LockEntityFeature.OPEN

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        status = self._device.get_lock_status()
        self._attr_is_locked = status is LockStatus.LOCKED
        self._attr_is_locking = status is LockStatus.LOCKING
        self._attr_is_unlocking = status is LockStatus.UNLOCKING
        self._attr_is_jammed = status in {
            LockStatus.LOCKING_STOP,
            LockStatus.UNLOCKING_STOP,
        }

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        self._last_run_success = await self._device.lock()
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self._device.is_night_latch_enabled():
            self._last_run_success = await self._device.unlock_without_unlatch()
        else:
            self._last_run_success = await self._device.unlock()
        self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the lock."""
        self._last_run_success = await self._device.unlock()
        self.async_write_ha_state()
