"""Support for Repetier-Server sensors."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_SENSORS,
    CONF_MONITORED_CONDITIONS,
    TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify as util_slugify
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['pyrepetier==3.0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'RepetierServer'
DOMAIN = 'repetier'
REPETIER_API = 'repetier_api'


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer[CONF_NAME]) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


SENSOR_TYPES = {
    # Type, Unit, Icon
    'bed_temperature': ['temperature', TEMP_CELSIUS, 'mdi:thermometer',
                        '_bed_'],
    'extruder_temperature': ['temperature', TEMP_CELSIUS, 'mdi:thermometer',
                             '_extruder_'],
    'chamber_temperature': ['temperature', TEMP_CELSIUS, 'mdi:thermometer',
                            '_chamber_'],
    'current_state': ['state', None, 'mdi:printer-3d', ''],
    'current_job': ['progress', '%', 'mdi:file-percent', '_current_job'],
    'time_remaining': ['progress', None, 'mdi:clock-end', '_remaining'],
    'time_elapsed': ['progress', None, 'mdi:clock-start', '_elapsed'],
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
    })], has_all_unique_names),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Repetier Server component."""
    import pyrepetier

    hass.data[REPETIER_API] = {}
    sensor_info = []

    for repetier in config[DOMAIN]:
        _LOGGER.debug("Repetier server config %s", repetier[CONF_HOST])

        url = "http://{}".format(repetier[CONF_HOST])
        port = repetier[CONF_PORT]
        api_key = repetier[CONF_API_KEY]

        client = pyrepetier.Repetier(
            url=url,
            port=port,
            apikey=api_key)

        printers = client.getprinters()

        if not printers:
            return False

        hass.data[REPETIER_API][repetier[CONF_NAME]] = printers

        sensors = repetier[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        for pidx, printer in enumerate(printers):
            printer.get_data()
            for sensor_type in sensors:
                sensvar = {}
                sensvar['sensor_type'] = sensor_type
                sensvar['printer_id'] = pidx
                sensvar['name'] = printer.slug
                sensvar['printer_name'] = repetier[CONF_NAME]
                sensor_info.append(sensvar)

    load_platform(hass, 'sensor', DOMAIN, sensor_info, config)

    return True
