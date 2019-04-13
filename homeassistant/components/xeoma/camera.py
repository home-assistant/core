"""Support for Xeoma Cameras."""
import logging

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CAMERAS = 'cameras'
CONF_HIDE = 'hide'
CONF_IMAGE_NAME = 'image_name'
CONF_NEW_VERSION = 'new_version'
CONF_VIEWER_PASSWORD = 'viewer_password'
CONF_VIEWER_USERNAME = 'viewer_username'

CAMERAS_SCHEMA = vol.Schema({
    vol.Required(CONF_IMAGE_NAME): cv.string,
    vol.Optional(CONF_HIDE, default=False): cv.boolean,
    vol.Optional(CONF_NAME): cv.string,
}, required=False)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_CAMERAS):
        vol.Schema(vol.All(cv.ensure_list, [CAMERAS_SCHEMA])),
    vol.Optional(CONF_NEW_VERSION, default=True): cv.boolean,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Discover and setup Xeoma Cameras."""
    from pyxeoma.xeoma import Xeoma, XeomaError

    host = config[CONF_HOST]
    login = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    xeoma = Xeoma(host, login, password)

    try:
        await xeoma.async_test_connection()
        discovered_image_names = await xeoma.async_get_image_names()
        discovered_cameras = [
            {
                CONF_IMAGE_NAME: image_name,
                CONF_HIDE: False,
                CONF_NAME: image_name,
                CONF_VIEWER_USERNAME: username,
                CONF_VIEWER_PASSWORD: pw

            }
            for image_name, username, pw in discovered_image_names
        ]

        for cam in config.get(CONF_CAMERAS, []):
            camera = next(
                (dc for dc in discovered_cameras
                 if dc[CONF_IMAGE_NAME] == cam[CONF_IMAGE_NAME]), None)

            if camera is not None:
                if CONF_NAME in cam:
                    camera[CONF_NAME] = cam[CONF_NAME]
                if CONF_HIDE in cam:
                    camera[CONF_HIDE] = cam[CONF_HIDE]

        cameras = list(filter(lambda c: not c[CONF_HIDE], discovered_cameras))
        async_add_entities(
            [XeomaCamera(xeoma, camera[CONF_IMAGE_NAME], camera[CONF_NAME],
                         camera[CONF_VIEWER_USERNAME],
                         camera[CONF_VIEWER_PASSWORD]) for camera in cameras])
    except XeomaError as err:
        _LOGGER.error("Error: %s", err.message)
        return


class XeomaCamera(Camera):
    """Implementation of a Xeoma camera."""

    def __init__(self, xeoma, image, name, username, password):
        """Initialize a Xeoma camera."""
        super().__init__()
        self._xeoma = xeoma
        self._name = name
        self._image = image
        self._username = username
        self._password = password
        self._last_image = None

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        from pyxeoma.xeoma import XeomaError
        try:
            image = await self._xeoma.async_get_camera_image(
                self._image, self._username, self._password)
            self._last_image = image
        except XeomaError as err:
            _LOGGER.error("Error fetching image: %s", err.message)

        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name
