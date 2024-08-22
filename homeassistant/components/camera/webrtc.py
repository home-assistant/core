"""Helper for WebRTC support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, StreamType
from .util import get_camera_from_entity_id

if TYPE_CHECKING:
    from . import Camera


DATA_WEBRTC_PROVIDERS: HassKey[set[CameraWebRTCProvider]] = HassKey(
    "camera_web_rtc_providers"
)


@dataclass
class CameraWebRTCProviderSettings:
    """Return type for get_provider_settings."""

    stun_servers: list[str]


class CameraWebRTCProvider(Protocol):
    """WebRTC provider."""

    async def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""

    async def async_get_settings(self) -> CameraWebRTCProviderSettings:
        """Return provider settings."""


def async_register_webrtc_provider(
    hass: HomeAssistant,
    provider: CameraWebRTCProvider,
) -> Callable[[], None]:
    """Register a WebRTC provider.

    The first provider to satisfy the offer will be used.
    """
    if DOMAIN not in hass.data:
        raise ValueError("Unexpected state, camera not loaded")

    providers: set[CameraWebRTCProvider] = hass.data.setdefault(
        DATA_WEBRTC_PROVIDERS, set()
    )

    def remove_provider() -> None:
        providers.discard(provider)
        hass.async_create_task(_async_refresh_providers(hass))

    providers.add(provider)
    hass.async_create_task(_async_refresh_providers(hass))
    return remove_provider


RTSP_PREFIXES = {"rtsp://", "rtsps://", "rtmp://"}

# An RtspToWebRtcProvider accepts these inputs:
#     stream_source: The RTSP url
#     offer_sdp: The WebRTC SDP offer
#     stream_id: A unique id for the stream, used to update an existing source
# The output is the SDP answer, or None if the source or offer is not eligible.
# The Callable may throw HomeAssistantError on failure.
type RtspToWebRtcProviderType = Callable[[str, str, str], Awaitable[str | None]]


class _CameraRtspToWebRTCProvider(CameraWebRTCProvider):
    def __init__(self, fn: RtspToWebRtcProviderType) -> None:
        """Initialize the RTSP to WebRTC provider."""
        self._fn = fn

    async def async_is_supported(self, stream_source: str) -> bool:
        """Return if this provider is supports the Camera as source."""
        return any(stream_source.startswith(prefix) for prefix in RTSP_PREFIXES)

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""
        if not (stream_source := await camera.stream_source()):
            return None

        return await self._fn(stream_source, offer_sdp, camera.entity_id)

    async def async_get_settings(self) -> CameraWebRTCProviderSettings:
        """Return provider settings."""
        return CameraWebRTCProviderSettings(stun_servers=[])


def async_register_rtsp_to_web_rtc_provider(
    hass: HomeAssistant,
    domain: str,
    provider: RtspToWebRtcProviderType,
) -> Callable[[], None]:
    """Register an RTSP to WebRTC provider.

    The first provider to satisfy the offer will be used.
    """
    provider_instance = _CameraRtspToWebRTCProvider(provider)
    return async_register_webrtc_provider(hass, provider_instance)


async def _async_refresh_providers(hass: HomeAssistant) -> None:
    """Check all cameras for any state changes for registered providers."""

    component: EntityComponent[Camera] = hass.data[DOMAIN]
    await asyncio.gather(
        *(camera.async_refresh_providers() for camera in component.entities)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/get_provider_settings",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def ws_get_provider_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle webRTC provider settings command.

    This signal path is used to route the offer created by the client to the
    camera device through the integration for negotiation on initial setup,
    which returns an answer. The actual streaming is handled entirely between
    the client and camera device.

    Async friendly.
    """
    entity_id = msg["entity_id"]
    camera = get_camera_from_entity_id(hass, entity_id)
    if camera.frontend_stream_type != StreamType.WEB_RTC:
        connection.send_error(
            msg["id"],
            "web_rtc_offer_failed",
            (
                "Camera does not support WebRTC,"
                f" frontend_stream_type={camera.frontend_stream_type}"
            ),
        )
        return

    connection.send_result(
        msg["id"],
        {
            "settings": [
                provider.async_get_settings() for provider in camera.webrtc_providers
            ]
        },
    )


async def async_get_supported_providers(
    hass: HomeAssistant, stream_source: str
) -> list[CameraWebRTCProvider]:
    """Return a list of supported providers for the camera."""
    return [
        provider
        for provider in hass.data[DATA_WEBRTC_PROVIDERS]
        if await provider.async_is_supported(stream_source)
    ]
