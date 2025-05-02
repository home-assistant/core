"""Support for yalexs ble securemode (deadlock mode)."""

from __future__ import annotations

from typing import Any

from yalexs_ble import ConnectionInfo, LockInfo, LockState, LockStatus

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup securemode switch."""
    async_add_entities([YaleXSBLESecuremodeSwitch(entry.runtime_data)])


class YaleXSBLESecuremodeSwitch(YALEXSBLEEntity, SwitchEntity):
    """Securemode switch for a Yale BLE lock."""

    _attr_has_entity_name = True
    # Hide the securemode switch be default
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def name(self):
        """Name of the entity."""
        return "Securemode"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        lock_state = new_state.lock
        if lock_state is LockStatus.SECUREMODE:
            self._attr_is_on = True
        else:
            self._attr_is_on = False
        super()._async_update_state(new_state, lock_info, connection_info)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlocks both the deadlock and lock."""
        await self._device.unlock()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """DeadLock the lock."""
        await self._device.securemode()
