"""
Shows the available amount of public city bikes for Velo Antwerpen.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nmbs/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NMBS'
DEFAULT_ICON = 'mdi:train'

CONF_STATION_FROM = 'station_from'
CONF_STATION_TO = 'station_to'
CONF_STATION_LIVE = 'station_live'

REQUIREMENTS = ['pyrail==0.0.3']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_FROM): cv.string,
    vol.Required(CONF_STATION_TO): cv.string,
    vol.Required(CONF_STATION_LIVE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

def get_time_until(departure_time=None):
    """Calculate the time between now and a train's departure time"""
    if departure_time is None:
        return 0

    delta = dt_util.utc_from_timestamp(int(departure_time)) - dt_util.now()

    return round((delta.total_seconds() / 60))


def get_delay(delay=0):
    """Calculate the delay in minutes. Delays are expressed in seconds"""
    return round((int(delay) / 60))

def get_ride_duration(departure_time, arrival_time, delay=0):
    """Calculate the total travel time: duration + delay and return in minutes"""
    duration = dt_util.utc_from_timestamp(int(arrival_time)) - dt_util.utc_from_timestamp(int(departure_time))
    duration_time = round((duration.total_seconds() / 60))
    return int(duration_time) + get_delay(int(delay))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Velo sensor."""
    from pyrail import iRail
    api_client = iRail()

    name = config.get(CONF_NAME)
    station_from = config.get(CONF_STATION_FROM)
    station_to = config.get(CONF_STATION_TO)
    station_live = config.get(CONF_STATION_LIVE)

    add_entities([
        NMBSLiveBoard(name, station_live, api_client),
        NMBSSensor(name, station_from, station_to, api_client),
    ], True)


class NMBSLiveBoard(Entity):
    def __init__(self, name, live_station, api_client):
        self._name = "NMBS Live"
        self._station = live_station
        self._api_client = api_client
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self._attrs is not None and int(self._attrs["delay"]) > 0:
            return "mdi:bus-alert"
        else:
            return "mdi:bus-clock"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        if self._state is None or self._attrs is None:
            return None

        delay = get_delay(self._attrs["delay"])
        departure = get_time_until(self._attrs['time'])

        return {
            "Delay": "{} minutes".format(delay) if delay > 0 else "None",
            "Vehicle ID": self._attrs['vehicle'],
            "Occupancy": self._attrs['occupancy']['name'],
            "Extra train": 'Yes' if int(self._attrs['isExtra']) > 0 else 'No',
            "Departure": "In {} minutes".format(departure),
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

    def update(self):
        liveboard = self._api_client.get_liveboard(self._station)
        next_departure = liveboard["departures"]["departure"][0]

        self._attrs = next_departure
        self._state = "Track {} - {}".format(next_departure["platform"], next_departure["station"])


class NMBSSensor(Entity):
    """Get the available amount of bikes and set the selected station as attributes"""

    def __init__(self, name, station_from, station_to, api_client):
        """Initialize the NMBS sensor."""
        self._name = name
        self._station_from = station_from
        self._station_to = station_to
        self._api_client = api_client
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return DEFAULT_NAME

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        # TODO: use HA thingy
        return "minutes"

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        delay = get_delay(self._attrs["departure"]["delay"])
        if self._attrs is not None and delay > 0:
            return "mdi:alert-octagon"
        else:
            return "mdi:train"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._state is None or self._attrs is None:
            return None

        delay = get_delay(self._attrs["departure"]["delay"])
        departure = get_time_until(self._attrs["departure"]['time'])

        return {
            "Delay": "{} minutes".format(delay) if delay > 0 else "None",
            "Vehicle ID": self._attrs["departure"]['vehicle'],
            "Occupancy": self._attrs["departure"]['occupancy']['name'],
            # "Via": self._attrs["vias"]["via"][0]["station"] if self._attrs["vias"] is not None else "Direct line",
            # "Transfer time": get_delay(self._attrs["vias"]["via"][0]["timeBetween"]) if self._attrs["vias"] is not None else "Direct line",
            "Departure": "In {} minutes".format(departure),
            "Direction": self._attrs["departure"]["direction"]["name"],
            "Platform (departing)": self._attrs["departure"]["platform"],
            "Platform (arriving)": self._attrs["arrival"]["platform"],
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Set the state to the available amount of bikes as a number"""
        connections = self._api_client.get_connections(self._station_from, self._station_to)
        next_connection = None

        if int(connections["connection"][0]["departure"]["left"]) > 0:
            next_connection = connections["connection"][1]
        else:
            next_connection = connections["connection"][0]

        self._attrs = next_connection

        duration = get_ride_duration(
            next_connection['departure']['time'],
            next_connection['arrival']['time'],
            next_connection['departure']['delay'],
        )

        self._state = duration
