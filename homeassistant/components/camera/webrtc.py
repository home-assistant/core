"""Helper for WebRTC support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Protocol
import uuid

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.dict import DataClassDictMixin
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.hass_dict import HassKey

from .const import DATA_COMPONENT, DOMAIN, StreamType
from .helper import get_camera_from_entity_id

if TYPE_CHECKING:
    from . import Camera

_LOGGER = logging.getLogger(__name__)


DATA_WEBRTC_PROVIDERS: HassKey[set[CameraWebRTCProvider]] = HassKey(
    "camera_webrtc_providers"
)
DATA_WEBRTC_LEGACY_PROVIDERS: HassKey[set[CameraWebRTCLegacyProvider]] = HassKey(
    "camera_webrtc_legacy_providers"
)
DATA_ICE_SERVERS: HassKey[list[Callable[[], Coroutine[Any, Any, RTCIceServer]]]] = (
    HassKey("camera_webrtc_ice_servers")
)


class _RTCBaseModel(DataClassDictMixin):
    """Base class for RTC models."""

    class Config(BaseConfig):
        """Mashumaro config."""

        # Serialize to spec conform names and omit default values
        omit_default = True
        serialize_by_alias = True


@dataclass
class RTCIceServer(_RTCBaseModel):
    """RTC Ice Server.

    See https://www.w3.org/TR/webrtc/#rtciceserver-dictionary
    """

    urls: list[str] | str
    username: str | None = None
    credential: str | None = None


@dataclass
class RTCConfiguration(_RTCBaseModel):
    """RTC Configuration.

    See https://www.w3.org/TR/webrtc/#rtcconfiguration-dictionary
    """

    ice_servers: list[RTCIceServer] = field(
        metadata=field_options(alias="iceServers"), default_factory=list
    )


@dataclass(kw_only=True)
class WebRTCClientConfiguration(DataClassDictMixin):
    """WebRTC configuration for the client.

    Not part of the spec, but required to configure client.
    """

    class Config(BaseConfig):
        """Mashumaro config."""

        serialize_by_alias = True

    configuration: RTCConfiguration = field(default_factory=RTCConfiguration)
    data_channel: str | None = field(
        metadata=field_options(alias="dataChannel"), default=None
    )
    get_all_candidates_upfront: bool = field(init=False, default=False)


class CameraWebRTCProvider(Protocol):
    """WebRTC provider."""

    async def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""

    async def async_handle_web_rtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_result: Callable[[dict], None],
    ) -> bool:
        """Handle the WebRTC offer and return the answer via the provided callback.

        Return value determines if the offer was handled successfully.
        """

    async def async_on_webrtc_candidate(self, session_id: str, candidate: str) -> None:
        """Handle the WebRTC candidate."""

    @callback
    def close_session(self, session_id: str) -> None:
        """Close the session."""


class CameraWebRTCLegacyProvider(Protocol):
    """WebRTC provider."""

    async def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""

    async def async_handle_web_rtc_offer(
        self, camera: Camera, offer_sdp: str
    ) -> str | None:
        """Handle the WebRTC offer and return an answer."""


def _async_register_webrtc_provider[_T](
    hass: HomeAssistant,
    key: HassKey[set[_T]],
    provider: _T,
) -> Callable[[], None]:
    """Register a WebRTC provider.

    The first provider to satisfy the offer will be used.
    """
    if DOMAIN not in hass.data:
        raise ValueError("Unexpected state, camera not loaded")

    providers = hass.data.setdefault(key, set())

    @callback
    def remove_provider() -> None:
        providers.remove(provider)
        hass.async_create_task(_async_refresh_providers(hass))

    if provider in providers:
        raise ValueError("Provider already registered")

    providers.add(provider)
    hass.async_create_task(_async_refresh_providers(hass))
    return remove_provider


def async_register_webrtc_provider(
    hass: HomeAssistant,
    provider: CameraWebRTCProvider,
) -> Callable[[], None]:
    """Register a WebRTC provider.

    The first provider to satisfy the offer will be used.
    """
    return _async_register_webrtc_provider(hass, DATA_WEBRTC_PROVIDERS, provider)


async def _async_refresh_providers(hass: HomeAssistant) -> None:
    """Check all cameras for any state changes for registered providers."""

    component = hass.data[DATA_COMPONENT]
    await asyncio.gather(
        *(camera.async_refresh_providers() for camera in component.entities)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/offer",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("offer"): str,
    }
)
@websocket_api.async_response
async def ws_webrtc_offer(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle the signal path for a WebRTC stream.

    This signal path is used to route the offer created by the client to the
    camera device through the integration for negotiation on initial setup.
    The ws endpoint returns an subscription id, where ice candidates and the
    final answer will be returned.
    The actual streaming is handled entirely between the client and camera device.

    Async friendly.
    """
    entity_id = msg["entity_id"]
    offer = msg["offer"]
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

    session_id = uuid.uuid4().hex
    connection.subscriptions[session_id] = partial(
        camera.close_webrtc_session, session_id
    )

    # Send subscription id to client
    connection.send_result(msg["id"], {"subscription_id": session_id})

    @callback
    def send_event(value: dict) -> None:
        """Push a value to websocket."""
        connection.send_message(
            websocket_api.event_message(
                session_id,
                value,
            )
        )

    if camera.supports_async_webrtc_offer:
        await camera.async_handle_web_rtc_offer(offer, session_id, send_event)
    else:
        try:
            answer = await camera.async_handle_web_rtc_offer(offer)
        except (HomeAssistantError, ValueError) as ex:
            _LOGGER.error("Error handling WebRTC offer: %s", ex)
            send_event(
                {"type": "error", "code": "web_rtc_offer_failed", "message": str(ex)}
            )
        except TimeoutError:
            _LOGGER.error("Timeout handling WebRTC offer")
            send_event(
                {
                    "type": "error",
                    "code": "web_rtc_offer_failed",
                    "message": "Timeout handling WebRTC offer",
                }
            )
        else:
            send_event({"type": "answer", "answer": answer})


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

    config = (await camera.async_get_webrtc_client_configuration()).to_dict()
    connection.send_result(
        msg["id"],
        config,
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/candidate",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("subscription_id"): str,
        vol.Required("candidate"): str,
    }
)
@websocket_api.async_response
async def ws_candidate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle WebRTC candidate websocket command."""
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

    await camera.async_on_webrtc_candiate(msg["subscription_id"], msg["candidate"])
    connection.send_message(websocket_api.result_message(msg["id"]))


async def async_register_ws(hass: HomeAssistant) -> None:
    """Register camera webrtc ws endpoints."""

    websocket_api.async_register_command(hass, ws_webrtc_offer)
    websocket_api.async_register_command(hass, ws_get_client_config)
    websocket_api.async_register_command(hass, ws_candidate)


async def _async_get_supported_provider[
    _T: CameraWebRTCLegacyProvider | CameraWebRTCProvider
](hass: HomeAssistant, camera: Camera, key: HassKey[set[_T]]) -> _T | None:
    """Return the first supported provider for the camera."""
    providers = hass.data.get(key)
    if not providers or not (stream_source := await camera.stream_source()):
        return None

    for provider in providers:
        if await provider.async_is_supported(stream_source):
            return provider

    return None


async def async_get_supported_provider(
    hass: HomeAssistant, camera: Camera
) -> CameraWebRTCProvider | None:
    """Return the first supported provider for the camera."""
    return await _async_get_supported_provider(hass, camera, DATA_WEBRTC_PROVIDERS)


async def async_get_supported_legacy_provider(
    hass: HomeAssistant, camera: Camera
) -> CameraWebRTCLegacyProvider | None:
    """Return the first supported provider for the camera."""
    return await _async_get_supported_provider(
        hass, camera, DATA_WEBRTC_LEGACY_PROVIDERS
    )


@callback
def register_ice_server(
    hass: HomeAssistant,
    get_ice_server_fn: Callable[[], Coroutine[Any, Any, RTCIceServer]],
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


class _CameraRtspToWebRTCProvider(CameraWebRTCLegacyProvider):
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
    return _async_register_webrtc_provider(
        hass, DATA_WEBRTC_LEGACY_PROVIDERS, provider_instance
    )
