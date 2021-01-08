"""Camera support for the Skybell HD Doorbell."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as SKYBELL_DOMAIN, SkybellDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)

IMAGE_AVATAR = "avatar"
IMAGE_ACTIVITY = "activity"

CONF_ACTIVITY_NAME = "activity_name"
CONF_AVATAR_NAME = "avatar_name"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[IMAGE_AVATAR]): vol.All(
            cv.ensure_list, [vol.In([IMAGE_AVATAR, IMAGE_ACTIVITY])]
        ),
        vol.Optional(CONF_ACTIVITY_NAME): cv.string,
        vol.Optional(CONF_AVATAR_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform for a Skybell device."""
    cond = config[CONF_MONITORED_CONDITIONS]
    names = {}
    names[IMAGE_ACTIVITY] = config.get(CONF_ACTIVITY_NAME)
    names[IMAGE_AVATAR] = config.get(CONF_AVATAR_NAME)
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = []
    for device in skybell.get_devices():
        for camera_type in cond:
            sensors.append(SkybellCamera(device, camera_type, names.get(camera_type)))

    add_entities(sensors, True)


class SkybellCamera(SkybellDevice, Camera):
    """A camera implementation for Skybell devices."""

    def __init__(self, device, camera_type, name=None):
        """Initialize a camera for a Skybell device."""
        self._type = camera_type
        SkybellDevice.__init__(self, device)
        Camera.__init__(self)
        if name is not None:
            self._name = f"{self._device.name} {name}"
        else:
            self._name = self._device.name
        self._url = None
        self._response = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def image_url(self):
        """Get the camera image url based on type."""
        if self._type == IMAGE_ACTIVITY:
            return self._device.activity_image
        return self._device.image

    def camera_image(self):
        """Get the latest camera image."""
        super().update()

        if self._url != self.image_url:
            self._url = self.image_url

            try:
                self._response = requests.get(self._url, stream=True, timeout=10)
            except requests.HTTPError as err:
                _LOGGER.warning("Failed to get camera image: %s", err)
                self._response = None

        if not self._response:
            return None

        return self._response.content
