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

REQUIREMENTS = ['python-nest==2.10.0']

DOMAIN = 'nest'

NEST = None

STRUCTURES_TO_INCLUDE = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, cv.string)
    })
}, extra=vol.ALLOW_EXTRA)


def devices():
    """Generator returning list of devices and their location."""
    try:
        for structure in NEST.structures:
            if structure.name in STRUCTURES_TO_INCLUDE:
                for device in structure.devices:
                    yield (structure, device)
            else:
                _LOGGER.debug("Ignoring structure %s, not in %s",
                              structure.name, STRUCTURES_TO_INCLUDE)
    except socket.error:
        _LOGGER.error("Connection error logging into the nest web service.")


def protect_devices():
    """Generator returning list of protect devices."""
    try:
        for structure in NEST.structures:
            if structure.name in STRUCTURES_TO_INCLUDE:
                for device in structure.protectdevices:
                    yield(structure, device)
            else:
                _LOGGER.info("Ignoring structure %s, not in %s",
                             structure.name, STRUCTURES_TO_INCLUDE)
    except socket.error:
        _LOGGER.error("Connection error logging into the nest web service.")


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Nest thermostat component."""
    global NEST
    global STRUCTURES_TO_INCLUDE

    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    import nest

    NEST = nest.Nest(username, password)

    if CONF_STRUCTURE not in conf:
        STRUCTURES_TO_INCLUDE = [s.name for s in NEST.structures]
    else:
        STRUCTURES_TO_INCLUDE = conf[CONF_STRUCTURE]

    _LOGGER.debug("Structures to include: %s", STRUCTURES_TO_INCLUDE)
    return True
