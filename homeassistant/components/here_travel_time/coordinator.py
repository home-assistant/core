"""The HERE Travel Time integration."""
from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

import here_routing
from here_routing import HERERoutingApi, Return, RoutingMode, Spans, TransportMode
import here_transit
from here_transit import HERETransitApi
import voluptuous as vol

from homeassistant.const import ATTR_ATTRIBUTION, UnitOfLength
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROUTE_MODE_FASTEST,
)
from .model import HERETravelTimeConfig, HERETravelTimeData

_LOGGER = logging.getLogger(__name__)


class HERERoutingDataUpdateCoordinator(DataUpdateCoordinator):
    """here_routing DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        config: HERETravelTimeConfig,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = HERERoutingApi(api_key)
        self.config = config

    async def _async_update_data(self) -> HERETravelTimeData | None:
        """Get the latest data from the HERE Routing API."""
        origin, destination, arrival, departure = prepare_parameters(
            self.hass, self.config
        )

        route_mode = (
            RoutingMode.FAST
            if self.config.route_mode == ROUTE_MODE_FASTEST
            else RoutingMode.SHORT
        )

        _LOGGER.debug(
            "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, arrival: %s, departure: %s",
            origin,
            destination,
            route_mode,
            TransportMode(self.config.travel_mode),
            arrival,
            departure,
        )

        response = await self._api.route(
            transport_mode=TransportMode(self.config.travel_mode),
            origin=here_routing.Place(origin[0], origin[1]),
            destination=here_routing.Place(destination[0], destination[1]),
            routing_mode=route_mode,
            arrival_time=arrival,
            departure_time=departure,
            return_values=[Return.POLYINE, Return.SUMMARY],
            spans=[Spans.NAMES],
        )

        _LOGGER.debug("Raw response is: %s", response)

        return self._parse_routing_response(response)

    def _parse_routing_response(self, response) -> HERETravelTimeData:
        """Parse the routing response dict to a HERETravelTimeData."""
        section: dict = response["routes"][0]["sections"][0]
        summary: dict = section["summary"]
        mapped_origin_lat: float = section["departure"]["place"]["location"]["lat"]
        mapped_origin_lon: float = section["departure"]["place"]["location"]["lng"]
        mapped_destination_lat: float = section["arrival"]["place"]["location"]["lat"]
        mapped_destination_lon: float = section["arrival"]["place"]["location"]["lng"]
        distance: float = DistanceConverter.convert(
            summary["length"], UnitOfLength.METERS, UnitOfLength.KILOMETERS
        )
        origin_name: str | None = None
        if (names := section["spans"][0].get("names")) is not None:
            origin_name = names[0]["value"]
        destination_name: str | None = None
        if (names := section["spans"][-1].get("names")) is not None:
            destination_name = names[0]["value"]
        return HERETravelTimeData(
            {
                ATTR_ATTRIBUTION: None,
                ATTR_DURATION: round(summary["baseDuration"] / 60),  # type: ignore[misc]
                ATTR_DURATION_IN_TRAFFIC: round(summary["duration"] / 60),
                ATTR_DISTANCE: distance,
                ATTR_ORIGIN: f"{mapped_origin_lat},{mapped_origin_lon}",
                ATTR_DESTINATION: f"{mapped_destination_lat},{mapped_destination_lon}",
                ATTR_ORIGIN_NAME: origin_name,
                ATTR_DESTINATION_NAME: destination_name,
            }
        )


class HERETransitDataUpdateCoordinator(DataUpdateCoordinator):
    """HERETravelTime DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        config: HERETravelTimeConfig,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = HERETransitApi(api_key)
        self.config = config

    async def _async_update_data(self) -> HERETravelTimeData | None:
        """Get the latest data from the HERE Routing API."""
        origin, destination, arrival, departure = prepare_parameters(
            self.hass, self.config
        )

        _LOGGER.debug(
            "Requesting transit route for origin: %s, destination: %s, arrival: %s, departure: %s",
            origin,
            destination,
            arrival,
            departure,
        )

        response = await self._api.route(
            origin=here_transit.Place(latitude=origin[0], longitude=origin[1]),
            destination=here_transit.Place(
                latitude=destination[0], longitude=destination[1]
            ),
            arrival_time=arrival,
            departure_time=departure,
            return_values=[
                here_transit.Return.POLYLINE,
                here_transit.Return.TRAVEL_SUMMARY,
            ],
        )

        _LOGGER.debug("Raw response is: %s", response)

        return self._parse_transit_response(response)

    def _parse_transit_response(self, response) -> HERETravelTimeData:
        """Parse the transit response dict to a HERETravelTimeData."""
        sections: dict = response["routes"][0]["sections"]
        attribution: str | None = build_hass_attribution(sections)
        mapped_origin_lat: float = sections[0]["departure"]["place"]["location"]["lat"]
        mapped_origin_lon: float = sections[0]["departure"]["place"]["location"]["lng"]
        mapped_destination_lat: float = sections[-1]["arrival"]["place"]["location"][
            "lat"
        ]
        mapped_destination_lon: float = sections[-1]["arrival"]["place"]["location"][
            "lng"
        ]
        distance: float = DistanceConverter.convert(
            sum(section["travelSummary"]["length"] for section in sections),
            UnitOfLength.METERS,
            UnitOfLength.KILOMETERS,
        )
        duration: float = sum(
            section["travelSummary"]["duration"] for section in sections
        )
        return HERETravelTimeData(
            {
                ATTR_ATTRIBUTION: attribution,
                ATTR_DURATION: round(duration / 60),  # type: ignore[misc]
                ATTR_DURATION_IN_TRAFFIC: round(duration / 60),
                ATTR_DISTANCE: distance,
                ATTR_ORIGIN: f"{mapped_origin_lat},{mapped_origin_lon}",
                ATTR_DESTINATION: f"{mapped_destination_lat},{mapped_destination_lon}",
                ATTR_ORIGIN_NAME: sections[0]["departure"]["place"].get("name"),
                ATTR_DESTINATION_NAME: sections[-1]["arrival"]["place"].get("name"),
            }
        )


def prepare_parameters(
    hass: HomeAssistant,
    config: HERETravelTimeConfig,
) -> tuple[list[str], list[str], str | None, str | None]:
    """Prepare parameters for the HERE api."""

    def _from_entity_id(entity_id: str) -> list[str]:
        coordinates = find_coordinates(hass, entity_id)
        if coordinates is None:
            raise UpdateFailed(f"No coordinates found for {entity_id}")
        if coordinates is entity_id:
            raise UpdateFailed(f"Could not find entity {entity_id}")
        try:
            formatted_coordinates = coordinates.split(",")
            vol.Schema(cv.gps(formatted_coordinates))
        except (AttributeError, vol.ExactSequenceInvalid) as ex:
            raise UpdateFailed(
                f"{entity_id} does not have valid coordinates: {coordinates}"
            ) from ex
        return formatted_coordinates

    # Destination
    if config.destination_entity_id is not None:
        destination = _from_entity_id(config.destination_entity_id)
    else:
        destination = [
            str(config.destination_latitude),
            str(config.destination_longitude),
        ]

    # Origin
    if config.origin_entity_id is not None:
        origin = _from_entity_id(config.origin_entity_id)
    else:
        origin = [
            str(config.origin_latitude),
            str(config.origin_longitude),
        ]

    # Arrival/Departure
    arrival: str | None = None
    departure: str | None = None
    if config.arrival is not None:
        arrival = next_datetime(config.arrival).isoformat()
    if config.departure is not None:
        departure = next_datetime(config.departure).isoformat()

    return (origin, destination, arrival, departure)


def build_hass_attribution(sections: dict) -> str | None:
    """Build a hass frontend ready string out of the attributions."""
    relevant_attributions = []
    for section in sections:
        if (attributions := section.get("attributions")) is not None:
            for attribution in attributions:
                if (href := attribution.get("href")) is not None:
                    relevant_attributions.append(f"{href}")
                if (text := attribution.get("text")) is not None:
                    relevant_attributions.append(text)
    if len(relevant_attributions) > 0:
        return ",".join(relevant_attributions)
    return None


def next_datetime(simple_time: time) -> datetime:
    """Take a time like 08:00:00 and combine it with the current date."""
    combined = datetime.combine(dt.start_of_local_day(), simple_time)
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return combined
