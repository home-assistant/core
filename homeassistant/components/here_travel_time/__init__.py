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
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import (
    ARRIVAL_TIME,
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_ROUTE_MODE,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEPARTURE_TIME,
    DOMAIN,
    NO_ROUTE_ERROR_MESSAGE,
    ROUTE_MODE_FASTEST,
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
    setup_options(hass, config_entry)

    arrival = (
        config_entry.options[CONF_TIME]
        if config_entry.options[CONF_TIME_TYPE] == ARRIVAL_TIME
        else None
    )
    departure = (
        config_entry.options[CONF_TIME]
        if config_entry.options[CONF_TIME_TYPE] == DEPARTURE_TIME
        else None
    )

    here_travel_time_config = HERETravelTimeConfig(
        origin=config_entry.data[CONF_ORIGIN],
        destination=config_entry.data[CONF_DESTINATION],
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
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


def setup_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up options for a config entry if not set."""
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
                CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
                CONF_TIME_TYPE: DEPARTURE_TIME,
                CONF_UNIT_SYSTEM: hass.config.units.name,
                CONF_TIME: None,
            },
        )


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

        origin = find_coordinates(self.hass, self.config.origin)
        if origin is None:
            raise InvalidCoordinatesException(
                f"Could not resolve coordinates from {self.config.origin}"
            )
        try:
            here_formatted_origin = origin.split(",")
            vol.Schema(cv.gps(here_formatted_origin))
        except (AttributeError, vol.Invalid) as ex:
            raise InvalidCoordinatesException(
                f"{origin} are not valid coordinates"
            ) from ex
        destination = find_coordinates(self.hass, self.config.destination)
        if destination is None:
            raise InvalidCoordinatesException(
                f"Could not resolve coordinates from {self.config.destination}"
            )
        try:
            here_formatted_destination = destination.split(",")
            vol.Schema(cv.gps(here_formatted_destination))
        except (vol.Invalid) as ex:
            raise InvalidCoordinatesException(
                f"{destination} are not valid coordinates"
            ) from ex
        arrival: str | None = None
        departure: str | None = None
        if self.config.arrival is not None:
            arrival = convert_time_to_isodate(self.config.arrival)
        if self.config.departure is not None:
            departure = convert_time_to_isodate(self.config.departure)

        if arrival is None and departure is None:
            departure = "now"

        return (here_formatted_origin, here_formatted_destination, arrival, departure)


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
