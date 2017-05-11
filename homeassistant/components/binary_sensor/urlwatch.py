"""
This component provides support for detecting changes to url content.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.urlwatch/
"""
import logging
from datetime import timedelta
import hashlib
from os.path import exists
from threading import Lock
import pickle
import voluptuous as vol
import requests

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)

from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, CONF_VERIFY_SSL)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['beautifulsoup4==4.6.0']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

DOMAIN = 'urlwatch'

DEFAULT_NAME = 'URLWatch'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the URL watch sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    method = 'GET'
    verify_ssl = config.get(CONF_VERIFY_SSL)

    data_file = hass.config.path("{}.pickle".format(DOMAIN))
    storage = StoredData(data_file)

    content = HttpData(method, resource, verify_ssl)
    content.update()

    if content.data is None:
        _LOGGER.error("Unable to fetch data from %s", resource)
        return False

    add_devices([
        URLWatchBinarySensor(hass, content, name, storage)
    ])


class URLWatchBinarySensor(BinarySensorDevice):
    """Representation of a URL watch sensor."""

    def __init__(self, hass, content, name, storage):
        """Initialize a URL watch sensor."""
        self.content = content
        self._name = name
        self._state = None
        self._storage = storage
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from the source and updates the state."""
        # Default is no change
        self._state = False

        self.content.update()

        from bs4 import BeautifulSoup

        _LOGGER.debug("Fetching content from url %s", self.content.url)

        raw_data = BeautifulSoup(self.content.data, 'html.parser')
        _LOGGER.debug("Url contained %s", raw_data)

        current_hash = hashlib.sha1(raw_data.encode()).hexdigest()
        _LOGGER.debug("Calculated hash is %s", current_hash)

        self._last_hash = self._storage.get_hash(self.content.url)

        if self._last_hash:
            if self._last_hash == current_hash:
                self._state = False
            else:
                self._storage.put_hash(self.content.url, current_hash)
                self._state = True
        else:
            self._storage.put_hash(self.content.url, current_hash)


class StoredData(object):
    """Abstraction over pickle data storage."""

    def __init__(self, data_file):
        """Initialize pickle data storage."""
        self._data_file = data_file
        self._lock = Lock()
        self._data = {}
        self._fetch_data()

    def _fetch_data(self):
        """Fetch data stored into pickle file."""
        if exists(self._data_file):
            try:
                _LOGGER.debug("Fetching data from file %s", self._data_file)
                with self._lock, open(self._data_file, 'rb') as myfile:
                    self._data = pickle.load(myfile) or {}
            # pylint: disable=bare-except
            except:
                _LOGGER.error("Error loading data from pickled file %s",
                              self._data_file)

    def get_hash(self, url):
        """Return stored hash for given url."""
        self._fetch_data()
        return self._data.get(url)

    def put_hash(self, url, new_hash):
        """Update hash for given URL."""
        self._fetch_data()
        with self._lock, open(self._data_file, 'wb') as myfile:
            self._data.update({url: new_hash})
            _LOGGER.debug("Overwriting hash for url %s in storage file %s",
                          url, self._data_file)
            try:
                pickle.dump(self._data, myfile)
            # pylint: disable=bare-except
            except:
                _LOGGER.error(
                    "Error saving pickled data to %s", self._data_file)


# pylint: disable=too-few-public-methods
class HttpData(object):
    """Class for handling the data retrieval."""

    def __init__(self, method, resource, verify_ssl):
        """Initialize the data object."""
        self.url = resource
        self._request = requests.Request(
            method, self.url, headers=None, auth=None, data=None).prepare()
        self._verify_ssl = verify_ssl
        self.data = None

    def update(self):
        """Get the latest data from REST service with provided method."""
        try:
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=10, verify=self._verify_ssl)

            self.data = response.text
        except requests.exceptions.RequestException:
            _LOGGER.error("Error fetching data: %s", self._request)
            self.data = None
