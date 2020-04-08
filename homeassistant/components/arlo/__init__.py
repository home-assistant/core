"""Support for Netgear Arlo IP cameras."""
from datetime import timedelta
import logging

from pyarlo import PyArlo
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by arlo.netgear.com"

DATA_ARLO = "data_arlo"
DEFAULT_BRAND = "Netgear Arlo"
DOMAIN = "arlo"

NOTIFICATION_ID = "arlo_notification"
NOTIFICATION_TITLE = "Arlo Component Setup"

SCAN_INTERVAL = timedelta(seconds=60)

SIGNAL_UPDATE_ARLO = "arlo_update"

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


def setup(hass, config):
    """Set up an Arlo component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:

        arlo = PyArlo(username, password, preload=False)
        if not arlo.is_connected:
            return False

        # assign refresh period to base station thread
        arlo_base_station = next((station for station in arlo.base_stations), None)

        if arlo_base_station is not None:
            arlo_base_station.refresh_rate = scan_interval.total_seconds()
        elif not arlo.cameras:
            _LOGGER.error("No Arlo camera or base station available.")
            return False

        hass.data[DATA_ARLO] = arlo

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Netgear Arlo: %s", str(ex))
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def hub_refresh(event_time):
        """Call ArloHub to refresh information."""
        _LOGGER.debug("Updating Arlo Hub component")
        hass.data[DATA_ARLO].update(update_cameras=True, update_base_station=True)
        dispatcher_send(hass, SIGNAL_UPDATE_ARLO)

    # register service
    hass.services.register(DOMAIN, "update", hub_refresh)

    # register scan interval for ArloHub
    track_time_interval(hass, hub_refresh, scan_interval)
    return True
