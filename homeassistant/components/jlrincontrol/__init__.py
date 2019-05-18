"""Support for Jaguar/Land Rover InControl services"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send
)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

__LOGGER = logging.getLogger(__name__)

DOMAIN = 'jlrincontrol'
DATA_KEY = DOMAIN

SIGNAL_STATE_UPDATED = '{}.updated'.format(DOMAIN)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setup the jlrpy component"""
    import jlrpy

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    data = hass.data[DATA_KEY] = JLRData(config)

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

        hass.states.async_set('jlrtest.fuel_level', vehicle_status.get('FUEL_LEVEL_PERC'))

    def discover_vehicle(vehicle):
        data.vehicles.add(vehicle.vin)
        get_info(vehicle)


    async def update(now):
        """Update status from the online service"""
        try:
            if not connection.get_user_info():
                __LOGGER.warning("Could not get data from service")
                return False

            for vehicle in connection.vehicles:
                if vehicle.vin not in data.vehicles:
                    discover_vehicle(vehicle)

            async_dispatcher_send(hass, SIGNAL_STATE_UPDATED)

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
        self.vehicles = set()
        self.instruments = set()
        self.config = config[DOMAIN]
        self.names = self.config.get(CONF_NAME)

    def instrument(self, vin, component, attr):
        """Return corresponding instrument."""
        return next((instrument
                     for instrument in self.instruments
                     if instrument.vehicle.vin == vin and
                     instrument.component == component and
                     instrument.attr == attr), None)

    def vehicle_name(self, vehicle):
        """Provide a friendly name for a vehicle."""
        if (self._registration_number(vehicle) and
            self._registration_number(vehicle).lower()) in self.names:
            return self.names[self._registration_number(vehicle).lower()]
        if vehicle.vin and vehicle.vin.lower() in self.names:
            return self.names[vehicle.vin.lower()]
        if self._registration_number(vehicle):
            return self._registration_number(vehicle)
        if vehicle.vin:
            return vehicle.vin
        return ''

    def _registration_number(self, vehicle):
        return vehicle.get_attributes().get('registrationNumber')
