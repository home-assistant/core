"""Component to interface with cameras."""

from __future__ import annotations

import asyncio
import collections
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timedelta
from enum import IntFlag
from functools import partial
import logging
import os
from random import SystemRandom
import time
from typing import Any, Final, final

from aiohttp import hdrs, web
import attr
from propcache import cached_property
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.stream import (
    FORMAT_CONTENT_TYPE,
    OUTPUT_FORMATS,
    Orientation,
    Stream,
    create_stream,
)
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FILENAME,
    CONTENT_TYPE_MULTIPART,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.network import get_url
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.loader import bind_hass

from .const import (  # noqa: F401
    _DEPRECATED_STREAM_TYPE_HLS,
    _DEPRECATED_STREAM_TYPE_WEB_RTC,
    CAMERA_IMAGE_TIMEOUT,
    CAMERA_STREAM_SOURCE_TIMEOUT,
    CONF_DURATION,
    CONF_LOOKBACK,
    DATA_CAMERA_PREFS,
    DATA_COMPONENT,
    DOMAIN,
    PREF_ORIENTATION,
    PREF_PRELOAD_STREAM,
    SERVICE_RECORD,
    CameraState,
    StreamType,
)
from .helper import get_camera_from_entity_id
from .img_util import scale_jpeg_camera_image
from .prefs import CameraPreferences, DynamicStreamSettings  # noqa: F401
from .webrtc import (
    DATA_ICE_SERVERS,
    CameraWebRTCProvider,
    RTCIceServer,
    WebRTCClientConfiguration,
    async_get_supported_providers,
    async_register_rtsp_to_web_rtc_provider,  # noqa: F401
    register_ice_server,
    ws_get_client_config,
)

_LOGGER = logging.getLogger(__name__)


ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

SERVICE_ENABLE_MOTION: Final = "enable_motion_detection"
SERVICE_DISABLE_MOTION: Final = "disable_motion_detection"
SERVICE_SNAPSHOT: Final = "snapshot"
SERVICE_PLAY_STREAM: Final = "play_stream"

ATTR_FILENAME: Final = "filename"
ATTR_MEDIA_PLAYER: Final = "media_player"
ATTR_FORMAT: Final = "format"

# These constants are deprecated as of Home Assistant 2024.10
# Please use the StreamType enum instead.
_DEPRECATED_STATE_RECORDING = DeprecatedConstantEnum(CameraState.RECORDING, "2025.10")
_DEPRECATED_STATE_STREAMING = DeprecatedConstantEnum(CameraState.STREAMING, "2025.10")
_DEPRECATED_STATE_IDLE = DeprecatedConstantEnum(CameraState.IDLE, "2025.10")


class CameraEntityFeature(IntFlag):
    """Supported features of the camera entity."""

    ON_OFF = 1
    STREAM = 2


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Pleease use the CameraEntityFeature enum instead.
_DEPRECATED_SUPPORT_ON_OFF: Final = DeprecatedConstantEnum(
    CameraEntityFeature.ON_OFF, "2025.1"
)
_DEPRECATED_SUPPORT_STREAM: Final = DeprecatedConstantEnum(
    CameraEntityFeature.STREAM, "2025.1"
)


DEFAULT_CONTENT_TYPE: Final = "image/jpeg"
ENTITY_IMAGE_URL: Final = "/api/camera_proxy/{0}?token={1}"

TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=5)
_RND: Final = SystemRandom()

MIN_STREAM_INTERVAL: Final = 0.5  # seconds

CAMERA_SERVICE_SNAPSHOT: VolDictType = {vol.Required(ATTR_FILENAME): cv.template}

CAMERA_SERVICE_PLAY_STREAM: VolDictType = {
    vol.Required(ATTR_MEDIA_PLAYER): cv.entities_domain(DOMAIN_MP),
    vol.Optional(ATTR_FORMAT, default="hls"): vol.In(OUTPUT_FORMATS),
}

CAMERA_SERVICE_RECORD: VolDictType = {
    vol.Required(CONF_FILENAME): cv.template,
    vol.Optional(CONF_DURATION, default=30): vol.Coerce(int),
    vol.Optional(CONF_LOOKBACK, default=0): vol.Coerce(int),
}


class CameraEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes camera entities."""


@attr.s
class Image:
    """Represent an image."""

    content_type: str = attr.ib()
    content: bytes = attr.ib()


@bind_hass
async def async_request_stream(hass: HomeAssistant, entity_id: str, fmt: str) -> str:
    """Request a stream for a camera entity."""
    camera = get_camera_from_entity_id(hass, entity_id)
    return await _async_stream_endpoint_url(hass, camera, fmt)


async def _async_get_image(
    camera: Camera,
    timeout: int = 10,
    width: int | None = None,
    height: int | None = None,
) -> Image:
    """Fetch a snapshot image from a camera.

    If width and height are passed, an attempt to scale
    the image will be made on a best effort basis.
    Not all cameras can scale images or return jpegs
    that we can scale, however the majority of cases
    are handled.
    """
    with suppress(asyncio.CancelledError, TimeoutError):
        async with asyncio.timeout(timeout):
            image_bytes = (
                await _async_get_stream_image(
                    camera, width=width, height=height, wait_for_next_keyframe=False
                )
                if camera.use_stream_for_stills
                else await camera.async_camera_image(width=width, height=height)
            )
            if image_bytes:
                content_type = camera.content_type
                image = Image(content_type, image_bytes)
                if (
                    width is not None
                    and height is not None
                    and ("jpeg" in content_type or "jpg" in content_type)
                ):
                    assert width is not None
                    assert height is not None
                    return Image(
                        content_type, scale_jpeg_camera_image(image, width, height)
                    )

                return image

    raise HomeAssistantError("Unable to get image")


@bind_hass
async def async_get_image(
    hass: HomeAssistant,
    entity_id: str,
    timeout: int = 10,
    width: int | None = None,
    height: int | None = None,
) -> Image:
    """Fetch an image from a camera entity.

    width and height will be passed to the underlying camera.
    """
    camera = get_camera_from_entity_id(hass, entity_id)
    return await _async_get_image(camera, timeout, width, height)


async def _async_get_stream_image(
    camera: Camera,
    width: int | None = None,
    height: int | None = None,
    wait_for_next_keyframe: bool = False,
) -> bytes | None:
    if not camera.stream and CameraEntityFeature.STREAM in camera.supported_features:
        camera.stream = await camera.async_create_stream()
    if camera.stream:
        return await camera.stream.async_get_image(
            width=width, height=height, wait_for_next_keyframe=wait_for_next_keyframe
        )
    return None


@bind_hass
async def async_get_stream_source(hass: HomeAssistant, entity_id: str) -> str | None:
    """Fetch the stream source for a camera entity."""
    camera = get_camera_from_entity_id(hass, entity_id)
    return await camera.stream_source()


@bind_hass
async def async_get_mjpeg_stream(
    hass: HomeAssistant, request: web.Request, entity_id: str
) -> web.StreamResponse | None:
    """Fetch an mjpeg stream from a camera entity."""
    camera = get_camera_from_entity_id(hass, entity_id)

    try:
        stream = await camera.handle_async_mjpeg_stream(request)
    except ConnectionResetError:
        stream = None
        _LOGGER.debug("Error while writing MJPEG stream to transport")
    return stream


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the camera component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[Camera](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    prefs = CameraPreferences(hass)
    await prefs.async_load()
    hass.data[DATA_CAMERA_PREFS] = prefs

    hass.http.register_view(CameraImageView(component))
    hass.http.register_view(CameraMjpegStream(component))

    websocket_api.async_register_command(hass, ws_camera_stream)
    websocket_api.async_register_command(hass, ws_camera_web_rtc_offer)
    websocket_api.async_register_command(hass, websocket_get_prefs)
    websocket_api.async_register_command(hass, websocket_update_prefs)
    websocket_api.async_register_command(hass, ws_get_client_config)

    await component.async_setup(config)

    async def preload_stream(_event: Event) -> None:
        """Load stream prefs and start stream if preload_stream is True."""
        for camera in list(component.entities):
            stream_prefs = await prefs.get_dynamic_stream_settings(camera.entity_id)
            if not stream_prefs.preload_stream:
                continue
            stream = await camera.async_create_stream()
            if not stream:
                continue
            stream.add_provider("hls")
            await stream.start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, preload_stream)

    @callback
    def update_tokens(t: datetime) -> None:
        """Update tokens of the entities."""
        for entity in component.entities:
            entity.async_update_token()
            entity.async_write_ha_state()

    unsub = async_track_time_interval(
        hass, update_tokens, TOKEN_CHANGE_INTERVAL, name="Camera update tokens"
    )

    @callback
    def unsub_track_time_interval(_event: Event) -> None:
        """Unsubscribe track time interval timer."""
        unsub()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsub_track_time_interval)

    component.async_register_entity_service(
        SERVICE_ENABLE_MOTION, None, "async_enable_motion_detection"
    )
    component.async_register_entity_service(
        SERVICE_DISABLE_MOTION, None, "async_disable_motion_detection"
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(
        SERVICE_SNAPSHOT, CAMERA_SERVICE_SNAPSHOT, async_handle_snapshot_service
    )
    component.async_register_entity_service(
        SERVICE_PLAY_STREAM,
        CAMERA_SERVICE_PLAY_STREAM,
        async_handle_play_stream_service,
    )
    component.async_register_entity_service(
        SERVICE_RECORD, CAMERA_SERVICE_RECORD, async_handle_record_service
    )

    async def get_ice_server() -> RTCIceServer:
        return RTCIceServer(urls="stun:stun.home-assistant.io:3478")

    register_ice_server(hass, get_ice_server)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


CACHED_PROPERTIES_WITH_ATTR_ = {
    "brand",
    "frame_interval",
    "frontend_stream_type",
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
        {"access_token", "entity_picture"}
    )

    # Entity Properties
    _attr_brand: str | None = None
    _attr_frame_interval: float = MIN_STREAM_INTERVAL
    _attr_frontend_stream_type: StreamType | None
    _attr_is_on: bool = True
    _attr_is_recording: bool = False
    _attr_is_streaming: bool = False
    _attr_model: str | None = None
    _attr_motion_detection_enabled: bool = False
    _attr_should_poll: bool = False  # No need to poll cameras
    _attr_state: None = None  # State is determined by is_on
    _attr_supported_features: CameraEntityFeature = CameraEntityFeature(0)

    def __init__(self) -> None:
        """Initialize a camera."""
        self.stream: Stream | None = None
        self.stream_options: dict[str, str | bool | float] = {}
        self.content_type: str = DEFAULT_CONTENT_TYPE
        self.access_tokens: collections.deque = collections.deque([], 2)
        self._warned_old_signature = False
        self.async_update_token()
        self._create_stream_lock: asyncio.Lock | None = None
        self._webrtc_providers: list[CameraWebRTCProvider] = []

    @cached_property
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
    def supported_features(self) -> CameraEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def supported_features_compat(self) -> CameraEntityFeature:
        """Return the supported features as CameraEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is int:  # noqa: E721
            new_features = CameraEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

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

    @property
    def frontend_stream_type(self) -> StreamType | None:
        """Return the type of stream supported by this camera.

        A camera may have a single stream type which is used to inform the
        frontend which camera attributes and player to use. The default type
        is to use HLS, and components can override to change the type.
        """
        if hasattr(self, "_attr_frontend_stream_type"):
            return self._attr_frontend_stream_type
        if CameraEntityFeature.STREAM not in self.supported_features_compat:
            return None
        if self._webrtc_providers:
            return StreamType.WEB_RTC
        return StreamType.HLS

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if (stream := self.stream) and not stream.available:
            return False
        return super().available

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
                    dynamic_stream_settings=await self.hass.data[
                        DATA_CAMERA_PREFS
                    ].get_dynamic_stream_settings(self.entity_id),
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

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        """Handle the WebRTC offer and return an answer.

        This is used by cameras with CameraEntityFeature.STREAM
        and StreamType.WEB_RTC.

        Integrations can override with a native WebRTC implementation.
        """
        for provider in self._webrtc_providers:
            if answer := await provider.async_handle_web_rtc_offer(self, offer_sdp):
                return answer
        raise HomeAssistantError(
            "WebRTC offer was not accepted by the supported providers"
        )

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
    def state_attributes(self) -> dict[str, str | None]:
        """Return the camera state attributes."""
        attrs = {"access_token": self.access_tokens[-1]}

        if model := self.model:
            attrs["model_name"] = model

        if brand := self.brand:
            attrs["brand"] = brand

        if motion_detection_enabled := self.motion_detection_enabled:
            attrs["motion_detection"] = motion_detection_enabled

        if frontend_stream_type := self.frontend_stream_type:
            attrs["frontend_stream_type"] = frontend_stream_type

        return attrs

    @callback
    def async_update_token(self) -> None:
        """Update the used token."""
        self.access_tokens.append(hex(_RND.getrandbits(256))[2:])
        self.__dict__.pop("entity_picture", None)

    async def async_internal_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_internal_added_to_hass()
        # Avoid calling async_refresh_providers() in here because it
        # it will write state a second time since state is always
        # written when an entity is added to hass.
        self._webrtc_providers = await self._async_get_supported_webrtc_providers()

    async def async_refresh_providers(self) -> None:
        """Determine if any of the registered providers are suitable for this entity.

        This affects state attributes, so it should be invoked any time the registered
        providers or inputs to the state attributes change.

        Returns True if any state was updated (and needs to be written)
        """
        old_providers = self._webrtc_providers
        new_providers = await self._async_get_supported_webrtc_providers()
        self._webrtc_providers = new_providers
        if old_providers != new_providers:
            self.async_write_ha_state()

    async def _async_get_supported_webrtc_providers(
        self,
    ) -> list[CameraWebRTCProvider]:
        """Get the all providers that supports this camera."""
        if CameraEntityFeature.STREAM not in self.supported_features_compat:
            return []

        return await async_get_supported_providers(self.hass, self)

    @property
    def webrtc_providers(self) -> list[CameraWebRTCProvider]:
        """Return the WebRTC providers."""
        return self._webrtc_providers

    async def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration adjustable per integration."""
        return WebRTCClientConfiguration()

    @final
    async def async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration and extend it with the registered ice servers."""
        config = await self._async_get_webrtc_client_configuration()

        ice_servers = await asyncio.gather(
            *[server() for server in self.hass.data.get(DATA_ICE_SERVERS, [])]
        )
        config.configuration.ice_servers.extend(ice_servers)

        return config


class CameraView(HomeAssistantView):
    """Base CameraView."""

    requires_auth = False

    def __init__(self, component: EntityComponent[Camera]) -> None:
        """Initialize a basic camera view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Start a GET request."""
        if (camera := self.component.get_entity(entity_id)) is None:
            raise web.HTTPNotFound

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") in camera.access_tokens
        )

        if not authenticated:
            # Attempt with invalid bearer token, raise unauthorized
            # so ban middleware can handle it.
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized
            # Invalid sigAuth or camera access token
            raise web.HTTPForbidden

        if not camera.is_on:
            _LOGGER.debug("Camera is off")
            raise web.HTTPServiceUnavailable

        return await self.handle(request, camera)

    async def handle(self, request: web.Request, camera: Camera) -> web.StreamResponse:
        """Handle the camera request."""
        raise NotImplementedError


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = "/api/camera_proxy/{entity_id}"
    name = "api:camera:image"

    async def handle(self, request: web.Request, camera: Camera) -> web.Response:
        """Serve camera image."""
        width = request.query.get("width")
        height = request.query.get("height")
        try:
            image = await _async_get_image(
                camera,
                CAMERA_IMAGE_TIMEOUT,
                int(width) if width else None,
                int(height) if height else None,
            )
        except (HomeAssistantError, ValueError) as ex:
            raise web.HTTPInternalServerError from ex

        return web.Response(body=image.content, content_type=image.content_type)


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = "/api/camera_proxy_stream/{entity_id}"
    name = "api:camera:stream"

    async def handle(self, request: web.Request, camera: Camera) -> web.StreamResponse:
        """Serve camera stream, possibly with interval."""
        if (interval_str := request.query.get("interval")) is None:
            try:
                stream = await camera.handle_async_mjpeg_stream(request)
            except ConnectionResetError:
                stream = None
                _LOGGER.debug("Error while writing MJPEG stream to transport")
            if stream is None:
                raise web.HTTPBadGateway
            return stream

        try:
            # Compose camera stream from stills
            interval = float(interval_str)
            if interval < MIN_STREAM_INTERVAL:
                raise ValueError(f"Stream interval must be > {MIN_STREAM_INTERVAL}")  # noqa: TRY301
            return await camera.handle_async_still_stream(request, interval)
        except ValueError as err:
            raise web.HTTPBadRequest from err


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/stream",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("format", default="hls"): vol.In(OUTPUT_FORMATS),
    }
)
@websocket_api.async_response
async def ws_camera_stream(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get camera stream websocket command.

    Async friendly.
    """
    try:
        entity_id = msg["entity_id"]
        camera = get_camera_from_entity_id(hass, entity_id)
        url = await _async_stream_endpoint_url(hass, camera, fmt=msg["format"])
        connection.send_result(msg["id"], {"url": url})
    except HomeAssistantError as ex:
        _LOGGER.error("Error requesting stream: %s", ex)
        connection.send_error(msg["id"], "start_stream_failed", str(ex))
    except TimeoutError:
        _LOGGER.error("Timeout getting stream source")
        connection.send_error(
            msg["id"], "start_stream_failed", "Timeout getting stream source"
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/web_rtc_offer",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("offer"): str,
    }
)
@websocket_api.async_response
async def ws_camera_web_rtc_offer(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle the signal path for a WebRTC stream.

    This signal path is used to route the offer created by the client to the
    camera device through the integration for negotiation on initial setup,
    which returns an answer. The actual streaming is handled entirely between
    the client and camera device.

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
    try:
        answer = await camera.async_handle_web_rtc_offer(offer)
    except (HomeAssistantError, ValueError) as ex:
        _LOGGER.error("Error handling WebRTC offer: %s", ex)
        connection.send_error(msg["id"], "web_rtc_offer_failed", str(ex))
    except TimeoutError:
        _LOGGER.error("Timeout handling WebRTC offer")
        connection.send_error(
            msg["id"], "web_rtc_offer_failed", "Timeout handling WebRTC offer"
        )
    else:
        connection.send_result(msg["id"], {"answer": answer})


@websocket_api.websocket_command(
    {vol.Required("type"): "camera/get_prefs", vol.Required("entity_id"): cv.entity_id}
)
@websocket_api.async_response
async def websocket_get_prefs(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle request for account info."""
    stream_prefs = await hass.data[DATA_CAMERA_PREFS].get_dynamic_stream_settings(
        msg["entity_id"]
    )
    connection.send_result(msg["id"], asdict(stream_prefs))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "camera/update_prefs",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional(PREF_PRELOAD_STREAM): bool,
        vol.Optional(PREF_ORIENTATION): vol.Coerce(Orientation),
    }
)
@websocket_api.async_response
async def websocket_update_prefs(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle request for account info."""
    changes = dict(msg)
    changes.pop("id")
    changes.pop("type")
    entity_id = changes.pop("entity_id")
    try:
        entity_prefs = await hass.data[DATA_CAMERA_PREFS].async_update(
            entity_id, **changes
        )
    except HomeAssistantError as ex:
        _LOGGER.error("Error setting camera preferences: %s", ex)
        connection.send_error(msg["id"], "update_failed", str(ex))
    else:
        connection.send_result(msg["id"], entity_prefs)


async def async_handle_snapshot_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle snapshot services calls."""
    hass = camera.hass
    filename: Template = service_call.data[ATTR_FILENAME]

    snapshot_file = filename.async_render(variables={ATTR_ENTITY_ID: camera})

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        raise HomeAssistantError(
            f"Cannot write `{snapshot_file}`, no access to path; `allowlist_external_dirs` may need to be adjusted in `configuration.yaml`"
        )

    async with asyncio.timeout(CAMERA_IMAGE_TIMEOUT):
        image = (
            await _async_get_stream_image(camera, wait_for_next_keyframe=True)
            if camera.use_stream_for_stills
            else await camera.async_camera_image()
        )

    if image is None:
        return

    def _write_image(to_file: str, image_data: bytes) -> None:
        """Executor helper to write image."""
        os.makedirs(os.path.dirname(to_file), exist_ok=True)
        with open(to_file, "wb") as img_file:
            img_file.write(image_data)

    try:
        await hass.async_add_executor_job(_write_image, snapshot_file, image)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)


async def async_handle_play_stream_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle play stream services calls."""
    hass = camera.hass
    fmt = service_call.data[ATTR_FORMAT]
    url = await _async_stream_endpoint_url(camera.hass, camera, fmt)
    url = f"{get_url(hass)}{url}"

    await hass.services.async_call(
        DOMAIN_MP,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: service_call.data[ATTR_MEDIA_PLAYER],
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: FORMAT_CONTENT_TYPE[fmt],
        },
        blocking=True,
        context=service_call.context,
    )


async def _async_stream_endpoint_url(
    hass: HomeAssistant, camera: Camera, fmt: str
) -> str:
    stream = await camera.async_create_stream()
    if not stream:
        raise HomeAssistantError(
            f"{camera.entity_id} does not support play stream service"
        )

    stream.add_provider(fmt)
    await stream.start()
    return stream.endpoint_url(fmt)


async def async_handle_record_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle stream recording service calls."""
    stream = await camera.async_create_stream()

    if not stream:
        raise HomeAssistantError(f"{camera.entity_id} does not support record service")

    filename = service_call.data[CONF_FILENAME]
    video_path = filename.async_render(variables={ATTR_ENTITY_ID: camera})

    await stream.async_record(
        video_path,
        duration=service_call.data[CONF_DURATION],
        lookback=service_call.data[CONF_LOOKBACK],
    )


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
