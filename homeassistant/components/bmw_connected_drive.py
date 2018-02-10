"""
Reads vehicle status from BMW connected drive portal.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/bmw_connected_drive/
"""
import logging
import asyncio

import voluptuous as vol
from homeassistant.helpers import discovery

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD
)


REQUIREMENTS = ['bimmer_connected==0.1.0']

_LOGGER = logging.getLogger(__name__)

CONF_VIN = 'vin'
DOMAIN = 'bmw_connected_drive'
CONF_VALUES = 'values'


LENGTH_ATTRIBUTES = [
    'remaining_range_fuel',
    'mileage',
    ]

VAILD_ATTRIBUTES = LENGTH_ATTRIBUTES + [
    'timestamp',
    'remaining_fuel',
]

VEHICLE_SCHEMA = vol.Schema({
    vol.Required(CONF_VIN): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_VALUES, default=VAILD_ATTRIBUTES):
        vol.All(cv.ensure_list, [vol.In(VAILD_ATTRIBUTES)]),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        cv.string: VEHICLE_SCHEMA
    },
}, extra=vol.ALLOW_EXTRA)


BMW_COMPONENTS = ['device_tracker', 'sensor']


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Demo sensors."""
    vehicles = []
    for name, vehicle_config in config[DOMAIN].items():
        vin = vehicle_config[CONF_VIN]
        username = vehicle_config[CONF_USERNAME]
        password = vehicle_config[CONF_PASSWORD]
        _LOGGER.debug('Adding new vehicle %s as %s', vin, name)
        bimmer = BMWConnectedDriveVehicle(name, vin, username, password)
        vehicles.append(bimmer)

    hass.data[DOMAIN] = vehicles

    for component in BMW_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class BMWConnectedDriveVehicle(object):
    """Representation of a BMW vehicle."""

    def __init__(self, name: str, vin: str, username: str, password: str):
        """Constructor."""
        from bimmer_connected import BimmerConnected
        self.bimmer = BimmerConnected(vin, username, password, cache=True)
        self.name = name
