"""Template functions to return HDate instances & other information."""


from __future__ import annotations

import datetime as dt
import logging
from typing import cast

from hdate import HDate, Zmanim

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

DOMAIN = "jewish_calendar"

LOGGER = logging.getLogger(__name__)


class JewishCalendarTemplates:
    """Registers services for the jewish_calendar integration."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Register the services."""
        data = hass.data[DOMAIN]

        self._location = data["location"]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._diaspora = data["diaspora"]

        template.register_function(
            hass,
            "get_hebrew_date",
            self.get_hebrew_date,
        )
        template.register_filter(
            hass,
            "get_hebrew_date",
            self.get_hebrew_date,
        )

        template.register_function(
            hass,
            "get_zmanim",
            self.get_zmanim,
        )
        template.register_filter(
            hass,
            "get_zmanim",
            self.get_zmanim,
        )

    def get_hebrew_date(self, val: str | int | float | dt.datetime, /) -> HDate:
        """Template function that returns an HDate object."""
        return HDate(
            parse_date_param(val), diaspora=self._diaspora, hebrew=self._hebrew
        )

    def get_zmanim(self, val: str | int | float | dt.datetime, /) -> HDate:
        """Template function that returns a Zmanim object."""
        return Zmanim(
            parse_date_param(val),
            location=self._location,
            hebrew=self._hebrew,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
        )


def parse_date_param(val: str | int | float | dt.datetime) -> dt.datetime:
    """Parse a date-like parameter into a date object."""

    if isinstance(val, dt.datetime):
        return val
    if isinstance(val, HDate):
        return cast(dt.datetime, val.gdate)
    if isinstance(val, str):
        return cast(dt.datetime, dt_util.parse_datetime(val))
    if isinstance(val, float | int):
        return dt_util.utc_from_timestamp(val)
    raise ValueError("Unknown datetime value {val}")
