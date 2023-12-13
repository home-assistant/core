"""The EnergyZero services."""
from __future__ import annotations

from datetime import date, datetime
from functools import partial

from energyzero import Electricity, Gas, VatOption

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_END,
    ATTR_INCL_VAT,
    ATTR_START,
    DOMAIN,
    ENERGY_SERVICE_NAME,
    GAS_SERVICE_NAME,
    SERVICE_SCHEMA,
    PriceType,
)
from .coordinator import EnergyZeroDataUpdateCoordinator


def __get_date(date_input: str | None) -> date | datetime:
    """Get date."""
    if not date_input:
        return dt_util.now().date()

    if value := dt_util.parse_datetime(date_input):
        return value

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


def __serialize_prices(prices: Electricity | Gas) -> ServiceResponse:
    """Serialize prices."""
    return {
        "prices": [
            {
                key: str(value) if isinstance(value, datetime) else value
                for key, value in timestamp_price.items()
            }
            for timestamp_price in prices.timestamp_prices
        ]
    }


async def __get_prices(
    call: ServiceCall,
    *,
    coordinator: EnergyZeroDataUpdateCoordinator,
    price_type: PriceType,
) -> ServiceResponse:
    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE if call.data.get(ATTR_INCL_VAT) else VatOption.EXCLUDE

    data: Electricity | Gas

    if price_type == PriceType.GAS:
        data = await coordinator.energyzero.gas_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )
    else:
        data = await coordinator.energyzero.energy_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )

    return __serialize_prices(data)


async def async_register_services(
    hass: HomeAssistant, coordinator: EnergyZeroDataUpdateCoordinator
):
    """Set up EnergyZero services."""

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        partial(__get_prices, coordinator=coordinator, price_type=PriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        partial(__get_prices, coordinator=coordinator, price_type=PriceType.ENERGY),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
