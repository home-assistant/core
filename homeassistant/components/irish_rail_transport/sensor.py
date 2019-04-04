"""Support for Irish Rail RTPI information."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyirishrail==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_STATION = "Station"
ATTR_ORIGIN = "Origin"
ATTR_DESTINATION = "Destination"
ATTR_DIRECTION = "Direction"
ATTR_STOPS_AT = "Stops at"
ATTR_DUE_IN = "Due in"
ATTR_DUE_AT = "Due at"
ATTR_EXPECT_AT = "Expected at"
ATTR_NEXT_UP = "Later Train"
ATTR_TRAIN_TYPE = "Train type"
ATTRIBUTION = "Data provided by Irish Rail"

CONF_STATION = 'station'
CONF_DESTINATION = 'destination'
CONF_DIRECTION = 'direction'
CONF_STOPS_AT = 'stops_at'

DEFAULT_NAME = 'Next Train'
ICON = 'mdi:train'

SCAN_INTERVAL = timedelta(minutes=2)
TIME_STR_FORMAT = '%H:%M'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): cv.string,
    vol.Optional(CONF_DIRECTION): cv.string,
    vol.Optional(CONF_DESTINATION): cv.string,
    vol.Optional(CONF_STOPS_AT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Irish Rail transport sensor."""
    from pyirishrail.pyirishrail import IrishRailRTPI
    station = config.get(CONF_STATION)
    direction = config.get(CONF_DIRECTION)
    destination = config.get(CONF_DESTINATION)
    stops_at = config.get(CONF_STOPS_AT)
    name = config.get(CONF_NAME)

    irish_rail = IrishRailRTPI()
    data = IrishRailTransportData(
        irish_rail, station, direction, destination, stops_at)
    add_entities([IrishRailTransportSensor(
        data, station, direction, destination, stops_at, name)], True)


class IrishRailTransportSensor(Entity):
    """Implementation of an irish rail public transport sensor."""

    def __init__(self, data, station, direction, destination, stops_at, name):
        """Initialize the sensor."""
        self.data = data
        self._station = station
        self._direction = direction
        self._direction = direction
        self._stops_at = stops_at
        self._name = name
        self._state = None
        self._times = []

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._times:
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1][ATTR_ORIGIN] + " to "
                next_up += self._times[1][ATTR_DESTINATION] + " in "
                next_up += self._times[1][ATTR_DUE_IN]

            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_STATION: self._station,
                ATTR_ORIGIN: self._times[0][ATTR_ORIGIN],
                ATTR_DESTINATION: self._times[0][ATTR_DESTINATION],
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_EXPECT_AT: self._times[0][ATTR_EXPECT_AT],
                ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
                ATTR_STOPS_AT: self._times[0][ATTR_STOPS_AT],
                ATTR_NEXT_UP: next_up,
                ATTR_TRAIN_TYPE: self._times[0][ATTR_TRAIN_TYPE],
            }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and update the states."""
        self.data.update()
        self._times = self.data.info
        if self._times:
            self._state = self._times[0][ATTR_DUE_IN]
        else:
            self._state = None


class IrishRailTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, irish_rail, station, direction, destination, stops_at):
        """Initialize the data object."""
        self._ir_api = irish_rail
        self.station = station
        self.direction = direction
        self.destination = destination
        self.stops_at = stops_at
        self.info = self._empty_train_data()

    def update(self):
        """Get the latest data from irishrail."""
        trains = self._ir_api.get_station_by_name(
            self.station, direction=self.direction,
            destination=self.destination, stops_at=self.stops_at)
        stops_at = self.stops_at if self.stops_at else ''
        self.info = []
        for train in trains:
            train_data = {
                ATTR_STATION: self.station,
                ATTR_ORIGIN: train.get('origin'),
                ATTR_DESTINATION: train.get('destination'),
                ATTR_DUE_IN: train.get('due_in_mins'),
                ATTR_DUE_AT: train.get('scheduled_arrival_time'),
                ATTR_EXPECT_AT: train.get('expected_departure_time'),
                ATTR_DIRECTION: train.get('direction'),
                ATTR_STOPS_AT: stops_at,
                ATTR_TRAIN_TYPE: train.get('type'),
            }
            self.info.append(train_data)

        if not self.info:
            self.info = self._empty_train_data()

    def _empty_train_data(self):
        """Generate info for an empty train."""
        dest = self.destination if self.destination else ''
        direction = self.direction if self.direction else ''
        stops_at = self.stops_at if self.stops_at else ''
        return [{ATTR_STATION: self.station,
                 ATTR_ORIGIN: '',
                 ATTR_DESTINATION: dest,
                 ATTR_DUE_IN: 'n/a',
                 ATTR_DUE_AT: 'n/a',
                 ATTR_EXPECT_AT: 'n/a',
                 ATTR_DIRECTION: direction,
                 ATTR_STOPS_AT: stops_at,
                 ATTR_TRAIN_TYPE: '',
                 }]
