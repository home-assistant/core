"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import holidays
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, WEEKDAYS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt

from .const import (
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_STATE,
    CONF_WORKDAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ALLOWED_DAYS = WEEKDAYS + ["holiday"]

# By default, Monday - Friday are workdays
DEFAULT_WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]
# By default, public holidays, Saturdays and Sundays are excluded from workdays
DEFAULT_EXCLUDES = ["sat", "sun", "holiday"]
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


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COUNTRY): valid_country,
        vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): vol.All(
            cv.ensure_list, [vol.In(ALLOWED_DAYS)]
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
        vol.Optional(CONF_PROVINCE): cv.string,
        vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): vol.All(
            cv.ensure_list, [vol.In(ALLOWED_DAYS)]
        ),
        vol.Optional(CONF_ADD_HOLIDAYS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_REMOVE_HOLIDAYS): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Workday platform."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Workday sensor."""
    sensor_name = config_entry.data.get(CONF_NAME)
    country = config_entry.data[CONF_COUNTRY]
    province = config_entry.data.get(CONF_PROVINCE)
    state = config_entry.data.get(CONF_STATE)
    days_offset = config_entry.data[CONF_OFFSET]
    workdays = config_entry.data[CONF_WORKDAYS]
    excludes = config_entry.data[CONF_EXCLUDES]
    add_holidays = config_entry.options.get(CONF_ADD_HOLIDAYS)
    remove_holidays: list[str] | None = config_entry.options.get(CONF_REMOVE_HOLIDAYS)

    year = (get_date(dt.now()) + timedelta(days=days_offset)).year
    obj_holidays = getattr(holidays, country)(prov=province, state=state, years=year)

    # Add custom holidays
    try:
        obj_holidays.append(add_holidays)
    except TypeError:
        _LOGGER.debug("No custom holidays or invalid holidays")

    # Remove holidays
    if remove_holidays:
        for date in remove_holidays:
            try:
                # is this formatted as a date?
                if dt.parse_date(date):
                    # remove holiday by date
                    removed = obj_holidays.pop(date)
                    _LOGGER.debug("Removed %s", date)
                else:
                    # remove holiday by name
                    _LOGGER.debug("Treating '%s' as named holiday", date)
                    removed = obj_holidays.pop_named(date)
                    for holiday in removed:
                        _LOGGER.debug("Removed %s by name '%s'", holiday, date)
            except KeyError as unmatched:
                _LOGGER.warning("No holiday found matching %s", unmatched)

    _LOGGER.debug("Found the following holidays for your configuration:")
    for date, name in sorted(obj_holidays.items()):
        _LOGGER.debug("%s %s", date, name)

    async_add_entities(
        new_entities=[
            IsWorkdaySensor(
                obj_holidays,
                workdays,
                excludes,
                days_offset,
                sensor_name,
                config_entry.unique_id,
            )
        ],
        update_before_add=True,
    )


def day_to_string(day: int) -> str | None:
    """Convert day index 0 - 7 to string."""
    try:
        return ALLOWED_DAYS[day]
    except IndexError:
        return None


def get_date(date):
    """Return date. Needed for testing."""
    return date


class IsWorkdaySensor(BinarySensorEntity):
    """Implementation of a Workday sensor."""

    def __init__(self, obj_holidays, workdays, excludes, days_offset, name, unique_id):
        """Initialize the Workday sensor."""
        self._name = name
        self._obj_holidays = obj_holidays
        self._workdays = workdays
        self._excludes = excludes
        self._days_offset = days_offset
        self._state = None
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self._state

    def is_include(self, day, now) -> bool:
        """Check if given day is in the includes list."""
        if day in self._workdays:
            return True
        if "holiday" in self._workdays and now in self._obj_holidays:
            return True

        return False

    def is_exclude(self, day, now) -> bool:
        """Check if given day is in the excludes list."""
        if day in self._excludes:
            return True
        if "holiday" in self._excludes and now in self._obj_holidays:
            return True

        return False

    @property
    def extra_state_attributes(self):
        """Return the attributes of the entity."""
        # return self._attributes
        return {
            CONF_WORKDAYS: self._workdays,
            CONF_EXCLUDES: self._excludes,
            CONF_OFFSET: self._days_offset,
        }

    async def async_update(self) -> None:
        """Get date and look whether it is a holiday."""
        # Default is no workday
        self._state = False

        # Get ISO day of the week (1 = Monday, 7 = Sunday)
        date = get_date(dt.now()) + timedelta(days=self._days_offset)
        day = date.isoweekday() - 1
        day_of_week = day_to_string(day)

        if self.is_include(day_of_week, date):
            self._state = True

        if self.is_exclude(day_of_week, date):
            self._state = False
