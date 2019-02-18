"""
Get ride details and liveboard details for NMBS (Belgian railway).

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
DEFAULT_NAME_LIVE = "NMBS Live"

DEFAULT_ICON = "mdi:train"
DEFAULT_ICON_ALERT = "mdi:alert-octagon"

CONF_STATION_FROM = 'station_from'
CONF_STATION_TO = 'station_to'
CONF_STATION_LIVE = 'station_live'

REQUIREMENTS = ["pyrail==0.0.3"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_FROM): cv.string,
    vol.Required(CONF_STATION_TO): cv.string,
    vol.Optional(CONF_STATION_LIVE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def get_time_until(departure_time=None):
    """Calculate the time between now and a train's departure time."""
    if departure_time is None:
        return 0

    delta = dt_util.utc_from_timestamp(int(departure_time)) - dt_util.now()
    return round((delta.total_seconds() / 60))


def get_delay_in_minutes(delay=0):
    """Get the delay in minutes from a delay in seconds."""
    return round((int(delay) / 60))


def get_ride_duration(departure_time, arrival_time, delay=0):
    """Calculate the total travel time in minutes."""
    duration = dt_util.utc_from_timestamp(
        int(arrival_time)) - dt_util.utc_from_timestamp(int(departure_time))
    duration_time = int(round((duration.total_seconds() / 60)))
    return duration_time + get_delay_in_minutes(delay)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NMBS sensor with iRail API."""
    from pyrail import iRail
    api_client = iRail()

    name = config[CONF_NAME]
    station_from = config[CONF_STATION_FROM]
    station_to = config[CONF_STATION_TO]
    station_live = config.get(CONF_STATION_LIVE)

    sensors = [NMBSSensor(name, station_from, station_to, api_client)]

    if station_live is not None:
        sensors.append(NMBSLiveBoard(station_live, api_client))

    add_entities(sensors, True)


class NMBSLiveBoard(Entity):
    """Get the next train from a station's liveboard."""

    def __init__(self, live_station, api_client):
        """Initialize the sensor for getting liveboard data."""
        self._station = live_station
        self._api_client = api_client
        self._attrs = {}
        self._state = None

    @property
    def name(self):
        """Return the sensor default name."""
        return DEFAULT_NAME_LIVE

    @property
    def icon(self):
        """Return the default icon or an alert icon if delays."""
        if self._attrs is not None and int(self._attrs['delay']) > 0:
            return DEFAULT_ICON_ALERT

        return DEFAULT_ICON

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the sensor attributes if data is available."""
        if self._state is None or self._attrs is None:
            return None

        delay = get_delay_in_minutes(self._attrs["delay"])
        departure = get_time_until(self._attrs['time'])

        attrs = {
            'departure': "In {} minutes".format(departure),
            'extra_train': int(self._attrs['isExtra']) > 0,
            'occupancy': self._attrs['occupancy']['name'],
            'vehicle_id': self._attrs['vehicle'],
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

        if delay > 0:
            attrs['delay'] = "{} minutes".format(delay)

        return attrs

    def update(self):
        """Set the state equal to the next departure."""
        liveboard = self._api_client.get_liveboard(self._station)
        next_departure = liveboard['departures']['departure'][0]

        self._attrs = next_departure
        self._state = "Track {} - {}".format(
            next_departure['platform'], next_departure['station'])


class NMBSSensor(Entity):
    """Get the the total travel time for a given connection."""

    def __init__(self, name, station_from, station_to, api_client):
        """Initialize the NMBS connection sensor."""
        self._name = name
        self._station_from = station_from
        self._station_to = station_to
        self._api_client = api_client
        self._attrs = {}
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'min'

    @property
    def icon(self):
        """Return the sensor default icon or an alert icon if any delay."""
        if self._attrs is not None:
            delay = get_delay_in_minutes(self._attrs['departure']['delay'])
            if delay > 0:
                return "mdi:alert-octagon"

        return "mdi:train"

    @property
    def device_state_attributes(self):
        """Return sensor attributes if data is available."""
        if self._state is None or self._attrs is None:
            return None

        delay = get_delay_in_minutes(self._attrs['departure']['delay'])
        departure = get_time_until(self._attrs['departure']['time'])

        attrs = {
            'departure': "In {} minutes".format(departure),
            'direction': self._attrs['departure']['direction']['name'],
            'occupancy': self._attrs['departure']['occupancy']['name'],
            "platform_arriving": self._attrs['arrival']['platform'],
            "platform_departing": self._attrs['departure']['platform'],
            "vehicle_id": self._attrs['departure']['vehicle'],
            ATTR_ATTRIBUTION: "https://api.irail.be/",
        }

        if delay > 0:
            attrs['delay'] = "{} minutes".format(delay)

        return attrs

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Set the state to the duration of a connection."""
        connections = self._api_client.get_connections(
            self._station_from, self._station_to)

        next_connection = None

        if int(connections['connection'][0]['departure']['left']) > 0:
            next_connection = connections['connection'][1]
        else:
            next_connection = connections['connection'][0]

        self._attrs = next_connection

        duration = get_ride_duration(
            next_connection['departure']['time'],
            next_connection['arrival']['time'],
            next_connection['departure']['delay'],
        )

        self._state = duration
