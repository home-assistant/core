"""Support for Melnor RainCloud sprinkler water timer."""

from datetime import timedelta
import logging

from raincloudy.core import RainCloudy
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DATA_RAINCLOUD, SIGNAL_UPDATE_RAINCLOUD

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "raincloud_notification"
NOTIFICATION_TITLE = "Rain Cloud Setup"

DOMAIN = "raincloud"

SCAN_INTERVAL = timedelta(seconds=20)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Melnor RainCloud component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        raincloud = RainCloudy(username=username, password=password)
        if not raincloud.is_connected:
            raise HTTPError  # noqa: TRY301
        hass.data[DATA_RAINCLOUD] = RainCloudHub(raincloud)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Rain Cloud service: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def hub_refresh(event_time):
        """Call Raincloud hub to refresh information."""
        _LOGGER.debug("Updating RainCloud Hub component")
        hass.data[DATA_RAINCLOUD].data.update()
        dispatcher_send(hass, SIGNAL_UPDATE_RAINCLOUD)

    # Call the Raincloud API to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


class RainCloudHub:
    """Representation of a base RainCloud device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data
