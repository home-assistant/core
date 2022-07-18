"""Support for Season sensors."""
from __future__ import annotations

from datetime import date, datetime

import ephem
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utcnow

from .const import DEFAULT_NAME, DOMAIN, TYPE_ASTRONOMICAL, VALID_TYPES

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

SEASON_ICONS = {
    STATE_SPRING: "mdi:flower",
    STATE_SUMMER: "mdi:sunglasses",
    STATE_AUTUMN: "mdi:leaf",
    STATE_WINTER: "mdi:snowflake",
}


PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=TYPE_ASTRONOMICAL): vol.In(VALID_TYPES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the season sensor platform."""
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
    """Set up the platform from config entry."""
    hemisphere = EQUATOR
    if hass.config.latitude < 0:
        hemisphere = SOUTHERN
    elif hass.config.latitude > 0:
        hemisphere = NORTHERN

    async_add_entities([SeasonSensorEntity(entry, hemisphere)], True)


def get_season(
    current_date: date, hemisphere: str, season_tracking_type: str
) -> str | None:
    """Calculate the current season."""

    if hemisphere == "equator":
        return None

    if season_tracking_type == TYPE_ASTRONOMICAL:
        spring_start = ephem.next_equinox(str(current_date.year)).datetime()
        summer_start = ephem.next_solstice(str(current_date.year)).datetime()
        autumn_start = ephem.next_equinox(spring_start).datetime()
        winter_start = ephem.next_solstice(summer_start).datetime()
    else:
        spring_start = datetime(2017, 3, 1).replace(year=current_date.year)
        summer_start = spring_start.replace(month=6)
        autumn_start = spring_start.replace(month=9)
        winter_start = spring_start.replace(month=12)

    season = STATE_WINTER
    if spring_start <= current_date < summer_start:
        season = STATE_SPRING
    elif summer_start <= current_date < autumn_start:
        season = STATE_SUMMER
    elif autumn_start <= current_date < winter_start:
        season = STATE_AUTUMN

    # If user is located in the southern hemisphere swap the season
    if hemisphere == NORTHERN:
        return season
    return HEMISPHERE_SEASON_SWAP.get(season)


class SeasonSensorEntity(SensorEntity):
    """Representation of the current season."""

    _attr_device_class = "season__season"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, hemisphere: str) -> None:
        """Initialize the season."""
        self._attr_unique_id = entry.entry_id
        self.hemisphere = hemisphere
        self.type = entry.data[CONF_TYPE]
        self._attr_device_info = DeviceInfo(
            name=entry.title,
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    def update(self) -> None:
        """Update season."""
        self._attr_native_value = get_season(
            utcnow().replace(tzinfo=None), self.hemisphere, self.type
        )

        self._attr_icon = "mdi:cloud"
        if self._attr_native_value:
            self._attr_icon = SEASON_ICONS[self._attr_native_value]
