"""Support for Abode Security System cameras."""
from datetime import timedelta
import logging

import requests

from homeassistant.components.camera import Camera
from homeassistant.util import Throttle

from . import DOMAIN as ABODE_DOMAIN, AbodeDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Abode camera devices."""
    import abodepy.helpers.constants as CONST
    import abodepy.helpers.timeline as TIMELINE

    data = hass.data[ABODE_DOMAIN]

    devices = []
    for device in data.abode.get_devices(generic_type=CONST.TYPE_CAMERA):
        if data.is_excluded(device):
            continue

        devices.append(AbodeCamera(data, device, TIMELINE.CAPTURE_IMAGE))

    data.devices.extend(devices)

    add_entities(devices)


class AbodeCamera(AbodeDevice, Camera):
    """Representation of an Abode camera."""

    def __init__(self, data, device, event):
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, data, device)
        Camera.__init__(self)
        self._event = event
        self._response = None

    async def async_added_to_hass(self):
        """Subscribe Abode events."""
        await super().async_added_to_hass()

        self.hass.async_add_job(
            self._data.abode.events.add_timeline_callback,
            self._event, self._capture_callback
        )

    def capture(self):
        """Request a new image capture."""
        return self._device.capture()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_image(self):
        """Find a new image on the timeline."""
        if self._device.refresh_image():
            self.get_image()

    def get_image(self):
        """Attempt to download the most recent capture."""
        if self._device.image_url:
            try:
                self._response = requests.get(
                    self._device.image_url, stream=True)

                self._response.raise_for_status()
            except requests.HTTPError as err:
                _LOGGER.warning("Failed to get camera image: %s", err)
                self._response = None
        else:
            self._response = None

    def camera_image(self):
        """Get a camera image."""
        self.refresh_image()

        if self._response:
            return self._response.content

        return None

    def _capture_callback(self, capture):
        """Update the image with the device then refresh device."""
        self._device.update_image_location(capture)
        self.get_image()
        self.schedule_update_ha_state()
