"""Support for tracking the moon phases."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import get_moon_phase
from .const import (
    DOMAIN,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)

MOON_ICONS = {
    STATE_FIRST_QUARTER: "mdi:moon-first-quarter",
    STATE_FULL_MOON: "mdi:moon-full",
    STATE_LAST_QUARTER: "mdi:moon-last-quarter",
    STATE_NEW_MOON: "mdi:moon-new",
    STATE_WANING_CRESCENT: "mdi:moon-waning-crescent",
    STATE_WANING_GIBBOUS: "mdi:moon-waning-gibbous",
    STATE_WAXING_CRESCENT: "mdi:moon-waxing-crescent",
    STATE_WAXING_GIBBOUS: "mdi:moon-waxing-gibbous",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    async_add_entities([MoonSensorEntity(entry)], True)


class MoonSensorEntity(SensorEntity):
    """Representation of a Moon sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        STATE_NEW_MOON,
        STATE_WAXING_CRESCENT,
        STATE_FIRST_QUARTER,
        STATE_WAXING_GIBBOUS,
        STATE_FULL_MOON,
        STATE_WANING_GIBBOUS,
        STATE_LAST_QUARTER,
        STATE_WANING_CRESCENT,
    ]
    _attr_translation_key = "phase"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the moon sensor."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            name="Moon",
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self) -> None:
        """Get the time and updates the states."""
        today = dt_util.now().date()
        self._attr_native_value = get_moon_phase(today)

        self._attr_icon = MOON_ICONS.get(self._attr_native_value)
