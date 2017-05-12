"""
Support for Nest devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nest/
"""
import logging
import socket

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_STRUCTURE, CONF_FILENAME, CONF_BINARY_SENSORS, CONF_SENSORS,
    CONF_MONITORED_CONDITIONS)
from homeassistant.loader import get_component

REQUIREMENTS = ['python-nest==3.1.0']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nest'

DATA_NEST = 'nest'

NEST_CONFIG_FILE = 'nest.conf'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list)
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, cv.string),
        vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS): SENSOR_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)


def request_configuration(nest, hass, config):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    if 'nest' in _CONFIGURING:
        _LOGGER.debug("configurator failed")
        configurator.notify_errors(
            _CONFIGURING['nest'], "Failed to configure, please try again.")
        return

    def nest_configuration_callback(data):
        """Run when the configuration callback is called."""
        _LOGGER.debug("configurator callback")
        pin = data.get('pin')
        setup_nest(hass, nest, config, pin=pin)

    _CONFIGURING['nest'] = configurator.request_config(
        hass, "Nest", nest_configuration_callback,
        description=('To configure Nest, click Request Authorization below, '
                     'log into your Nest account, '
                     'and then enter the resulting PIN'),
        link_name='Request Authorization',
        link_url=nest.authorize_url,
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the PIN', 'type': ''}]
    )


def setup_nest(hass, nest, config, pin=None):
    """Set up the Nest devices."""
    if pin is not None:
        _LOGGER.debug("pin acquired, requesting access token")
        nest.request_token(pin)

    if nest.access_token is None:
        _LOGGER.debug("no access_token, requesting configuration")
        request_configuration(nest, hass, config)
        return

    if 'nest' in _CONFIGURING:
        _LOGGER.debug("configuration done")
        configurator = get_component('configurator')
        configurator.request_done(_CONFIGURING.pop('nest'))

    _LOGGER.debug("proceeding with setup")
    conf = config[DOMAIN]
    hass.data[DATA_NEST] = NestDevice(hass, conf, nest)

    _LOGGER.debug("proceeding with discovery")
    discovery.load_platform(hass, 'climate', DOMAIN, {}, config)
    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)

    sensor_config = conf.get(CONF_SENSORS, {})
    discovery.load_platform(hass, 'sensor', DOMAIN, sensor_config, config)

    binary_sensor_config = conf.get(CONF_BINARY_SENSORS, {})
    discovery.load_platform(hass, 'binary_sensor', DOMAIN,
                            binary_sensor_config, config)

    _LOGGER.debug("setup done")

    return True


def setup(hass, config):
    """Set up the Nest thermostat component."""
    import nest

    if 'nest' in _CONFIGURING:
        return

    conf = config[DOMAIN]
    client_id = conf[CONF_CLIENT_ID]
    client_secret = conf[CONF_CLIENT_SECRET]
    filename = config.get(CONF_FILENAME, NEST_CONFIG_FILE)

    access_token_cache_file = hass.config.path(filename)

    nest = nest.Nest(
        access_token_cache_file=access_token_cache_file,
        client_id=client_id, client_secret=client_secret)
    setup_nest(hass, nest, config)

    return True


class NestDevice(object):
    """Structure Nest functions for hass."""

    def __init__(self, hass, conf, nest):
        """Init Nest Devices."""
        self.hass = hass
        self.nest = nest

        if CONF_STRUCTURE not in conf:
            self._structure = [s.name for s in nest.structures]
        else:
            self._structure = conf[CONF_STRUCTURE]
        _LOGGER.debug("Structures to include: %s", self._structure)

    def thermostats(self):
        """Generate a list of thermostats and their location."""
        try:
            for structure in self.nest.structures:
                if structure.name in self._structure:
                    for device in structure.thermostats:
                        yield (structure, device)
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self._structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def smoke_co_alarms(self):
        """Generate a list of smoke co alarams."""
        try:
            for structure in self.nest.structures:
                if structure.name in self._structure:
                    for device in structure.smoke_co_alarms:
                        yield(structure, device)
                else:
                    _LOGGER.info("Ignoring structure %s, not in %s",
                                 structure.name, self._structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def cameras(self):
        """Generate a list of cameras."""
        try:
            for structure in self.nest.structures:
                if structure.name in self._structure:
                    for device in structure.cameras:
                        yield(structure, device)
                else:
                    _LOGGER.info("Ignoring structure %s, not in %s",
                                 structure.name, self._structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")
