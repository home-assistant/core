"""The HERE Travel Time integration."""
from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

import async_timeout
from herepy import NoRouteFoundError, RouteMode, RoutingApi, RoutingResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_MODE,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_METERS,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NO_ROUTE_ERROR_MESSAGE,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODES_VEHICLE,
)
from .model import HERERoutingData, HERETravelTimeConfig

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HERE Travel Time from a config entry."""
    api_key = config_entry.data[CONF_API_KEY]
    here_client = RoutingApi(api_key)

    arrival = (
        dt.parse_time(config_entry.options[CONF_ARRIVAL_TIME])
        if config_entry.options[CONF_ARRIVAL_TIME] is not None
        else None
    )
    departure = (
        dt.parse_time(config_entry.options[CONF_DEPARTURE_TIME])
        if config_entry.options[CONF_DEPARTURE_TIME] is not None
        else None
    )

    here_travel_time_config = HERETravelTimeConfig(
        destination_latitude=config_entry.data.get(CONF_DESTINATION_LATITUDE),
        destination_longitude=config_entry.data.get(CONF_DESTINATION_LONGITUDE),
        destination_entity_id=config_entry.data.get(CONF_DESTINATION_ENTITY_ID),
        origin_latitude=config_entry.data.get(CONF_ORIGIN_LATITUDE),
        origin_longitude=config_entry.data.get(CONF_ORIGIN_LONGITUDE),
        origin_entity_id=config_entry.data.get(CONF_ORIGIN_ENTITY_ID),
        travel_mode=config_entry.data[CONF_MODE],
        route_mode=config_entry.options[CONF_ROUTE_MODE],
        units=config_entry.options[CONF_UNIT_SYSTEM],
        arrival=arrival,
        departure=departure,
    )

    coordinator = HereTravelTimeDataUpdateCoordinator(
        hass,
        here_client,
        here_travel_time_config,
    )
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


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
        try:
            origin, destination, arrival, departure = self._prepare_parameters()

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s, arrival: %s, departure: %s",
                origin,
                destination,
                RouteMode[self.config.route_mode],
                RouteMode[self.config.travel_mode],
                RouteMode[TRAFFIC_MODE_ENABLED],
                arrival,
                departure,
            )

            response: RoutingResponse = self._api.public_transport_timetable(
                origin,
                destination,
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
                distance = IMPERIAL_SYSTEM.length(distance, LENGTH_METERS)
            else:
                # Convert to kilometers
                distance = distance / 1000
            return HERERoutingData(
                {
                    ATTR_ATTRIBUTION: attribution,
                    ATTR_DURATION: round(summary["baseTime"] / 60),  # type: ignore[misc]
                    ATTR_DURATION_IN_TRAFFIC: round(traffic_time / 60),
                    ATTR_DISTANCE: distance,
                    ATTR_ROUTE: response.route_short,
                    ATTR_ORIGIN: ",".join(origin),
                    ATTR_DESTINATION: ",".join(destination),
                    ATTR_ORIGIN_NAME: waypoint[0]["mappedRoadName"],
                    ATTR_DESTINATION_NAME: waypoint[1]["mappedRoadName"],
                }
            )
        except InvalidCoordinatesException as ex:
            _LOGGER.error("Could not call HERE api: %s", ex)
        return None

    def _prepare_parameters(
        self,
    ) -> tuple[list[str], list[str], str | None, str | None]:
        """Prepare parameters for the HERE api."""

        def _from_entity_id(entity_id: str) -> list[str]:
            coordinates = find_coordinates(self.hass, entity_id)
            if coordinates is None:
                raise InvalidCoordinatesException(
                    f"No coordinatnes found for {entity_id}"
                )
            try:
                here_formatted_coordinates = coordinates.split(",")
                vol.Schema(cv.gps(here_formatted_coordinates))
            except (AttributeError, vol.Invalid) as ex:
                raise InvalidCoordinatesException(
                    f"{coordinates} are not valid coordinates"
                ) from ex
            return here_formatted_coordinates

        # Destination
        if self.config.destination_entity_id is not None:
            destination = _from_entity_id(self.config.destination_entity_id)
        else:
            destination = [
                str(self.config.destination_latitude),
                str(self.config.destination_longitude),
            ]

        # Origin
        if self.config.origin_entity_id is not None:
            origin = _from_entity_id(self.config.origin_entity_id)
        else:
            origin = [
                str(self.config.origin_latitude),
                str(self.config.origin_longitude),
            ]

        # Arrival/Departure
        arrival: str | None = None
        departure: str | None = None
        if self.config.arrival is not None:
            arrival = convert_time_to_isodate(self.config.arrival)
        if self.config.departure is not None:
            departure = convert_time_to_isodate(self.config.departure)

        if arrival is None and departure is None:
            departure = "now"

        return (origin, destination, arrival, departure)


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


class InvalidCoordinatesException(Exception):
    """Coordinates for origin or destination are malformed."""
