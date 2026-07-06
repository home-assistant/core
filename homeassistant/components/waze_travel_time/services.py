"""Services for Waze."""

from datetime import timedelta

from pywaze.route_calculator import WazeRouteCalculator
import voluptuous as vol

from homeassistant.const import CONF_REGION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    DurationSelectorConfig,
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_BASE_COORDINATES,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_TIME_DELTA,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_FILTER,
    DEFAULT_TIME_DELTA,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    METRIC_UNITS,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)
from .coordinator import async_get_travel_times
from .helpers import base_coordinates_to_tuple

SERVICE_GET_TRAVEL_TIMES = "get_travel_times"
SERVICE_GET_TRAVEL_TIMES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ORIGIN): TextSelector(),
        vol.Required(CONF_DESTINATION): TextSelector(),
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=REGIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
                sort=True,
            )
        ),
        vol.Optional(CONF_REALTIME, default=False): BooleanSelector(),
        vol.Optional(CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=VEHICLE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_VEHICLE_TYPE,
                sort=True,
            )
        ),
        vol.Optional(CONF_UNITS, default=METRIC_UNITS): SelectSelector(
            SelectSelectorConfig(
                options=UNITS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNITS,
                sort=True,
            )
        ),
        vol.Optional(CONF_AVOID_TOLL_ROADS, default=False): BooleanSelector(),
        vol.Optional(CONF_AVOID_SUBSCRIPTION_ROADS, default=False): BooleanSelector(),
        vol.Optional(CONF_AVOID_FERRIES, default=False): BooleanSelector(),
        vol.Optional(CONF_INCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_EXCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_TIME_DELTA): DurationSelector(
            DurationSelectorConfig(allow_negative=True, enable_second=False)
        ),
        vol.Optional(CONF_BASE_COORDINATES): LocationSelector(),
    }
)


async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
    """Get travel times."""
    httpx_client = get_async_client(service.hass)
    client = WazeRouteCalculator(
        region=service.data[CONF_REGION].upper(), client=httpx_client
    )

    origin_coordinates = find_coordinates(service.hass, service.data[CONF_ORIGIN])
    destination_coordinates = find_coordinates(
        service.hass, service.data[CONF_DESTINATION]
    )

    origin = origin_coordinates or service.data[CONF_ORIGIN]
    destination = destination_coordinates or service.data[CONF_DESTINATION]
    base_coordinates = base_coordinates_to_tuple(
        service.data.get(CONF_BASE_COORDINATES)
    )

    time_delta = int(
        timedelta(
            **service.data.get(CONF_TIME_DELTA, DEFAULT_TIME_DELTA)
        ).total_seconds()
        / 60
    )

    response = await async_get_travel_times(
        client=client,
        origin=origin,
        destination=destination,
        vehicle_type=service.data[CONF_VEHICLE_TYPE],
        avoid_toll_roads=service.data[CONF_AVOID_TOLL_ROADS],
        avoid_subscription_roads=service.data[CONF_AVOID_SUBSCRIPTION_ROADS],
        avoid_ferries=service.data[CONF_AVOID_FERRIES],
        realtime=service.data[CONF_REALTIME],
        units=service.data[CONF_UNITS],
        incl_filters=service.data.get(CONF_INCL_FILTER, DEFAULT_FILTER),
        excl_filters=service.data.get(CONF_EXCL_FILTER, DEFAULT_FILTER),
        time_delta=time_delta,
        base_coordinates=base_coordinates,
    )
    return {"routes": [vars(route) for route in response]}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRAVEL_TIMES,
        async_get_travel_times_service,
        SERVICE_GET_TRAVEL_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
