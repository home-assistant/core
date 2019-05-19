"""Support for Jaguar/Land Rover InControl services"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

__LOGGER = logging.getLogger(__name__)

DOMAIN = 'jlrincontrol'
SIGNAL_VEHICLE_SEEN = '{}.vehicle_seen'.format(DOMAIN)
DATA_KEY = DOMAIN
CONF_MUTABLE = 'mutable'

RESOURCES = {
    'FUEL_LEVEL_PERC': ('sensor', 'Fuel level', 'mdi:fuel', '%'),
    'DISTANCE_TO_EMPTY_FUEL': ('sensor', 'Range', 'mdi:road', 'km')
}

SIGNAL_STATE_UPDATED = '{}.updated'.format(DOMAIN)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_NAME, default={}): vol.Schema(
            {cv.slug: cv.string}),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setup the jlrpy component"""
    import jlrpy

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    state = hass.data[DATA_KEY] = JLRData(config)

    connection = jlrpy.Connection(username, password)

    def format_nicely(raw_data):
        dict_only = {}
        for el in raw_data:
            dict_only[el.get('key')] = el.get('value')
        return dict_only

    def get_info(vehicle):
        """Load vehicle"""
        __LOGGER.info("cccccccc")
        info = vehicle.get_status()
        vehicle_status = format_nicely(info.get('vehicleStatus'))

        # hass.states.async_set('jlrtest.fuel_level', vehicle_status.get('FUEL_LEVEL_PERC'))

    def discover_vehicle(vehicle):
        state.entities[vehicle.vin] = []

        for attr, (component, *_) in RESOURCES.items():
            hass.async_create_task(
                hass.helpers.discovery.async_load_platform(
                    'sensor', DOMAIN, (vehicle.vin, attr), config
                )
            )

    async def update_vehicle(vehicle):
        """Update information on vehicle"""
        state.vehicles[vehicle.vin] = vehicle
        if vehicle.vin not in state.entities:
            discover_vehicle(vehicle)

        for entity in state.entities[vehicle.vin]:
            entity.schedule_update_ha_state()

        async_dispatcher_send(hass, SIGNAL_VEHICLE_SEEN, vehicle)


    async def update(now):
        """Update status from the online service"""
        try:
            if not connection.get_user_info():
                __LOGGER.warning("Could not get data from service")
                return False

            for vehicle in connection.vehicles:
                await update_vehicle(vehicle)

            return True
        finally:
            async_track_point_in_utc_time(hass, update,
                                          utcnow() + timedelta(minutes=5))  # TODO: replace 60 with scan interval

    __LOGGER.info("Logging into InControl")

    return await update(utcnow())


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
        if (vehicle.vin and vehicle.vin.lower() in self.names):
            return self.names[vehicle.vin.lower()]
        elif vehicle.vin:
            return vehicle.vin
        else:
            return ''


class JLREntity(Entity):
    """Base class for all JLR Vehicle entities."""

    def __init__(self, hass, vin, attribute):
        """Initialize the entity."""
        self._hass = hass
        self._vin = vin
        self._attribute = attribute
        self._state.entities[self._vin].append(self)
        self._val = self._get_vehicle_status(self.vehicle)

    def _get_vehicle_status(self, vehicle):
        dict_only = {}
        for el in vehicle.get_status().get('vehicleStatus'):
            dict_only[el.get('key')] = el.get('value')
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
        return dict(model='{} {} {}'.format(vehicle_attr['modelYear'], vehicle_attr['vehicleBrand'],
                                            vehicle_attr['vehicleType']))
