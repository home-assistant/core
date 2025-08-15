"""Support for Yale Access Bluetooth select entities."""

from __future__ import annotations

from yalexs_ble import AutoLockMode, DoorStatus

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up locks."""
    data = entry.runtime_data
    lock = data.lock
    if lock.lock_info and lock.lock_info.door_sense:
        async_add_entities(
            [YaleXSBLEAutoLockModeSelect(data), YaleXSBLEAutoLockDurationSelect(data)]
        )


class YaleXSBLEAutoLockModeSelect(YALEXSBLEEntity, SelectEntity):
    """A yale xs ble auto lock mode selector."""

    _attr_translation_key = "auto_lock_mode"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the entity."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_auto_lock_mode"
        self._attr_options = self._device.auto_lock_modes

    @property
    def available(self) -> bool:
        """Check if the entity is available."""
        return self._device.door_status != DoorStatus.UNKNOWN

    @property
    def current_option(self) -> str | None:
        """Retrieve the current auto lock mode value as a string."""
        if self._device.auto_lock is None:
            return None
        mode = self._device.auto_lock.mode
        if mode == AutoLockMode.OFF:
            return "off"
        if mode == AutoLockMode.TIMER:
            return "timer"
        if mode == AutoLockMode.INSTANT:
            return "instant"
        raise ValueError(f"Unknown AutoLockMode: {mode}")

    async def async_select_option(self, option: str) -> None:
        """Change the auto lock mode."""
        mode = AutoLockMode.OFF
        if option == "timer":
            mode = AutoLockMode.TIMER
        elif option == "instant":
            mode = AutoLockMode.INSTANT
        await self._device.set_auto_lock_mode(mode)


class YaleXSBLEAutoLockDurationSelect(YALEXSBLEEntity, SelectEntity):
    """A yale xs ble auto lock duration selector."""

    _attr_translation_key = "auto_lock_duration"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the entity."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_auto_lock_duration"
        self._attr_options = [str(dur) for dur in self._device.auto_lock_durations]

    @property
    def available(self) -> bool:
        """Check if the entity is available."""
        return self._device.door_status != DoorStatus.UNKNOWN

    @property
    def current_option(self) -> str | None:
        """Retrieve the current auto lock duration as a string."""
        if self._device.auto_lock is None:
            return None
        return str(self._device.auto_lock.duration)

    async def async_select_option(self, option: str) -> None:
        """Change the auto lock duration."""
        await self._device.set_auto_lock_duration(int(option))
