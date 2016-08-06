"""
Support for Nest thermostats and protect smoke alarms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_STRUCTURE

REQUIREMENTS = ['python-nest==2.9.2']
DOMAIN = 'nest'

NEST = None

STRUCTURES_TO_INCLUDE = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_STRUCTURE): vol.Any(str, list),
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def devices():
    """Generator returning list of devices and their location."""
    try:
        for structure in NEST.structures:
            if structure.name in STRUCTURES_TO_INCLUDE:
                for device in structure.devices:
                    yield (structure, device)
            else:
                _LOGGER.info("Ignoring structure %s, not in %s", structure.name, STRUCTURES_TO_INCLUDE)
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
                _LOGGER.info("Ignoring structure %s, not in %s", structure.name, STRUCTURES_TO_INCLUDE)
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

    if not CONF_STRUCTURE in conf:
        STRUCTURES_TO_INCLUDE = []
        for structure in NEST.structures:
            STRUCTURES_TO_INCLUDE.append(structure.name)
    elif isinstance(conf[CONF_STRUCTURE], list):
        STRUCTURES_TO_INCLUDE = conf[CONF_STRUCTURE]
    else:
        STRUCTURES_TO_INCLUDE = [conf[CONF_STRUCTURE]]

    _LOGGER.info("Structures to include: %s", STRUCTURES_TO_INCLUDE)
    return True
