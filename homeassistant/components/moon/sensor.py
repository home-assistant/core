"""Support for tracking the moon phases."""
from __future__ import annotations

from astral import moon
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import DEFAULT_NAME, DOMAIN

STATE_FIRST_QUARTER = "first_quarter"
STATE_FULL_MOON = "full_moon"
STATE_LAST_QUARTER = "last_quarter"
STATE_NEW_MOON = "new_moon"
STATE_WANING_CRESCENT = "waning_crescent"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_WAXING_GIBBOUS = "waxing_gibbous"
STATE_WAXING_CRESCENT = "waxing_crescent"

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

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Moon sensor."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    async_add_entities([MoonSensorEntity(entry)], True)


class MoonSensorEntity(SensorEntity):
    """Representation of a Moon sensor."""

    _attr_device_class = "moon__phase"
    _attr_has_entity_name = True
    _attr_name = "Phase"

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
        state = moon.phase(today)

        if state < 0.5 or state > 27.5:
            self._attr_native_value = STATE_NEW_MOON
        elif state < 6.5:
            self._attr_native_value = STATE_WAXING_CRESCENT
        elif state < 7.5:
            self._attr_native_value = STATE_FIRST_QUARTER
        elif state < 13.5:
            self._attr_native_value = STATE_WAXING_GIBBOUS
        elif state < 14.5:
            self._attr_native_value = STATE_FULL_MOON
        elif state < 20.5:
            self._attr_native_value = STATE_WANING_GIBBOUS
        elif state < 21.5:
            self._attr_native_value = STATE_LAST_QUARTER
        else:
            self._attr_native_value = STATE_WANING_CRESCENT

        self._attr_icon = MOON_ICONS.get(self._attr_native_value)
