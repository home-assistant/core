"""
Support for SmartHab device integration.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smarthab/
"""
import logging

import voluptuous as vol

from homeassistant.helpers.discovery import load_platform
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (
    CONF_EMAIL, CONF_PASSWORD, CONF_URL)
import homeassistant.helpers.config_validation as cv

DOMAIN = 'smarthab'
DATA_HUB = 'hub'

REQUIREMENTS = ['smarthab==0.19']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_URL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config) -> bool:
    """Set up the SmartHab platform."""
    import pysmarthab

    sh_conf = config.get(DOMAIN)

    # Assign configuration variables
    username = sh_conf.get(CONF_EMAIL)
    password = sh_conf.get(CONF_PASSWORD)
    base_url = sh_conf.get(CONF_URL)

    # Verify that configuration exists
    if username is None or password is None:
        _LOGGER.error(
            "SmartHab username or password is empty, please check your"
            " configuration")
        return False

    if base_url is None:
        base_url = pysmarthab.SmartHab.DEFAULT_BASE_API_URL

    # Setup connection with SmartHab API
    hub = pysmarthab.SmartHab(base_url=base_url)

    try:
        hub.login(username, password)
    except pysmarthab.RequestFailedException as ex:
        raise PlatformNotReady(ex)

    # Verify that passed in configuration works
    if not hub.is_logged_in():
        _LOGGER.error("Could not authenticate with SmartHab API")
        raise PlatformNotReady

    # Pass hub object to child platforms
    hass.data[DOMAIN] = {
        DATA_HUB: hub
    }

    load_platform(hass, 'light', DOMAIN, None, config)
    load_platform(hass, 'cover', DOMAIN, None, config)

    return True
