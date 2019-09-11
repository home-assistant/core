"""The nzbget component."""
from datetime import timedelta
import logging

import pynzbgetapi
import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nzbget"
DATA_NZBGET = "data_nzbget"
DATA_UPDATED = "nzbget_data_updated"

DEFAULT_NAME = "NZBGet"
DEFAULT_PORT = 6789

DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)

SENSOR_TYPES = {
    "article_cache": ["ArticleCacheMB", "Article Cache", "MB"],
    "average_download_rate": ["AverageDownloadRate", "Average Speed", "MB/s"],
    "download_paused": ["DownloadPaused", "Download Paused", None],
    "download_rate": ["DownloadRate", "Speed", "MB/s"],
    "download_size": ["DownloadedSizeMB", "Size", "MB"],
    "free_disk_space": ["FreeDiskSpaceMB", "Disk Free", "MB"],
    "post_paused": ["PostPaused", "Post Processing Paused", None],
    "remaining_size": ["RemainingSizeMB", "Queue Size", "MB"],
    "uptime": ["UpTimeSec", "Uptime", "min"],
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(
                    CONF_MONITORED_VARIABLES, default=["download_rate"]
                ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
                vol.Optional(CONF_SSL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the NZBGet sensors."""
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    ssl = "s" if config[DOMAIN][CONF_SSL] else ""
    name = config[DOMAIN][CONF_NAME]
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    monitored_types = config[DOMAIN].get(CONF_MONITORED_VARIABLES)
    scan_interval = config[DOMAIN].get(CONF_SCAN_INTERVAL)

    try:
        nzbget_api = pynzbgetapi.NZBGetAPI(host, username, password, ssl, ssl, port)
        nzbget_api.version()
        _LOGGER.debug("Successfully validated NZBGet API connection.")
    except pynzbgetapi.NZBGetAPIException as conn_err:
        _LOGGER.error("Error setting up NZBGet API: %s", conn_err)
        return False

    nzbget_data = hass.data[DATA_NZBGET] = NZBGetData(hass, nzbget_api)
    nzbget_data.update()

    def refresh(event_time):
        """Get the latest data from NZBGet."""
        nzbget_data.update()

    track_time_interval(hass, refresh, scan_interval)

    sensorconfig = {"sensors": monitored_types, "client_name": name}

    hass.helpers.discovery.load_platform("sensor", DOMAIN, sensorconfig, config)

    return True


class NZBGetData:
    """Get the latest data and update the states."""

    def __init__(self, hass, api):
        """Initialize the NZBGet RPC API."""
        self.hass = hass
        self.status = None
        self.available = True
        self._api = api

    def update(self):
        """Get the latest data from NZBGet instance."""
        try:
            self.status = self._api.status()
            dispatcher_send(self.hass, DATA_UPDATED)
        except requests.exceptions.ConnectionError:
            self.available = False
            _LOGGER.error("Unable to refresh NZBGet data")
