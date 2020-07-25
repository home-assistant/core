"""The Mullvad integration."""
from datetime import timedelta
import logging

from mullvad_api import MullvadAPI, MullvadAPIError
import voluptuous as vol

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mullvad"
MULLVAD_COMPONENTS = ("sensor", "binary_sensor")
SCAN_INTERVAL = timedelta(seconds=60)

# Validate user configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period}
        )
    },
    extra=vol.ALLOW_EXTRA,
)
BINARY_SENSORS = ("mullvad_exit_ip",)

SENSORS = (
    "ip",
    "country",
    "city",
    "longitude",
    "latitude",
    "mullvad_exit_ip_hostname",
    "mullvad_server_type",
    "blacklisted",
    "organization",
)


def setup(hass, config):
    """Set up the Mullvad integration."""
    # Fetch Mullvad API data
    conf = config[DOMAIN]

    try:
        mullvad = MullvadAPI()
    except MullvadAPIError:
        _LOGGER.error("Mullvad setup failed - Check network connection")

    hass.data[DOMAIN] = mullvad.data

    def mullvad_update(event_time):
        """Update data from Mullvad API."""
        try:
            mullvad.update()
        except MullvadAPIError:
            _LOGGER.error("Mullvad update failed")
            return False

        hass.data[DOMAIN] = mullvad.data

    # Update sensors on time interval
    track_time_interval(hass, mullvad_update, conf[CONF_SCAN_INTERVAL])

    for component in MULLVAD_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True
