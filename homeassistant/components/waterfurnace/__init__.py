"""Support for Waterfurnaces."""

import logging

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import WaterFurnaceCoordinator

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up waterfurnace platform."""

    config = base_config[DOMAIN]

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    wfconn = WaterFurnace(username, password)
    # NOTE(sdague): login will throw an exception if this doesn't
    # work, which will abort the setup.
    try:
        wfconn.login()
    except WFCredentialError:
        _LOGGER.error("Invalid credentials for waterfurnace login")
        return False

    coordinator = WaterFurnaceCoordinator(hass, wfconn)
    hass.data[DOMAIN] = coordinator

    discovery.load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    return True
