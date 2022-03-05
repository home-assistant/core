"""Support for tracking which astronomical or meteorological season it is."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

import ephem
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME, CONF_TYPE, TIME_DAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import as_local, get_time_zone, utcnow

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Season"

DEVICE_CLASS_SEASON = "season__season"

EQUATOR = "equator"
NORTHERN = "northern"
SOUTHERN = "southern"

STATE_NONE = None
STATE_AUTUMN = "autumn"
STATE_SPRING = "spring"
STATE_SUMMER = "summer"
STATE_WINTER = "winter"

TYPE_ASTRONOMICAL = "astronomical"
TYPE_METEOROLOGICAL = "meteorological"

ENTITY_SEASON = "season"
ENTITY_DAYS_LEFT = "days_left"
ENTITY_DAYS_IN = "days_in"
ENTITY_NEXT_SEASON = "next_season"

ATTR_LAST_UPDATED = "last_updated"

VALID_TYPES = [
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
]

HEMISPHERE_SEASON_SWAP = {
    STATE_WINTER: STATE_SUMMER,
    STATE_SPRING: STATE_AUTUMN,
    STATE_AUTUMN: STATE_SPRING,
    STATE_SUMMER: STATE_WINTER,
}

ICON_DEFAULT = "mdi:cloud"
ICON_DAYS_LEFT = "mdi:calendar-arrow-right"
ICON_DAYS_IN = "mdi:calendar-arrow-left"
ICON_NEXT_SEASON = "mdi:calendar"

SEASON_ICONS = {
    STATE_NONE: ICON_DEFAULT,
    STATE_SPRING: "mdi:flower",
    STATE_SUMMER: "mdi:sunglasses",
    STATE_AUTUMN: "mdi:leaf",
    STATE_WINTER: "mdi:snowflake",
}

SCAN_INTERVAL = timedelta(seconds=30)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=25)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ENTITY_SEASON,
        name="Season",
        icon=ICON_DEFAULT,
        device_class=DEVICE_CLASS_SEASON,
    ),
    SensorEntityDescription(
        key=ENTITY_DAYS_LEFT,
        name="Days Left",
        native_unit_of_measurement=TIME_DAYS,
        icon=ICON_DAYS_LEFT,
    ),
    SensorEntityDescription(
        key=ENTITY_DAYS_IN,
        name="Days In",
        native_unit_of_measurement=TIME_DAYS,
        icon=ICON_DAYS_IN,
    ),
    SensorEntityDescription(
        key=ENTITY_NEXT_SEASON,
        name="Next Start Date",
        icon=ICON_NEXT_SEASON,
    ),
)


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
    """Display the current season."""
    _type: str = config[CONF_TYPE]
    name: str = config[CONF_NAME]

    if hass.config.latitude < 0:
        hemisphere = SOUTHERN
    elif hass.config.latitude > 0:
        hemisphere = NORTHERN
    else:
        hemisphere = EQUATOR

    if hemisphere == EQUATOR:
        _LOGGER.warning(
            "Season cannot be determined for equator, 'unknown' state will be shown"
        )

    _LOGGER.debug(_type)

    season_data = SeasonData(hemisphere, _type, hass.config.time_zone)

    await season_data.async_update()

    entities = []
    for description in SENSOR_TYPES:
        if description.key in ENTITY_SEASON:
            entities.append(Season(season_data, description, name))
        elif hemisphere not in EQUATOR:
            entities.append(Season(season_data, description, name))

    async_add_entities(entities, True)


class Season(SensorEntity):
    """Representation of the current season."""

    def __init__(
        self,
        season_data,
        description: SensorEntityDescription,
        name,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        if name in DEFAULT_NAME and description.key != ENTITY_SEASON:
            self._attr_name = f"{name} {description.name}"
        else:
            self._attr_name = f"{description.name}"
        self.season_data = season_data
        self.datetime = None

    async def async_update(self):
        """Get the latest data from Season and update the state."""
        await self.season_data.async_update()
        if self.entity_description.key in self.season_data.data:
            self._attr_native_value = self.season_data.data[self.entity_description.key]
            if self.entity_description.key in ENTITY_SEASON:
                self._attr_icon = SEASON_ICONS[
                    self.season_data.data[self.entity_description.key]
                ]
                self._attr_extra_state_attributes = {
                    ATTR_LAST_UPDATED: self.season_data.data[ATTR_LAST_UPDATED]
                }


class SeasonData:
    """Calculate the current season."""

    def __init__(self, hemisphere, _type, time_zone):
        """Initialize the data object."""

        self.hemisphere = hemisphere
        self.time_zone = time_zone
        self.type = _type
        self.datetime = None
        self._data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from season."""
        # Update data
        self._data = get_season(
            self,
            utcnow().replace(tzinfo=None),
            self.hemisphere,
            self.type,
            self.time_zone,
            self._data,
        )


def get_season(
    self,
    current_date: datetime,
    hemisphere: str,
    season_tracking_type: str,
    time_zone: str,
    data,
) -> str | None:
    """Calculate the current season."""

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

    if hemisphere != EQUATOR:
        if current_date < spring_start or current_date >= winter_start:
            season = STATE_WINTER
            if current_date.month >= 12:
                spring_start = ephem.next_equinox(str(current_date.year + 1)).datetime()
            else:
                winter_start = ephem.next_solstice(
                    summer_start.replace(year=current_date.year - 1)
                ).datetime()
            days_left = spring_start.date() - current_date.date()
            days_in = current_date.date() - winter_start.date()
            next_date = spring_start
        elif current_date < summer_start:
            season = STATE_SPRING
            days_left = summer_start.date() - current_date.date()
            days_in = current_date.date() - spring_start.date()
            next_date = summer_start
        elif current_date < autumn_start:
            season = STATE_SUMMER
            days_left = autumn_start.date() - current_date.date()
            days_in = current_date.date() - summer_start.date()
            next_date = autumn_start
        elif current_date < winter_start:
            season = STATE_AUTUMN
            days_left = winter_start.date() - current_date.date()
            days_in = current_date.date() - autumn_start.date()
            next_date = winter_start

        if time_zone is not None:
            next_date = as_local(next_date.replace(tzinfo=get_time_zone("UTC")))
    else:
        season = str(STATE_NONE)
        days_left = STATE_NONE
        days_in = STATE_NONE
        next_date = STATE_NONE

    last_update = as_local(current_date.replace(tzinfo=get_time_zone("UTC")))

    # If user is located in the southern hemisphere swap the season
    if hemisphere == SOUTHERN:
        season = HEMISPHERE_SEASON_SWAP.get(season)

    if hemisphere == EQUATOR:
        self.data = {
            ENTITY_SEASON: season,
            ENTITY_DAYS_LEFT: days_left,
            ENTITY_DAYS_IN: days_in,
            ENTITY_NEXT_SEASON: next_date,
            ATTR_LAST_UPDATED: last_update,
        }
    else:
        self.data = {
            ENTITY_SEASON: season,
            ENTITY_DAYS_LEFT: days_left.days,
            ENTITY_DAYS_IN: abs(days_in.days) + 1,
            ENTITY_NEXT_SEASON: next_date.strftime("%Y-%m-%d, %H:%M:%S"),
            ATTR_LAST_UPDATED: last_update,
        }

    return data
