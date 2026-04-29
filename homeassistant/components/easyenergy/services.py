"""Services for easyEnergy integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from functools import partial
from typing import Final

from easyenergy import Electricity, Gas, PriceInterval, VatOption
from easyenergy.const import MARKET_TIMEZONE
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector, service
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EasyEnergyConfigEntry, EasyEnergyDataUpdateCoordinator

ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_INCL_VAT: Final = "incl_vat"

GAS_SERVICE_NAME: Final = "get_gas_prices"
ENERGY_USAGE_SERVICE_NAME: Final = "get_energy_usage_prices"
ENERGY_RETURN_SERVICE_NAME: Final = "get_energy_return_prices"
BASE_SERVICE_SCHEMA: Final = {
    vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
        {
            "integration": DOMAIN,
        }
    ),
    vol.Optional(ATTR_START): str,
    vol.Optional(ATTR_END): str,
}
SERVICE_SCHEMA: Final = vol.Schema(
    {
        **BASE_SERVICE_SCHEMA,
        vol.Required(ATTR_INCL_VAT): bool,
    }
)
RETURN_SERVICE_SCHEMA: Final = vol.Schema(BASE_SERVICE_SCHEMA)


class PriceType(StrEnum):
    """Type of price."""

    ENERGY_USAGE = "energy_usage"
    ENERGY_RETURN = "energy_return"
    GAS = "gas"


def __get_date(
    date_input: str | None,
) -> tuple[date, datetime | None]:
    """Get date for the API and optional datetime for response filtering."""
    if not date_input:
        return dt_util.now().date(), None

    if date_value := dt_util.parse_date(date_input):
        return date_value, None

    if not (datetime_value := dt_util.parse_datetime(date_input)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_date",
            translation_placeholders={
                "date": date_input,
            },
        )

    datetime_utc = dt_util.as_utc(datetime_value)
    return datetime_utc.astimezone(MARKET_TIMEZONE).date(), datetime_utc


def __filter_prices(
    prices: list[dict[str, float | datetime]],
    intervals: tuple[PriceInterval, ...],
    start: datetime,
    end: datetime,
) -> list[dict[str, float | datetime]]:
    """Filter prices to the requested datetime range."""
    included_timestamps = {
        interval.starts_at
        for interval in intervals
        if interval.ends_at > start and interval.starts_at < end
    }

    return [
        timestamp_price
        for timestamp_price in prices
        if timestamp_price["timestamp"] in included_timestamps
    ]


def __serialize_prices(prices: list[dict[str, float | datetime]]) -> ServiceResponse:
    """Serialize prices to service response."""
    return {
        "prices": [
            {
                key: str(value) if isinstance(value, datetime) else value
                for key, value in timestamp_price.items()
            }
            for timestamp_price in prices
        ]
    }


def __get_coordinator(call: ServiceCall) -> EasyEnergyDataUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry: EasyEnergyConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
    )
    return entry.runtime_data


async def __get_prices(
    call: ServiceCall,
    *,
    price_type: PriceType,
) -> ServiceResponse:
    """Get prices from easyEnergy."""
    coordinator = __get_coordinator(call)

    start_date, start_datetime = __get_date(call.data.get(ATTR_START))
    end_date, end_datetime = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE
    if call.data.get(ATTR_INCL_VAT) is False:
        vat = VatOption.EXCLUDE

    data: Electricity | Gas

    if price_type == PriceType.GAS:
        data = await coordinator.easyenergy.gas_prices(
            start_date=start_date,
            end_date=end_date,
            vat=vat,
        )
        prices = data.timestamp_prices
    else:
        data = await coordinator.easyenergy.energy_prices(
            start_date=start_date,
            end_date=end_date,
            vat=vat,
        )

        if price_type == PriceType.ENERGY_USAGE:
            prices = data.timestamp_prices
        else:
            prices = data.timestamp_return_prices

    if start_datetime or end_datetime:
        filter_start = start_datetime or dt_util.as_utc(
            dt_util.start_of_local_day(start_date)
        )
        filter_end = end_datetime or dt_util.as_utc(
            dt_util.start_of_local_day(end_date + timedelta(days=1))
        )
        prices = __filter_prices(
            prices,
            data.intervals,
            filter_start,
            filter_end,
        )

    return __serialize_prices(prices)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for easyEnergy integration."""

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        partial(__get_prices, price_type=PriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_USAGE_SERVICE_NAME,
        partial(__get_prices, price_type=PriceType.ENERGY_USAGE),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_RETURN_SERVICE_NAME,
        partial(__get_prices, price_type=PriceType.ENERGY_RETURN),
        schema=RETURN_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
