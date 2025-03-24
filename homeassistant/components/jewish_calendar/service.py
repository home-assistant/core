"""Services for Jewish Calendar."""

import datetime

from hdate import HebrewDate
from hdate.omer import Nusach, Omer
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)

from . import JewishCalendarConfigEntry
from .const import DOMAIN

OMER_SCHEMA = vol.Schema(
    {
        vol.Required("date", default=datetime.date.today): datetime.date,
        vol.Required("nusach", default="sfarad"): str,
        vol.Required("language"): str,
    }
)


def async_setup_services(
    hass: HomeAssistant, config_entry: JewishCalendarConfigEntry
) -> None:
    """Set up the Jewish Calendar services."""

    async def get_omer_count(call: ServiceCall) -> ServiceResponse:
        """Return the Omer blessing for a given date."""
        hebrew_date = HebrewDate.from_gdate(call.data["date"])
        nusach = Nusach[call.data["nusach"].upper()]
        language = call.data.get("language", config_entry.runtime_data.language)
        omer = Omer(date=hebrew_date, nusach=nusach, language=language)
        return {
            "message": str(omer.count_str()),
            "hebrew_date": str(hebrew_date),
            "weeks": omer.week,
            "days": omer.day,
            "total_days": omer.total_days,
        }

    hass.services.async_register(
        DOMAIN,
        "count_omer",
        get_omer_count,
        schema=OMER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
