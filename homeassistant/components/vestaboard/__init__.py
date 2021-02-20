"""Support for Vestaboard."""
import logging

import vestaboard
import voluptuous as vol

from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

CONF_API_SECRET = "api_secret"

_LOGGER = logging.getLogger(__name__)


DOMAIN = "vestaboard"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the VestaboardManager."""
    _LOGGER.debug("Setting up Vestaboard platform")
    conf = config[DOMAIN]
    hvbm = HassVestaboardManager(
        apiKey=conf[CONF_API_KEY], apiSecret=conf[CONF_API_SECRET]
    )
    subscriptions = hvbm.manager.get_subscriptions()
    if not subscriptions:
        _LOGGER.error("No Vestaboard subscriptions found")
        return False

    hass.data[DOMAIN] = hvbm
    for sub in subscriptions:
        _LOGGER.debug("Discovered Vestaboard subscription: %s", sub)

    return True


class HassVestaboardManager:
    """A class that encapsulated requests to the Vestaboard manager."""

    def __init__(self, apiKey, apiSecret):
        """Initialize HassVestaboardManager and connect to Vestaboard."""

        _LOGGER.debug("Connecting to Vestaboard")
        self.manager = vestaboard.Installable(
            apiKey=apiKey,
            apiSecret=apiSecret,
            getSubscription=False,
            saveCredentials=False,
        )
        self._apiKey = apiKey
        self._apiSecret = apiSecret
