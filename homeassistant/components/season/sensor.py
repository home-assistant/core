"""Support for tracking which astronomical or meteorological season it is."""
from __future__ import annotations

from datetime import date, datetime
import logging

import ephem
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Season"

EQUATOR = "equator"

NORTHERN = "northern"

SOUTHERN = "southern"
STATE_AUTUMN = "autumn"
STATE_SPRING = "spring"
STATE_SUMMER = "summer"
STATE_WINTER = "winter"

TYPE_ASTRONOMICAL = "astronomical"
TYPE_METEOROLOGICAL = "meteorological"

VALID_TYPES = [TYPE_ASTRONOMICAL, TYPE_METEOROLOGICAL]

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Display the current season."""
    _type: str = config[CONF_TYPE]
    name: str = config[CONF_NAME]

    if hass.config.latitude < 0:
        hemisphere = SOUTHERN
    elif hass.config.latitude > 0:
        hemisphere = NORTHERN
    else:
        hemisphere = EQUATOR

    _LOGGER.debug(_type)
    add_entities([Season(hemisphere, _type, name)], True)


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

    if spring_start <= current_date < summer_start:
        season = STATE_SPRING
    elif summer_start <= current_date < autumn_start:
        season = STATE_SUMMER
    elif autumn_start <= current_date < winter_start:
        season = STATE_AUTUMN
    elif winter_start <= current_date or spring_start > current_date:
        season = STATE_WINTER

    # If user is located in the southern hemisphere swap the season
    if hemisphere == NORTHERN:
        return season
    return HEMISPHERE_SEASON_SWAP.get(season)


class Season(SensorEntity):
    """Representation of the current season."""

    _attr_device_class = "season__season"

    def __init__(self, hemisphere: str, season_tracking_type: str, name: str) -> None:
        """Initialize the season."""
        self._attr_name = name
        self.hemisphere = hemisphere
        self.type = season_tracking_type

    def update(self) -> None:
        """Update season."""
        self._attr_native_value = get_season(
            utcnow().replace(tzinfo=None), self.hemisphere, self.type
        )

        self._attr_icon = "mdi:cloud"
        if self._attr_native_value:
            self._attr_icon = SEASON_ICONS[self._attr_native_value]
