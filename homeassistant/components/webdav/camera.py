"""
This component models a WebDAV share full of images as a camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.webdav/
"""

import logging

import asyncio
from datetime import timedelta
from aiohttp import ClientError
import voluptuous as vol
from webdav3.client import Client
from webdav3.exceptions import WebDavException

from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, SUPPORT_ON_OFF
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval


_LOGGER = logging.getLogger(__name__)

CONF_CERTIFICATE_PATH = "ssl_client_certificate"
CONF_IMAGE_INTERVAL = "image_interval"
CONF_KEY_PATH = "ssl_client_key"

STREAM_URL = "/api/camera_proxy_stream/{0}?token={1}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_CERTIFICATE_PATH): cv.string,
        vol.Optional(CONF_KEY_PATH): cv.string,
        vol.Optional(CONF_PATH, default="/"): cv.string,
        vol.Required(CONF_IMAGE_INTERVAL): cv.time_period,
    }
)

# This must be separate from frame interval since listing can be expensive
SCAN_INTERVAL = timedelta(minutes=15)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a single webdav camera."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    path = config[CONF_PATH]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    token = config.get(CONF_TOKEN)
    cert_path = config.get(CONF_CERTIFICATE_PATH)
    key_path = config.get(CONF_KEY_PATH)
    client = Client(
        {
            "webdav_hostname": host,
            "webdav_login": username,
            "webdav_password": password,
            "webdav_token": token,
            "webdav_cert_path": cert_path,
            "webdav_key_path": key_path,
            "webdav_root": path,
        }
    )
    session = async_get_clientsession(hass)

    try:
        client.list("/")  # This will throw if we can't access the share
        add_entities(
            [WebDavCamera(name, client, session, config[CONF_IMAGE_INTERVAL])],
            update_before_add=True,
        )
    except WebDavException as exception:
        _LOGGER.warning("Failed to connect to %s: %s", client.get_url(""), exception)
        raise PlatformNotReady()


class WebDavCamera(Camera):
    """Models a WebDAV share as a camera.

    Displays image files in the share in sorted order by filename.
    """

    def __init__(self, name, client, session, image_interval):
        """Initialize the webdav camera."""
        super().__init__()
        self._available = True
        self._has_images = True
        self._client = client
        self._directory = "/"
        self._files = []
        self._image_interval = image_interval
        self._image_number = 0
        self._image = None
        self._image_lock = None
        self._name = name
        self._session = session
        self._stop_advancing = None

    async def async_added_to_hass(self):
        """Set up periodic image advancement."""
        self._image_lock = asyncio.Lock()
        self.turn_on()
        await self._advance()

    @property
    def stream_source(self):
        """Return the proxy stream path."""
        return STREAM_URL.format(self.entity_id, self.access_tokens[-1])

    @property
    def should_poll(self):
        """Return True.

        This camera needs to poll because it's pulling from a file share and
        the contents of the share may change.
        """
        return True

    @property
    def supported_features(self):
        """Return supported features."""
        return [SUPPORT_ON_OFF]

    def update(self):
        """Fetch the current contents of the file share."""
        try:
            self._files = [
                filename
                for filename in self._client.list(self._directory)
                if not filename.endswith("/")
            ]
            self._files.sort()
            if not self._available:
                self._available = True
                _LOGGER.info("Reconnected to WebDAV camera %s", self.name)
        except WebDavException as exception:
            self._files = []
            if self._available:
                self._available = False
                _LOGGER.warning(
                    "Could not open WebDAV camera %s. Message: %s", self.name, exception
                )

    @property
    def available(self):
        """Return True if the file share is available and contains images."""
        return self._available and self._has_images

    @property
    def name(self):
        """Return the name of this entity."""
        return self._name

    async def async_camera_image(self):
        """Fetch the current image from the share."""
        with await self._image_lock:
            if self._image is not None:
                return self._image
            file_name = self._image_url

            try:
                async with self._session.get(file_name) as resp:
                    resp.raise_for_status()
                    # Cache the image; that way streams don't fetch it too much
                    self._image = await resp.read()
            except ClientError as error:
                _LOGGER.warning("Failed to download %s: %s", file_name, error)
                self._available = False

            return self._image

    @property
    def is_on(self):
        """Return True if the camera is playing through files in the share."""
        return self._stop_advancing is not None

    def turn_on(self):
        """Start playing through files in the share."""
        if not self._stop_advancing:
            self._stop_advancing = async_track_time_interval(
                self.hass, self._advance, self._image_interval
            )

    def turn_off(self):
        """Stop playing through files in the share."""
        if self._stop_advancing:
            self._stop_advancing()
            self._stop_advancing = None

    @property
    def _image_filename(self):
        return self._files[self._image_number % len(self._files)]

    @property
    def _image_url(self):
        return self._client.get_url(self._directory + self._image_filename)

    async def _advance(self, _=None):
        images_checked = 0
        while images_checked < len(self._files):
            self._image_number += 1
            images_checked += 1
            content_type = self._client.get_property(
                self._image_filename, {"name": "getcontenttype", "namespace": "DAV:"}
            )
            if content_type is None or not content_type.startswith("image/"):
                continue

            with await self._image_lock:
                self._image = None
            self.async_schedule_update_ha_state()
            if not self._has_images:
                _LOGGER.info(
                    "Image files have appeared on %s", self._client.get_url("")
                )
                self._has_images = True
            return
        if self._has_images:
            _LOGGER.warning("Found no image files on %s", self._client.get_url(""))
            self._has_images = False
