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


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer['name']) for printer in value]
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
    'current_state': ['state', None, 'mdi:printer-3d', None],
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
    success = False

    for repetier in config[DOMAIN]:
        _LOGGER.debug("Repetier server config %s", repetier[CONF_HOST])

        url = 'http://' + repetier[CONF_HOST]
        port = repetier[CONF_PORT]
        api_key = repetier[CONF_API_KEY]

        server = pyrepetier.Repetier(
            url=url,
            port=port,
            apikey=api_key)

        printers = server.getprinters()

        if printers is False:
            return False

        sensors = repetier[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        for printer in printers:
            printer.get_data()
            for sensor_type in sensors:
                sensvar = {}
                sensvar['sensor_type'] = sensor_type
                sensvar['printer'] = printer
                name = printer.slug
                if sensor_type == 'current_state':
                    sensvar['name'] = name
                    sensvar['data_key'] = '0'
                    load_platform(hass, 'sensor', DOMAIN, sensvar, repetier)
                elif sensor_type == 'current_job':
                    name = name + SENSOR_TYPES[sensor_type][3]
                    sensvar['name'] = name
                    sensvar['data_key'] = '0'
                    load_platform(hass, 'sensor', DOMAIN, sensvar, repetier)
                elif sensor_type == 'time_remaining':
                    name = name + SENSOR_TYPES[sensor_type][3]
                    sensvar['name'] = name
                    sensvar['data_key'] = '0'
                    load_platform(hass, 'sensor', DOMAIN, sensvar, repetier)
                elif sensor_type == 'time_elapsed':
                    name = name + SENSOR_TYPES[sensor_type][3]
                    sensvar['name'] = name
                    sensvar['data_key'] = '0'
                    load_platform(hass, 'sensor', DOMAIN, sensvar, repetier)
                elif sensor_type == 'bed_temperature':
                    if printer.heatedbeds is None:
                        continue
                    name = name + SENSOR_TYPES[sensor_type][3]
                    idx = 0
                    for bed in printer.heatedbeds:
                        name = name + str(idx)
                        sensvar['name'] = name
                        sensvar['data_key'] = idx
                        sensvar['bed'] = bed
                        idx += 1
                        load_platform(hass, 'sensor', DOMAIN, sensvar,
                                      repetier)
                elif sensor_type == 'extruder_temperature':
                    if printer.extruder is None:
                        continue
                    name = name + SENSOR_TYPES[sensor_type][3]
                    idx = 0
                    for extruder in printer.extruder:
                        name = name + str(idx)
                        sensvar['name'] = name
                        sensvar['data_key'] = idx
                        sensvar['extruder'] = extruder
                        idx += 1
                        load_platform(hass, 'sensor', DOMAIN, sensvar,
                                      repetier)
                elif sensor_type == 'chamber_temperature':
                    if printer.heatedchambers is None:
                        continue
                    name = name + SENSOR_TYPES[sensor_type][3]
                    idx = 0
                    for chamber in printer.heatedchambers:
                        name = name + str(idx)
                        sensvar['name'] = name
                        sensvar['data_key'] = idx
                        sensvar['chamber'] = chamber
                        idx += 1
                        load_platform(hass, 'sensor', DOMAIN, sensvar,
                                      repetier)

            success = True

    return success
