"""Define services for the Swiss public transport integration."""

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
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


async def _async_fetch_connections(
    call: ServiceCall,
) -> ServiceResponse:
    """Fetch a set of connections."""
    config_entry: SwissPublicTransportConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Swiss public transport integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_FETCH_CONNECTIONS,
        _async_fetch_connections,
        schema=SERVICE_FETCH_CONNECTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
