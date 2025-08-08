"""The Waze Travel Time data coordinator."""

import asyncio
from collections.abc import Collection
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Literal

from pywaze.route_calculator import CalcRoutesResponse, WazeRouteCalculator, WRCError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DOMAIN,
    IMPERIAL_UNITS,
    SEMAPHORE,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

SECONDS_BETWEEN_API_CALLS = 0.5


async def async_get_travel_times(
    client: WazeRouteCalculator,
    origin: str,
    destination: str,
    vehicle_type: str,
    avoid_toll_roads: bool,
    avoid_subscription_roads: bool,
    avoid_ferries: bool,
    realtime: bool,
    units: Literal["metric", "imperial"] = "metric",
    incl_filters: Collection[str] | None = None,
    excl_filters: Collection[str] | None = None,
) -> list[CalcRoutesResponse]:
    """Get all available routes."""

    incl_filters = incl_filters or ()
    excl_filters = excl_filters or ()

    _LOGGER.debug(
        "Getting update for origin: %s destination: %s",
        origin,
        destination,
    )
    routes = []
    vehicle_type = "" if vehicle_type.upper() == "CAR" else vehicle_type.upper()
    try:
        routes = await client.calc_routes(
            origin,
            destination,
            vehicle_type=vehicle_type,
            avoid_toll_roads=avoid_toll_roads,
            avoid_subscription_roads=avoid_subscription_roads,
            avoid_ferries=avoid_ferries,
            real_time=realtime,
            alternatives=3,
        )

        if len(routes) < 1:
            _LOGGER.warning("No routes found")
            return routes

        _LOGGER.debug("Got routes: %s", routes)

        incl_routes: list[CalcRoutesResponse] = []

        def should_include_route(route: CalcRoutesResponse) -> bool:
            if len(incl_filters) < 1:
                return True
            should_include = any(
                street_name in incl_filters or "" in incl_filters
                for street_name in route.street_names
            )
            if not should_include:
                _LOGGER.debug(
                    "Excluding route [%s], because no inclusive filter matched any streetname",
                    route.name,
                )
                return False
            return True

        incl_routes = [route for route in routes if should_include_route(route)]

        filtered_routes: list[CalcRoutesResponse] = []

        def should_exclude_route(route: CalcRoutesResponse) -> bool:
            for street_name in route.street_names:
                for excl_filter in excl_filters:
                    if excl_filter == street_name:
                        _LOGGER.debug(
                            "Excluding route, because exclusive filter [%s] matched streetname: %s",
                            excl_filter,
                            route.name,
                        )
                        return True
            return False

        filtered_routes = [
            route for route in incl_routes if not should_exclude_route(route)
        ]

        if len(filtered_routes) < 1:
            _LOGGER.warning("No routes matched your filters")
            return filtered_routes

        if units == IMPERIAL_UNITS:
            filtered_routes = [
                CalcRoutesResponse(
                    name=route.name,
                    distance=DistanceConverter.convert(
                        route.distance, UnitOfLength.KILOMETERS, UnitOfLength.MILES
                    ),
                    duration=route.duration,
                    street_names=route.street_names,
                )
                for route in filtered_routes
                if route.distance is not None
            ]

    except WRCError as exp:
        raise UpdateFailed(f"Error on retrieving data: {exp}") from exp

    else:
        return filtered_routes


@dataclass
class WazeTravelTimeData:
    """WazeTravelTime data class."""

    origin: str
    destination: str
    duration: float | None
    distance: float | None
    route: str | None


class WazeTravelTimeCoordinator(DataUpdateCoordinator[WazeTravelTimeData]):
    """Waze Travel Time DataUpdateCoordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: WazeRouteCalculator,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._origin = config_entry.data[CONF_ORIGIN]
        self._destination = config_entry.data[CONF_DESTINATION]

    async def _async_update_data(self) -> WazeTravelTimeData:
        """Get the latest data from Waze."""
        origin_coordinates = find_coordinates(self.hass, self._origin)
        destination_coordinates = find_coordinates(self.hass, self._destination)

        _LOGGER.debug(
            "Fetching Route for %s, from %s to %s",
            self.config_entry.title,
            self._origin,
            self._destination,
        )
        await self.hass.data[DOMAIN][SEMAPHORE].acquire()
        try:
            if origin_coordinates is None or destination_coordinates is None:
                raise UpdateFailed("Unable to determine origin or destination")

            # Grab options on every update
            incl_filter = self.config_entry.options[CONF_INCL_FILTER]
            excl_filter = self.config_entry.options[CONF_EXCL_FILTER]
            realtime = self.config_entry.options[CONF_REALTIME]
            vehicle_type = self.config_entry.options[CONF_VEHICLE_TYPE]
            avoid_toll_roads = self.config_entry.options[CONF_AVOID_TOLL_ROADS]
            avoid_subscription_roads = self.config_entry.options[
                CONF_AVOID_SUBSCRIPTION_ROADS
            ]
            avoid_ferries = self.config_entry.options[CONF_AVOID_FERRIES]
            routes = await async_get_travel_times(
                self.client,
                origin_coordinates,
                destination_coordinates,
                vehicle_type,
                avoid_toll_roads,
                avoid_subscription_roads,
                avoid_ferries,
                realtime,
                self.config_entry.options[CONF_UNITS],
                incl_filter,
                excl_filter,
            )
            if len(routes) < 1:
                travel_data = WazeTravelTimeData(
                    origin=origin_coordinates,
                    destination=destination_coordinates,
                    duration=None,
                    distance=None,
                    route=None,
                )

            else:
                route = routes[0]

                travel_data = WazeTravelTimeData(
                    origin=origin_coordinates,
                    destination=destination_coordinates,
                    duration=route.duration,
                    distance=route.distance,
                    route=route.name,
                )

            await asyncio.sleep(SECONDS_BETWEEN_API_CALLS)

        finally:
            self.hass.data[DOMAIN][SEMAPHORE].release()

        return travel_data
