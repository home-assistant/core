"""
Support for observing the availability and contents of a WebDAV share.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.webdav/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA
)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PATH, CONF_NAME, CONF_TOKEN
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['webdavclient3==0.9']

CONF_CERTIFICATE_PATH = "ssl_client_certificate"
CONF_KEY_PATH = "ssl_client_key"
DEVICE_CLASS = "connectivity"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_TOKEN): cv.string,
    vol.Optional(CONF_CERTIFICATE_PATH): cv.string,
    vol.Optional(CONF_KEY_PATH): cv.string,
    vol.Optional(CONF_PATH, default="/"): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a single WebDAV share."""
    from webdav3.client import Client
    from webdav3.exceptions import WebDavException

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    path = config.get(CONF_PATH)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    token = config.get(CONF_TOKEN)
    cert_path = config.get(CONF_CERTIFICATE_PATH)
    key_path = config.get(CONF_KEY_PATH)
    client = Client({
        "webdav_hostname": host,
        "webdav_login": username,
        "webdav_password": password,
        "webdav_token": token,
        "webdav_cert_path": cert_path,
        "webdav_key_path": key_path,
        "webdav_root": path,
    })

    try:
        client.list('/')  # This will throw if we can't access the share
        add_entities([WebDAVSensor(name, client)], update_before_add=True)
    except WebDavException as exception:
        _LOGGER.error(
            "Failed to connect to %s: %s",
            client.get_url(""),
            exception)


class WebDAVSensor(BinarySensorDevice):
    """A sensor that monitors a WebDAV share."""

    def __init__(self, name, client):
        """Create the sensor."""
        self._name = name
        self._client = client

        self._files = []
        self._available = False

    def update(self):
        """Get the current contents of the share."""
        from webdav3.exceptions import WebDavException
        try:
            directory = '/'
            self._files = [
                self._client.get_url(directory + filename)
                for filename in self._client.list(directory)
                if not filename.endswith('/')]
            self._available = True
        except WebDavException as exception:
            self._files = []
            self._available = False
            _LOGGER.debug(
                "Could not open share %s. Message: %s",
                self.unique_id,
                exception)

    @property
    def name(self):
        """Return the name of this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the URL for the share."""
        return self._client.get_url("")

    @property
    def is_on(self):
        """Return true if the share is currently available."""
        return self._available

    @property
    def device_class(self):
        """Return the device class of this sensor."""
        return DEVICE_CLASS

    @property
    def device_state_attributes(self):
        """Return the list of files on the share."""
        return {
            "files": self._files,
        }
