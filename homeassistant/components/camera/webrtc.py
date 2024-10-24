"""Helper for WebRTC support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any, Protocol

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.webrtc import RTCIceServer

from .const import DATA_COMPONENT, DOMAIN, StreamType
from .helper import get_camera_from_entity_id

if TYPE_CHECKING:
    from . import Camera


DATA_WEBRTC_PROVIDERS: HassKey[set[CameraWebRTCProvider]] = HassKey(
    "camera_web_rtc_providers"
)
DATA_ICE_SERVERS: HassKey[list[Callable[[], Iterable[RTCIceServer]]]] = HassKey(
    "camera_web_rtc_ice_servers"
)


class CameraWebRTCProvider(Protocol):
    """WebRTC provider."""

    async def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""


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

    @callback
    def remove_provider() -> None:
        providers.remove(provider)
        hass.async_create_task(_async_refresh_providers(hass))

    if provider in providers:
        raise ValueError("Provider already registered")

    providers.add(provider)
    hass.async_create_task(_async_refresh_providers(hass))
    return remove_provider


async def _async_refresh_providers(hass: HomeAssistant) -> None:
    """Check all cameras for any state changes for registered providers."""

    component = hass.data[DATA_COMPONENT]
    await asyncio.gather(
        *(camera.async_refresh_providers() for camera in component.entities)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/get_client_config",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def ws_get_client_config(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get WebRTC client config websocket command."""
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

    config = (await camera.async_get_webrtc_client_configuration()).to_frontend_dict()
    connection.send_result(
        msg["id"],
        config,
    )


async def async_get_supported_providers(
    hass: HomeAssistant, camera: Camera
) -> list[CameraWebRTCProvider]:
    """Return a list of supported providers for the camera."""
    providers = hass.data.get(DATA_WEBRTC_PROVIDERS)
    if not providers or not (stream_source := await camera.stream_source()):
        return []

    return [
        provider
        for provider in providers
        if await provider.async_is_supported(stream_source)
    ]


@callback
def async_register_ice_servers(
    hass: HomeAssistant,
    get_ice_server_fn: Callable[[], Iterable[RTCIceServer]],
) -> Callable[[], None]:
    """Register a ICE server.

    The registering integration is responsible to implement caching if needed.
    """
    servers = hass.data.setdefault(DATA_ICE_SERVERS, [])

    def remove() -> None:
        servers.remove(get_ice_server_fn)

    servers.append(get_ice_server_fn)
    return remove


# The following code is legacy code that was introduced with rtsp_to_webrtc and will be deprecated/removed in the future.
# Left it so custom integrations can still use it.

_RTSP_PREFIXES = {"rtsp://", "rtsps://", "rtmp://"}

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
        return any(stream_source.startswith(prefix) for prefix in _RTSP_PREFIXES)

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""
        if not (stream_source := await camera.stream_source()):
            return None

        return await self._fn(stream_source, offer_sdp, camera.entity_id)


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
