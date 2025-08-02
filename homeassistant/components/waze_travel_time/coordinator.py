"""The Waze Travel Time data coordinator."""

import asyncio
from collections.abc import Collection
from datetime import timedelta
import logging
from typing import Literal

import httpx
from pywaze.route_calculator import CalcRoutesResponse, WazeRouteCalculator, WRCError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
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
) -> list[CalcRoutesResponse] | None:
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

        if len(filtered_routes) < 1:
            _LOGGER.warning("No routes found")
            return None
    except WRCError as exp:
        _LOGGER.warning("Error on retrieving data: %s", exp)
        return None

    else:
        return filtered_routes


class WazeTravelTimeData:
    """WazeTravelTime Data object."""

    def __init__(
        self, region: str, client: httpx.AsyncClient, config_entry: ConfigEntry
    ) -> None:
        """Set up WazeRouteCalculator."""
        self.config_entry = config_entry
        self.client = WazeRouteCalculator(region=region, client=client)
        self.origin: str | None = None
        self.destination: str | None = None
        self.duration = None
        self.distance = None
        self.route = None

    async def async_update(self):
        """Update WazeRouteCalculator data."""
        _LOGGER.debug(
            "Getting update for origin: %s destination: %s",
            self.origin,
            self.destination,
        )
        if self.origin is not None and self.destination is not None:
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
                self.origin,
                self.destination,
                vehicle_type,
                avoid_toll_roads,
                avoid_subscription_roads,
                avoid_ferries,
                realtime,
                self.config_entry.options[CONF_UNITS],
                incl_filter,
                excl_filter,
            )
            if routes:
                route = routes[0]
            else:
                _LOGGER.warning("No routes found")
                return

            self.duration = route.duration
            self.distance = route.distance
            self.route = route.name


class WazeTravelTimeCoordinator(DataUpdateCoordinator[None]):
    """Waze Travel Time DataUpdateCoordinator."""

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
        self.config_entry = config_entry
        self.client = client
        self.origin = config_entry.data[CONF_ORIGIN]
        self.destination = config_entry.data[CONF_DESTINATION]
        self.region = config_entry.data[CONF_REGION]
        self.waze_data = WazeTravelTimeData(
            self.region,
            get_async_client(hass),
            config_entry,
        )

    async def _async_update_data(self) -> None:
        """Get the latest data from Waze."""
        self.waze_data.origin = find_coordinates(self.hass, self.origin)
        self.waze_data.destination = find_coordinates(self.hass, self.destination)

        _LOGGER.debug("Fetching Route for %s", self.config_entry.title)  # type: ignore[union-attr]
        await self.hass.data[DOMAIN][SEMAPHORE].acquire()
        try:
            await self.waze_data.async_update()
            await asyncio.sleep(SECONDS_BETWEEN_API_CALLS)
        finally:
            self.hass.data[DOMAIN][SEMAPHORE].release()
