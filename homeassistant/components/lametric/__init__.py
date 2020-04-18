"""Support for LaMetric time."""
import logging

from lmnotify import LaMetricManager
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

DOMAIN = "lametric"
LAMETRIC_DEVICES = "LAMETRIC_DEVICES"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the LaMetricManager."""
    _LOGGER.debug("Setting up LaMetric platform")
    conf = config[DOMAIN]
    hlmn = HassLaMetricManager(
        client_id=conf[CONF_CLIENT_ID], client_secret=conf[CONF_CLIENT_SECRET]
    )
    devices = hlmn.manager.get_devices()
    if not devices:
        _LOGGER.error("No LaMetric devices found")
        return False

    hass.data[DOMAIN] = hlmn
    for dev in devices:
        _LOGGER.debug("Discovered LaMetric device: %s", dev)

    return True


class HassLaMetricManager:
    """A class that encapsulated requests to the LaMetric manager."""

    def __init__(self, client_id, client_secret):
        """Initialize HassLaMetricManager and connect to LaMetric."""

        _LOGGER.debug("Connecting to LaMetric")
        self.manager = LaMetricManager(client_id, client_secret)
        self._client_id = client_id
        self._client_secret = client_secret
