"""Base entity for the Camera platform."""

import asyncio
import collections
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from random import SystemRandom
import time
from typing import Any, Final, final, override

from aiohttp import web
from propcache.api import cached_property
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.labs import async_is_preview_feature_enabled
from homeassistant.components.stream import Stream, create_stream
from homeassistant.components.web_rtc import async_get_ice_servers
from homeassistant.const import CONTENT_TYPE_MULTIPART, EntityStateAttribute
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import (
    CAMERA_STREAM_SOURCE_TIMEOUT,
    DEFAULT_CONTENT_TYPE,
    DOMAIN,
    ENTITY_IMAGE_URL,
    MIN_STREAM_INTERVAL,
    PREVIEW_FEATURE_TWO_WAY_AUDIO,
    CameraEntityFeature,
    CameraEntityStateAttribute,
    CameraState,
    StreamType,
)
from .prefs import get_dynamic_camera_stream_settings
from .webrtc import (
    CameraWebRTCProvider,
    WebRTCClientConfiguration,
    WebRTCSendMessage,
    async_call_webrtc_provider,
    async_get_supported_provider,
)

_RND: Final = SystemRandom()


class CameraEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes camera entities."""


@dataclass(frozen=True, kw_only=True)
class CameraEntityCapabilities:
    """Capabilities declared by a camera entity."""

    two_way_audio: bool = False


@dataclass(frozen=True)
class CameraCapabilities:
    """Camera capabilities resolved for the frontend."""

    frontend_stream_types: set[StreamType]
    two_way_audio: bool = False


async def async_get_still_stream(
    request: web.Request,
    image_cb: Callable[[], Awaitable[bytes | None]],
    content_type: str,
    interval: float,
) -> web.StreamResponse:
    """Generate an HTTP MJPEG stream from camera images.

    This method must be run in the event loop.
    """
    response = web.StreamResponse()
    response.content_type = CONTENT_TYPE_MULTIPART.format("--frameboundary")
    await response.prepare(request)

    async def write_to_mjpeg_stream(img_bytes: bytes) -> None:
        """Write image to stream."""
        await response.write(
            bytes(
                "--frameboundary\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(img_bytes)}\r\n\r\n",
                "utf-8",
            )
            + img_bytes
            + b"\r\n"
        )

    last_image = None

    while True:
        last_fetch = time.monotonic()
        img_bytes = await image_cb()
        if not img_bytes:
            break

        if img_bytes != last_image:
            await write_to_mjpeg_stream(img_bytes)

            # Chrome always shows the n-1 frame:
            # https://issues.chromium.org/issues/41199053
            # https://issues.chromium.org/issues/40791855
            # We send the first frame twice to ensure it shows
            # Subsequent frames are not a concern at reasonable frame rates
            # (even 1/10 FPS is about the latency of HLS)
            if last_image is None:
                await write_to_mjpeg_stream(img_bytes)
            last_image = img_bytes

        next_fetch = last_fetch + interval
        now = time.monotonic()
        if next_fetch > now:
            sleep_time = next_fetch - now
            await asyncio.sleep(sleep_time)

    return response


CACHED_PROPERTIES_WITH_ATTR_ = {
    "brand",
    "camera_entity_capabilities",
    "frame_interval",
    "is_on",
    "is_recording",
    "is_streaming",
    "model",
    "motion_detection_enabled",
    "supported_features",
}


class Camera(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """The base class for camera entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {CameraEntityStateAttribute.ACCESS_TOKEN, EntityStateAttribute.ENTITY_PICTURE}
    )

    # Entity Properties
    entity_description: CameraEntityDescription
    _attr_brand: str | None = None
    _attr_camera_entity_capabilities = CameraEntityCapabilities()
    _attr_frame_interval: float = MIN_STREAM_INTERVAL
    _attr_is_on: bool = True
    _attr_is_recording: bool = False
    _attr_is_streaming: bool = False
    _attr_model: str | None = None
    _attr_motion_detection_enabled: bool = False
    _attr_should_poll: bool = False  # No need to poll cameras
    _attr_state: None = None  # State is determined by is_on
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature(0)

    __supports_stream: CameraEntityFeature | None = None

    def __init__(self) -> None:
        """Initialize a camera."""
        self.stream: Stream | None = None
        self.stream_options: dict[str, str | bool | float] = {}
        self.content_type: str = DEFAULT_CONTENT_TYPE
        self.access_tokens: collections.deque = collections.deque(maxlen=2)
        self._warned_old_signature = False
        self.async_update_token()
        self._create_stream_lock: asyncio.Lock | None = None
        self._webrtc_provider: CameraWebRTCProvider | None = None
        self._supports_native_async_webrtc = (
            type(self).async_handle_async_webrtc_offer
            != Camera.async_handle_async_webrtc_offer
        )

    @cached_property
    @override
    def entity_picture(self) -> str:
        """Return a link to the camera feed as entity picture."""
        if self._attr_entity_picture is not None:
            return self._attr_entity_picture
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_tokens[-1])

    @cached_property
    def use_stream_for_stills(self) -> bool:
        """Whether or not to use stream to generate stills."""
        return False

    @cached_property
    @override
    def supported_features(self) -> CameraEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self._attr_is_recording

    @cached_property
    def is_streaming(self) -> bool:
        """Return true if the device is streaming."""
        return self._attr_is_streaming

    @cached_property
    def brand(self) -> str | None:
        """Return the camera brand."""
        return self._attr_brand

    @cached_property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._attr_motion_detection_enabled

    @cached_property
    def model(self) -> str | None:
        """Return the camera model."""
        return self._attr_model

    @cached_property
    def frame_interval(self) -> float:
        """Return the interval between frames of the mjpeg stream."""
        return self._attr_frame_interval

    @cached_property
    def camera_entity_capabilities(self) -> CameraEntityCapabilities:
        """Return the capabilities declared by the camera entity."""
        return self._attr_camera_entity_capabilities

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        if (stream := self.stream) and not stream.available:
            return False
        return super().available

    @final
    @property
    def webrtc_provider(self) -> CameraWebRTCProvider | None:
        """Return the WebRTC provider."""
        return self._webrtc_provider

    async def async_create_stream(self) -> Stream | None:
        """Create a Stream for stream_source."""
        # There is at most one stream (a decode worker) per camera
        if not self._create_stream_lock:
            self._create_stream_lock = asyncio.Lock()
        async with self._create_stream_lock:
            if not self.stream:
                async with asyncio.timeout(CAMERA_STREAM_SOURCE_TIMEOUT):
                    source = await self.stream_source()
                if not source:
                    return None
                self.stream = create_stream(
                    self.hass,
                    source,
                    options=self.stream_options,
                    dynamic_stream_settings=await get_dynamic_camera_stream_settings(
                        self.hass, self.entity_id
                    ),
                    stream_label=self.entity_id,
                )
                self.stream.set_update_callback(self.async_write_ha_state)
            return self.stream

    async def stream_source(self) -> str | None:
        """Return the source of the stream.

        This is used by cameras with CameraEntityFeature.STREAM
        and StreamType.HLS.
        """
        return None

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle the async WebRTC offer.

        Async means that it could take some time to process
        the offer and responses/message will be sent with the
        send_message callback.
        This method is used by cameras with
        CameraEntityFeature.STREAM.
        An integration overriding this method must also
        implement async_on_webrtc_candidate.

        Integrations can override with a native WebRTC implementation.
        """
        if self._webrtc_provider:
            await self._webrtc_provider.async_handle_async_webrtc_offer(
                self, offer_sdp, session_id, send_message
            )
            return

        raise HomeAssistantError("Camera does not support WebRTC")

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        raise NotImplementedError

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        return await self.hass.async_add_executor_job(
            partial(self.camera_image, width=width, height=height)
        )

    async def handle_async_still_stream(
        self, request: web.Request, interval: float
    ) -> web.StreamResponse:
        """Generate an HTTP MJPEG stream from camera images."""
        return await async_get_still_stream(
            request, self.async_camera_image, self.content_type, interval
        )

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        """Serve an HTTP MJPEG stream from the camera.

        This method can be overridden by camera platforms to proxy
        a direct stream from the camera.
        """
        return await self.handle_async_still_stream(request, self.frame_interval)

    @property
    @final
    @override
    def state(self) -> str:
        """Return the camera state."""
        if self.is_recording:
            return CameraState.RECORDING
        if self.is_streaming:
            return CameraState.STREAMING
        return CameraState.IDLE

    @cached_property
    def is_on(self) -> bool:
        """Return true if on."""
        return self._attr_is_on

    def turn_off(self) -> None:
        """Turn off camera."""
        raise NotImplementedError

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self.hass.async_add_executor_job(self.turn_off)

    def turn_on(self) -> None:
        """Turn on camera."""
        raise NotImplementedError

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self.hass.async_add_executor_job(self.turn_on)

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        raise NotImplementedError

    async def async_enable_motion_detection(self) -> None:
        """Call the job and enable motion detection."""
        await self.hass.async_add_executor_job(self.enable_motion_detection)

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        raise NotImplementedError

    async def async_disable_motion_detection(self) -> None:
        """Call the job and disable motion detection."""
        await self.hass.async_add_executor_job(self.disable_motion_detection)

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the camera state attributes."""
        attrs: dict[str, str | bool | None] = {
            CameraEntityStateAttribute.ACCESS_TOKEN: self.access_tokens[-1]
        }

        if model := self.model:
            attrs[CameraEntityStateAttribute.MODEL_NAME] = model

        if brand := self.brand:
            attrs[CameraEntityStateAttribute.BRAND] = brand

        if motion_detection_enabled := self.motion_detection_enabled:
            attrs[CameraEntityStateAttribute.MOTION_DETECTION] = (
                motion_detection_enabled
            )

        return attrs

    @callback
    def async_update_token(self) -> None:
        """Update the used token."""
        self.access_tokens.append(hex(_RND.getrandbits(256))[2:])
        self.__dict__.pop("entity_picture", None)

    @callback
    @override
    def async_internal_entity_id_changed(self, old_entity_id: str) -> None:
        """Drop the cached entity picture, its URL embeds the entity_id."""
        super().async_internal_entity_id_changed(old_entity_id)
        self.__dict__.pop("entity_picture", None)

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_internal_added_to_hass()
        self.__supports_stream = self.supported_features & CameraEntityFeature.STREAM
        await self.async_refresh_providers(write_state=False)

    @override
    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._webrtc_provider:
            await async_call_webrtc_provider(
                self._webrtc_provider.async_unregister_camera(self),
                "unregistering WebRTC provider for",
                self.entity_id,
            )
            self._webrtc_provider = None
        await super().async_internal_will_remove_from_hass()

    async def async_refresh_providers(self, *, write_state: bool = True) -> None:
        """Determine if any of the registered providers are suitable for this entity.

        This affects state attributes, so it should be invoked any time the registered
        providers or inputs to the state attributes change.
        """
        old_provider = self._webrtc_provider
        new_provider = None

        # Skip all providers if the camera has a native WebRTC implementation
        if not self._supports_native_async_webrtc:
            # Camera doesn't have a native WebRTC implementation
            new_provider = await self._async_get_supported_webrtc_provider(
                async_get_supported_provider
            )

        if old_provider == new_provider:
            return

        if old_provider:
            await async_call_webrtc_provider(
                old_provider.async_unregister_camera(self),
                "unregistering WebRTC provider for",
                self.entity_id,
            )

        if new_provider:
            await async_call_webrtc_provider(
                new_provider.async_register_camera(self),
                "registering WebRTC provider for",
                self.entity_id,
            )

        self._webrtc_provider = new_provider
        if write_state:
            self.async_write_ha_state()

    async def _async_get_supported_webrtc_provider[_T](
        self, fn: Callable[[HomeAssistant, Camera], Coroutine[None, None, _T | None]]
    ) -> _T | None:
        """Get first provider that supports this camera."""
        if CameraEntityFeature.STREAM not in self.supported_features:
            return None

        return await fn(self.hass, self)

    @callback
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration adjustable per integration."""
        return WebRTCClientConfiguration()

    @final
    @callback
    def async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration.

        Extend it with the registered ice servers.
        """
        config = self._async_get_webrtc_client_configuration()

        ice_servers = async_get_ice_servers(self.hass)
        config.configuration.ice_servers.extend(ice_servers)

        return config

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC candidate."""
        if self._webrtc_provider:
            await self._webrtc_provider.async_on_webrtc_candidate(session_id, candidate)
        else:
            raise HomeAssistantError("Cannot handle WebRTC candidate")

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        if self._webrtc_provider:
            self._webrtc_provider.async_close_session(session_id)

    @final
    @property
    def camera_capabilities(self) -> CameraCapabilities:
        """Return the camera capabilities."""
        frontend_stream_types = set()
        if CameraEntityFeature.STREAM in self.supported_features:
            if self._supports_native_async_webrtc:
                # The camera has a native WebRTC implementation
                frontend_stream_types.add(StreamType.WEB_RTC)
            else:
                frontend_stream_types.add(StreamType.HLS)

                if self._webrtc_provider:
                    frontend_stream_types.add(StreamType.WEB_RTC)

        return CameraCapabilities(
            frontend_stream_types,
            # Two way audio is only available over WebRTC
            two_way_audio=(
                self.camera_entity_capabilities.two_way_audio
                and StreamType.WEB_RTC in frontend_stream_types
                and async_is_preview_feature_enabled(
                    self.hass, DOMAIN, PREVIEW_FEATURE_TWO_WAY_AUDIO
                )
            ),
        )

    @callback
    @override
    def _async_write_ha_state(self) -> None:
        """Write the state to the state machine.

        Schedules async_refresh_providers if support of streams have changed.
        """
        super()._async_write_ha_state()
        if self.__supports_stream != (
            supports_stream := self.supported_features & CameraEntityFeature.STREAM
        ):
            self.__supports_stream = supports_stream
            self.hass.async_create_task(self.async_refresh_providers())
