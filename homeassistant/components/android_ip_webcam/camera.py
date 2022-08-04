"""Support for Android IP Webcam Cameras."""
from __future__ import annotations

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AndroidIPCamDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam camera from config entry."""
    filter_urllib3_logging()
    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        [
            IPWebcamCamera(
                coordinator.config_entry.data[CONF_NAME],
                coordinator.config_entry.entry_id,
                coordinator.ipcam.mjpeg_url,
                coordinator.ipcam.image_url,
                coordinator.config_entry.data.get(CONF_USERNAME),
                coordinator.config_entry.data.get(CONF_PASSWORD, ""),
            )
        ]
    )


class IPWebcamCamera(MjpegCamera):
    """Representation of a IP Webcam camera."""

    def __init__(
        self,
        name: str,
        entry_id: str,
        mjpeg_url: str,
        still_image_url: str,
        username: str | None,
        password: str,
    ) -> None:
        """Initialize the camera."""
        super().__init__(
            name=name,
            mjpeg_url=mjpeg_url,
            still_image_url=still_image_url,
            authentication=HTTP_BASIC_AUTHENTICATION,
            username=username,
            password=password,
        )
        self._attr_unique_id = f"{entry_id}-camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=name,
        )
