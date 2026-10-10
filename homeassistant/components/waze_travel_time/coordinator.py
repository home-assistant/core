"""The Waze Travel Time data coordinator."""

import asyncio
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import timedelta
import logging
from math import ceil, floor
from typing import Literal, override

import httpx
from pywaze.route_calculator import CalcRoutesResponse, WazeRouteCalculator, WRCError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.unit_conversion import DistanceConverter

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
    DOMAIN,
    IMPERIAL_UNITS,
    MIN_UPDATE_INTERVAL_MINUTES,
    ROUTING_QUOTA_RESERVE,
    ROUTING_QUOTA_WINDOW_MINUTES,
    ROUTING_REQUEST_QUOTA,
    SEMAPHORE_KEY,
)
from .helpers import base_coordinates_to_tuple

_LOGGER = logging.getLogger(__name__)

POLLING_COORDINATORS: HassKey[set[WazeTravelTimeCoordinator]] = HassKey(
    f"{DOMAIN}_polling_coordinators"
)

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
    time_delta: int = 0,
    base_coordinates: tuple[float, float] | None = None,
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
            time_delta=time_delta,
            base_coords=base_coordinates,
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
                    "Excluding route [%s], because no"
                    " inclusive filter matched any streetname",
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
                            "Excluding route, because"
                            " exclusive filter [%s]"
                            " matched streetname: %s",
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
    except httpx.RequestError as exp:
        raise UpdateFailed(f"Connection error: {exp}") from exp

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
            update_interval=timedelta(minutes=MIN_UPDATE_INTERVAL_MINUTES),
        )
        self.client = client
        self._origin = config_entry.data[CONF_ORIGIN]
        self._destination = config_entry.data[CONF_DESTINATION]

    @callback
    @override
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: object = None
    ) -> Callable[[], None]:
        """Update intervals when this coordinator starts calling the API."""
        remove_listener = super().async_add_listener(update_callback, context)
        if not self.config_entry.pref_disable_polling:
            coordinators = self.hass.data.setdefault(POLLING_COORDINATORS, set())
            if self not in coordinators:
                coordinators.add(self)
                self._async_update_intervals()
        return remove_listener

    @callback
    @override
    def _unschedule_refresh(self) -> None:
        """Update intervals when this coordinator stops calling the API."""
        super()._unschedule_refresh()
        self._async_remove_polling_coordinator()

    @override
    async def async_shutdown(self) -> None:
        """Update intervals when the config_entry is unloaded or setup fails."""
        await super().async_shutdown()
        self._async_remove_polling_coordinator()

    @callback
    def _async_remove_polling_coordinator(self) -> None:
        """Remove this coordinator from the interval calculation."""
        if coordinators := self.hass.data.get(POLLING_COORDINATORS):
            coordinators.discard(self)
            self._async_update_intervals()

    @callback
    def _async_update_intervals(self) -> None:
        """Apply the shared routing budget to all automatically polled routes.

        Automatic polling reserves 10% of an empirically observed routing quota per
        public IP. Each route update makes one routing request, including alternatives.
        Manual refreshes, get_travel_times service calls, startup requests, and other
        consumers sharing the public IP can still exhaust the quota. Dynamic intervals
        are preventive and do not guarantee protection against 429 responses.
        """
        coordinators = self.hass.data[POLLING_COORDINATORS]
        request_budget = ROUTING_REQUEST_QUOTA * (1 - ROUTING_QUOTA_RESERVE)
        if len(coordinators) > request_budget:
            async_create_issue(
                self.hass,
                DOMAIN,
                "too_many_polling_routes",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="too_many_polling_routes",
                translation_placeholders={"max_routes": str(floor(request_budget))},
                learn_more_url="https://www.home-assistant.io/integrations/waze_travel_time/#defining-a-custom-polling-interval",
            )
        else:
            async_delete_issue(self.hass, DOMAIN, "too_many_polling_routes")

        if not coordinators:
            return

        polling_rounds = floor(request_budget / len(coordinators))
        if polling_rounds > 0:
            # Keep another round beyond the window boundary, allowing for timer rounding.
            minutes = floor(ROUTING_QUOTA_WINDOW_MINUTES / polling_rounds) + 1
        else:
            minutes = ceil(
                ROUTING_QUOTA_WINDOW_MINUTES * len(coordinators) / request_budget
            )
        interval = timedelta(minutes=max(MIN_UPDATE_INTERVAL_MINUTES, minutes))
        for coordinator in coordinators:
            if coordinator.update_interval != interval:
                coordinator.update_interval = interval
                coordinator._schedule_refresh()  # noqa: SLF001

    @override
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
        await self.hass.data[SEMAPHORE_KEY].acquire()
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
            time_delta = int(
                timedelta(**self.config_entry.options[CONF_TIME_DELTA]).total_seconds()
                / 60
            )
            base_coordinates = base_coordinates_to_tuple(
                self.config_entry.options.get(CONF_BASE_COORDINATES)
            )

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
                time_delta,
                base_coordinates,
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
            self.hass.data[SEMAPHORE_KEY].release()

        return travel_data
