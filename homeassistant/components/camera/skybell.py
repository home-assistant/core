"""
Camera support for the Skybell HD Doorbell.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.skybell/
"""
from datetime import timedelta
import logging

import requests

from homeassistant.components.camera import Camera
from homeassistant.components.skybell import (
    DOMAIN as SKYBELL_DOMAIN, SkybellDevice)

DEPENDENCIES = ['skybell']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a Skybell device."""
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = []
    for device in skybell.get_devices():
        sensors.append(SkybellCamera(device))

    add_entities(sensors, True)


class SkybellCamera(SkybellDevice, Camera):
    """A camera implementation for Skybell devices."""

    def __init__(self, device):
        """Initialize a camera for a Skybell device."""
        SkybellDevice.__init__(self, device)
        Camera.__init__(self)
        self._name = self._device.name
        self._url = None
        self._response = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def camera_image(self):
        """Get the latest camera image."""
        super().update()

        if self._url != self._device.image:
            self._url = self._device.image

            try:
                self._response = requests.get(
                    self._url, stream=True, timeout=10)
            except requests.HTTPError as err:
                _LOGGER.warning("Failed to get camera image: %s", err)
                self._response = None

        if not self._response:
            return None

        return self._response.content
