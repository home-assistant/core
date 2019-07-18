"""Support for Jaguar/Land Rover InControl services."""
import logging
from datetime import timedelta
import urllib.error

import voluptuous as vol

import jlrpy


import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, \
    CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers.dispatcher import (
    dispatcher_send
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow




_LOGGER = logging.getLogger(__name__)

DOMAIN = 'jlrincontrol'
SIGNAL_VEHICLE_SEEN = '{}.vehicle_seen'.format(DOMAIN)
DATA_KEY = DOMAIN
CONF_MUTABLE = 'mutable'

MIN_UPDATE_INTERVAL = timedelta(minutes=1)
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

RESOURCES = {
    'FUEL_LEVEL_PERC': ('sensor', 'Fuel level', 'mdi:fuel', '%'),
    'DISTANCE_TO_EMPTY_FUEL': ('sensor', 'Range', 'mdi:road', 'km'),
    'EXT_KILOMETERS_TO_SERVICE': ('sensor', 'Distance to next service',
                                  'mdi:garage', 'km'),
    'ODOMETER_METER': ('sensor', 'Odometer', 'mdi:car', 'km'),
    'DOOR_IS_ALL_DOORS_LOCKED': ('binary_sensor', 'All Doors Locked',
                                 'mdi:lock', 'lock')


}

SIGNAL_STATE_UPDATED = '{}.updated'.format(DOMAIN)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL):
            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)),
        vol.Required(CONF_NAME): vol.Schema(
            {cv.slug: cv.string}),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the jlrpy component."""

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    state = hass.data[DATA_KEY] = JLRData(config)

    interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    connection = None
    try:
        connection = jlrpy.Connection(username, password)
    except urllib.error.HTTPError:
        _LOGGER.error("Could not connect to JLR. Please check your credentials")
        return False

    vehicles = []
    for vehicle in connection.vehicles:
        vehicle.info = vehicle.get_status()
        vehicles.append(vehicle)

    def discover_vehicle(vehicle):
        state.entities[vehicle.vin] = []

        for attr, (component, *_) in RESOURCES.items():
            hass.helpers.discovery.load_platform(
                component, DOMAIN, (vehicle.vin, attr), config
            )

    def update_vehicle(vehicle):
        """Update information on vehicle."""
        _LOGGER.info("Pulling info from JLR")

        state.vehicles[vehicle.vin] = vehicle
        if vehicle.vin not in state.entities:
            discover_vehicle(vehicle)

        for entity in state.entities[vehicle.vin]:
            entity.schedule_update_ha_state()

        dispatcher_send(hass, SIGNAL_VEHICLE_SEEN, vehicle)

    def update(now):
        """Update status from the online service."""
        _LOGGER.info("Update method in INIT")
        try:
            if not connection:
                _LOGGER.warning("Could not get data from service")
                return False

            for vehicle in vehicles:
                update_vehicle(vehicle)

            return True
        finally:
            track_point_in_utc_time(hass, update,
                                    utcnow() + interval)

    return update(utcnow())


class JLRData:
    """Hold component state."""

    def __init__(self, config):
        """Initialize the component state."""
        self.entities = {}
        self.vehicles = {}
        self.config = config[DOMAIN]
        self.names = self.config.get(CONF_NAME)

    def vehicle_name(self, vehicle):
        """Provide a friendly name for a vehicle."""
        if vehicle.vin and vehicle.vin.lower() in self.names:
            return self.names[vehicle.vin.lower()]

        if vehicle.vin:
            return vehicle.vin

        return ''


class JLREntity(Entity):
    """Base class for all JLR Vehicle entities."""

    def __init__(self, hass, vin, attribute):
        """Initialize the entity."""
        self._hass = hass
        self._vin = vin
        self._attribute = attribute
        self._state.entities[self._vin].append(self)

    @staticmethod
    def get_vehicle_status(vehicle_status):
        """Converts a weird quasi-dict returned by jlrpy into a proper dict"""
        dict_only = {}
        for element in vehicle_status:
            dict_only[element.get('key')] = element.get('value')
        return dict_only

    @property
    def _state(self):
        return self._hass.data[DATA_KEY]

    @property
    def vehicle(self):
        """Return vehicle."""
        return self._state.vehicles[self._vin]

    @property
    def _entity_name(self):
        return RESOURCES[self._attribute][1]

    @property
    def _vehicle_name(self):
        return self._state.vehicle_name(self.vehicle)

    @property
    def name(self):
        """Return full name of the entity."""
        return '{} {}'.format(
            self._vehicle_name,
            self._entity_name)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        vehicle_attr = self.vehicle.get_attributes()
        return dict(model='{} {} {}'.format(vehicle_attr['modelYear'],
                                            vehicle_attr['vehicleBrand'],
                                            vehicle_attr['vehicleType']))
