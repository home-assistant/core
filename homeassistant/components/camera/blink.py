"""
Support for Blink system camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.blink/
"""
import logging

from datetime import timedelta
import requests

from homeassistant.components.blink import DOMAIN
from homeassistant.components.camera import Camera
from homeassistant.util import Throttle

DEPENDENCIES = ['blink']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Blink Camera."""
    if discovery_info is None:
        return

    data = hass.data[DOMAIN].blink
    devs = list()
    for name in data.cameras:
        devs.append(BlinkCamera(hass, config, data, name))

    add_devices(devs)


class BlinkCamera(Camera):
    """An implementation of a Blink Camera."""

    def __init__(self, hass, config, data, name):
        """Initialize a camera."""
        super().__init__()
        self.data = data
        self.hass = hass
        self._name = name
        self.notifications = self.data.cameras[self._name].notifications
        self.response = None

        _LOGGER.info("Initialized blink camera %s", self._name)

    @property
    def name(self):
        """Return the camera name."""
        return self._name

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def request_image(self):
        """Request a new image from Blink servers."""
        _LOGGER.info("Requesting new image from blink servers")
        image_url = self.check_for_motion()
        header = self.data.cameras[self._name].header
        self.response = requests.get(image_url, headers=header, stream=True)

    def check_for_motion(self):
        """Check if motion has been detected since last update."""
        self.data.refresh()
        notifs = self.data.cameras[self._name].notifications
        if notifs > self.notifications:
            # We detected motion at some point
            self.data.last_motion()
            self.notifications = notifs
            # returning motion image currently not working
            # return self.data.cameras[self._name].motion['image']
        elif notifs < self.notifications:
            self.notifications = notifs

        return self.data.camera_thumbs[self._name]

    def camera_image(self):
        """Return a still image reponse from the camera."""
        self.request_image()
        return self.response.content
