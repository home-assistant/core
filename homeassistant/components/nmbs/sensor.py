"""Get ride details and liveboard details for NMBS (Belgian railway)."""
import logging

from pyrail import iRail
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    TIME_MINUTES,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NMBS"

DEFAULT_ICON = "mdi:train"
DEFAULT_ICON_ALERT = "mdi:alert-octagon"

CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_STATION_LIVE = "station_live"
CONF_EXCLUDE_VIAS = "exclude_vias"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_FROM): cv.string,
        vol.Required(CONF_STATION_TO): cv.string,
        vol.Optional(CONF_STATION_LIVE): cv.string,
        vol.Optional(CONF_EXCLUDE_VIAS, default=False): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
    }
)


def get_time_until(departure_time=None):
    """Calculate the time between now and a train's departure time."""
    if departure_time is None:
        return 0

    delta = dt_util.utc_from_timestamp(int(departure_time)) - dt_util.now()
    return round(delta.total_seconds() / 60)


def get_delay_in_minutes(delay=0):
    """Get the delay in minutes from a delay in seconds."""
    return round(int(delay) / 60)


def get_ride_duration(departure_time, arrival_time, delay=0):
    """Calculate the total travel time in minutes."""
    duration = dt_util.utc_from_timestamp(
        int(arrival_time)
    ) - dt_util.utc_from_timestamp(int(departure_time))
    duration_time = int(round(duration.total_seconds() / 60))
    return duration_time + get_delay_in_minutes(delay)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NMBS sensor with iRail API."""

    api_client = iRail()

    name = config[CONF_NAME]
    show_on_map = config[CONF_SHOW_ON_MAP]
    station_from = config[CONF_STATION_FROM]
    station_to = config[CONF_STATION_TO]
    station_live = config.get(CONF_STATION_LIVE)
    excl_vias = config[CONF_EXCLUDE_VIAS]

    sensors = [
        NMBSSensor(api_client, name, show_on_map, station_from, station_to, excl_vias)
    ]

    if station_live is not None:
        sensors.append(
            NMBSLiveBoard(api_client, station_live, station_from, station_to)
        )

    add_entities(sensors, True)


class NMBSLiveBoard(SensorEntity):
    """Get the next train from a station's liveboard."""

    def __init__(self, api_client, live_station, station_from, station_to):
        """Initialize the sensor for getting liveboard data."""
        self._station = live_station
        self._api_client = api_client
        self._station_from = station_from
        self._station_to = station_to
        self._attrs = {}
        self._state = None

    @property
    def name(self):
        """Return the sensor default name."""
        return f"NMBS Live ({self._station})"

    @property
    def unique_id(self):
        """Return a unique ID."""
        unique_id = f"{self._station}_{self._station_from}_{self._station_to}"

        return f"nmbs_live_{unique_id}"

    @property
    def icon(self):
        """Return the default icon or an alert icon if delays."""
        if self._attrs and int(self._attrs["delay"]) > 0:
            return DEFAULT_ICON_ALERT

        return DEFAULT_ICON

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the sensor attributes if data is available."""
        if self._state is None or not self._attrs:
            return None

        delay = get_delay_in_minutes(self._attrs["delay"])
        departure = get_time_until(self._attrs["time"])

        attrs = {
            "departure": f"In {departure} minutes",
            "departure_minutes": departure,
            "extra_train": int(self._attrs["isExtra"]) > 0,
            "vehicle_id": self._attrs["vehicle"],
            "monitored_station": self._station,
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

        if delay > 0:
            attrs["delay"] = f"{delay} minutes"
            attrs["delay_minutes"] = delay

        return attrs

    def update(self):
        """Set the state equal to the next departure."""
        liveboard = self._api_client.get_liveboard(self._station)

        if liveboard is None or not liveboard.get("departures"):
            return

        next_departure = liveboard["departures"]["departure"][0]

        self._attrs = next_departure
        self._state = (
            f"Track {next_departure['platform']} - {next_departure['station']}"
        )


class NMBSSensor(SensorEntity):
    """Get the the total travel time for a given connection."""

    def __init__(
        self, api_client, name, show_on_map, station_from, station_to, excl_vias
    ):
        """Initialize the NMBS connection sensor."""
        self._name = name
        self._show_on_map = show_on_map
        self._api_client = api_client
        self._station_from = station_from
        self._station_to = station_to
        self._excl_vias = excl_vias

        self._attrs = {}
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Return the sensor default icon or an alert icon if any delay."""
        if self._attrs:
            delay = get_delay_in_minutes(self._attrs["departure"]["delay"])
            if delay > 0:
                return "mdi:alert-octagon"

        return "mdi:train"

    @property
    def extra_state_attributes(self):
        """Return sensor attributes if data is available."""
        if self._state is None or not self._attrs:
            return None

        delay = get_delay_in_minutes(self._attrs["departure"]["delay"])
        departure = get_time_until(self._attrs["departure"]["time"])

        attrs = {
            "departure": f"In {departure} minutes",
            "departure_minutes": departure,
            "destination": self._station_to,
            "direction": self._attrs["departure"]["direction"]["name"],
            "platform_arriving": self._attrs["arrival"]["platform"],
            "platform_departing": self._attrs["departure"]["platform"],
            "vehicle_id": self._attrs["departure"]["vehicle"],
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

        if self._show_on_map and self.station_coordinates:
            attrs[ATTR_LATITUDE] = self.station_coordinates[0]
            attrs[ATTR_LONGITUDE] = self.station_coordinates[1]

        if self.is_via_connection and not self._excl_vias:
            via = self._attrs["vias"]["via"][0]

            attrs["via"] = via["station"]
            attrs["via_arrival_platform"] = via["arrival"]["platform"]
            attrs["via_transfer_platform"] = via["departure"]["platform"]
            attrs["via_transfer_time"] = get_delay_in_minutes(
                via["timeBetween"]
            ) + get_delay_in_minutes(via["departure"]["delay"])

        if delay > 0:
            attrs["delay"] = f"{delay} minutes"
            attrs["delay_minutes"] = delay

        return attrs

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def station_coordinates(self):
        """Get the lat, long coordinates for station."""
        if self._state is None or not self._attrs:
            return []

        latitude = float(self._attrs["departure"]["stationinfo"]["locationY"])
        longitude = float(self._attrs["departure"]["stationinfo"]["locationX"])
        return [latitude, longitude]

    @property
    def is_via_connection(self):
        """Return whether the connection goes through another station."""
        if not self._attrs:
            return False

        return "vias" in self._attrs and int(self._attrs["vias"]["number"]) > 0

    def update(self):
        """Set the state to the duration of a connection."""
        connections = self._api_client.get_connections(
            self._station_from, self._station_to
        )

        if connections is None or not connections.get("connection"):
            return

        if int(connections["connection"][0]["departure"]["left"]) > 0:
            next_connection = connections["connection"][1]
        else:
            next_connection = connections["connection"][0]

        self._attrs = next_connection

        if self._excl_vias and self.is_via_connection:
            _LOGGER.debug(
                "Skipping update of NMBSSensor \
                because this connection is a via"
            )
            return

        duration = get_ride_duration(
            next_connection["departure"]["time"],
            next_connection["arrival"]["time"],
            next_connection["departure"]["delay"],
        )

        self._state = duration
