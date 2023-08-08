"""Support for Prosegur cameras."""
from __future__ import annotations

import logging

from pyprosegur.auth import Auth
from pyprosegur.exceptions import ProsegurException
from pyprosegur.installation import Camera as InstallationCamera, Installation

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import DOMAIN
from .const import SERVICE_REQUEST_IMAGE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Prosegur camera platform."""

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_REQUEST_IMAGE,
        {},
        "async_request_image",
    )

    _installation = await Installation.retrieve(
        hass.data[DOMAIN][entry.entry_id], entry.data["contract"]
    )

    async_add_entities(
        [
            ProsegurCamera(_installation, camera, hass.data[DOMAIN][entry.entry_id])
            for camera in _installation.cameras
        ],
        update_before_add=True,
    )


class ProsegurCamera(Camera):
    """Representation of a Smart Prosegur Camera."""

    def __init__(
        self, installation: Installation, camera: InstallationCamera, auth: Auth
    ) -> None:
        """Initialize Prosegur Camera component."""
        Camera.__init__(self)

        self._installation = installation
        self._camera = camera
        self._auth = auth
        self._attr_name = camera.description
        self._attr_unique_id = f"{self._installation.contract} {camera.id}"

        self._attr_device_info = DeviceInfo(
            name=self._camera.description,
            manufacturer="Prosegur",
            model="smart camera",
            identifiers={(DOMAIN, self._installation.contract)},
            configuration_url="https://smart.prosegur.com",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""

        _LOGGER.debug("Get image for %s", self._camera.description)
        try:
            return await self._installation.get_image(self._auth, self._camera.id)

        except ProsegurException as err:
            _LOGGER.error("Image %s doesn't exist: %s", self._camera.description, err)

        return None

    async def async_request_image(self):
        """Request new image from the camera."""

        _LOGGER.debug("Request image for %s", self._camera.description)
        try:
            await self._installation.request_image(self._auth, self._camera.id)

        except ProsegurException as err:
            _LOGGER.error(
                "Could not request image from camera %s: %s",
                self._camera.description,
                err,
            )
