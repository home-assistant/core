"""Utility functions for the Workday integration."""
from datetime import date, timedelta
import logging
from types import MappingProxyType
from typing import Any

import holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY
from homeassistant.util import dt

from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    DEFAULT_OFFSET,
)

_LOGGER = logging.getLogger(__name__)


def build_holidays(
    user_input: dict[str, Any] | MappingProxyType[str, Any]
) -> holidays.HolidayBase:
    """Validate the user input and create a holiday object."""
    country: str = user_input[CONF_COUNTRY]
    days_offset: int = user_input.get(CONF_OFFSET, DEFAULT_OFFSET)
    year: int = (dt.now() + timedelta(days=days_offset)).year
    province: str = user_input.get(CONF_PROVINCE, "")
    if province and province not in holidays.list_supported_countries()[country]:
        raise NoProvinceError()
    _LOGGER.debug(
        "Creating base holiday object with country=%s, province=%s, days_offset=%d, year=%d",
        country,
        province,
        days_offset,
        year,
    )
    obj_holidays: holidays.HolidayBase = getattr(holidays, country)(
        years=year, subdiv=province
    )

    new_holiday: holidays.DateLike
    for new_holiday in user_input.get(CONF_ADD_HOLIDAYS, "").split(","):
        if new_holiday == "":
            continue
        try:
            obj_holidays.append(new_holiday)
        except ValueError as exc:
            raise AddHolidayError() from exc

    for remove_holiday in user_input.get(CONF_REMOVE_HOLIDAYS, "").split(","):
        if remove_holiday == "":
            continue
        try:
            if dt.parse_date(remove_holiday):
                obj_holidays.pop(remove_holiday)
            else:
                obj_holidays.pop_named(remove_holiday)
        except KeyError as exc:
            raise NoSuchHolidayError() from exc

    _LOGGER.debug("Found the following holidays for your configuration:")
    for holiday_date, name in sorted(obj_holidays.items()):
        _LOGGER.debug("%s %s", holiday_date.strftime("%Y-%m-%d"), name)

    return obj_holidays


def day_to_string(day: int) -> str | None:
    """Convert day index 0 - 7 to string."""
    try:
        return ALLOWED_DAYS[day]
    except IndexError:
        return None


def get_date(input_date: date) -> date:
    """Return date. Needed for testing."""
    return input_date


def config_entry_to_string(entry: ConfigEntry) -> str:
    """Print a ConfigEntry as a string."""
    return f"""domain={entry.domain}
    title={entry.title}
    data={entry.data}
    options={entry.options}
    entry_id={entry.entry_id}
    unique_id={entry.unique_id}
    state={entry.state}
    """


class NoProvinceError(ValueError):
    """Error thrown when an invalid province is given."""


class AddHolidayError(ValueError):
    """Error thrown when trying to add a badly formatted holiday."""


class NoSuchHolidayError(ValueError):
    """Error thrown when trying to remove a holiday that doesn't exist."""
