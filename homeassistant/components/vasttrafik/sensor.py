"""Support for Västtrafik public transport."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import vasttrafik
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import now

from . import VasttrafikConfigEntry
from .const import (
    CONF_DEPARTURES,
    CONF_FROM,
    CONF_HEADING,
    CONF_KEY,
    CONF_LINES,
    CONF_SECRET,
    CONF_TRACKS,
    DEFAULT_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

# Platform schema for YAML configuration (backward compatibility)
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_KEY): cv.string,
        vol.Required(CONF_SECRET): cv.string,
        vol.Required(CONF_DEPARTURES): [
            {
                vol.Required(CONF_FROM): cv.string,
                vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.positive_int,
                vol.Optional(CONF_HEADING): cv.string,
                vol.Optional(CONF_LINES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_NAME): cv.string,
            }
        ],
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor (YAML configuration - backward compatibility)."""
    planner = vasttrafik.JournyPlanner(config.get(CONF_KEY), config.get(CONF_SECRET))
    add_entities(
        (
            VasttrafikDepartureSensor(
                planner,
                departure.get(CONF_NAME),
                departure.get(CONF_FROM),
                departure.get(CONF_HEADING),
                departure.get(CONF_LINES),
                departure.get(CONF_TRACKS, []),
                departure.get(CONF_DELAY),
                f"yaml_{departure.get(CONF_FROM)}",  # Use a YAML-specific entry ID
            )
            for departure in config[CONF_DEPARTURES]
        ),
        True,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VasttrafikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Västtrafik sensor based on a config entry."""
    planner = entry.runtime_data

    if entry.data.get("is_departure_board"):
        # This is a departure board entry - create departure sensor
        sensors = [
            VasttrafikDepartureSensor(
                planner,
                entry.data.get(CONF_NAME),
                entry.data.get(CONF_FROM),
                entry.data.get(CONF_HEADING),
                entry.data.get(CONF_LINES, []),
                entry.data.get(CONF_TRACKS, []),
                entry.data.get(CONF_DELAY, DEFAULT_DELAY),
                entry.entry_id,
            )
        ]
    else:
        # This is the main integration - create status sensor and any departure sensors from options
        sensors = [VasttrafikStatusSensor(planner, entry.title, entry.entry_id)]

        # Add departure sensors from options (for backward compatibility)
        departures = entry.options.get(CONF_DEPARTURES, [])
        for departure in departures:
            sensors.append(
                VasttrafikDepartureSensor(
                    planner,
                    departure.get(CONF_NAME),
                    departure.get(CONF_FROM),
                    departure.get(CONF_HEADING),
                    departure.get(CONF_LINES, []),
                    departure.get(CONF_TRACKS, []),
                    departure.get(CONF_DELAY, DEFAULT_DELAY),
                    f"{entry.entry_id}_{departure.get(CONF_FROM)}",
                )
            )

    async_add_entities(sensors, True)


class VasttrafikStatusSensor(SensorEntity):
    """Implementation of a Västtrafik Status Sensor to show API connectivity."""

    _attr_attribution = "Data provided by Västtrafik"
    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self, planner: vasttrafik.JournyPlanner, name: str, entry_id: str
    ) -> None:
        """Initialize the status sensor."""
        self._planner = planner
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry_id}_status"
        self._state = None

        # Create device info for the main Västtrafik service
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Västtrafik API",
            manufacturer="Västtrafik",
            model="Public Transport API",
            entry_type="service",
        )

    @property
    def native_value(self) -> str | None:
        """Return the status of the API connection."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Test the API connection."""
        try:
            # Test connection by getting location info for a common station
            await self.hass.async_add_executor_job(
                self._planner.location_name, "Centralstationen"
            )
            self._state = "Connected"
        except vasttrafik.Error:
            _LOGGER.debug("API connection failed")
            self._state = "Disconnected"
        except Exception:
            _LOGGER.exception("Unexpected error testing API connection")
            self._state = "Error"


class VasttrafikDepartureSensor(SensorEntity):
    """Implementation of a Vasttrafik Departure Sensor."""

    _attr_attribution = "Data provided by Västtrafik"
    _attr_icon = "mdi:train"

    def __init__(
        self, planner, name, departure, heading, lines, tracks, delay, entry_id
    ):
        """Initialize the sensor."""
        self._planner = planner
        self._attr_name = name if name else "Next departure"
        self._departure_name = departure
        self._heading_name = heading
        self._departure = None  # Will be resolved on first update
        self._heading = None  # Will be resolved on first update
        self._lines = lines if lines else None
        self._tracks = tracks if tracks else None
        self._delay = timedelta(minutes=delay)
        self._departureboard = None
        self._state = None
        self._attributes = None
        self._attr_unique_id = (
            f"{entry_id}_departure_{departure.lower().replace(' ', '_')}"
        )
        self._attr_has_entity_name = True

        # Create device info for this departure board
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"departure_{departure.lower().replace(' ', '_')}")},
            name=f"{departure} Departure Board",
            manufacturer="Västtrafik",
            model="Departure Board",
            entry_type="service",
        )

    def get_station_id(self, location):
        """Get the station ID."""
        if location.isdecimal():
            station_info = {"station_name": location, "station_id": location}
        else:
            station_id = self._planner.location_name(location)[0]["gid"]
            station_info = {"station_name": location, "station_id": station_id}
        return station_info

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the departure board."""
        # Resolve station IDs on first update (deferred from __init__ to avoid blocking calls)
        if self._departure is None:
            self._departure = await self.hass.async_add_executor_job(
                self.get_station_id, self._departure_name
            )
        if self._heading_name and self._heading is None:
            self._heading = await self.hass.async_add_executor_job(
                self.get_station_id, self._heading_name
            )

        try:
            self._departureboard = await self.hass.async_add_executor_job(
                self._planner.departureboard,
                self._departure["station_id"],
                now() + self._delay,
                self._heading["station_id"] if self._heading else None,
            )
        except vasttrafik.Error:
            _LOGGER.debug("Unable to read departure board")
            self._departureboard = None

        if not self._departureboard:
            _LOGGER.debug(
                "No departures from departure station %s to destination station %s",
                self._departure["station_name"],
                self._heading["station_name"] if self._heading else "ANY",
            )
            self._state = None
            self._attributes = {}
        else:
            departures_list = []
            next_departure = None
            total_departures = len(self._departureboard)

            _LOGGER.debug(
                "Processing %d departures for %s (line_filter=%s, track_filter=%s)",
                total_departures,
                self._departure["station_name"],
                self._lines,
                self._tracks,
            )

            for departure in self._departureboard:
                service_journey = departure.get("serviceJourney", {})
                line = service_journey.get("line", {})

                if departure.get("isCancelled"):
                    continue

                stop_point = departure.get("stopPoint", {})
                line_name = line.get("shortName")
                platform = stop_point.get("platform")

                # Apply line filter if specified
                line_matches = not self._lines or line_name in self._lines

                # Apply track filter if specified
                track_matches = not self._tracks or platform in self._tracks

                _LOGGER.debug(
                    "Departure: line=%s, platform=%s, line_matches=%s, track_matches=%s",
                    line_name,
                    platform,
                    line_matches,
                    track_matches,
                )

                if line_matches and track_matches:
                    # Parse departure time
                    departure_time = None
                    if "estimatedOtherwisePlannedTime" in departure:
                        try:
                            departure_time = datetime.fromisoformat(
                                departure["estimatedOtherwisePlannedTime"]
                            ).strftime("%H:%M")
                        except ValueError:
                            departure_time = departure["estimatedOtherwisePlannedTime"]

                    # Set the next departure as the sensor state (first valid one)
                    if next_departure is None:
                        next_departure = departure_time

                    # Build departure info for attributes
                    departure_info = {
                        "time": departure_time,
                        "line": line.get("shortName"),
                        "direction": service_journey.get("direction"),
                        "track": stop_point.get("platform"),
                        "accessibility": "wheelChair"
                        if line.get("isWheelchairAccessible")
                        else None,
                        "line_color": line.get("backgroundColor"),
                        "line_text_color": line.get("foregroundColor"),
                    }

                    # Add to departures list (limit to first 5 departures)
                    if len(departures_list) < 5:
                        departures_list.append(
                            {k: v for k, v in departure_info.items() if v is not None}
                        )

            # Set sensor state to next departure time
            self._state = next_departure

            _LOGGER.debug(
                "Departure board update complete: found %d matching departures, next_departure=%s",
                len(departures_list),
                next_departure,
            )

            # Set attributes with multiple departures and general info
            self._attributes = {
                "departures": departures_list,
                "station": self._departure["station_name"],
                "destination": self._heading["station_name"]
                if self._heading
                else "Any direction",
                "line_filter": self._lines if self._lines else None,
                "track_filter": self._tracks if self._tracks else None,
                "delay_minutes": self._delay.seconds // 60 % 60,
                "next_update": (now() + timedelta(seconds=120)).strftime("%H:%M:%S"),
            }

            # Remove None values
            self._attributes = {
                k: v for k, v in self._attributes.items() if v is not None
            }
