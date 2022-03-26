"""Support for LaMetric time."""
from lmnotify import LaMetricManager
import voluptuous as vol

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER

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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LaMetricManager."""
    LOGGER.debug("Setting up LaMetric platform")
    conf = config[DOMAIN]
    hlmn = HassLaMetricManager(
        client_id=conf[CONF_CLIENT_ID], client_secret=conf[CONF_CLIENT_SECRET]
    )
    if not (devices := hlmn.manager.get_devices()):
        LOGGER.error("No LaMetric devices found")
        return False

    hass.data[DOMAIN] = hlmn
    for dev in devices:
        LOGGER.debug("Discovered LaMetric device: %s", dev)

    return True


class HassLaMetricManager:
    """A class that encapsulated requests to the LaMetric manager."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        """Initialize HassLaMetricManager and connect to LaMetric."""

        LOGGER.debug("Connecting to LaMetric")
        self.manager = LaMetricManager(client_id, client_secret)
        self._client_id = client_id
        self._client_secret = client_secret
