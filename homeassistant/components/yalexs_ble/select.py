"""Support for Yale Access Bluetooth select entities."""

from __future__ import annotations

import logging

from yalexs_ble import AutoLockMode, DoorStatus

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData

_LOGGER = logging.getLogger(__name__)


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


# Mapping between AutoLockMode and string representation
AUTO_LOCK_MODE_TO_OPTION = {
    AutoLockMode.OFF: "off",
    AutoLockMode.TIMER: "timer",
    AutoLockMode.INSTANT: "instant",
}
OPTION_TO_AUTO_LOCK_MODE = {v: k for k, v in AUTO_LOCK_MODE_TO_OPTION.items()}


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
            _LOGGER.debug("%s: auto_lock is None", self._device.address)
            return None
        mode = self._device.auto_lock.mode
        duration = self._device.auto_lock.duration
        _LOGGER.debug(
            "%s: current auto_lock mode=%s (%s), duration=%s",
            self._device.address,
            mode,
            type(mode).__name__,
            duration,
        )
        try:
            option = AUTO_LOCK_MODE_TO_OPTION[mode]
        except KeyError as err:
            raise ValueError(f"Unknown AutoLockMode: {mode}") from err
        else:
            _LOGGER.debug(
                "%s: mapped mode to option '%s'", self._device.address, option
            )
            return option

    async def async_select_option(self, option: str) -> None:
        """Change the auto lock mode."""
        try:
            mode = OPTION_TO_AUTO_LOCK_MODE[option]
        except KeyError as err:
            raise ValueError(f"Unknown auto lock mode option: {option}") from err
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
