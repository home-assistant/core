"""The HERE Travel Time integration."""
from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

import async_timeout
from herepy import NoRouteFoundError, RouteMode, RoutingApi, RoutingResponse

from homeassistant.const import ATTR_ATTRIBUTION, CONF_UNIT_SYSTEM_IMPERIAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NO_ROUTE_ERROR_MESSAGE,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODES_VEHICLE,
    HERERoutingData,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


class HERETravelTimeData:
    """HERETravelTime data object."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: RoutingApi,
        origin: str | None,
        destination: str | None,
        origin_entity_id: str | None,
        destination_entity_id: str | None,
        travel_mode: str,
        route_mode: str,
        units: str,
        arrival: datetime,
        departure: datetime,
    ) -> None:
        """Initialize."""
        self._hass = hass
        self._api = api
        self.coordinator: DataUpdateCoordinator[HERERoutingData | None] | None = None
        self.origin = origin
        self.origin_entity_id = origin_entity_id
        self.destination = destination
        self.destination_entity_id = destination_entity_id
        self.travel_mode = travel_mode
        self.route_mode = route_mode
        self.arrival = arrival
        self.departure = departure
        self.units = units

    async def async_update(self) -> HERERoutingData | None:
        """Get the latest data from the HERE Routing API."""
        try:
            async with async_timeout.timeout(10):
                return await self._hass.async_add_executor_job(self._update)
        except NoRouteFoundError as error:
            raise UpdateFailed(NO_ROUTE_ERROR_MESSAGE) from error

    async def async_setup(self) -> None:
        """Set up the HERETravelTime integration."""
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        await self.coordinator.async_config_entry_first_refresh()

    def _update(self) -> HERERoutingData | None:
        """Get the latest data from the HERE Routing API."""
        if self.origin_entity_id is not None:
            self.origin = find_coordinates(self._hass, self.origin_entity_id)

        if self.destination_entity_id is not None:
            self.destination = find_coordinates(self._hass, self.destination_entity_id)
        if self.destination is not None and self.origin is not None:
            # Convert location to HERE friendly location
            destination = self.destination.split(",")
            origin = self.origin.split(",")
            arrival: str | None = None
            departure: str | None = "now"
            if (arrival := self.arrival) is not None:
                arrival = convert_time_to_isodate(arrival)
            if (departure := self.departure) is not None:
                departure = convert_time_to_isodate(departure)

            if departure is None and arrival is None:
                departure = "now"

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s, arrival: %s, departure: %s",
                origin,
                destination,
                RouteMode[self.route_mode],
                RouteMode[self.travel_mode],
                RouteMode[TRAFFIC_MODE_ENABLED],
                arrival,
                departure,
            )

            response: RoutingResponse = self._api.public_transport_timetable(
                origin,
                destination,
                True,
                [
                    RouteMode[self.route_mode],
                    RouteMode[self.travel_mode],
                    RouteMode[TRAFFIC_MODE_ENABLED],
                ],
                arrival=arrival,
                departure=departure,
            )

            _LOGGER.debug(
                "Raw response is: %s", response.response  # pylint: disable=no-member
            )

            source_attribution = response.response.get(  # pylint: disable=no-member
                "sourceAttribution"
            )
            attribution: str | None = None
            if source_attribution is not None:
                attribution = build_hass_attribution(source_attribution)
            route: list = response.response["route"]  # pylint: disable=no-member
            summary: dict = route[0]["summary"]
            waypoint: list = route[0]["waypoint"]
            distance: float = summary["distance"]
            traffic_time: float = summary["baseTime"]
            if self.travel_mode in TRAVEL_MODES_VEHICLE:
                traffic_time = summary["trafficTime"]
            if self.units == CONF_UNIT_SYSTEM_IMPERIAL:
                # Convert to miles.
                distance = distance / 1609.344
            else:
                # Convert to kilometers
                distance = distance / 1000
            return {
                ATTR_ATTRIBUTION: attribution,
                ATTR_DURATION: summary["baseTime"] / 60,
                ATTR_DURATION_IN_TRAFFIC: traffic_time / 60,
                ATTR_DISTANCE: distance,
                ATTR_ROUTE: response.route_short,
                ATTR_ORIGIN: ",".join(origin),
                ATTR_DESTINATION: ",".join(destination),
                ATTR_ORIGIN_NAME: waypoint[0]["mappedRoadName"],
                ATTR_DESTINATION_NAME: waypoint[1]["mappedRoadName"],
            }
        return None


def build_hass_attribution(source_attribution: dict) -> str | None:
    """Build a hass frontend ready string out of the sourceAttribution."""
    if (suppliers := source_attribution.get("supplier")) is not None:
        supplier_titles = []
        for supplier in suppliers:
            if (title := supplier.get("title")) is not None:
                supplier_titles.append(title)
        joined_supplier_titles = ",".join(supplier_titles)
        attribution = f"With the support of {joined_supplier_titles}. All information is provided without warranty of any kind."
        return attribution
    return None


def convert_time_to_isodate(simple_time: time) -> str:
    """Take a time like 08:00:00 and combine it with the current date."""
    combined = datetime.combine(dt.start_of_local_day(), simple_time)
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return combined.isoformat()
