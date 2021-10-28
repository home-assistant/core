"""The HERE Travel Time integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

import async_timeout
from herepy import NoRouteFoundError, RouteMode, RoutingApi, RoutingResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MODE,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import (
    ARRIVAL_TIME,
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
    TRACKABLE_DOMAINS,
    TRAFFIC_MODE_ENABLED,
    HERERoutingData,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HERE Travel Time from a config entry."""
    here_data = HERETravelTimeData(hass, config_entry)
    await here_data.async_setup()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = here_data
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class HERETravelTimeData:
    """HERETravelTime data object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._hass = hass
        self._config_entry = config_entry
        self._api = RoutingApi(config_entry.data[CONF_API_KEY])
        self.coordinator: DataUpdateCoordinator[HERERoutingData | None] | None = None

    async def async_update(self) -> HERERoutingData | None:
        """Get the latest data from the HERE Routing API."""
        try:
            async with async_timeout.timeout(10):
                return await self._hass.async_add_executor_job(self._update)
        except NoRouteFoundError as error:
            raise UpdateFailed(NO_ROUTE_ERROR_MESSAGE) from error

    async def async_setup(self) -> None:
        """Set up the HERETravelTime integration."""
        if not self._config_entry.options:
            options = {
                CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
                CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
                CONF_TIME_TYPE: DEPARTURE_TIME,
                CONF_UNIT_SYSTEM: self._hass.config.units.name,
                CONF_TIME: "now",
            }
            self._hass.config_entries.async_update_entry(
                self._config_entry, options=options
            )
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
        if (destination := self._config_entry.data[CONF_DESTINATION]).split(".", 1)[
            0
        ] in TRACKABLE_DOMAINS:
            destination = find_coordinates(self._hass, destination)

        if (origin := self._config_entry.data[CONF_ORIGIN]).split(".", 1)[
            0
        ] in TRACKABLE_DOMAINS:
            origin = find_coordinates(self._hass, origin)

        if destination is not None and origin is not None:
            # Convert location to HERE friendly location
            destination = destination.split(",")
            origin = origin.split(",")
            arrival: str | None = None
            departure: str | None = "now"
            if self._config_entry.options[CONF_TIME_TYPE] == ARRIVAL_TIME:
                if (conf_arrival := self._config_entry.options[CONF_TIME]) != "":
                    arrival = convert_time_to_isodate(conf_arrival)
                    if arrival is None:
                        arrival = ""
                        _LOGGER.warning(
                            "Supplied arrival time could not be parsed. It was ignored"
                        )
            if self._config_entry.options[CONF_TIME_TYPE] == DEPARTURE_TIME:
                if (conf_departure := self._config_entry.options[CONF_TIME]) not in [
                    "",
                    "now",
                ]:
                    departure = convert_time_to_isodate(conf_departure)
                    if departure is None:
                        departure = "now"
                        _LOGGER.warning(
                            "Supplied departure time could not be parsed. It was ignored"
                        )

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s, arrival: %s, departure: %s",
                origin,
                destination,
                RouteMode[self._config_entry.options[CONF_ROUTE_MODE]],
                RouteMode[self._config_entry.data[CONF_MODE]],
                RouteMode[TRAFFIC_MODE_ENABLED],
                arrival,
                departure,
            )

            response: RoutingResponse = self._api.public_transport_timetable(
                origin,
                destination,
                True,
                [
                    RouteMode[self._config_entry.options[CONF_ROUTE_MODE]],
                    RouteMode[self._config_entry.data[CONF_MODE]],
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
            if (
                self._config_entry.options[CONF_UNIT_SYSTEM]
                == CONF_UNIT_SYSTEM_IMPERIAL
            ):
                # Convert to miles.
                distance = distance / 1609.344
            else:
                # Convert to kilometers
                distance = distance / 1000
            return {
                "attribution": attribution,
                "base_time": summary["baseTime"],
                "traffic_time": summary["trafficTime"],
                "distance": distance,
                "route": response.route_short,
                "origin": ",".join(origin),
                "destination": ",".join(destination),
                "origin_name": waypoint[0]["mappedRoadName"],
                "destination_name": waypoint[1]["mappedRoadName"],
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


def convert_time_to_isodate(timestr: str) -> str | None:
    """Take a string like 08:00:00 and combine it with the current date."""
    if (parsed_time := dt.parse_time(timestr)) is None:
        return None
    if (
        combined := datetime.combine(dt.start_of_local_day(), parsed_time)
    ) < datetime.now():
        combined = combined + timedelta(days=1)
    return combined.isoformat()
