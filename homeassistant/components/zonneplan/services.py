"""Actions for the Zonneplan integration."""

from enum import StrEnum

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector, service

from .const import DOMAIN


class ZonneplanService(StrEnum):
    """Zonneplan actions."""

    GET_ELECTRICITY_PRICES = "get_electricity_prices"


class ZonneplanServiceArgument(StrEnum):
    """Zonneplan action fields."""

    CONFIG_ENTRY = "config_entry"
    INTERVAL = "interval"


GET_ELECTRICITY_PRICES_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            ZonneplanServiceArgument.CONFIG_ENTRY
        ): selector.ConfigEntrySelector({"integration": DOMAIN}),
        probatio.Required(ZonneplanServiceArgument.INTERVAL): probatio.In(
            ("hour", "quarter")
        ),
    }
)


async def _async_get_electricity_prices(call: ServiceCall) -> ServiceResponse:
    """Return the electricity prices the integration has fetched."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ZonneplanServiceArgument.CONFIG_ENTRY]
    )

    coordinator = entry.runtime_data.coordinator
    prices = (
        coordinator.data.electricity_prices
        if call.data[ZonneplanServiceArgument.INTERVAL] == "hour"
        else coordinator.data.electricity_quarter_prices
    )
    if prices is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_electricity_prices",
        )
    return {
        "prices": [
            {
                "start": point.start_date.isoformat(),
                "end": point.end_date.isoformat(),
                "price": float(point.price_tax_included.euro),
            }
            for point in prices.prices
        ]
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Zonneplan actions."""
    hass.services.async_register(
        DOMAIN,
        ZonneplanService.GET_ELECTRICITY_PRICES,
        _async_get_electricity_prices,
        schema=GET_ELECTRICITY_PRICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
