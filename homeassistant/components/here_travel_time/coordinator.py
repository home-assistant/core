"""The HERE Travel Time integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging
from typing import Any

import here_routing
from here_routing import (
    HERERoutingApi,
    HERERoutingTooManyRequestsError,
    Return,
    RoutingMode,
    Spans,
    TrafficMode,
    TransportMode,
)
import here_transit
from here_transit import (
    HERETransitApi,
    HERETransitConnectionError,
    HERETransitDepartureArrivalTooCloseError,
    HERETransitNoRouteFoundError,
    HERETransitTooManyRequestsError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROUTE_MODE_FASTEST,
)
from .model import HERETravelTimeAPIParams, HERETravelTimeData

BACKOFF_MULTIPLIER = 1.1

_LOGGER = logging.getLogger(__name__)

type HereConfigEntry = ConfigEntry[
    HERETransitDataUpdateCoordinator | HERERoutingDataUpdateCoordinator
]


class HERERoutingDataUpdateCoordinator(DataUpdateCoordinator[HERETravelTimeData]):
    """HERETravelTime DataUpdateCoordinator for the routing API."""

    config_entry: HereConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HereConfigEntry,
        api_key: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = HERERoutingApi(api_key)

    async def _async_update_data(self) -> HERETravelTimeData:
        """Get the latest data from the HERE Routing API."""
        params = prepare_parameters(self.hass, self.config_entry)

        _LOGGER.debug(
            (
                "Requesting route for origin: %s, destination: %s, route_mode: %s,"
                " mode: %s, arrival: %s, departure: %s, traffic_mode: %s"
            ),
            params.origin,
            params.destination,
            params.route_mode,
            TransportMode(params.travel_mode),
            params.arrival,
            params.departure,
            params.traffic_mode,
        )

        try:
            response = await self._api.route(
                transport_mode=TransportMode(params.travel_mode),
                origin=here_routing.Place(
                    float(params.origin[0]), float(params.origin[1])
                ),
                destination=here_routing.Place(
                    float(params.destination[0]), float(params.destination[1])
                ),
                routing_mode=params.route_mode,
                arrival_time=params.arrival,
                departure_time=params.departure,
                traffic_mode=params.traffic_mode,
                return_values=[Return.POLYINE, Return.SUMMARY],
                spans=[Spans.NAMES],
            )
        except HERERoutingTooManyRequestsError as error:
            assert self.update_interval is not None
            _LOGGER.debug(
                "Rate limit has been reached. Increasing update interval to %s",
                self.update_interval.total_seconds() * BACKOFF_MULTIPLIER,
            )
            self.update_interval = timedelta(
                seconds=self.update_interval.total_seconds() * BACKOFF_MULTIPLIER
            )
            raise UpdateFailed("Rate limit has been reached") from error
        _LOGGER.debug("Raw response is: %s", response)

        if self.update_interval != timedelta(seconds=DEFAULT_SCAN_INTERVAL):
            _LOGGER.debug(
                "Resetting update interval to %s",
                DEFAULT_SCAN_INTERVAL,
            )
            self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        return self._parse_routing_response(response)

    def _parse_routing_response(self, response: dict[str, Any]) -> HERETravelTimeData:
        """Parse the routing response dict to a HERETravelTimeData."""
        distance: float = 0.0
        duration: int = 0
        duration_in_traffic: int = 0

        for section in response["routes"][0]["sections"]:
            distance += DistanceConverter.convert(
                section["summary"]["length"],
                UnitOfLength.METERS,
                UnitOfLength.KILOMETERS,
            )
            duration += section["summary"]["baseDuration"]
            duration_in_traffic += section["summary"]["duration"]

        first_section = response["routes"][0]["sections"][0]
        last_section = response["routes"][0]["sections"][-1]
        mapped_origin_lat: float = first_section["departure"]["place"]["location"][
            "lat"
        ]
        mapped_origin_lon: float = first_section["departure"]["place"]["location"][
            "lng"
        ]
        mapped_destination_lat: float = last_section["arrival"]["place"]["location"][
            "lat"
        ]
        mapped_destination_lon: float = last_section["arrival"]["place"]["location"][
            "lng"
        ]
        origin_name: str | None = None
        if (names := first_section["spans"][0].get("names")) is not None:
            origin_name = names[0]["value"]
        destination_name: str | None = None
        if (names := last_section["spans"][-1].get("names")) is not None:
            destination_name = names[0]["value"]
        return HERETravelTimeData(
            attribution=None,
            duration=duration,
            duration_in_traffic=duration_in_traffic,
            distance=distance,
            origin=f"{mapped_origin_lat},{mapped_origin_lon}",
            destination=f"{mapped_destination_lat},{mapped_destination_lon}",
            origin_name=origin_name,
            destination_name=destination_name,
        )


class HERETransitDataUpdateCoordinator(
    DataUpdateCoordinator[HERETravelTimeData | None]
):
    """HERETravelTime DataUpdateCoordinator for the transit API."""

    config_entry: HereConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HereConfigEntry,
        api_key: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._api = HERETransitApi(api_key)

    async def _async_update_data(self) -> HERETravelTimeData | None:
        """Get the latest data from the HERE Routing API."""
        params = prepare_parameters(self.hass, self.config_entry)

        _LOGGER.debug(
            (
                "Requesting transit route for origin: %s, destination: %s, arrival: %s,"
                " departure: %s"
            ),
            params.origin,
            params.destination,
            params.arrival,
            params.departure,
        )
        try:
            response = await self._api.route(
                origin=here_transit.Place(
                    latitude=params.origin[0], longitude=params.origin[1]
                ),
                destination=here_transit.Place(
                    latitude=params.destination[0], longitude=params.destination[1]
                ),
                arrival_time=params.arrival,
                departure_time=params.departure,
                return_values=[
                    here_transit.Return.POLYLINE,
                    here_transit.Return.TRAVEL_SUMMARY,
                ],
            )
        except HERETransitTooManyRequestsError as error:
            assert self.update_interval is not None
            _LOGGER.debug(
                "Rate limit has been reached. Increasing update interval to %s",
                self.update_interval.total_seconds() * BACKOFF_MULTIPLIER,
            )
            self.update_interval = timedelta(
                seconds=self.update_interval.total_seconds() * BACKOFF_MULTIPLIER
            )
            raise UpdateFailed("Rate limit has been reached") from error
        except HERETransitDepartureArrivalTooCloseError:
            _LOGGER.debug("Ignoring HERETransitDepartureArrivalTooCloseError")
            return None
        except (HERETransitConnectionError, HERETransitNoRouteFoundError) as error:
            raise UpdateFailed from error

        _LOGGER.debug("Raw response is: %s", response)
        if self.update_interval != timedelta(seconds=DEFAULT_SCAN_INTERVAL):
            _LOGGER.debug(
                "Resetting update interval to %s",
                DEFAULT_SCAN_INTERVAL,
            )
            self.update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        return self._parse_transit_response(response)

    def _parse_transit_response(self, response: dict[str, Any]) -> HERETravelTimeData:
        """Parse the transit response dict to a HERETravelTimeData."""
        sections: list[dict[str, Any]] = response["routes"][0]["sections"]
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
        duration: int = sum(
            section["travelSummary"]["duration"] for section in sections
        )
        return HERETravelTimeData(
            attribution=attribution,
            duration=duration,
            duration_in_traffic=duration,
            distance=distance,
            origin=f"{mapped_origin_lat},{mapped_origin_lon}",
            destination=f"{mapped_destination_lat},{mapped_destination_lon}",
            origin_name=sections[0]["departure"]["place"].get("name"),
            destination_name=sections[-1]["arrival"]["place"].get("name"),
        )


def prepare_parameters(
    hass: HomeAssistant,
    config_entry: HereConfigEntry,
) -> HERETravelTimeAPIParams:
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
    if (
        destination_entity_id := config_entry.data.get(CONF_DESTINATION_ENTITY_ID)
    ) is not None:
        destination = _from_entity_id(str(destination_entity_id))
    else:
        destination = [
            str(config_entry.data[CONF_DESTINATION_LATITUDE]),
            str(config_entry.data[CONF_DESTINATION_LONGITUDE]),
        ]

    # Origin
    if (origin_entity_id := config_entry.data.get(CONF_ORIGIN_ENTITY_ID)) is not None:
        origin = _from_entity_id(str(origin_entity_id))
    else:
        origin = [
            str(config_entry.data[CONF_ORIGIN_LATITUDE]),
            str(config_entry.data[CONF_ORIGIN_LONGITUDE]),
        ]

    # Arrival/Departure
    arrival: datetime | None = None
    if (
        conf_arrival := dt_util.parse_time(
            config_entry.options.get(CONF_ARRIVAL_TIME, "")
        )
    ) is not None:
        arrival = next_datetime(conf_arrival)
    departure: datetime | None = None
    if (
        conf_departure := dt_util.parse_time(
            config_entry.options.get(CONF_DEPARTURE_TIME, "")
        )
    ) is not None:
        departure = next_datetime(conf_departure)

    route_mode = (
        RoutingMode.FAST
        if config_entry.options[CONF_ROUTE_MODE] == ROUTE_MODE_FASTEST
        else RoutingMode.SHORT
    )
    traffic_mode = (
        TrafficMode.DISABLED
        if config_entry.options[CONF_TRAFFIC_MODE] is False
        else TrafficMode.DEFAULT
    )

    return HERETravelTimeAPIParams(
        destination=destination,
        origin=origin,
        travel_mode=config_entry.data[CONF_MODE],
        route_mode=route_mode,
        arrival=arrival,
        departure=departure,
        traffic_mode=traffic_mode,
    )


def build_hass_attribution(sections: list[dict[str, Any]]) -> str | None:
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
    combined = datetime.combine(dt_util.start_of_local_day(), simple_time)
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return combined
