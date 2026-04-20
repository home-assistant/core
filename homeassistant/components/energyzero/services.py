"""The EnergyZero services."""

from __future__ import annotations

from datetime import date
from enum import Enum
from functools import partial
from typing import Final
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, EnergyZeroNoDataError, Interval, PriceType
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
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
from .coordinator import EnergyZeroConfigEntry, EnergyZeroDataUpdateCoordinator

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


class ServicePriceType(Enum):
    """Type of service."""

    ENERGY = "energy"
    GAS = "gas"


def __get_local_date(date_input: str | None, local_tz: ZoneInfo) -> date:
    """Get date normalized to the configured Home Assistant timezone."""
    if not date_input:
        return dt_util.now().astimezone(local_tz).date()

    if value := dt_util.parse_datetime(date_input):
        if value.tzinfo is None:
            value = value.replace(tzinfo=local_tz)
        else:
            value = value.astimezone(local_tz)
        return value.date()

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


def __serialize_prices(prices: EnergyPrices) -> ServiceResponse:
    """Serialize prices."""
    return {
        "prices": [
            {
                "price": price,
                "timestamp": str(time_range.start_including),
            }
            for time_range, price in prices.prices.items()
        ]
    }


def __get_coordinator(call: ServiceCall) -> EnergyZeroDataUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry_id: str = call.data[ATTR_CONFIG_ENTRY]
    entry: EnergyZeroConfigEntry | None = call.hass.config_entries.async_get_entry(
        entry_id
    )

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

    return entry.runtime_data


async def __get_prices(
    call: ServiceCall,
    *,
    price_type: ServicePriceType,
) -> ServiceResponse:
    coordinator = __get_coordinator(call)
    local_tz = ZoneInfo(call.hass.config.time_zone)
    start_input = call.data.get(ATTR_START)
    end_input = call.data.get(ATTR_END)

    # Keep backward-compatible single-day behavior when only `end` is provided.
    start = __get_local_date(start_input or end_input, local_tz)
    end = __get_local_date(end_input, local_tz) if end_input else start

    if start_input and end_input and end != start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_range",
            translation_placeholders={
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )

    selected_price_type = (
        PriceType.MARKET_WITH_VAT if call.data[ATTR_INCL_VAT] else PriceType.MARKET
    )

    data: EnergyPrices

    if price_type == ServicePriceType.GAS:
        try:
            data = await coordinator.energyzero.get_gas_prices(
                start_date=start,
                end_date=end,
                price_type=selected_price_type,
                local_tz=local_tz,
            )
        except EnergyZeroNoDataError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={
                    "date": start.isoformat(),
                },
            ) from err
    else:
        try:
            data = await coordinator.energyzero.get_electricity_prices(
                start_date=start,
                end_date=end,
                interval=Interval.HOUR,
                price_type=selected_price_type,
                local_tz=local_tz,
            )
        except EnergyZeroNoDataError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={
                    "date": start.isoformat(),
                },
            ) from err

    return __serialize_prices(data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up EnergyZero services."""

    hass.services.async_register(
        DOMAIN,
        GAS_SERVICE_NAME,
        partial(__get_prices, price_type=ServicePriceType.GAS),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        partial(__get_prices, price_type=ServicePriceType.ENERGY),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
