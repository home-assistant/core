"""Services for the Google Travel Time integration."""

from typing import cast

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError, PermissionDenied
from google.maps.routing_v2 import RoutesAsyncClient

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
    TRAVEL_MODES_TO_GOOGLE_SDK_ENUM,
)
from .helpers import (
    async_compute_routes,
    create_routes_api_disabled_issue,
    delete_routes_api_disabled_issue,
)
from .schemas import SERVICE_GET_TRANSIT_TIMES_SCHEMA, SERVICE_GET_TRAVEL_TIMES_SCHEMA

SERVICE_GET_TRAVEL_TIMES = "get_travel_times"
SERVICE_GET_TRANSIT_TIMES = "get_transit_times"


def _build_routes_response(response) -> list[dict]:
    """Build the routes response from the API response."""
    if response is None or not response.routes:
        return []
    return [
        {
            "duration": route.duration.seconds,
            "duration_text": route.localized_values.duration.text,
            "static_duration_text": route.localized_values.static_duration.text,
            "distance_meters": route.distance_meters,
            "distance_text": route.localized_values.distance.text,
        }
        for route in response.routes
    ]


def _raise_service_error(
    hass: HomeAssistant, entry: ConfigEntry, exc: Exception
) -> None:
    """Raise a HomeAssistantError based on the exception."""
    if isinstance(exc, PermissionDenied):
        create_routes_api_disabled_issue(hass, entry)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="permission_denied",
        ) from exc
    if isinstance(exc, GoogleAPIError):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="api_error",
            translation_placeholders={"error": str(exc)},
        ) from exc
    raise exc


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Google Travel Time integration."""

    async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
        """Handle the service call to get travel times (non-transit modes)."""
        entry = async_get_config_entry(
            service.hass, DOMAIN, service.data[ATTR_CONFIG_ENTRY_ID]
        )
        api_key = entry.data[CONF_API_KEY]

        travel_mode = TRAVEL_MODES_TO_GOOGLE_SDK_ENUM[service.data[CONF_MODE]]

        client_options = ClientOptions(api_key=api_key)
        client = RoutesAsyncClient(client_options=client_options)

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

        client_options = ClientOptions(api_key=api_key)
        client = RoutesAsyncClient(client_options=client_options)

        try:
            response = await async_compute_routes(
                client=client,
                origin=service.data[CONF_ORIGIN],
                destination=service.data[CONF_DESTINATION],
                hass=hass,
                travel_mode=TRAVEL_MODES_TO_GOOGLE_SDK_ENUM["transit"],
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
