"""Provide a mock remote platform.

Call init before using it in your tests to ensure clean test data.
"""

from homeassistant.components.camera import Camera, CameraEntityFeature, StreamType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Return mock entities."""
    async_add_entities_callback(
        [AttrFrontendStreamTypeCamera(), PropertyFrontendStreamTypeCamera()]
    )


class AttrFrontendStreamTypeCamera(Camera):
    """attr frontend stream type Camera."""

    _attr_name = "attr frontend stream type"
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM
    _attr_frontend_stream_type: StreamType = StreamType.WEB_RTC


class PropertyFrontendStreamTypeCamera(Camera):
    """property frontend stream type Camera."""

    _attr_name = "property frontend stream type"
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature.STREAM

    @property
    def frontend_stream_type(self) -> StreamType | None:
        """Return the stream type of the camera."""
        return StreamType.WEB_RTC
