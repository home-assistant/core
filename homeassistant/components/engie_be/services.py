"""Services for the ENGIE Belgium integration."""

from datetime import UTC, date, timedelta
from typing import TYPE_CHECKING

from aioengiebelgium import EngieBeEpexNotPublishedError, EngieBeError, EpexGranularity
import probatio

from homeassistant.const import ATTR_DATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_GET_EPEX_PRICES_FOR_DATE
from .coordinator import BRUSSELS_TIME_ZONE, epex_window

if TYPE_CHECKING:
    from . import EngieBeConfigEntry

ATTR_CONFIG_ENTRY = "config_entry"
ATTR_GRANULARITY = "granularity"

SERVICE_GET_EPEX_PRICES_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(ATTR_DATE): cv.date,
        probatio.Optional(ATTR_GRANULARITY, default=EpexGranularity.HOURLY.name): (
            probatio.All(
                cv.string,
                probatio.Upper,
                probatio.In([granularity.name for granularity in EpexGranularity]),
            )
        ),
    }
)


def _validate_date(asked_date: date) -> None:
    """Reject any date other than today and tomorrow in Brussels."""
    today = dt_util.now(BRUSSELS_TIME_ZONE).date()
    if asked_date not in (today, today + timedelta(days=1)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_date",
            translation_placeholders={"date": asked_date.isoformat()},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services of the ENGIE Belgium integration."""

    async def get_epex_prices_for_date(call: ServiceCall) -> ServiceResponse:
        """Fetch EPEX day-ahead prices for the requested date."""
        entry: EngieBeConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
        )
        asked_date: date = call.data[ATTR_DATE]
        granularity = EpexGranularity[call.data[ATTR_GRANULARITY]]
        _validate_date(asked_date)
        start, end = epex_window(asked_date)
        try:
            payload = await entry.runtime_data.client.async_get_epex_prices(
                start, end, granularity=granularity
            )
        except EngieBeEpexNotPublishedError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="prices_not_published",
                translation_placeholders={"date": asked_date.isoformat()},
            ) from err
        except EngieBeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        return {
            "slots": [
                {
                    "start": slot.start.astimezone(UTC).isoformat(),
                    "end": slot.end.astimezone(UTC).isoformat(),
                    "value": slot.value_eur_per_kwh,
                }
                for slot in payload.slots
            ]
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_EPEX_PRICES_FOR_DATE,
        get_epex_prices_for_date,
        schema=SERVICE_GET_EPEX_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
