"""Support for a DoorBird video doorbell."""

import logging
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['DoorBirdPy==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbird'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the DoorBird component."""
    device_ip = config[DOMAIN].get(CONF_HOST)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    from doorbirdpy import DoorBird
    device = DoorBird(device_ip, username, password)
    status = device.ready()

    if status[0]:
        _LOGGER.info("Connected to DoorBird at %s as %s", device_ip, username)
        hass.data[DOMAIN] = device
        return True
    elif status[1] == 401:
        _LOGGER.error("Authorization rejected by DoorBird at %s", device_ip)
        return False
    else:
        _LOGGER.error("Could not connect to DoorBird at %s: Error %s",
                      device_ip, str(status[1]))
        return False
