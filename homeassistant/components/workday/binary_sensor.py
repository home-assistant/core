"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from datetime import date, timedelta

from holidays import (
    HolidayBase,
    __version__ as python_holidays_version,
    country_holidays,
)

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DOMAIN,
    LOGGER,
)


def validate_dates(holiday_list: list[str]) -> list[str]:
    """Validate and adds to list of dates to add or remove."""
    calc_holidays: list[str] = []
    for add_date in holiday_list:
        if add_date.find(",") > 0:
            dates = add_date.split(",", maxsplit=1)
            d1 = dt_util.parse_date(dates[0])
            d2 = dt_util.parse_date(dates[1])
            if d1 is None or d2 is None:
                LOGGER.error("Incorrect dates in date range: %s", add_date)
                continue
            _range: timedelta = d2 - d1
            for i in range(_range.days + 1):
                day = d1 + timedelta(days=i)
                calc_holidays.append(day.strftime("%Y-%m-%d"))
            continue
        calc_holidays.append(add_date)
    return calc_holidays


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Workday sensor."""
    add_holidays: list[str] = entry.options[CONF_ADD_HOLIDAYS]
    remove_holidays: list[str] = entry.options[CONF_REMOVE_HOLIDAYS]
    country: str | None = entry.options.get(CONF_COUNTRY)
    days_offset: int = int(entry.options[CONF_OFFSET])
    excludes: list[str] = entry.options[CONF_EXCLUDES]
    province: str | None = entry.options.get(CONF_PROVINCE)
    sensor_name: str = entry.options[CONF_NAME]
    workdays: list[str] = entry.options[CONF_WORKDAYS]

    year: int = (dt_util.now() + timedelta(days=days_offset)).year

    if country:
        cls: HolidayBase = country_holidays(country, subdiv=province, years=year)
        obj_holidays: HolidayBase = country_holidays(
            country,
            subdiv=province,
            years=year,
            language=cls.default_language,
        )
    else:
        obj_holidays = HolidayBase()

    calc_add_holidays: list[str] = validate_dates(add_holidays)
    calc_remove_holidays: list[str] = validate_dates(remove_holidays)

    # Add custom holidays
    try:
        obj_holidays.append(calc_add_holidays)  # type: ignore[arg-type]
    except ValueError as error:
        LOGGER.error("Could not add custom holidays: %s", error)

    # Remove holidays
    for remove_holiday in calc_remove_holidays:
        try:
            # is this formatted as a date?
            if dt_util.parse_date(remove_holiday):
                # remove holiday by date
                removed = obj_holidays.pop(remove_holiday)
                LOGGER.debug("Removed %s", remove_holiday)
            else:
                # remove holiday by name
                LOGGER.debug("Treating '%s' as named holiday", remove_holiday)
                removed = obj_holidays.pop_named(remove_holiday)
                for holiday in removed:
                    LOGGER.debug("Removed %s by name '%s'", holiday, remove_holiday)
        except KeyError as unmatched:
            LOGGER.warning("No holiday found matching %s", unmatched)

    LOGGER.debug("Found the following holidays for your configuration:")
    for holiday_date, name in sorted(obj_holidays.items()):
        # Make explicit str variable to avoid "Incompatible types in assignment"
        _holiday_string = holiday_date.strftime("%Y-%m-%d")
        LOGGER.debug("%s %s", _holiday_string, name)

    async_add_entities(
        [
            IsWorkdaySensor(
                obj_holidays,
                workdays,
                excludes,
                days_offset,
                sensor_name,
                entry.entry_id,
            )
        ],
        True,
    )


class IsWorkdaySensor(BinarySensorEntity):
    """Implementation of a Workday sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = DOMAIN

    def __init__(
        self,
        obj_holidays: HolidayBase,
        workdays: list[str],
        excludes: list[str],
        days_offset: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Workday sensor."""
        self._obj_holidays = obj_holidays
        self._workdays = workdays
        self._excludes = excludes
        self._days_offset = days_offset
        self._attr_extra_state_attributes = {
            CONF_WORKDAYS: workdays,
            CONF_EXCLUDES: excludes,
            CONF_OFFSET: days_offset,
        }
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="python-holidays",
            model=python_holidays_version,
            name=name,
        )

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
        adjusted_date = dt_util.now() + timedelta(days=self._days_offset)
        day = adjusted_date.isoweekday() - 1
        day_of_week = ALLOWED_DAYS[day]

        if self.is_include(day_of_week, adjusted_date):
            self._attr_is_on = True

        if self.is_exclude(day_of_week, adjusted_date):
            self._attr_is_on = False
