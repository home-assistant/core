"""Sensor to indicate whether the current day is a workday."""
from datetime import date, timedelta
import logging
from typing import Any

import holidays

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt

from .const import (
    ALLOWED_DAYS,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)
from .util import build_holidays, config_entry_to_string, day_to_string, get_date

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Workday sensor."""
    _LOGGER.debug("WorkdayBinarySensor async setup: %s", config_entry_to_string(entry))

    sensor = WorkdayBinarySensor(entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = sensor

    entities = [sensor]
    for ent in entities:
        await ent.async_update()
    async_add_entities(entities)


class WorkdayBinarySensor(BinarySensorEntity):
    """Implementation of a Workday sensor."""

    _obj_holidays: holidays.HolidayBase
    _workdays: list[str]
    _excludes: list[str]
    _days_offset: int

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Workday sensor."""
        self.update_attributes(entry)

    def update_attributes(self, entry: ConfigEntry) -> None:
        """Update binary sensor attributes."""
        _LOGGER.debug(
            "Updating Workday sensor attributes: %s", config_entry_to_string(entry)
        )

        holiday_data: dict[str, Any] = {}
        holiday_data.update(entry.data)
        holiday_data.update(entry.options)
        self._obj_holidays = build_holidays(holiday_data)

        self._attr_name = entry.data[CONF_NAME]
        self._workdays = entry.options.get(CONF_WORKDAYS, DEFAULT_WORKDAYS)
        self._excludes = entry.options.get(CONF_EXCLUDES, DEFAULT_EXCLUDES)
        self._days_offset = entry.options.get(CONF_OFFSET, DEFAULT_OFFSET)
        self._attr_extra_state_attributes = {
            CONF_WORKDAYS: self._workdays,
            CONF_EXCLUDES: self._excludes,
            CONF_OFFSET: self._days_offset,
            "holidays": sorted([d.strftime("%Y-%m-%d") for d in self._obj_holidays]),
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
        _LOGGER.debug("Starting async_update for Workday sensor '%s'", self._attr_name)
        # Default is no workday
        self._attr_is_on = False

        # Get ISO day of the week (1 = Monday, 7 = Sunday)
        adjusted_date = get_date(dt.now()) + timedelta(days=self._days_offset)
        day = adjusted_date.isoweekday() - 1
        day_of_week = day_to_string(day)

        if day_of_week is None:
            _LOGGER.warning(
                "Unknown day of week number %d (expected 0-%d), assuming binary sensor should be False",
                day,
                len(ALLOWED_DAYS) - 1,
            )
            return

        if self.is_include(day_of_week, adjusted_date):
            _LOGGER.debug(
                "%s or %s is a workday, setting binary sensor True",
                day_of_week,
                adjusted_date.strftime("%Y-%m-%d"),
            )
            self._attr_is_on = True

        if self.is_exclude(day_of_week, adjusted_date):
            _LOGGER.debug(
                "%s or %s is not a workday, setting binary sensor False",
                day_of_week,
                adjusted_date.strftime("%Y-%m-%d"),
            )
            self._attr_is_on = False
