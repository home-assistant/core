"""Camera support for the Skybell HD Doorbell."""
from __future__ import annotations

import logging

import requests
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import SkybellDevice
from .const import (
    CAMERA_TYPES,
    CONF_ACTIVITY_NAME,
    CONF_AVATAR_NAME,
    DATA_COORDINATOR,
    DATA_DEVICES,
    DOMAIN,
    IMAGE_ACTIVITY,
    IMAGE_AVATAR,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[IMAGE_AVATAR]): vol.All(
            cv.ensure_list, [vol.In([IMAGE_AVATAR, IMAGE_ACTIVITY])]
        ),
        vol.Optional(CONF_ACTIVITY_NAME): cv.string,
        vol.Optional(CONF_AVATAR_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Skybell switch."""
    skybell_data = hass.data[DOMAIN][entry.entry_id]

    cameras = []
    for camera in CAMERA_TYPES:
        for device in skybell_data[DATA_DEVICES]:
            cameras.append(
                SkybellCamera(
                    skybell_data[DATA_COORDINATOR],
                    device,
                    camera,
                    entry.entry_id,
                )
            )

    async_add_entities(cameras)


class SkybellCamera(SkybellDevice, Camera):
    """A camera implementation for Skybell devices."""

    def __init__(
        self,
        coordinator,
        device,
        camera,
        server_unique_id,
    ):
        """Initialize a camera for a Skybell device."""
        super().__init__(coordinator, device, camera, server_unique_id)
        Camera.__init__(self)
        if CAMERA_TYPES[camera] is not None:
            self._name = f"{device.name} {CAMERA_TYPES[camera]}"
        else:
            self._name = device.name

        self._camera = camera
        self._device = device
        self._url = None
        self._response = None

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the camera."""
        return f"{self._server_unique_id}/{self._camera}"

    @property
    def image_url(self):
        """Get the camera image url based on type."""
        if self._camera == IMAGE_ACTIVITY:
            return self._device.activity_image
        return self._device.image

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get the latest camera image."""
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
