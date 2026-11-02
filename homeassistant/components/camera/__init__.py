"""Component to interface with cameras."""

import asyncio
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timedelta
import logging
from typing import Any, Final, override

from aiohttp import hdrs, web
import attr
import probatio

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.stream import OUTPUT_FORMATS, Orientation
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_FILENAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FILENAME,
    ATTR_FORMAT,
    ATTR_MEDIA_PLAYER,
    CAMERA_IMAGE_TIMEOUT,
    CONF_DURATION,
    CONF_LOOKBACK,
    DATA_CAMERA_PREFS,
    DATA_COMPONENT,
    DEFAULT_CONTENT_TYPE,
    DOMAIN,
    MIN_STREAM_INTERVAL,
    PREF_ORIENTATION,
    PREF_PRELOAD_STREAM,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
    SERVICE_PLAY_STREAM,
    SERVICE_RECORD,
    SERVICE_SNAPSHOT,
    CameraEntityFeature,
    CameraEntityStateAttribute,
    CameraService,
    CameraServiceArgument,
    CameraState,
    StreamType,
)
from .entity import (
    Camera,
    CameraCapabilities,
    CameraEntityCapabilities,
    CameraEntityDescription,
    async_get_still_stream,
)
from .helper import (
    async_get_stream_image,
    async_stream_endpoint_url,
    get_camera_from_entity_id,
)
from .img_util import TurboJPEGSingleton, scale_jpeg_camera_image
from .prefs import (
    CameraPreferences,
    DynamicStreamSettings,
    get_dynamic_camera_stream_settings,
)
from .services import async_setup_services
from .webrtc import (
    CameraWebRTCProvider,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCClientConfiguration,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
    async_call_webrtc_provider,
    async_register_webrtc_provider,
    async_register_ws,
)

_LOGGER = logging.getLogger(__name__)


ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)


TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=5)


__all__ = [
    "ATTR_FILENAME",
    "ATTR_FORMAT",
    "ATTR_MEDIA_PLAYER",
    "CAMERA_IMAGE_TIMEOUT",
    "CONF_DURATION",
    "CONF_FILENAME",
    "CONF_LOOKBACK",
    "DEFAULT_CONTENT_TYPE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_DISABLE_MOTION",
    "SERVICE_ENABLE_MOTION",
    "SERVICE_PLAY_STREAM",
    "SERVICE_RECORD",
    "SERVICE_SNAPSHOT",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "TOKEN_CHANGE_INTERVAL",
    "Camera",
    "CameraCapabilities",
    "CameraEntityCapabilities",
    "CameraEntityDescription",
    "CameraEntityFeature",
    "CameraEntityStateAttribute",
    "CameraImageView",
    "CameraService",
    "CameraServiceArgument",
    "CameraState",
    "CameraView",
    "CameraWebRTCProvider",
    "DynamicStreamSettings",
    "Image",
    "StreamType",
    "TurboJPEGSingleton",
    "WebRTCAnswer",
    "WebRTCCandidate",
    "WebRTCClientConfiguration",
    "WebRTCError",
    "WebRTCMessage",
    "WebRTCSendMessage",
    "async_get_image",
    "async_get_mjpeg_stream",
    "async_get_still_stream",
    "async_get_stream_source",
    "async_register_webrtc_provider",
    "async_request_stream",
    "get_camera_from_entity_id",
    "get_dynamic_camera_stream_settings",
]


@attr.s
class Image:
    """Represent an image."""

    content_type: str = attr.ib()
    content: bytes = attr.ib()


async def async_request_stream(hass: HomeAssistant, entity_id: str, fmt: str) -> str:
    """Request a stream for a camera entity."""
    camera = get_camera_from_entity_id(hass, entity_id)
    return await async_stream_endpoint_url(hass, camera, fmt)


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
    with suppress(TimeoutError):
        async with asyncio.timeout(timeout):
            image_bytes = (
                await async_get_stream_image(
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


async def async_get_stream_source(hass: HomeAssistant, entity_id: str) -> str | None:
    """Fetch the stream source for a camera entity."""
    camera = get_camera_from_entity_id(hass, entity_id)
    return await camera.stream_source()


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
    websocket_api.async_register_command(hass, websocket_get_prefs)
    websocket_api.async_register_command(hass, websocket_update_prefs)
    websocket_api.async_register_command(hass, ws_camera_capabilities)
    async_register_ws(hass)

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

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class CameraView(HomeAssistantView):
    """Base CameraView."""

    requires_auth = False

    def __init__(self, component: EntityComponent[Camera]) -> None:
        """Initialize a basic camera view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Start a GET request."""
        if (camera := self.component.get_entity(entity_id)) is None:
            raise (
                web.HTTPNotFound if request[KEY_AUTHENTICATED] else web.HTTPUnauthorized
            )

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") in camera.access_tokens
        )

        if not authenticated:
            if hdrs.AUTHORIZATION in request.headers:
                # A failed request that carried an Authorization header is a real
                # Bearer auth attempt — return 401 and let the ban middleware count
                # it as a wrong login.
                raise web.HTTPUnauthorized
            # No Authorization header: most likely a benign signed-URL / query-
            # token request whose token has expired (e.g. a browser tab left
            # open that re-fetches resources later). Return 403 so it doesn't
            # register as a wrong login and ban the user's own IP.
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

    @override
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

    @override
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
        probatio.Required("type"): "camera/capabilities",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def ws_camera_capabilities(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle get camera capabilities websocket command.

    Async friendly.
    """
    camera = get_camera_from_entity_id(hass, msg["entity_id"])
    connection.send_result(msg["id"], asdict(camera.camera_capabilities))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "camera/stream",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Optional("format", default="hls"): probatio.In(OUTPUT_FORMATS),
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
        url = await async_stream_endpoint_url(hass, camera, fmt=msg["format"])
        connection.send_result(msg["id"], {"url": url})
    except HomeAssistantError as ex:
        _LOGGER.error("Error requesting stream: %s", ex)
        connection.send_error(
            msg["id"],
            "start_stream_failed",
            str(ex),
            translation_domain=ex.translation_domain,
            translation_key=ex.translation_key,
            translation_placeholders=ex.translation_placeholders,
        )
    except TimeoutError:
        _LOGGER.error("Timeout getting stream source")
        connection.send_error(
            msg["id"], "start_stream_failed", "Timeout getting stream source"
        )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "camera/get_prefs",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_get_prefs(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle request for account info."""
    stream_prefs = await get_dynamic_camera_stream_settings(hass, msg["entity_id"])
    connection.send_result(msg["id"], asdict(stream_prefs))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "camera/update_prefs",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Optional(PREF_PRELOAD_STREAM): bool,
        probatio.Optional(PREF_ORIENTATION): probatio.Coerce(Orientation),
    }
)
@websocket_api.require_admin
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
        if (camera := hass.data[DATA_COMPONENT].get_entity(entity_id)) and (
            provider := camera.webrtc_provider
        ):
            await async_call_webrtc_provider(
                provider.async_on_camera_prefs_update(camera),
                "notifying WebRTC provider of preferences update for",
                entity_id,
            )
        connection.send_result(msg["id"], entity_prefs)
