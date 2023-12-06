"""The easyEnergy integration."""
from __future__ import annotations

from datetime import date, datetime

from easyenergy import Electricity, Gas, VatOption

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
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

PLATFORMS = [Platform.SENSOR]


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


def __serialize_prices(
    prices: Electricity | Gas,
    price_type: PriceType,
) -> dict[str, float]:
    """Serialize prices."""
    if price_type == PriceType.ENERGY_USAGE:
        return {
            str(timestamp): price for timestamp, price in prices.usage_prices.items()
        }
    if price_type == PriceType.ENERGY_RETURN:
        return {
            str(timestamp): price for timestamp, price in prices.return_prices.items()
        }
    return {str(timestamp): price for timestamp, price in prices.prices.items()}


async def __get_prices(
    coordinator: EasyEnergyDataUpdateCoordinator,
    call: ServiceCall,
    price_type: PriceType,
) -> ServiceResponse:
    """Get prices from easyEnergy."""
    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    incl_vat = call.data.get(ATTR_INCL_VAT)
    vat = (
        VatOption.EXCLUDE
        if incl_vat is not None and not incl_vat
        else VatOption.INCLUDE
    )

    data: Electricity | Gas

    if price_type == PriceType.GAS:
        data = await coordinator.easyenergy.gas_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )
    else:
        data = await coordinator.easyenergy.energy_prices(
            start_date=start,
            end_date=end,
            vat=vat,
        )

    return __serialize_prices(data, price_type)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up easyEnergy from a config entry."""

    coordinator = EasyEnergyDataUpdateCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.easyenergy.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload easyEnergy config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
