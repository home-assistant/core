"""Services for Nord Pool integration."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import TYPE_CHECKING

from pynordpool import (
    AREAS,
    Currency,
    NordPoolAuthenticationError,
    NordPoolEmptyResponseError,
    NordPoolError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

if TYPE_CHECKING:
    from . import NordPoolConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTR_CONFIG_ENTRY = "config_entry"
ATTR_AREAS = "areas"
ATTR_CURRENCY = "currency"

SERVICE_GET_PRICES_FOR_DATE = "get_prices_for_date"
SERVICE_GET_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Required(ATTR_DATE): cv.date,
        vol.Optional(ATTR_AREAS): vol.All(vol.In(list(AREAS)), cv.ensure_list, [str]),
        vol.Optional(ATTR_CURRENCY): vol.All(
            cv.string, vol.In([currency.value for currency in Currency])
        ),
    }
)


def get_config_entry(hass: HomeAssistant, entry_id: str) -> NordPoolConfigEntry:
    """Return config entry."""
    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Nord Pool integration."""

    async def get_prices_for_date(call: ServiceCall) -> ServiceResponse:
        """Get price service."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        asked_date: date = call.data[ATTR_DATE]
        client = entry.runtime_data.client

        areas: list[str] = entry.data[ATTR_AREAS]
        if _areas := call.data.get(ATTR_AREAS):
            areas = _areas

        currency: str = entry.data[ATTR_CURRENCY]
        if _currency := call.data.get(ATTR_CURRENCY):
            currency = _currency

        areas = [area.upper() for area in areas]
        currency = currency.upper()

        try:
            price_data = await client.async_get_delivery_period(
                datetime.combine(asked_date, dt_util.utcnow().time()),
                Currency(currency),
                areas,
            )
        except NordPoolAuthenticationError as error:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NordPoolEmptyResponseError as error:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="empty_response",
            ) from error
        except NordPoolError as error:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from error

        result: dict[str, JsonValueType] = {}
        for area in areas:
            result[area] = [
                {
                    "start": price_entry.start.isoformat(),
                    "end": price_entry.end.isoformat(),
                    "price": price_entry.entry[area],
                }
                for price_entry in price_data.entries
            ]
        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        get_prices_for_date,
        schema=SERVICE_GET_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
