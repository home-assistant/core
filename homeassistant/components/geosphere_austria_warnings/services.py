"""Services for the GeoSphere Austria Warnings integration."""

from typing import cast

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .coordinator import GeoSphereConfigEntry
from .warnings import serialize_warnings

SERVICE_GET_WARNINGS = "get_warnings"
ATTR_CONFIG_ENTRY = "config_entry"

SERVICE_GET_WARNINGS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector(
            {"integration": DOMAIN}
        )
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the GeoSphere Austria Warnings services."""

    async def get_warnings(call: ServiceCall) -> ServiceResponse:
        """Return cached warnings for the selected config entry."""
        entry = cast(
            GeoSphereConfigEntry,
            service.async_get_config_entry(
                hass,
                DOMAIN,
                call.data[ATTR_CONFIG_ENTRY],
            ),
        )
        data = entry.runtime_data.data

        return {
            "active_warnings": serialize_warnings(data.active_warnings),
            "advance_warnings": serialize_warnings(data.advance_warnings),
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_WARNINGS,
        get_warnings,
        schema=SERVICE_GET_WARNINGS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
