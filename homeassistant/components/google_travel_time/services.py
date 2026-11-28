"""Services for the Google Travel Time integration."""

import datetime as dt
from typing import Any, cast

from google_maps_routing_api import ComputeRoutesResponse, GoogleMapsRoutingApiAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_MODE,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_get_config_entry

from .const import (
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DOMAIN,
    TRAVEL_MODES_TO_API_ENUM,
)
from .helpers import (
    async_compute_routes,
    create_routes_api_disabled_issue,
    delete_routes_api_disabled_issue,
    get_client,
    get_localized_text,
    is_routes_api_disabled,
)
from .schemas import SERVICE_GET_TRANSIT_TIMES_SCHEMA, SERVICE_GET_TRAVEL_TIMES_SCHEMA

SERVICE_GET_TRAVEL_TIMES = "get_travel_times"
SERVICE_GET_TRANSIT_TIMES = "get_transit_times"


def _seconds(value: dt.timedelta | None) -> int:
    """Return a duration in whole seconds, or 0 when it is missing."""
    return int(value.total_seconds()) if value is not None else 0


def _build_routes_response(
    response: ComputeRoutesResponse | None,
) -> list[dict[str, Any]]:
    """Build the routes response from the API response."""
    if response is None or not response.routes:
        return []
    return [
        {
            "duration": _seconds(route.duration),
            "duration_text": get_localized_text(
                route.localized_values.duration if route.localized_values else None
            ),
            "static_duration_text": get_localized_text(
                route.localized_values.static_duration
                if route.localized_values
                else None
            ),
            "distance_meters": route.distance_meters or 0,
            "distance_text": get_localized_text(
                route.localized_values.distance if route.localized_values else None
            ),
        }
        for route in response.routes
    ]


def _raise_service_error(
    hass: HomeAssistant, entry: ConfigEntry, exc: Exception
) -> None:
    """Raise a HomeAssistantError based on the exception."""
    if isinstance(exc, HomeAssistantError):
        raise exc
    if isinstance(exc, GoogleMapsRoutingApiAuthError) and is_routes_api_disabled(exc):
        create_routes_api_disabled_issue(hass, entry)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="permission_denied",
        ) from exc
    if isinstance(exc, TimeoutError):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout",
        ) from exc
    # Wrap any other error too, so that continue_on_error works for all failures
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="api_error",
        translation_placeholders={"error": str(exc) or type(exc).__name__},
    ) from exc


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Google Travel Time integration."""

    async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
        """Handle the service call to get travel times (non-transit modes)."""
        entry = async_get_config_entry(
            service.hass, DOMAIN, service.data[ATTR_CONFIG_ENTRY_ID]
        )
        api_key = entry.data[CONF_API_KEY]

        travel_mode = TRAVEL_MODES_TO_API_ENUM[service.data[CONF_MODE]]

        client = get_client(hass, api_key)

        try:
            response = await async_compute_routes(
                client=client,
                origin=service.data[CONF_ORIGIN],
                destination=service.data[CONF_DESTINATION],
                hass=hass,
                travel_mode=travel_mode,
                units=service.data[CONF_UNITS],
                language=service.data.get(CONF_LANGUAGE),
                avoid=service.data.get(CONF_AVOID),
                traffic_model=service.data.get(CONF_TRAFFIC_MODEL),
                departure_time=service.data.get(CONF_DEPARTURE_TIME),
            )
        except Exception as ex:  # noqa: BLE001
            _raise_service_error(hass, entry, ex)

        delete_routes_api_disabled_issue(hass, entry)
        return cast(ServiceResponse, {"routes": _build_routes_response(response)})

    async def async_get_transit_times_service(service: ServiceCall) -> ServiceResponse:
        """Handle the service call to get transit times."""
        entry = async_get_config_entry(
            service.hass, DOMAIN, service.data[ATTR_CONFIG_ENTRY_ID]
        )
        api_key = entry.data[CONF_API_KEY]

        client = get_client(hass, api_key)

        try:
            response = await async_compute_routes(
                client=client,
                origin=service.data[CONF_ORIGIN],
                destination=service.data[CONF_DESTINATION],
                hass=hass,
                travel_mode=TRAVEL_MODES_TO_API_ENUM["transit"],
                units=service.data[CONF_UNITS],
                language=service.data.get(CONF_LANGUAGE),
                transit_mode=service.data.get(CONF_TRANSIT_MODE),
                transit_routing_preference=service.data.get(
                    CONF_TRANSIT_ROUTING_PREFERENCE
                ),
                departure_time=service.data.get(CONF_DEPARTURE_TIME),
                arrival_time=service.data.get(CONF_ARRIVAL_TIME),
            )
        except Exception as ex:  # noqa: BLE001
            _raise_service_error(hass, entry, ex)

        delete_routes_api_disabled_issue(hass, entry)

        return cast(ServiceResponse, {"routes": _build_routes_response(response)})

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRAVEL_TIMES,
        async_get_travel_times_service,
        SERVICE_GET_TRAVEL_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRANSIT_TIMES,
        async_get_transit_times_service,
        SERVICE_GET_TRANSIT_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
