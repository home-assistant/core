"""Helper for WebRTC support."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass, field
from functools import cache, partial, wraps
import logging
from typing import TYPE_CHECKING, Any

from mashumaro import MissingField
import voluptuous as vol
from webrtc_models import (
    RTCConfiguration,
    RTCIceCandidate,
    RTCIceCandidateInit,
    RTCIceServer,
)

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ulid import ulid

from .const import DATA_COMPONENT, DOMAIN, StreamType
from .helper import get_camera_from_entity_id

if TYPE_CHECKING:
    from . import Camera

_LOGGER = logging.getLogger(__name__)


DATA_WEBRTC_PROVIDERS: HassKey[set[CameraWebRTCProvider]] = HassKey(
    "camera_webrtc_providers"
)
DATA_ICE_SERVERS: HassKey[list[Callable[[], Iterable[RTCIceServer]]]] = HassKey(
    "camera_webrtc_ice_servers"
)


_WEBRTC = "WebRTC"


@dataclass(frozen=True)
class WebRTCMessage:
    """Base class for WebRTC messages."""

    @classmethod
    @cache
    def _get_type(cls) -> str:
        _, _, name = cls.__name__.partition(_WEBRTC)
        return name.lower()

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the message."""
        data = asdict(self)
        data["type"] = self._get_type()
        return data


@dataclass(frozen=True)
class WebRTCSession(WebRTCMessage):
    """WebRTC session."""

    session_id: str


@dataclass(frozen=True)
class WebRTCAnswer(WebRTCMessage):
    """WebRTC answer."""

    answer: str


@dataclass(frozen=True)
class WebRTCCandidate(WebRTCMessage):
    """WebRTC candidate."""

    candidate: RTCIceCandidate | RTCIceCandidateInit

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the message."""
        return {
            "type": self._get_type(),
            "candidate": self.candidate.to_dict(),
        }


@dataclass(frozen=True)
class WebRTCError(WebRTCMessage):
    """WebRTC error."""

    code: str
    message: str


type WebRTCSendMessage = Callable[[WebRTCMessage], None]


@dataclass(kw_only=True)
class WebRTCClientConfiguration:
    """WebRTC configuration for the client.

    Not part of the spec, but required to configure client.
    """

    configuration: RTCConfiguration = field(default_factory=RTCConfiguration)
    data_channel: str | None = None

    def to_frontend_dict(self) -> dict[str, Any]:
        """Return a dict that can be used by the frontend."""
        data: dict[str, Any] = {
            "configuration": self.configuration.to_dict(),
        }
        if self.data_channel is not None:
            data["dataChannel"] = self.data_channel
        return data


class CameraWebRTCProvider(ABC):
    """WebRTC provider."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the integration domain of the provider."""

    @callback
    @abstractmethod
    def async_is_supported(self, stream_source: str) -> bool:
        """Determine if the provider supports the stream source."""

    @abstractmethod
    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle the WebRTC offer and return the answer via the provided callback."""

    @abstractmethod
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        return  ## This is an optional method so we need a default here.


@callback
def async_register_webrtc_provider(
    hass: HomeAssistant,
    provider: CameraWebRTCProvider,
) -> Callable[[], None]:
    """Register a WebRTC provider.

    The first provider to satisfy the offer will be used.
    """
    if DOMAIN not in hass.data:
        raise ValueError("Unexpected state, camera not loaded")

    providers = hass.data.setdefault(DATA_WEBRTC_PROVIDERS, set())

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


type WsCommandWithCamera = Callable[
    [websocket_api.ActiveConnection, dict[str, Any], Camera],
    Awaitable[None],
]


def require_webrtc_support(
    error_code: str,
) -> Callable[[WsCommandWithCamera], websocket_api.AsyncWebSocketCommandHandler]:
    """Validate that the camera supports WebRTC."""

    def decorate(
        func: WsCommandWithCamera,
    ) -> websocket_api.AsyncWebSocketCommandHandler:
        """Decorate func."""

        @wraps(func)
        async def validate(
            hass: HomeAssistant,
            connection: websocket_api.ActiveConnection,
            msg: dict[str, Any],
        ) -> None:
            """Validate that the camera supports WebRTC."""
            entity_id = msg["entity_id"]
            camera = get_camera_from_entity_id(hass, entity_id)
            if StreamType.WEB_RTC not in (
                stream_types := camera.camera_capabilities.frontend_stream_types
            ):
                connection.send_error(
                    msg["id"],
                    error_code,
                    (
                        "Camera does not support WebRTC,"
                        f" frontend_stream_types={stream_types}"
                    ),
                )
                return

            await func(connection, msg, camera)

        return validate

    return decorate


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/offer",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("offer"): str,
    }
)
@websocket_api.async_response
@require_webrtc_support("webrtc_offer_failed")
async def ws_webrtc_offer(
    connection: websocket_api.ActiveConnection, msg: dict[str, Any], camera: Camera
) -> None:
    """Handle the signal path for a WebRTC stream.

    This signal path is used to route the offer created by the client to the
    camera device through the integration for negotiation on initial setup.
    The ws endpoint returns a subscription id, where ice candidates and the
    final answer will be returned.
    The actual streaming is handled entirely between the client and camera device.

    Async friendly.
    """
    offer = msg["offer"]
    session_id = ulid()
    connection.subscriptions[msg["id"]] = partial(
        camera.close_webrtc_session, session_id
    )

    connection.send_message(websocket_api.result_message(msg["id"]))

    @callback
    def send_message(message: WebRTCMessage) -> None:
        """Push a value to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                message.as_dict(),
            )
        )

    send_message(WebRTCSession(session_id))

    try:
        await camera.async_handle_async_webrtc_offer(offer, session_id, send_message)
    except HomeAssistantError as ex:
        _LOGGER.error("Error handling WebRTC offer: %s", ex)
        send_message(
            WebRTCError(
                "webrtc_offer_failed",
                str(ex),
            )
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/get_client_config",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
@require_webrtc_support("webrtc_get_client_config_failed")
async def ws_get_client_config(
    connection: websocket_api.ActiveConnection, msg: dict[str, Any], camera: Camera
) -> None:
    """Handle get WebRTC client config websocket command."""
    config = camera.async_get_webrtc_client_configuration().to_frontend_dict()
    connection.send_result(
        msg["id"],
        config,
    )


def _parse_webrtc_candidate_init(value: Any) -> RTCIceCandidateInit:
    """Validate and parse a WebRTCCandidateInit dict."""
    try:
        return RTCIceCandidateInit.from_dict(value)
    except (MissingField, ValueError) as ex:
        raise vol.Invalid(str(ex)) from ex


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/webrtc/candidate",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("session_id"): str,
        vol.Required("candidate"): _parse_webrtc_candidate_init,
    }
)
@websocket_api.async_response
@require_webrtc_support("webrtc_candidate_failed")
async def ws_candidate(
    connection: websocket_api.ActiveConnection, msg: dict[str, Any], camera: Camera
) -> None:
    """Handle WebRTC candidate websocket command."""
    await camera.async_on_webrtc_candidate(msg["session_id"], msg["candidate"])
    connection.send_message(websocket_api.result_message(msg["id"]))


@callback
def async_register_ws(hass: HomeAssistant) -> None:
    """Register camera webrtc ws endpoints."""

    websocket_api.async_register_command(hass, ws_webrtc_offer)
    websocket_api.async_register_command(hass, ws_get_client_config)
    websocket_api.async_register_command(hass, ws_candidate)


async def async_get_supported_provider(
    hass: HomeAssistant, camera: Camera
) -> CameraWebRTCProvider | None:
    """Return the first supported provider for the camera."""
    providers = hass.data.get(DATA_WEBRTC_PROVIDERS)
    if not providers or not (stream_source := await camera.stream_source()):
        return None

    for provider in providers:
        if provider.async_is_supported(stream_source):
            return provider

    return None


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
