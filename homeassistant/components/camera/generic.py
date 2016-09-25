"""
Support for IP Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.generic/
"""
import logging

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.exceptions import TemplateError
from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers import config_validation as cv, template

_LOGGER = logging.getLogger(__name__)

CONF_LIMIT_REFETCH_TO_URL_CHANGE = 'limit_refetch_to_url_change'
CONF_STILL_IMAGE_URL = 'still_image_url'

DEFAULT_NAME = 'Generic Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STILL_IMAGE_URL): vol.Any(cv.url, cv.template),
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_LIMIT_REFETCH_TO_URL_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a generic IP Camera."""
    add_devices([GenericCamera(hass, config)])


# pylint: disable=too-many-instance-attributes
class GenericCamera(Camera):
    """A generic implementation of an IP camera."""

    def __init__(self, hass, device_info):
        """Initialize a generic camera."""
        super().__init__()
        self.hass = hass
        self._name = device_info.get(CONF_NAME)
        self._still_image_url = template.compile_template(
            hass, device_info[CONF_STILL_IMAGE_URL])
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]

        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            if device_info[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION:
                self._auth = HTTPDigestAuth(username, password)
            else:
                self._auth = HTTPBasicAuth(username, password)
        else:
            self._auth = None

        self._last_url = None
        self._last_image = None

    def camera_image(self):
        """Return a still image response from the camera."""
        try:
            url = template.render(self.hass, self._still_image_url)
        except TemplateError as err:
            _LOGGER.error('Error parsing template %s: %s',
                          self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        kwargs = {'timeout': 10, 'auth': self._auth}

        try:
            response = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as error:
            _LOGGER.error('Error getting camera image: %s', error)
            return None

        self._last_url = url
        self._last_image = response.content
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
