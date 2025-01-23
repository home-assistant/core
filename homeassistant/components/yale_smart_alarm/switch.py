"""Switches for Yale Alarm."""

from __future__ import annotations

from typing import Any

from yalesmartalarmclient import YaleLock

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleLockEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: YaleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale switch entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        YaleAutolockSwitch(coordinator, lock)
        for lock in coordinator.locks
        if lock.supports_lock_config()
    )


class YaleAutolockSwitch(YaleLockEntity, SwitchEntity):
    """Representation of a Yale autolock switch."""

    _attr_translation_key = "autolock"

    def __init__(self, coordinator: YaleDataUpdateCoordinator, lock: YaleLock) -> None:
        """Initialize the Yale Autolock Switch."""
        super().__init__(coordinator, lock)
        self._attr_unique_id = f"{lock.sid()}-autolock"
        self._attr_is_on = self.lock_data.autolock()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if await self.hass.async_add_executor_job(self.lock_data.set_autolock, True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if await self.hass.async_add_executor_job(self.lock_data.set_autolock, False):
            self._attr_is_on = False
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.lock_data.autolock()
        super()._handle_coordinator_update()
