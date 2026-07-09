"""Services for the OMIE - Spain and Portugal electricity prices integration."""

import datetime as dt
from enum import StrEnum
from typing import Final

import aiohttp
from pyomie import QUARTER_HOURLY_START_DATE
import voluptuous as vol

from homeassistant.const import ATTR_DATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import OMIEConfigEntry
from .util import CET, pick_series_cet

ATTR_COUNTRIES: Final = "countries"


class Country(StrEnum):
    """Country to retrieve prices for."""

    ES = "es"
    PT = "pt"


SERVICE_GET_PRICES_FOR_DATE: Final = "get_prices_for_date"
SERVICE_GET_PRICES_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_DATE): cv.date,
        vol.Required(ATTR_COUNTRIES, default=[Country.ES, Country.PT]): vol.All(
            cv.ensure_list, [vol.Coerce(Country)]
        ),
    }
)

_QUARTER_HOUR: Final = dt.timedelta(minutes=15)
_SERIES_BY_COUNTRY: Final = {Country.ES: "es_spot_price", Country.PT: "pt_spot_price"}


async def _get_prices_for_date(call: ServiceCall) -> ServiceResponse:
    """Get OMIE spot prices for a specific date."""
    loaded_entries: list[OMIEConfigEntry] = (
        call.hass.config_entries.async_loaded_entries(DOMAIN)
    )
    if not loaded_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    entry = loaded_entries[0]
    market_date: dt.date = call.data[ATTR_DATE]
    countries: list[Country] = call.data[ATTR_COUNTRIES]

    if market_date < QUARTER_HOURLY_START_DATE:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="date_before_market_start",
            translation_placeholders={
                "date": market_date.isoformat(),
                "start_date": QUARTER_HOURLY_START_DATE.isoformat(),
            },
        )

    try:
        results = await entry.runtime_data.async_get_spot_price(market_date)
    except aiohttp.ClientResponseError as err:
        if err.status == 404:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="data_not_available",
                translation_placeholders={"date": market_date.isoformat()},
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    return {
        country.value: [
            {
                "start": start.isoformat(),
                # Add in UTC otherwise the end will be wrong across DST changes
                "end": (start.astimezone(dt.UTC) + _QUARTER_HOUR)
                .astimezone(CET)
                .isoformat(),
                "price": price_mwh / 1000,
            }
            for start, price_mwh in pick_series_cet(results, series_name).items()
        ]
        for country, series_name in _SERIES_BY_COUNTRY.items()
        if country in countries
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the OMIE integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        _get_prices_for_date,
        schema=SERVICE_GET_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
