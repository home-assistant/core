"""Support for getting information from thingsmobile account."""
import logging

from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "thingsmobile"

TIMEOUT = 5

_api_url = "https://www.thingsmobile.com/services/business-api/simStatus"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """
    Set up Things mobile sensor.

    first checks if it's possible to make a request fails otherwise
    """
    import requests

    conf = config[DOMAIN]
    api_key = conf.get(CONF_API_KEY)
    username = conf.get(CONF_USERNAME)

    try:
        requests.post(_api_url, {"username": username, "token": api_key})
        hass.data[DOMAIN] = {
            "body": {"username": username, "token": api_key},
            "url": _api_url,
        }
    except RequestException:
        _LOGGER.error("Could not communicate with things Mobile")
        return False
    return True
