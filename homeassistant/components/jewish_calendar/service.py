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
        vol.Required("nusach", default=Nusach.SFARAD): Nusach,
        vol.Required("language"): str,
    }
)


def async_setup_services(
    hass: HomeAssistant, config_entry: JewishCalendarConfigEntry
) -> None:
    """Set up the Jewish Calendar services."""

    async def get_omer_blessing(call: ServiceCall) -> ServiceResponse:
        """Return the Omer blessing for a given date."""
        value = Omer(
            date=HebrewDate.from_gdate(call.data["date"]),
            nusach=call.data["nusach"],
            language=call.data.get("language", config_entry.runtime_data.language),
        ).count_str()
        return {"message": str(value)}

    hass.services.async_register(
        DOMAIN,
        "get_omer_blessing",
        get_omer_blessing,
        schema=OMER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
