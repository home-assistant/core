"""
Support for monitoring NZBGet NZB client.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nzbget/
"""
from datetime import timedelta
import logging

from aiohttp.hdrs import CONTENT_TYPE
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_SSL, CONF_HOST, CONF_NAME, CONF_PORT, CONF_PASSWORD, CONF_USERNAME,
    CONTENT_TYPE_JSON, CONF_MONITORED_VARIABLES)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NZBGet'
DEFAULT_PORT = 6789

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

SENSOR_TYPES = {
    'article_cache': ['ArticleCacheMB', 'Article Cache', 'MB'],
    'average_download_rate': ['AverageDownloadRate', 'Average Speed', 'MB/s'],
    'download_paused': ['DownloadPaused', 'Download Paused', None],
    'download_rate': ['DownloadRate', 'Speed', 'MB/s'],
    'download_size': ['DownloadedSizeMB', 'Size', 'MB'],
    'free_disk_space': ['FreeDiskSpaceMB', 'Disk Free', 'MB'],
    'post_paused': ['PostPaused', 'Post Processing Paused', None],
    'remaining_size': ['RemainingSizeMB', 'Queue Size', 'MB'],
    'uptime': ['UpTimeSec', 'Uptime', 'min'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['download_rate']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NZBGet sensors."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    ssl = 's' if config.get(CONF_SSL) else ''
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    monitored_types = config.get(CONF_MONITORED_VARIABLES)

    url = "http{}://{}:{}/jsonrpc".format(ssl, host, port)

    try:
        nzbgetapi = NZBGetAPI(
            api_url=url, username=username, password=password)
        nzbgetapi.update()
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError) as conn_err:
        _LOGGER.error("Error setting up NZBGet API: %s", conn_err)
        return False

    devices = []
    for ng_type in monitored_types:
        new_sensor = NZBGetSensor(
            api=nzbgetapi, sensor_type=SENSOR_TYPES.get(ng_type),
            client_name=name)
        devices.append(new_sensor)

    add_entities(devices)


class NZBGetSensor(Entity):
    """Representation of a NZBGet sensor."""

    def __init__(self, api, sensor_type, client_name):
        """Initialize a new NZBGet sensor."""
        self._name = '{} {}'.format(client_name, sensor_type[1])
        self.type = sensor_type[0]
        self.client_name = client_name
        self.api = api
        self._state = None
        self._unit_of_measurement = sensor_type[2]
        self.update()
        _LOGGER.debug("Created NZBGet sensor: %s", self.type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update state of sensor."""
        try:
            self.api.update()
        except requests.exceptions.ConnectionError:
            # Error calling the API, already logged in api.update()
            return

        if self.api.status is None:
            _LOGGER.debug("Update of %s requested, but no status is available",
                          self._name)
            return

        value = self.api.status.get(self.type)
        if value is None:
            _LOGGER.warning("Unable to locate value for %s", self.type)
            return

        if "DownloadRate" in self.type and value > 0:
            # Convert download rate from Bytes/s to MBytes/s
            self._state = round(value / 2**20, 2)
        elif "UpTimeSec" in self.type and value > 0:
            # Convert uptime from seconds to minutes
            self._state = round(value / 60, 2)
        else:
            self._state = value


class NZBGetAPI:
    """Simple JSON-RPC wrapper for NZBGet's API."""

    def __init__(self, api_url, username=None, password=None):
        """Initialize NZBGet API and set headers needed later."""
        self.api_url = api_url
        self.status = None
        self.headers = {CONTENT_TYPE: CONTENT_TYPE_JSON}

        if username is not None and password is not None:
            self.auth = (username, password)
        else:
            self.auth = None
        self.update()

    def post(self, method, params=None):
        """Send a POST request and return the response as a dict."""
        payload = {'method': method}

        if params:
            payload['params'] = params
        try:
            response = requests.post(
                self.api_url, json=payload, auth=self.auth,
                headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as conn_exc:
            _LOGGER.error("Failed to update NZBGet status from %s. Error: %s",
                          self.api_url, conn_exc)
            raise

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update cached response."""
        self.status = self.post('status')['result']
