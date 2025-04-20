"""Services for Jewish Calendar."""

import datetime
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

SUPPORTED_LANGUAGES = {"en": "english", "fr": "french", "he": "hebrew"}
OMER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DATE): cv.date,
        vol.Required(ATTR_NUSACH, default="sfarad"): vol.In(
            [nusach.name.lower() for nusach in Nusach]
        ),
        vol.Required(CONF_LANGUAGE, default="he"): LanguageSelector(
            LanguageSelectorConfig(languages=list(SUPPORTED_LANGUAGES.keys()))
        ),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Jewish Calendar services."""

    async def get_omer_count(call: ServiceCall) -> ServiceResponse:
        """Return the Omer blessing for a given date."""
        if "date" in call.data:
            hebrew_date = HebrewDate.from_gdate(call.data["date"])
        else:
            now = dt_util.now()
            today = now.date()
            if (
                sunset := get_astral_event_date(hass, SUN_EVENT_SUNSET, today)
            ) is not None and now > dt_util.as_local(sunset):
                hebrew_date = HebrewDate.from_gdate(today + datetime.timedelta(days=1))
            else:
                hebrew_date = HebrewDate.from_gdate(today)

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
