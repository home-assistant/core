"""
Support for monitoring NZBGet nzb client.

Uses NZBGet's JSON-RPC API to query for monitored variables.
"""
import logging
from datetime import timedelta
import requests

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = []
SENSOR_TYPES = {
    "ArticleCacheMB": ("Article Cache", "MB"),
    "AverageDownloadRate": ("Average Speed", "MB/s"),
    "DownloadRate": ("Speed", "MB/s"),
    "DownloadPaused": ("Download Paused", None),
    "FreeDiskSpaceMB": ("Disk Free", "MB"),
    "PostPaused": ("Post Processing Paused", None),
    "RemainingSizeMB": ("Queue Size", "MB"),
}
DEFAULT_TYPES = [
    "DownloadRate",
    "DownloadPaused",
    "RemainingSizeMB",
]

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up nzbget sensors."""
    base_url = config.get("base_url")
    name = config.get("name", "NZBGet")
    username = config.get("username")
    password = config.get("password")
    monitored_types = config.get("monitored_variables", DEFAULT_TYPES)

    if not base_url:
        _LOGGER.error("Missing base_url config for NzbGet")
        return False

    url = "{}/jsonrpc".format(base_url)

    try:
        nzbgetapi = NZBGetAPI(api_url=url,
                              username=username,
                              password=password)
        nzbgetapi.update()
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError) as conn_err:
        _LOGGER.error("Error setting up NZBGet API: %r", conn_err)
        return False

    devices = []
    for ng_type in monitored_types:
        if ng_type in SENSOR_TYPES:
            new_sensor = NZBGetSensor(api=nzbgetapi,
                                      sensor_type=ng_type,
                                      client_name=name)
            devices.append(new_sensor)
        else:
            _LOGGER.error("Unknown nzbget sensor type: %s", ng_type)
    add_devices(devices)


class NZBGetAPI(object):
    """Simple json-rpc wrapper for nzbget's api."""

    def __init__(self, api_url, username=None, password=None):
        """Initialize NZBGet API and set headers needed later."""
        self.api_url = api_url
        self.status = None
        self.headers = {'content-type': 'application/json'}
        if username is not None and password is not None:
            self.auth = (username, password)
        else:
            self.auth = None
        # set the intial state
        self.update()

    def post(self, method, params=None):
        """Send a post request, and return the response as a dict."""
        payload = {"method": method}
        if params:
            payload['params'] = params
        try:
            response = requests.post(self.api_url,
                                     json=payload,
                                     auth=self.auth,
                                     headers=self.headers,
                                     timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as conn_exc:
            _LOGGER.error("Failed to update nzbget status from %s.  Error: %s",
                          self.api_url, conn_exc)
            raise

    @Throttle(timedelta(seconds=5))
    def update(self):
        """Update cached response."""
        try:
            self.status = self.post('status')['result']
        except requests.exceptions.ConnectionError:
            # failed to update status - exception already logged in self.post
            raise


class NZBGetSensor(Entity):
    """Represents an NZBGet sensor."""

    def __init__(self, api, sensor_type, client_name):
        """Initialize a new NZBGet sensor."""
        self._name = client_name + ' ' + SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.client_name = client_name
        self.api = api
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        # Set initial state
        self.update()
        _LOGGER.debug("created nzbget sensor %r", self)

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
        """Unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update state of sensor."""
        try:
            self.api.update()
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return

        if self.api.status is None:
            _LOGGER.debug("update of %s requested, but no status is available",
                          self._name)
            return

        value = self.api.status.get(self.type)
        if value is None:
            _LOGGER.warning("unable to locate value for %s", self.type)
            return

        if "DownloadRate" in self.type and value > 0:
            # Convert download rate from bytes/s to mb/s
            self._state = value / 1024 / 1024
        else:
            self._state = value
