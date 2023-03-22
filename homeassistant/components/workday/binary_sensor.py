"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

import holidays
from holidays import DateLike, HolidayBase
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_NAME, WEEKDAYS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)

ALLOWED_DAYS = WEEKDAYS + ["holiday"]

CONF_COUNTRY = "country"
CONF_PROVINCE = "province"
CONF_WORKDAYS = "workdays"
CONF_EXCLUDES = "excludes"
CONF_OFFSET = "days_offset"
CONF_ADD_HOLIDAYS = "add_holidays"
CONF_REMOVE_HOLIDAYS = "remove_holidays"

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
DEFAULT_NAME = "Workday Sensor"
DEFAULT_OFFSET = 0


def valid_country(value: Any) -> str:
    """Validate that the given country is supported."""
    value = cv.string(value)
    all_supported_countries = holidays.list_supported_countries()

    try:
        raw_value = value.encode("utf-8")
    except UnicodeError as err:
        raise vol.Invalid(
            "The country name or the abbreviation must be a valid UTF-8 string."
        ) from err
    if not raw_value:
        raise vol.Invalid("Country name or the abbreviation must not be empty.")
    if value not in all_supported_countries:
        raise vol.Invalid("Country is not supported.")
    return value


PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COUNTRY): valid_country,
        vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): vol.All(
            cv.ensure_list, [vol.In(ALLOWED_DAYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
        vol.Optional(CONF_PROVINCE): cv.string,
        vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): vol.All(
            cv.ensure_list, [vol.In(ALLOWED_DAYS)]
        ),
        vol.Optional(CONF_ADD_HOLIDAYS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_REMOVE_HOLIDAYS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Workday sensor."""
    add_holidays: list[DateLike] = config[CONF_ADD_HOLIDAYS]
    remove_holidays: list[str] = config[CONF_REMOVE_HOLIDAYS]
    country: str = config[CONF_COUNTRY]
    days_offset: int = config[CONF_OFFSET]
    excludes: list[str] = config[CONF_EXCLUDES]
    province: str | None = config.get(CONF_PROVINCE)
    sensor_name: str = config[CONF_NAME]
    workdays: list[str] = config[CONF_WORKDAYS]

    year: int = (get_date(dt.now()) + timedelta(days=days_offset)).year
    obj_holidays: HolidayBase = getattr(holidays, country)(years=year)

    if province:
        if (
            hasattr(obj_holidays, "subdivisions")
            and province in obj_holidays.subdivisions
        ):
            obj_holidays = getattr(holidays, country)(subdiv=province, years=year)
        else:
            _LOGGER.error("There is no subdivision %s in country %s", province, country)
            return

    # Add custom holidays
    try:
        obj_holidays.append(add_holidays)
    except TypeError:
        _LOGGER.debug("No custom holidays or invalid holidays")

    # Remove holidays
    try:
        for remove_holiday in remove_holidays:
            try:
                # is this formatted as a date?
                if dt.parse_date(remove_holiday):
                    # remove holiday by date
                    removed = obj_holidays.pop(remove_holiday)
                    _LOGGER.debug("Removed %s", remove_holiday)
                else:
                    # remove holiday by name
                    _LOGGER.debug("Treating '%s' as named holiday", remove_holiday)
                    removed = obj_holidays.pop_named(remove_holiday)
                    for holiday in removed:
                        _LOGGER.debug(
                            "Removed %s by name '%s'", holiday, remove_holiday
                        )
            except KeyError as unmatched:
                _LOGGER.warning("No holiday found matching %s", unmatched)
    except TypeError:
        _LOGGER.debug("No holidays to remove or invalid holidays")

    _LOGGER.debug("Found the following holidays for your configuration:")
    for holiday_date, name in sorted(obj_holidays.items()):
        # Make explicit str variable to avoid "Incompatible types in assignment"
        _holiday_string = holiday_date.strftime("%Y-%m-%d")
        _LOGGER.debug("%s %s", _holiday_string, name)

    add_entities(
        [IsWorkdaySensor(obj_holidays, workdays, excludes, days_offset, sensor_name)],
        True,
    )


def day_to_string(day: int) -> str | None:
    """Convert day index 0 - 7 to string."""
    try:
        return ALLOWED_DAYS[day]
    except IndexError:
        return None


def get_date(input_date: date) -> date:
    """Return date. Needed for testing."""
    return input_date


class IsWorkdaySensor(BinarySensorEntity):
    """Implementation of a Workday sensor."""

    def __init__(
        self,
        obj_holidays: HolidayBase,
        workdays: list[str],
        excludes: list[str],
        days_offset: int,
        name: str,
    ) -> None:
        """Initialize the Workday sensor."""
        self._attr_name = name
        self._obj_holidays = obj_holidays
        self._workdays = workdays
        self._excludes = excludes
        self._days_offset = days_offset
        self._attr_extra_state_attributes = {
            CONF_WORKDAYS: workdays,
            CONF_EXCLUDES: excludes,
            CONF_OFFSET: days_offset,
        }

    def is_include(self, day: str, now: date) -> bool:
        """Check if given day is in the includes list."""
        if day in self._workdays:
            return True
        if "holiday" in self._workdays and now in self._obj_holidays:
            return True

        return False

    def is_exclude(self, day: str, now: date) -> bool:
        """Check if given day is in the excludes list."""
        if day in self._excludes:
            return True
        if "holiday" in self._excludes and now in self._obj_holidays:
            return True

        return False

    async def async_update(self) -> None:
        """Get date and look whether it is a holiday."""
        # Default is no workday
        self._attr_is_on = False

        # Get ISO day of the week (1 = Monday, 7 = Sunday)
        adjusted_date = get_date(dt.now()) + timedelta(days=self._days_offset)
        day = adjusted_date.isoweekday() - 1
        day_of_week = day_to_string(day)

        if day_of_week is None:
            return

        if self.is_include(day_of_week, adjusted_date):
            self._attr_is_on = True

        if self.is_exclude(day_of_week, adjusted_date):
            self._attr_is_on = False
