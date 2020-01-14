"""The totalconnect component."""
import logging

from total_connect_client import TotalConnectClient
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "totalconnect"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

TOTALCONNECT_PLATFORMS = ["alarm_control_panel", "binary_sensor"]


def setup(hass, config):
    """Set up TotalConnect component."""
    conf = config[DOMAIN]

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    client = TotalConnectClient.TotalConnectClient(username, password)

    if client.token is False:
        _LOGGER.error("TotalConnect authentication failed")
        return False

    hass.data[DOMAIN] = TotalConnectSystem(username, password, client)

    for platform in TOTALCONNECT_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


class TotalConnectSystem:
    """TotalConnect System class."""

    def __init__(self, username, password, client):
        """Initialize the TotalConnect system."""
        self._username = username
        self._password = password
        self.client = client
