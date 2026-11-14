"""Services for Waze."""

from datetime import timedelta
from enum import StrEnum

import probatio
from pywaze.route_calculator import WazeRouteCalculator

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


class WazeTravelTimeService(StrEnum):
    """Store keys for Waze travel time services."""

    GET_TRAVEL_TIMES = "get_travel_times"


class WazeTravelTimeServiceArgument(StrEnum):
    """Store keys for Waze travel time service arguments."""

    ORIGIN = "origin"
    DESTINATION = "destination"
    REGION = "region"
    UNITS = "units"
    VEHICLE_TYPE = "vehicle_type"
    REALTIME = "realtime"
    AVOID_TOLL_ROADS = "avoid_toll_roads"
    AVOID_FERRIES = "avoid_ferries"
    AVOID_SUBSCRIPTION_ROADS = "avoid_subscription_roads"
    INCL_FILTER = "incl_filter"
    EXCL_FILTER = "excl_filter"
    TIME_DELTA = "time_delta"
    BASE_COORDINATES = "base_coordinates"


SERVICE_GET_TRAVEL_TIMES_SCHEMA = probatio.Schema(
    {
        probatio.Required(WazeTravelTimeServiceArgument.ORIGIN): TextSelector(),
        probatio.Required(WazeTravelTimeServiceArgument.DESTINATION): TextSelector(),
        probatio.Required(WazeTravelTimeServiceArgument.REGION): SelectSelector(
            SelectSelectorConfig(
                options=REGIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
                sort=True,
            )
        ),
        probatio.Optional(
            WazeTravelTimeServiceArgument.REALTIME, default=False
        ): BooleanSelector(),
        probatio.Optional(
            WazeTravelTimeServiceArgument.VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE
        ): SelectSelector(
            SelectSelectorConfig(
                options=VEHICLE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_VEHICLE_TYPE,
                sort=True,
            )
        ),
        probatio.Optional(
            WazeTravelTimeServiceArgument.UNITS, default=METRIC_UNITS
        ): SelectSelector(
            SelectSelectorConfig(
                options=UNITS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNITS,
                sort=True,
            )
        ),
        probatio.Optional(
            WazeTravelTimeServiceArgument.AVOID_TOLL_ROADS, default=False
        ): BooleanSelector(),
        probatio.Optional(
            WazeTravelTimeServiceArgument.AVOID_SUBSCRIPTION_ROADS, default=False
        ): BooleanSelector(),
        probatio.Optional(
            WazeTravelTimeServiceArgument.AVOID_FERRIES, default=False
        ): BooleanSelector(),
        probatio.Optional(WazeTravelTimeServiceArgument.INCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        probatio.Optional(WazeTravelTimeServiceArgument.EXCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        probatio.Optional(WazeTravelTimeServiceArgument.TIME_DELTA): DurationSelector(
            DurationSelectorConfig(allow_negative=True, enable_second=False)
        ),
        probatio.Optional(
            WazeTravelTimeServiceArgument.BASE_COORDINATES
        ): LocationSelector(),
    }
)


async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
    """Get travel times."""
    httpx_client = get_async_client(service.hass)

    origin_coordinates = find_coordinates(
        service.hass, service.data[WazeTravelTimeServiceArgument.ORIGIN]
    )
    destination_coordinates = find_coordinates(
        service.hass, service.data[WazeTravelTimeServiceArgument.DESTINATION]
    )

    origin = origin_coordinates or service.data[WazeTravelTimeServiceArgument.ORIGIN]
    destination = (
        destination_coordinates
        or service.data[WazeTravelTimeServiceArgument.DESTINATION]
    )
    base_coordinates = base_coordinates_to_tuple(
        service.data.get(WazeTravelTimeServiceArgument.BASE_COORDINATES)
    )

    time_delta = int(
        timedelta(
            **service.data.get(
                WazeTravelTimeServiceArgument.TIME_DELTA, DEFAULT_TIME_DELTA
            )
        ).total_seconds()
        / 60
    )

    async with WazeRouteCalculator(
        region=service.data[WazeTravelTimeServiceArgument.REGION].upper(),
        client=httpx_client,
    ) as client:
        response = await async_get_travel_times(
            client=client,
            origin=origin,
            destination=destination,
            vehicle_type=service.data[WazeTravelTimeServiceArgument.VEHICLE_TYPE],
            avoid_toll_roads=service.data[
                WazeTravelTimeServiceArgument.AVOID_TOLL_ROADS
            ],
            avoid_subscription_roads=service.data[
                WazeTravelTimeServiceArgument.AVOID_SUBSCRIPTION_ROADS
            ],
            avoid_ferries=service.data[WazeTravelTimeServiceArgument.AVOID_FERRIES],
            realtime=service.data[WazeTravelTimeServiceArgument.REALTIME],
            units=service.data[WazeTravelTimeServiceArgument.UNITS],
            incl_filters=service.data.get(
                WazeTravelTimeServiceArgument.INCL_FILTER, DEFAULT_FILTER
            ),
            excl_filters=service.data.get(
                WazeTravelTimeServiceArgument.EXCL_FILTER, DEFAULT_FILTER
            ),
            time_delta=time_delta,
            base_coordinates=base_coordinates,
        )
    return {"routes": [vars(route) for route in response]}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    hass.services.async_register(
        DOMAIN,
        WazeTravelTimeService.GET_TRAVEL_TIMES,
        async_get_travel_times_service,
        SERVICE_GET_TRAVEL_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
