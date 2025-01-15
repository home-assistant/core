"""Define services for the Swiss public transport integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LIMIT,
    CONNECTIONS_COUNT,
    CONNECTIONS_MAX,
    DOMAIN,
    SERVICE_FETCH_CONNECTIONS,
)
from .coordinator import SwissPublicTransportConfigEntry

SERVICE_FETCH_CONNECTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
        vol.Optional(ATTR_LIMIT, default=CONNECTIONS_COUNT): NumberSelector(
            NumberSelectorConfig(
                min=1, max=CONNECTIONS_MAX, mode=NumberSelectorMode.BOX
            )
        ),
    }
)


def async_get_entry(
    hass: HomeAssistant, config_entry_id: str
) -> SwissPublicTransportConfigEntry:
    """Get the Swiss public transport config entry."""
    if not (entry := hass.config_entries.async_get_entry(config_entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"target": config_entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": entry.title},
        )
    return entry


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Swiss public transport integration."""

    async def async_fetch_connections(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Fetch a set of connections."""
        config_entry = async_get_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])

        limit = call.data.get(ATTR_LIMIT) or CONNECTIONS_COUNT
        try:
            connections = await config_entry.runtime_data.fetch_connections_as_json(
                limit=int(limit)
            )
        except UpdateFailed as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={
                    "error": str(e),
                },
            ) from e
        return {"connections": connections}

    hass.services.async_register(
        DOMAIN,
        SERVICE_FETCH_CONNECTIONS,
        async_fetch_connections,
        schema=SERVICE_FETCH_CONNECTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
