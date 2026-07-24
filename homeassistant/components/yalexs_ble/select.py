"""Support for Yale Access Bluetooth selects."""

from __future__ import annotations

from yalexs_ble import ConnectionInfo, LockInfo, LockState
from yalexs_ble.const import AutoLockMode

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData

AUTO_LOCK_WHEN_OPTIONS = {
    "instant": AutoLockMode.INSTANT,
    "on_timer": AutoLockMode.TIMER,
}

TIMING_OPTIONS = {
    "10_s": 10,
    "30_s": 30,
    "1_min": 60,
    "1_min_30_s": 90,
    "2_min": 120,
    "2_min_30_s": 150,
    "3_min": 180,
    "4_min": 240,
    "5_min": 300,
    "10_min": 600,
    "20_min": 1200,
    "30_min": 1800,
}

TIMING_BY_DURATION = {duration: option for option, duration in TIMING_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yale Access Bluetooth selects."""
    async_add_entities(
        [
            YaleXSBLEAutoLockWhenSelect(entry.runtime_data),
            YaleXSBLEAutoLockTimingSelect(entry.runtime_data),
            YaleXSBLERelockTimingSelect(entry.runtime_data),
        ]
    )


class YaleXSBLEAutoLockWhenSelect(YALEXSBLEEntity, SelectEntity):
    """Yale Access Bluetooth auto-lock when select."""

    _attr_translation_key = "auto_lock_when"
    _attr_options = list(AUTO_LOCK_WHEN_OPTIONS)

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the select."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_auto_lock_when"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        if new_state.auto_lock is None or new_state.auto_lock.mode is AutoLockMode.OFF:
            self._attr_current_option = None
        elif new_state.auto_lock.mode is AutoLockMode.TIMER:
            self._attr_current_option = "on_timer"
        else:
            self._attr_current_option = "instant"
        super()._async_update_state(new_state, lock_info, connection_info)

    async def async_select_option(self, option: str) -> None:
        """Set the auto-lock mode."""
        await self._device.set_auto_lock_mode(AUTO_LOCK_WHEN_OPTIONS[option])


class YaleXSBLETimingSelect(YALEXSBLEEntity, SelectEntity):
    """Base class for Yale Access Bluetooth timing selects."""

    _attr_options = list(TIMING_OPTIONS)
    _mode: AutoLockMode

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the select."""
        super().__init__(data)

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_current_option = (
            TIMING_BY_DURATION.get(new_state.auto_lock.duration)
            if new_state.auto_lock and new_state.auto_lock.mode is self._mode
            else None
        )
        super()._async_update_state(new_state, lock_info, connection_info)

    async def async_select_option(self, option: str) -> None:
        """Set the timing."""
        await self._device.set_auto_lock_duration(TIMING_OPTIONS[option])


class YaleXSBLEAutoLockTimingSelect(YaleXSBLETimingSelect):
    """Yale Access Bluetooth auto-lock timing select."""

    _attr_translation_key = "auto_lock_timing"
    _mode = AutoLockMode.TIMER

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the select."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_auto_lock_timing"


class YaleXSBLERelockTimingSelect(YaleXSBLETimingSelect):
    """Yale Access Bluetooth re-lock timing select."""

    _attr_translation_key = "relock_timing"
    _mode = AutoLockMode.INSTANT

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the select."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_relock_timing"
