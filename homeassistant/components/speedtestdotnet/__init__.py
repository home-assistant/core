"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DATA_UPDATED, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

CONF_SERVER_ID = "server_id"
CONF_MANUAL = "manual"

DEFAULT_INTERVAL = timedelta(hours=1)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SERVER_ID): cv.positive_int,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(CONF_MANUAL, default=False): cv.boolean,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)
                ): vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Speedtest.net component."""
    conf = config[DOMAIN]
    data = hass.data[DOMAIN] = SpeedtestData(hass, conf.get(CONF_SERVER_ID))

    if not conf[CONF_MANUAL]:
        async_track_time_interval(hass, data.update, conf[CONF_SCAN_INTERVAL])

    def update(call=None):
        """Service call to manually update the data."""
        data.update()

    hass.services.async_register(DOMAIN, "speedtest", update)

    hass.async_create_task(
        async_load_platform(
            hass, SENSOR_DOMAIN, DOMAIN, conf[CONF_MONITORED_CONDITIONS], config
        )
    )

    return True


class SpeedtestData:
    """Get the latest data from speedtest.net."""

    def __init__(self, hass, server_id):
        """Initialize the data object."""
        self.data = None
        self._hass = hass
        self._servers = [] if server_id is None else [server_id]

    def update(self, now=None):
        """Get the latest data from speedtest.net."""

        _LOGGER.debug("Executing speedtest.net speed test")
        speed = speedtest.Speedtest()
        speed.get_servers(self._servers)
        speed.get_best_server()
        speed.download()
        speed.upload()
        self.data = speed.results.dict()
        dispatcher_send(self._hass, DATA_UPDATED)
