"""The nzbget component."""
from datetime import timedelta
import logging

import pynzbgetapi
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
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

ATTR_SPEED = "speed"

DOMAIN = "nzbget"
DATA_NZBGET = "data_nzbget"
DATA_UPDATED = "nzbget_data_updated"

DEFAULT_NAME = "NZBGet"
DEFAULT_PORT = 6789
DEFAULT_SPEED_LIMIT = 1000  # 1 Megabyte/Sec

DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)

SERVICE_PAUSE = "pause"
SERVICE_RESUME = "resume"
SERVICE_SET_SPEED = "set_speed"

SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.positive_int}
)

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
    scan_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    try:
        nzbget_api = pynzbgetapi.NZBGetAPI(host, username, password, ssl, ssl, port)
        nzbget_api.version()
    except pynzbgetapi.NZBGetAPIException as conn_err:
        _LOGGER.error("Error setting up NZBGet API: %s", conn_err)
        return False

    _LOGGER.debug("Successfully validated NZBGet API connection")

    nzbget_data = hass.data[DATA_NZBGET] = NZBGetData(hass, nzbget_api)
    nzbget_data.update()

    def service_handler(service):
        """Handle service calls."""
        if service.service == SERVICE_PAUSE:
            nzbget_data.pause_download()
        elif service.service == SERVICE_RESUME:
            nzbget_data.resume_download()
        elif service.service == SERVICE_SET_SPEED:
            limit = service.data[ATTR_SPEED]
            nzbget_data.rate(limit)

    hass.services.register(
        DOMAIN, SERVICE_PAUSE, service_handler, schema=vol.Schema({})
    )

    hass.services.register(
        DOMAIN, SERVICE_RESUME, service_handler, schema=vol.Schema({})
    )

    hass.services.register(
        DOMAIN, SERVICE_SET_SPEED, service_handler, schema=SPEED_LIMIT_SCHEMA
    )

    def refresh(event_time):
        """Get the latest data from NZBGet."""
        nzbget_data.update()

    track_time_interval(hass, refresh, scan_interval)

    sensorconfig = {"client_name": name}

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
            self.available = True
            dispatcher_send(self.hass, DATA_UPDATED)
        except pynzbgetapi.NZBGetAPIException as err:
            self.available = False
            _LOGGER.error("Unable to refresh NZBGet data: %s", err)

    def pause_download(self):
        """Pause download queue."""

        try:
            self._api.pausedownload()
        except pynzbgetapi.NZBGetAPIException as err:
            _LOGGER.error("Unable to pause queue: %s", err)

    def resume_download(self):
        """Resume download queue."""

        try:
            self._api.resumedownload()
        except pynzbgetapi.NZBGetAPIException as err:
            _LOGGER.error("Unable to resume download queue: %s", err)

    def rate(self, limit):
        """Set download speed."""

        try:
            if not self._api.rate(limit):
                _LOGGER.error("Limit was out of range")
        except pynzbgetapi.NZBGetAPIException as err:
            _LOGGER.error("Unable to set download speed: %s", err)
