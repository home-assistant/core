"""Support for Hydrawise cloud."""

from hydrawiser.core import Hydrawiser
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_HYDRAWISE,
    DOMAIN,
    LOGGER,
    NOTIFICATION_ID,
    NOTIFICATION_TITLE,
    SCAN_INTERVAL,
    SIGNAL_UPDATE_HYDRAWISE,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hunter Hydrawise component."""
    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        hydrawise = Hydrawiser(user_token=access_token)
        hass.data[DATA_HYDRAWISE] = HydrawiseHub(hydrawise)
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def hub_refresh(event_time):
        """Call Hydrawise hub to refresh information."""
        LOGGER.debug("Updating Hydrawise Hub component")
        hass.data[DATA_HYDRAWISE].data.update_controller_info()
        dispatcher_send(hass, SIGNAL_UPDATE_HYDRAWISE)

    # Call the Hydrawise API to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


class HydrawiseHub:
    """Representation of a base Hydrawise device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data
