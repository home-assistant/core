"""Camera support for the Skybell HD Doorbell."""
from __future__ import annotations

import logging

import requests
from requests.models import Response
from skybellpy.device import SkybellDevice
import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera,
    CameraEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SkybellEntity
from .const import DATA_COORDINATOR, DATA_DEVICES, DOMAIN, IMAGE_ACTIVITY, IMAGE_AVATAR

_LOGGER = logging.getLogger(__name__)


# Deprecated in Home Assistant 2021.12
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[IMAGE_AVATAR]): vol.All(
            cv.ensure_list, [vol.In([IMAGE_AVATAR, IMAGE_ACTIVITY])]
        ),
        vol.Optional("activity_name"): cv.string,
        vol.Optional("avatar_name"): cv.string,
    }
)

CAMERA_TYPES: tuple[CameraEntityDescription, ...] = (
    CameraEntityDescription(key="activity", name="Last Activity"),
    CameraEntityDescription(key="avatar", name="Camera"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    skybell = hass.data[DOMAIN][entry.entry_id]

    cameras = []
    for description in CAMERA_TYPES:
        for device in skybell[DATA_DEVICES]:
            cameras.append(
                SkybellCamera(
                    skybell[DATA_COORDINATOR],
                    device,
                    description,
                    entry.entry_id,
                )
            )

    async_add_entities(cameras)


class SkybellCamera(SkybellEntity, Camera):
    """A camera implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: SkybellDevice,
        description: EntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a camera for a Skybell device."""
        super().__init__(coordinator, device, server_unique_id)
        Camera.__init__(self)
        self.entity_description = description
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

        self._url = ""
        self._response: Response | None = None

    @property
    def image_url(self) -> str:
        """Get the camera image url based on type."""
        if self.entity_description.key == IMAGE_ACTIVITY:
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
