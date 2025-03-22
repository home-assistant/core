"""Mammotion camera entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pymammotion.aliyun.model.stream_subscription_response import (
    StreamSubscriptionResponse,
)
from pymammotion.utility.device_type import DeviceType

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    StreamType,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MammotionConfigEntry
from .coordinator import MammotionBaseUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionCameraEntityDescription(CameraEntityDescription):
    """Describes Mammotion camera entity."""

    stream_fn: Callable[[MammotionBaseUpdateCoordinator], StreamSubscriptionResponse]


CAMERAS: tuple[MammotionCameraEntityDescription, ...] = (
    MammotionCameraEntityDescription(
        key="webrtc_camera",
        stream_fn=lambda coordinator: coordinator.get_stream_subscription(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion camera entities."""
    mowers = entry.runtime_data
    for mower in mowers:
        if not DeviceType.is_luba1(mower.device.deviceName):
            print("CAMERA API THING: ")
            api = await mower.api.get_stream_subscription(mower.device.deviceName)
            print(api)
            # async_add_entities(
            #     MammotionWebRTCCamera(mower.reporting_coordinator, entity_description)
            #     for entity_description in CAMERAS
            # )


class MammotionWebRTCCamera(MammotionBaseEntity, Camera):
    """Mammotion WebRTC camera entity."""

    entity_description: MammotionCameraEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionCameraEntityDescription,
    ) -> None:
        """Initialize the WebRTC camera entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._stream_data: StreamSubscriptionResponse | None = None

    @property
    def frontend_stream_type(self) -> StreamType | None:
        """Return the type of stream supported by this camera."""
        return StreamType.WEB_RTC

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if self._stream_data is None:
            return {}

        return {
            "app_id": self._stream_data.appid,
            "channel_name": self._stream_data.channelName,
            "uid": self._stream_data.uid,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        # WebRTC cameras typically don't support still images
        return None

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Return the source of the stream."""
