"""Mammotion camera entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pymammotion.aliyun.model.stream_subscription_response import (
    StreamSubscriptionResponse,
)
from pymammotion.utility.device_type import DeviceType

from homeassistant.components.camera import Camera, CameraEntityDescription, StreamType
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

    async def async_get_stream_source(self) -> str | None:
        """Return the source of the stream."""
        try:
            self._stream_data = self.entity_description.stream_fn(self.coordinator)
            print(self._stream_data)
            if not self._stream_data:
                return None

            # Construct WebRTC offer using the stream data
            # This is a simplified example - adjust based on your WebRTC implementation
            return {
                "sdp": self._create_webrtc_offer(),
                "type": "offer",
            }
        except Exception:
            # _LOGGER.error("Failed to get stream source: %s", ex)
            return None

    def _create_webrtc_offer(self) -> str:
        """Create WebRTC offer from stream data."""
        if not self._stream_data:
            return ""

        # Create SDP offer using the stream data
        # This is a placeholder - implement according to your WebRTC requirements
        sdp = f"""v=0
            o=- {self._stream_data.uid} 2 IN IP4 0.0.0.0
            s=-
            t=0 0
            a=group:BUNDLE 0
            a=msid-semantic: WMS
            m=video 9 UDP/TLS/RTP/SAVPF 96
            c=IN IP4 0.0.0.0
            a=rtcp:9 IN IP4 0.0.0.0
            a=ice-ufrag:{self._stream_data.token[:8]}
                a=ice-pwd:{self._stream_data.token[8:24]}
            a=fingerprint:sha-256 {self._stream_data.token[24:]}
            a=setup:actpass
            a=mid:0
            a=extmap:1 urn:ietf:params:rtp-hdrext:toffset
            a=sendrecv
            a=rtcp-mux
            a=rtcp-rsize
            a=rtpmap:96 H264/90000
            a=rtcp-fb:96 nack
            a=rtcp-fb:96 nack pli
            a=rtcp-fb:96 goog-remb
            a=fmtp:96 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f
            """
        return sdp
