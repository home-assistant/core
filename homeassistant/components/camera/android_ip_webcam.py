"""
Support for IP Webcam, an Android app that acts as a full-featured webcam.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.android_ip_webcam/
"""
import asyncio
import logging
from contextlib import closing

import aiohttp
import async_timeout
import requests
from requests.auth import HTTPBasicAuth

from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_stream)
from homeassistant.components import android_ip_webcam

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})

DEPENDENCIES = ['android_ip_webcam']


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup an IP Webcam Camera."""
    if discovery_info is None:
        return
    devices = hass.data[android_ip_webcam.DATA_IP_WEBCAM]
    cameras = [IPWebcamCamera(hass, device)
               for key, device in devices.items()]
    yield from async_add_devices(cameras, True)


def extract_image_from_mjpeg(stream):
    """Take in a MJPEG stream object, return the jpg from it."""
    data = b''
    for chunk in stream:
        data += chunk
        jpg_start = data.find(b'\xff\xd8')
        jpg_end = data.find(b'\xff\xd9')
        if jpg_start != -1 and jpg_end != -1:
            jpg = data[jpg_start:jpg_end + 2]
            return jpg


class IPWebcamCamera(Camera):
    """An implementation of an IP camera that is reachable over a URL."""

    def __init__(self, hass, device):
        """Initialize a IP Webcam camera."""
        super(IPWebcamCamera, self).__init__()
        self._device = device
        self._name = self._device.name
        self._username = self._device.username
        self._password = self._device.password
        self._mjpeg_url = '{}/{}'.format(self._device.base_url, 'video')
        self._still_image_url = '{}/{}'.format(self._device.base_url,
                                               'photo.jpg')

        self._auth = None
        if self._username and self._password:
            self._auth = aiohttp.BasicAuth(self._username,
                                           password=self._password)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        websession = async_get_clientsession(self.hass)
        response = None
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = yield from websession.get(
                    self._still_image_url, auth=self._auth)

                image = yield from response.read()
                return image

        except asyncio.TimeoutError:
            _LOGGER.error('Timeout getting camera image')

        except (aiohttp.errors.ClientError,
                aiohttp.errors.ClientDisconnectedError) as err:
            _LOGGER.error('Error getting new camera image: %s', err)

        finally:
            if response is not None:
                yield from response.release()

    def camera_image(self):
        """Return a still image response from the camera."""
        if self._username and self._password:
            auth = HTTPBasicAuth(self._username, self._password)
            req = requests.get(
                self._mjpeg_url, auth=auth, stream=True, timeout=10)
        else:
            req = requests.get(self._mjpeg_url, stream=True, timeout=10)

        with closing(req) as response:
            return extract_image_from_mjpeg(response.iter_content(102400))

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        # connect to stream
        websession = async_get_clientsession(self.hass)
        stream_coro = websession.get(self._mjpeg_url, auth=self._auth)

        yield from async_aiohttp_proxy_stream(self.hass, request, stream_coro)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device.device_state_attributes

    def update(self):
        """Update the state."""
        self._device.update()
