"""The EnergyZero services."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from functools import partial
from typing import Final

from energyzero import Electricity, Gas, VatOption
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnergyZeroDataUpdateCoordinator

ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_INCL_VAT: Final = "incl_vat"

GAS_SERVICE_NAME: Final = "get_gas_prices"
ENERGY_SERVICE_NAME: Final = "get_energy_prices"
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_INCL_VAT): bool,
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
    }
)


class PriceType(Enum):
    """Type of price."""

    ENERGY = "energy"
    GAS = "gas"


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


def __get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> EnergyZeroDataUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry_id: str = call.data[ATTR_CONFIG_ENTRY]
    entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)

    if not entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={
                "config_entry": entry_id,
            },
        )
    if entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unloaded_config_entry",
            translation_placeholders={
                "config_entry": entry.title,
            },
        )

    coordinator: EnergyZeroDataUpdateCoordinator = hass.data[DOMAIN][entry_id]
    return coordinator


async def __get_prices(
    call: ServiceCall,
    *,
    hass: HomeAssistant,
    price_type: PriceType,
) -> ServiceResponse:
    coordinator = __get_coordinator(hass, call)

    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    vat = VatOption.INCLUDE

    if call.data.get(ATTR_INCL_VAT) is False:
        vat = VatOption.EXCLUDE

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up EnergyZero services."""

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        partial(__get_prices, hass=hass, price_type=PriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        partial(__get_prices, hass=hass, price_type=PriceType.ENERGY),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
