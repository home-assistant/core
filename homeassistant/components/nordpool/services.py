"""Services for Nord Pool integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from functools import partial
import logging
from typing import TYPE_CHECKING

from pynordpool import (
    AREAS,
    Currency,
    DeliveryPeriodData,
    NordPoolAuthenticationError,
    NordPoolClient,
    NordPoolEmptyResponseError,
    NordPoolError,
    PriceIndicesData,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

if TYPE_CHECKING:
    from . import NordPoolConfigEntry
from .const import ATTR_RESOLUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTR_CONFIG_ENTRY = "config_entry"
ATTR_AREAS = "areas"
ATTR_CURRENCY = "currency"

SERVICE_GET_PRICES_FOR_DATE = "get_prices_for_date"
SERVICE_GET_PRICE_INDICES_FOR_DATE = "get_price_indices_for_date"
SERVICE_GET_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_DATE): cv.date,
        vol.Optional(ATTR_AREAS): vol.All(vol.In(list(AREAS)), cv.ensure_list, [str]),
        vol.Optional(ATTR_CURRENCY): vol.All(
            cv.string, vol.In([currency.value for currency in Currency])
        ),
    }
)
SERVICE_GET_PRICE_INDICES_SCHEMA = SERVICE_GET_PRICES_SCHEMA.extend(
    {
        vol.Optional(ATTR_RESOLUTION, default=60): vol.All(
            cv.positive_int, vol.All(vol.Coerce(int), vol.In((15, 30, 60)))
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Nord Pool integration."""

    def get_service_params(
        call: ServiceCall,
    ) -> tuple[NordPoolClient, date, str, list[str], int]:
        """Return the parameters for the service."""
        entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
        client = entry.runtime_data.client
        asked_date: date = call.data[ATTR_DATE]

        areas: list[str] = entry.data[ATTR_AREAS]
        if _areas := call.data.get(ATTR_AREAS):
            areas = _areas

        currency: str = entry.data[ATTR_CURRENCY]
        if _currency := call.data.get(ATTR_CURRENCY):
            currency = _currency

        resolution: int = 60
        if _resolution := call.data.get(ATTR_RESOLUTION):
            resolution = _resolution

        areas = [area.upper() for area in areas]
        currency = currency.upper()

        return (client, asked_date, currency, areas, resolution)

    async def get_prices_for_date(
        client: NordPoolClient,
        asked_date: date,
        currency: str,
        areas: list[str],
        resolution: int,
    ) -> DeliveryPeriodData:
        """Get prices."""
        return await client.async_get_delivery_period(
            datetime.combine(asked_date, dt_util.utcnow().time()),
            Currency(currency),
            areas,
        )

    async def get_price_indices_for_date(
        client: NordPoolClient,
        asked_date: date,
        currency: str,
        areas: list[str],
        resolution: int,
    ) -> PriceIndicesData:
        """Get prices."""
        return await client.async_get_price_indices(
            datetime.combine(asked_date, dt_util.utcnow().time()),
            Currency(currency),
            areas,
            resolution=resolution,
        )

    async def get_prices(func: Callable, call: ServiceCall) -> ServiceResponse:
        """Get price service."""
        client, asked_date, currency, areas, resolution = get_service_params(call)

        try:
            price_data = await func(
                client,
                asked_date,
                currency,
                areas,
                resolution,
            )
        except NordPoolAuthenticationError as error:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NordPoolEmptyResponseError:
            return {area: [] for area in areas}
        except (NordPoolError, TimeoutError) as error:
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
        partial(get_prices, get_prices_for_date),
        schema=SERVICE_GET_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICE_INDICES_FOR_DATE,
        partial(get_prices, get_price_indices_for_date),
        schema=SERVICE_GET_PRICE_INDICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
