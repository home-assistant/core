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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import service
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONNECTIONS_COUNT, CONNECTIONS_MAX, DOMAIN
from .coordinator import (
    SwissPublicTransportConfigEntry,
    SwissPublicTransportDataUpdateCoordinator,
    SwissPublicTransportStationboardDataUpdateCoordinator,
)


class SwissPublicTransportService(StrEnum):
    """Store keys for Swiss public transport services."""

    FETCH_CONNECTIONS = "fetch_connections"
    FETCH_DEPARTURES = "fetch_departures"


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

SERVICE_FETCH_DEPARTURES_SCHEMA = SERVICE_FETCH_CONNECTIONS_SCHEMA


async def _async_fetch_connections(
    call: ServiceCall,
) -> ServiceResponse:
    """Fetch a set of connections."""
    config_entry: SwissPublicTransportConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    coordinator = config_entry.runtime_data
    if not isinstance(coordinator, SwissPublicTransportDataUpdateCoordinator):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_connection",
        )

    limit = (
        call.data.get(SwissPublicTransportServiceArgument.LIMIT) or CONNECTIONS_COUNT
    )
    try:
        connections = await coordinator.fetch_connections_as_json(limit=int(limit))
    except UpdateFailed as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "error": str(e),
            },
        ) from e
    return {"connections": connections}


async def _async_fetch_departures(
    call: ServiceCall,
) -> ServiceResponse:
    """Fetch a set of departures."""
    config_entry: SwissPublicTransportConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    coordinator = config_entry.runtime_data
    if not isinstance(
        coordinator, SwissPublicTransportStationboardDataUpdateCoordinator
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_stationboard",
        )

    return {
        "departures": await coordinator.fetch_departures_as_json(
            limit=int(call.data[SwissPublicTransportServiceArgument.LIMIT])
        )
    }


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
    hass.services.async_register(
        DOMAIN,
        SwissPublicTransportService.FETCH_DEPARTURES,
        _async_fetch_departures,
        schema=SERVICE_FETCH_DEPARTURES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
