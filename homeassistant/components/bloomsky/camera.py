"""Support for a camera of a BloomSky weather station."""

from __future__ import annotations

import logging

import requests

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up access to BloomSky cameras."""
    if discovery_info is not None:
        return

    bloomsky = hass.data[DOMAIN]

    for device in bloomsky.devices.values():
        add_entities([BloomSkyCamera(bloomsky, device)])


class BloomSkyCamera(Camera):
    """Representation of the images published from the BloomSky's camera."""

    def __init__(self, bs, device):
        """Initialize access to the BloomSky camera images."""
        super().__init__()
        self._attr_name = device["DeviceName"]
        self._id = device["DeviceID"]
        self._bloomsky = bs
        self._url = ""
        self._last_url = ""
        # last_image will store images as they are downloaded so that the
        # frequent updates in home-assistant don't keep poking the server
        # to download the same image over and over.
        self._last_image = ""
        self._logger = logging.getLogger(__name__)
        self._attr_unique_id = self._id

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Update the camera's image if it has changed."""
        try:
            self._url = self._bloomsky.devices[self._id]["Data"]["ImageURL"]
            self._bloomsky.refresh_devices()
            # If the URL hasn't changed then the image hasn't changed.
            if self._url != self._last_url:
                response = requests.get(self._url, timeout=10)
                self._last_url = self._url
                self._last_image = response.content
        except requests.exceptions.RequestException as error:
            self._logger.error("Error getting bloomsky image: %s", error)
            return None

        return self._last_image
