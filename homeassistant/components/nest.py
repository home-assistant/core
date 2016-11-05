"""
Support for Nest devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nest/
"""
import logging
import socket

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME, CONF_STRUCTURE)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['python-nest==2.11.0']

DOMAIN = 'nest'

DATA_NEST = 'nest'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, cv.string)
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Nest thermostat component."""
    import nest

    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    nest = nest.Nest(username, password)
    hass.data[DATA_NEST] = NestDevice(hass, conf, nest)

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

    def devices(self):
        """Generator returning list of devices and their location."""
        try:
            for structure in self.nest.structures:
                if structure.name in self._structure:
                    for device in structure.devices:
                        yield (structure, device)
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self._structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def protect_devices(self):
        """Generator returning list of protect devices."""
        try:
            for structure in self.nest.structures:
                if structure.name in self._structure:
                    for device in structure.protectdevices:
                        yield(structure, device)
                else:
                    _LOGGER.info("Ignoring structure %s, not in %s",
                                 structure.name, self._structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")
