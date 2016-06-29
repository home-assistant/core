"""
Support for Nest thermostats and protect smoke alarms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['python-nest==2.9.2']
DOMAIN = 'nest'

NEST = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def devices():
    """Generator returning list of devices and their location."""
    try:
        for structure in NEST.structures:
            for device in structure.devices:
                yield (structure, device)
    except socket.error:
        _LOGGER.error("Connection error logging into the nest web service.")


def protect_devices():
    """Generator returning list of protect devices."""
    try:
        for structure in NEST.structures:
            for device in structure.protectdevices:
                yield(structure, device)
    except socket.error:
        _LOGGER.error("Connection error logging into the nest web service.")


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Nest thermostat component."""
    global NEST

    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    import nest

    NEST = nest.Nest(username, password)

    return True
