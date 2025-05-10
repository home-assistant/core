"""Define services for the Overseerr integration."""

from typing import Required, TypedDict, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_GET_FORECAST
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


def async_get_entry(
    hass: HomeAssistant, config_entry_id: str
) -> StookwijzerConfigEntry:
    """Get the Overseerr config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": DOMAIN},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return cast(StookwijzerConfigEntry, entry)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Stookwijzer integration."""

    async def async_get_forecast(call: ServiceCall) -> ServiceResponse | None:
        """Get the forecast from API endpoint."""
        entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
