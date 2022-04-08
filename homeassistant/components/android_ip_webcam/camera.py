"""Support for Android IP Webcam Cameras."""
from __future__ import annotations

from homeassistant.components.mjpeg import MjpegCamera, filter_urllib3_logging
from homeassistant.const import HTTP_BASIC_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IP Webcam camera."""
    if discovery_info is None:
        return

    filter_urllib3_logging()
    async_add_entities([IPWebcamCamera(**discovery_info)])


class IPWebcamCamera(MjpegCamera):
    """Representation of a IP Webcam camera."""

    def __init__(
        self,
        name: str,
        mjpeg_url: str,
        still_image_url: str,
        username: str | None = None,
        password: str = "",
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
