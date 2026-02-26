"""Define services for the Stookwijzer integration."""

from typing import Required, TypedDict, cast

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import service

from .const import DOMAIN, SERVICE_GET_FORECAST
from .coordinator import StookwijzerConfigEntry

SERVICE_GET_FORECAST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
    }
)


class Forecast(TypedDict):
    """Typed Stookwijzer forecast dict."""

    datetime: Required[str]
    advice: str | None
    final: bool | None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Stookwijzer integration."""

    async def async_get_forecast(call: ServiceCall) -> ServiceResponse:
        """Get the forecast from API endpoint."""
        entry: StookwijzerConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        client = entry.runtime_data.client

        return cast(
            ServiceResponse,
            {
                "forecast": cast(
                    list[Forecast], await client.async_get_forecast() or []
                ),
            },
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FORECAST,
        async_get_forecast,
        schema=SERVICE_GET_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
