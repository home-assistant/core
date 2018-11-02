"""
Support for observing the availability and contents of a WebDAV share.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.webdav/
"""
import logging
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PATH, CONF_NAME, CONF_TOKEN
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['webdavclient3==0.9']

CONF_CERTIFICATE_PATH = "ssl_client_certificate"
CONF_KEY_PATH = "ssl_client_key"

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
    add_entities([WebDAVSensor(hass, config)])


class WebDAVSensor(Entity):
    """A sensor that monitors a WebDAV share."""

    def __init__(self, hass, config):
        """Create the sensor."""
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        token = config.get(CONF_TOKEN)
        cert_path = config.get(CONF_CERTIFICATE_PATH)
        key_path = config.get(CONF_KEY_PATH)
        self._path = config.get(CONF_PATH)

        from webdav3.client import Client

        self._client = Client({
            "webdav_hostname": self._host,
            "webdav_login": username,
            "webdav_password": password,
            "webdav_token": token,
            "webdav_cert_path": cert_path,
            "webdav_key_path": key_path,
            "webdav_root": self._path,
        })

        self._files = []
        self._available = False

    def update(self):
        """Get the current contents of the share."""
        from webdav3.exceptions import WebDavException
        try:
            self._files = [
                self._get_url(path) for path in self._client.list('/')
                if not path.endswith('/')]
            self._available = True
        except WebDavException as exception:
            self._files = []
            self._available = False
            _LOGGER.debug(
                "Could not open share %s. Message: %s",
                self.unique_id,
                str(exception))

    @property
    def name(self):
        """Return the name of this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the URL for the share."""
        return self._get_url("")

    @property
    def state(self):
        """Return true if the share is currently available."""
        return self._available

    @property
    def state_attributes(self):
        """Return the list of files on the share."""
        return {
            "files": self._files,
        }

    def _get_url(self, path):
        return "{host}{root}/{path}".format(host=self._host,
                                            root=quote(self._path),
                                            path=quote(path))
