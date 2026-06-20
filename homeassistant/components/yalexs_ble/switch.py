"""Support for Yale Access Bluetooth switches."""

from __future__ import annotations

from typing import Any

from yalexs_ble import ConnectionInfo, LockInfo, LockState
from yalexs_ble.const import AutoLockMode

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yale Access Bluetooth switches."""
    async_add_entities([YaleXSBLEAutoLockSwitch(entry.runtime_data)])


class YaleXSBLEAutoLockSwitch(YALEXSBLEEntity, SwitchEntity):
    """Yale Access Bluetooth auto-lock switch."""

    _attr_translation_key = "auto_lock"

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the switch."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_auto_lock"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_is_on = (
            None
            if new_state.auto_lock is None
            else new_state.auto_lock.mode is not AutoLockMode.OFF
        )
        super()._async_update_state(new_state, lock_info, connection_info)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn auto-lock on."""
        mode = AutoLockMode.INSTANT
        if self._device.auto_lock_prev and self._device.auto_lock_prev.mode:
            mode = self._device.auto_lock_prev.mode
        await self._device.set_auto_lock_mode(mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn auto-lock off."""
        await self._device.set_auto_lock_duration(0)
