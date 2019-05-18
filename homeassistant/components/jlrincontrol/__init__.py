"""Support for Jaguar/Land Rover InControl services"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send
)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

__LOGGER = logging.getLogger(__name__)

DOMAIN = 'jlrincontrol'

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

    __LOGGER.info(config[DOMAIN].get(CONF_USERNAME))
    __LOGGER.info(config[DOMAIN].get(CONF_PASSWORD))

    connection = jlrpy.Connection(config[DOMAIN].get(CONF_USERNAME), config[DOMAIN].get(CONF_PASSWORD))

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

    async def update(now):
        """Update status from the online service"""
        try:
            if not connection.vehicles[0].get_status:
                __LOGGER.warning("Could not get data from service")
                return False

            vehicle = connection.vehicles[0]  # TODO: make this looped for multiple vehicles
            get_info(vehicle)
            async_dispatcher_send(hass, SIGNAL_STATE_UPDATED)

            return True
        finally:
            async_track_point_in_utc_time(hass, update,
                                          utcnow() + timedelta(minutes=5))  # TODO: replace 60 with scan interval

    __LOGGER.info("Logging into InControl")

    return await update(utcnow())

# class JLRData:
#     """Hold component state"""

#     def __init__(self, config):
#         """Initialize the component state"""
#         self.vehicles = set()
#         self.config = config[DOMAIN]

#     def vehicle_name(self, vehicle):
#         """Provide a friendly name for a vehicle."""
#         if (vehicle)

# class MyEntity(Entity):
#     async def async_update(self):
#         """Latest STate"""
#         self._state = await async_add_executor_job()
