"""Define services for the Swiss public transport integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
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

from .const import CONNECTIONS_COUNT, CONNECTIONS_MAX, DOMAIN
from .coordinator import SwissPublicTransportConfigEntry


class SwissPublicTransportService(StrEnum):
    """Store keys for Swiss public transport services."""

    FETCH_CONNECTIONS = "fetch_connections"


class SwissPublicTransportServiceArgument(StrEnum):
    """Store keys for Swiss public transport service arguments."""

    LIMIT = "limit"


SERVICE_FETCH_CONNECTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
        probatio.Optional(
            SwissPublicTransportServiceArgument.LIMIT, default=CONNECTIONS_COUNT
        ): NumberSelector(
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
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    limit = (
        call.data.get(SwissPublicTransportServiceArgument.LIMIT) or CONNECTIONS_COUNT
    )
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
        SwissPublicTransportService.FETCH_CONNECTIONS,
        _async_fetch_connections,
        schema=SERVICE_FETCH_CONNECTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
