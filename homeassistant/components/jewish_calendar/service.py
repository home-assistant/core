"""Services for Jewish Calendar."""

import datetime
import logging
from typing import cast

from hdate import HebrewDate
from hdate.omer import Nusach, Omer
from hdate.translator import Language
import voluptuous as vol

from homeassistant.const import CONF_LANGUAGE, SUN_EVENT_SUNSET
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import LanguageSelector, LanguageSelectorConfig
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .const import ATTR_DATE, ATTR_NUSACH, DOMAIN, SERVICE_COUNT_OMER

_LOGGER = logging.getLogger(__name__)
SUPPORTED_LANGUAGES = {"en": "english", "fr": "french", "he": "hebrew"}
OMER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional("is_after_sunset", default=True): cv.boolean,
        vol.Required(ATTR_NUSACH, default="sfarad"): vol.In(
            [nusach.name.lower() for nusach in Nusach]
        ),
        vol.Optional(CONF_LANGUAGE, default="he"): LanguageSelector(
            LanguageSelectorConfig(languages=list(SUPPORTED_LANGUAGES.keys()))
        ),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Jewish Calendar services."""

    def get_hebrew_date(hass: HomeAssistant) -> HebrewDate:
        """Convert a Gregorian date to a Hebrew date."""
        after_sunset = is_after_sunset(hass)
        return HebrewDate.from_gdate(
            dt_util.now() + datetime.timedelta(days=int(after_sunset))
        )

    def is_after_sunset(hass: HomeAssistant) -> bool:
        """Determine if the current time is after sunset."""
        now = dt_util.now()
        today = now.date()
        event_date = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)
        if event_date is None:
            _LOGGER.error("Can't get sunset event date for %s", today)
            raise ValueError("Can't get sunset event date")
        sunset = dt_util.as_local(event_date)
        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)
        return now > sunset

    async def get_omer_count(call: ServiceCall) -> ServiceResponse:
        """Return the Omer blessing for a given date."""
        if "date" in call.data:
            date = call.data["date"]
            hebrew_date = HebrewDate.from_gdate(
                date + datetime.timedelta(days=int(call.data["is_after_sunset"]))
            )
        else:
            hebrew_date = get_hebrew_date(call.hass)
        nusach = Nusach[call.data["nusach"].upper()]

        # Currently Omer only supports Hebrew, English, and French and requires
        # the full language name
        language = cast(Language, SUPPORTED_LANGUAGES[call.data[CONF_LANGUAGE]])

        omer = Omer(date=hebrew_date, nusach=nusach, language=language)
        return {
            "message": str(omer.count_str()),
            "weeks": omer.week,
            "days": omer.day,
            "total_days": omer.total_days,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_COUNT_OMER,
        get_omer_count,
        schema=OMER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
