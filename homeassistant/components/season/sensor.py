"""Support for Season sensors."""

from __future__ import annotations

from datetime import datetime

import ephem

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TYPE_ASTRONOMICAL

EQUATOR = "equator"

NORTHERN = "northern"

SOUTHERN = "southern"
STATE_AUTUMN = "autumn"
STATE_SPRING = "spring"
STATE_SUMMER = "summer"
STATE_WINTER = "winter"

HEMISPHERE_SEASON_SWAP = {
    STATE_WINTER: STATE_SUMMER,
    STATE_SPRING: STATE_AUTUMN,
    STATE_AUTUMN: STATE_SPRING,
    STATE_SUMMER: STATE_WINTER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config entry."""
    hemisphere = EQUATOR
    if hass.config.latitude < 0:
        hemisphere = SOUTHERN
    elif hass.config.latitude > 0:
        hemisphere = NORTHERN

    async_add_entities([SeasonSensorEntity(entry, hemisphere)], True)


def get_season(
    current_datetime: datetime, hemisphere: str, season_tracking_type: str
) -> str | None:
    """Calculate the current season."""

    if hemisphere == "equator":
        return None

    if season_tracking_type == TYPE_ASTRONOMICAL:
        spring_start = (
            ephem.next_equinox(str(current_datetime.year))
            .datetime()
            .replace(tzinfo=dt_util.UTC)
        )
        summer_start = (
            ephem.next_solstice(str(current_datetime.year))
            .datetime()
            .replace(tzinfo=dt_util.UTC)
        )
        autumn_start = (
            ephem.next_equinox(spring_start).datetime().replace(tzinfo=dt_util.UTC)
        )
        winter_start = (
            ephem.next_solstice(summer_start).datetime().replace(tzinfo=dt_util.UTC)
        )
    else:
        spring_start = current_datetime.replace(
            month=3, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        summer_start = spring_start.replace(month=6)
        autumn_start = spring_start.replace(month=9)
        winter_start = spring_start.replace(month=12)

    season = STATE_WINTER
    if spring_start <= current_datetime < summer_start:
        season = STATE_SPRING
    elif summer_start <= current_datetime < autumn_start:
        season = STATE_SUMMER
    elif autumn_start <= current_datetime < winter_start:
        season = STATE_AUTUMN

    # If user is located in the southern hemisphere swap the season
    if hemisphere == NORTHERN:
        return season
    return HEMISPHERE_SEASON_SWAP.get(season)


class SeasonSensorEntity(SensorEntity):
    """Representation of the current season."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_name = None
    _attr_options = ["spring", "summer", "autumn", "winter"]
    _attr_translation_key = "season"

    def __init__(self, entry: ConfigEntry, hemisphere: str) -> None:
        """Initialize the season."""
        self._attr_unique_id = entry.entry_id
        self.hemisphere = hemisphere
        self.type = entry.data[CONF_TYPE]
        self._attr_device_info = DeviceInfo(
            translation_key="season",
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    def update(self) -> None:
        """Update season."""
        self._attr_native_value = get_season(dt_util.now(), self.hemisphere, self.type)
