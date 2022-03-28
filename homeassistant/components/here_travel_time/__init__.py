"""The HERE Travel Time integration."""
from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

import async_timeout
from herepy import NoRouteFoundError, RouteMode, RoutingApi, RoutingResponse

from homeassistant.const import ATTR_ATTRIBUTION, CONF_UNIT_SYSTEM_IMPERIAL, Platform
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
)
from .model import HERERoutingData, HERETravelTimeConfig

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class HereTravelTimeDataUpdateCoordinator(DataUpdateCoordinator):
    """HERETravelTime DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: RoutingApi,
        config: HERETravelTimeConfig,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = api
        self.config = config

    async def _async_update_data(self) -> HERERoutingData | None:
        """Get the latest data from the HERE Routing API."""
        try:
            async with async_timeout.timeout(10):
                return await self.hass.async_add_executor_job(self._update)
        except NoRouteFoundError as error:
            raise UpdateFailed(NO_ROUTE_ERROR_MESSAGE) from error

    def _update(self) -> HERERoutingData | None:
        """Get the latest data from the HERE Routing API."""
        if self.config.origin_entity_id is not None:
            origin = find_coordinates(self.hass, self.config.origin_entity_id)
        else:
            origin = self.config.origin

        if self.config.destination_entity_id is not None:
            destination = find_coordinates(self.hass, self.config.destination_entity_id)
        else:
            destination = self.config.destination
        if destination is not None and origin is not None:
            here_formatted_destination = destination.split(",")
            here_formatted_origin = origin.split(",")
            arrival: str | None = None
            departure: str | None = None
            if self.config.arrival is not None:
                arrival = convert_time_to_isodate(self.config.arrival)
            if self.config.departure is not None:
                departure = convert_time_to_isodate(self.config.departure)

            if arrival is None and departure is None:
                departure = "now"

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s, arrival: %s, departure: %s",
                here_formatted_origin,
                here_formatted_destination,
                RouteMode[self.config.route_mode],
                RouteMode[self.config.travel_mode],
                RouteMode[TRAFFIC_MODE_ENABLED],
                arrival,
                departure,
            )

            response: RoutingResponse = self._api.public_transport_timetable(
                here_formatted_origin,
                here_formatted_destination,
                True,
                [
                    RouteMode[self.config.route_mode],
                    RouteMode[self.config.travel_mode],
                    RouteMode[TRAFFIC_MODE_ENABLED],
                ],
                arrival=arrival,
                departure=departure,
            )

            _LOGGER.debug("Raw response is: %s", response.response)

            attribution: str | None = None
            if "sourceAttribution" in response.response:
                attribution = build_hass_attribution(
                    response.response.get("sourceAttribution")
                )
            route: list = response.response["route"]
            summary: dict = route[0]["summary"]
            waypoint: list = route[0]["waypoint"]
            distance: float = summary["distance"]
            traffic_time: float = summary["baseTime"]
            if self.config.travel_mode in TRAVEL_MODES_VEHICLE:
                traffic_time = summary["trafficTime"]
            if self.config.units == CONF_UNIT_SYSTEM_IMPERIAL:
                # Convert to miles.
                distance = distance / 1609.344
            else:
                # Convert to kilometers
                distance = distance / 1000
            return HERERoutingData(
                {
                    ATTR_ATTRIBUTION: attribution,
                    ATTR_DURATION: summary["baseTime"] / 60,  # type: ignore[misc]
                    ATTR_DURATION_IN_TRAFFIC: traffic_time / 60,
                    ATTR_DISTANCE: distance,
                    ATTR_ROUTE: response.route_short,
                    ATTR_ORIGIN: ",".join(here_formatted_origin),
                    ATTR_DESTINATION: ",".join(here_formatted_destination),
                    ATTR_ORIGIN_NAME: waypoint[0]["mappedRoadName"],
                    ATTR_DESTINATION_NAME: waypoint[1]["mappedRoadName"],
                }
            )
        return None


def build_hass_attribution(source_attribution: dict) -> str | None:
    """Build a hass frontend ready string out of the sourceAttribution."""
    if (suppliers := source_attribution.get("supplier")) is not None:
        supplier_titles = []
        for supplier in suppliers:
            if (title := supplier.get("title")) is not None:
                supplier_titles.append(title)
        joined_supplier_titles = ",".join(supplier_titles)
        return f"With the support of {joined_supplier_titles}. All information is provided without warranty of any kind."
    return None


def convert_time_to_isodate(simple_time: time) -> str:
    """Take a time like 08:00:00 and combine it with the current date."""
    combined = datetime.combine(dt.start_of_local_day(), simple_time)
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return combined.isoformat()
