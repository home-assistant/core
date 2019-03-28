"""
Support for Repetier-Server sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/repetier/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_MONITORED_CONDITIONS,
    TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify as util_slugify
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['pyrepetier==2.0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'RepetierServer'
DOMAIN = 'repetier'

SCAN_INTERVAL = timedelta(seconds=5)


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer['name']) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


BINARY_SENSOR_TYPES = {
    'Printing': ['state', None],
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

SENSOR_TYPES = {
    # Type, Unit, Icon
    'Temperatures': ['temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    "Current State": ['state', None, 'mdi:printer-3d'],
    "Job Percentage": ['progress', '%', 'mdi:file-percent'],
    "Time Remaining": ['progress', None, 'mdi:clock-end'],
    "Time Elapsed": ['progress', None, 'mdi:clock-start'],
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=3344): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS, default={}): BINARY_SENSOR_SCHEMA
    })], has_all_unique_names),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Repetier Server component."""
    import pyrepetier
    success = False

    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        return True

    for repetier in config[DOMAIN]:
        _LOGGER.debug("Repetier server config %s", repetier[CONF_HOST])

        url = 'http://' + repetier[CONF_HOST]
        port = repetier.get(CONF_PORT)
        apikey = repetier[CONF_API_KEY]

        server = pyrepetier.Repetier(
            url=url,
            port=port,
            apikey=apikey)
        printers = server.getPrinters()

        for printer in printers:
            sensors = repetier[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
            sensvar = {'printer': printer,
                       'url': url,
                       'port': port,
                       'apikey': apikey,
                       'name': printers[printer]['slug'],
                       'sensors': sensors}

            load_platform(hass, 'sensor', DOMAIN, sensvar, repetier)

            success = True

    return success
