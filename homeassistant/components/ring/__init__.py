"""Support for Ring Doorbell/Chimes."""
import logging

from datetime import timedelta
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import dispatcher_send
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = "ring_notification"
NOTIFICATION_TITLE = "Ring Setup"

DATA_RING_DOORBELLS = "ring_doorbells"
DATA_RING_STICKUP_CAMS = "ring_stickup_cams"
DATA_RING_CHIMES = "ring_chimes"

DOMAIN = "ring"
DEFAULT_CACHEDB = ".ring_cache.pickle"
DEFAULT_ENTITY_NAMESPACE = "ring"
SIGNAL_UPDATE_RING = "ring_update"

SCAN_INTERVAL = timedelta(seconds=10)

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
    """Set up the Ring component."""
    conf = config[DOMAIN]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    scan_interval = conf[CONF_SCAN_INTERVAL]

    try:
        from ring_doorbell import Ring

        cache = hass.config.path(DEFAULT_CACHEDB)
        ring = Ring(username=username, password=password, cache_file=cache)
        if not ring.is_connected:
            return False
        hass.data[DATA_RING_CHIMES] = chimes = ring.chimes
        hass.data[DATA_RING_DOORBELLS] = doorbells = ring.doorbells
        hass.data[DATA_RING_STICKUP_CAMS] = stickup_cams = ring.stickup_cams

        ring_devices = chimes + doorbells + stickup_cams

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def service_hub_refresh(service):
        hub_refresh()

    def timer_hub_refresh(event_time):
        hub_refresh()

    def hub_refresh():
        """Call ring to refresh information."""
        _LOGGER.debug("Updating Ring Hub component")

        for camera in ring_devices:
            _LOGGER.debug("Updating camera %s", camera.name)
            camera.update()

        dispatcher_send(hass, SIGNAL_UPDATE_RING)

    # register service
    hass.services.register(DOMAIN, "update", service_hub_refresh)

    # register scan interval for ring
    track_time_interval(hass, timer_hub_refresh, scan_interval)

    return True
