"""Support for SmartHab device integration."""
import logging

import pysmarthab
import voluptuous as vol

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

DOMAIN = "smarthab"
DATA_HUB = "hub"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config) -> bool:
    """Set up the SmartHab platform."""

    sh_conf = config.get(DOMAIN)

    # Assign configuration variables
    username = sh_conf[CONF_EMAIL]
    password = sh_conf[CONF_PASSWORD]

    # Setup connection with SmartHab API
    hub = pysmarthab.SmartHab()

    try:
        hub.login(username, password)
    except pysmarthab.RequestFailedException as ex:
        _LOGGER.error("Error while trying to reach SmartHab API.")
        _LOGGER.debug(ex, exc_info=True)
        return False

    # Verify that passed in configuration works
    if not hub.is_logged_in():
        _LOGGER.error("Could not authenticate with SmartHab API")
        return False

    # Pass hub object to child platforms
    hass.data[DOMAIN] = {DATA_HUB: hub}

    load_platform(hass, "light", DOMAIN, None, config)
    load_platform(hass, "cover", DOMAIN, None, config)

    return True
