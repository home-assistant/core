"""Services for easyEnergy integration."""

from datetime import date, datetime, timedelta
from enum import StrEnum
from functools import partial
from typing import Final

from easyenergy import (
    Electricity,
    ElectricityGranularity,
    ElectricityPriceType,
    Gas,
    PriceInterval,
    VatOption,
)
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
ATTR_GRANULARITY: Final = "granularity"
ATTR_PRICE_TYPE: Final = "price_type"

GAS_SERVICE_NAME: Final = "get_gas_prices"
ENERGY_USAGE_SERVICE_NAME: Final = "get_energy_usage_prices"
ENERGY_RETURN_SERVICE_NAME: Final = "get_energy_return_prices"


class ServicePriceType(StrEnum):
    """Type of price."""

    ENERGY_USAGE = "energy_usage"
    ENERGY_RETURN = "energy_return"
    GAS = "gas"


GRANULARITY_OPTIONS: Final = tuple(
    granularity.value for granularity in ElectricityGranularity
)
PRICE_TYPE_OPTIONS: Final = tuple(
    electricity_price_type.value for electricity_price_type in ElectricityPriceType
)

BASE_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
    }
)
GAS_SERVICE_SCHEMA: Final = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_INCL_VAT): bool,
        vol.Optional(
            ATTR_PRICE_TYPE, default=ElectricityPriceType.MARKET.value
        ): vol.In(PRICE_TYPE_OPTIONS),
    }
)
ENERGY_USAGE_SERVICE_SCHEMA: Final = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_INCL_VAT): bool,
        vol.Optional(
            ATTR_GRANULARITY, default=ElectricityGranularity.HOUR.value
        ): vol.In(GRANULARITY_OPTIONS),
        vol.Optional(
            ATTR_PRICE_TYPE, default=ElectricityPriceType.MARKET.value
        ): vol.In(PRICE_TYPE_OPTIONS),
    }
)
ENERGY_RETURN_SERVICE_SCHEMA: Final = BASE_SERVICE_SCHEMA.extend(
    {
        vol.Optional(
            ATTR_GRANULARITY, default=ElectricityGranularity.HOUR.value
        ): vol.In(GRANULARITY_OPTIONS),
    }
)


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


def __select_prices(
    data: Electricity | Gas, use_invoice: bool
) -> list[dict[str, float | datetime]]:
    """Select market or invoice prices from price data."""
    if not use_invoice:
        return data.timestamp_prices

    return [
        {"timestamp": interval.starts_at, "price": interval.invoice_price}
        for interval in data.intervals
    ]


def __get_coordinator(call: ServiceCall) -> EasyEnergyDataUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry: EasyEnergyConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
    )
    return entry.runtime_data


async def __get_prices(
    call: ServiceCall,
    *,
    service_price_type: ServicePriceType,
) -> ServiceResponse:
    """Get prices from easyEnergy."""
    coordinator = __get_coordinator(call)

    start_date, start_datetime = __get_date(call.data.get(ATTR_START))
    end_date, end_datetime = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE
    if call.data.get(ATTR_INCL_VAT) is False:
        vat = VatOption.EXCLUDE

    data: Electricity | Gas
    prices: list[dict[str, float | datetime]]

    if service_price_type == ServicePriceType.GAS:
        data = await coordinator.easyenergy.gas_prices(
            start_date=start_date,
            end_date=end_date,
            vat=vat,
        )
        prices = __select_prices(
            data, call.data[ATTR_PRICE_TYPE] == ElectricityPriceType.INVOICE.value
        )
    else:
        data = await coordinator.easyenergy.energy_prices(
            start_date=start_date,
            end_date=end_date,
            granularity=ElectricityGranularity(call.data[ATTR_GRANULARITY]),
            vat=vat,
        )

        if service_price_type == ServicePriceType.ENERGY_USAGE:
            prices = __select_prices(
                data, call.data[ATTR_PRICE_TYPE] == ElectricityPriceType.INVOICE.value
            )
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
        partial(__get_prices, service_price_type=ServicePriceType.GAS),
        schema=GAS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_USAGE_SERVICE_NAME,
        partial(__get_prices, service_price_type=ServicePriceType.ENERGY_USAGE),
        schema=ENERGY_USAGE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_RETURN_SERVICE_NAME,
        partial(__get_prices, service_price_type=ServicePriceType.ENERGY_RETURN),
        schema=ENERGY_RETURN_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
