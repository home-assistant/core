"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import holidays
from holidays import DateLike, HolidayBase
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
    LOGGER,
)

ATTR_NEXT_UPDATE = "next_update"


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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Workday sensor."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Workday sensor."""
    add_holidays: list[DateLike] = entry.options[CONF_ADD_HOLIDAYS]
    remove_holidays: list[str] = entry.options[CONF_REMOVE_HOLIDAYS]
    country: str = entry.options[CONF_COUNTRY]
    days_offset: int = int(entry.options[CONF_OFFSET])
    excludes: list[str] = entry.options[CONF_EXCLUDES]
    province: str | None = entry.options.get(CONF_PROVINCE)
    sensor_name: str = entry.options[CONF_NAME]
    workdays: list[str] = entry.options[CONF_WORKDAYS]

    year: int = (dt_util.now() + timedelta(days=days_offset)).year
    obj_holidays: HolidayBase = getattr(holidays, country)(years=year)

    if province:
        try:
            obj_holidays = getattr(holidays, country)(subdiv=province, years=year)
        except NotImplementedError:
            LOGGER.error("There is no subdivision %s in country %s", province, country)
            return

    # Add custom holidays
    try:
        obj_holidays.append(add_holidays)
    except ValueError as error:
        LOGGER.error("Could not add custom holidays: %s", error)

    # Remove holidays
    for remove_holiday in remove_holidays:
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
        self._next_update: datetime | None = None
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="python-holidays",
            model=holidays.__version__,
            name=name,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if TYPE_CHECKING:
            assert self._next_update is not None
        return {
            CONF_WORKDAYS: self._workdays,
            CONF_EXCLUDES: self._excludes,
            CONF_OFFSET: self._days_offset,
            ATTR_NEXT_UPDATE: self._next_update,
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
        adjusted_date = dt_util.now() + timedelta(days=self._days_offset)

        self._attr_is_on = self._calculate_state(adjusted_date)

        self._calculate_next_update()

    def _calculate_next_update(self) -> None:
        """Datetime when the next update to the state."""
        # Check current state.
        current_state = self._attr_is_on
        state = current_state

        adjusted_date = dt_util.start_of_local_day(dt_util.now()) + timedelta(
            days=self._days_offset
        )

        while current_state == state:
            adjusted_date = adjusted_date + timedelta(days=1)

            state = self._calculate_state(adjusted_date)

        self._next_update = adjusted_date

    def _calculate_state(self, adjusted_date) -> bool:
        """Calculate workday state based on a date."""
        # Default is no workday
        is_on = False

        # Get ISO day of the week (1 = Monday, 7 = Sunday)
        day = adjusted_date.isoweekday() - 1
        day_of_week = ALLOWED_DAYS[day]

        if self.is_include(day_of_week, adjusted_date):
            is_on = True

        if self.is_exclude(day_of_week, adjusted_date):
            is_on = False

        return is_on
