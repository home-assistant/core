"""Services for easyEnergy integration."""
from __future__ import annotations

from datetime import date, datetime

from easyenergy import Electricity, Gas, VatOption

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
    ENERGY_RETURN_SERVICE_NAME,
    ENERGY_USAGE_SERVICE_NAME,
    GAS_SERVICE_NAME,
    SERVICE_SCHEMA,
    PriceType,
)
from .coordinator import EasyEnergyDataUpdateCoordinator


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


async def __get_prices(
    coordinator: EasyEnergyDataUpdateCoordinator,
    call: ServiceCall,
    price_type: PriceType,
) -> ServiceResponse:
    """Get prices from easyEnergy."""
    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE
    if (incl_vat := call.data.get(ATTR_INCL_VAT)) is not None and not incl_vat:
        vat = VatOption.EXCLUDE

    data: Electricity | Gas

    if price_type == PriceType.GAS:
        data = await coordinator.easyenergy.gas_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )
        return {"prices": data.timestamp_prices}
    else:
        data = await coordinator.easyenergy.energy_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )

        if price_type == PriceType.ENERGY_USAGE:
            return {"prices": data.timestamp_usage_prices}
        return {"prices": data.timestamp_return_prices}


async def async_setup_services(
    hass: HomeAssistant,
    coordinator: EasyEnergyDataUpdateCoordinator,
) -> None:
    """Set up services for easyEnergy integration."""

    async def get_gas_prices(call: ServiceCall) -> ServiceResponse:
        """Search gas prices."""
        return await __get_prices(coordinator, call, PriceType.GAS)

    async def get_energy_usage_prices(call: ServiceCall) -> ServiceResponse:
        """Search energy usage prices."""
        return await __get_prices(coordinator, call, PriceType.ENERGY_USAGE)

    async def get_energy_return_prices(call: ServiceCall) -> ServiceResponse:
        """Search energy return prices."""
        return await __get_prices(coordinator, call, PriceType.ENERGY_RETURN)

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        get_gas_prices,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_USAGE_SERVICE_NAME,
        get_energy_usage_prices,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_RETURN_SERVICE_NAME,
        get_energy_return_prices,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
