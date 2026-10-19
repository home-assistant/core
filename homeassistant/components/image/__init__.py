"""The image integration."""

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import Final, override

from aiohttp import hdrs, web

from homeassistant.components.http import KEY_AUTHENTICATED, KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONTENT_TYPE_MULTIPART, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FILENAME,
    DATA_COMPONENT,
    DEFAULT_CONTENT_TYPE,
    DOMAIN,
    GET_IMAGE_TIMEOUT,
    IMAGE_TIMEOUT,
    SERVICE_SNAPSHOT,
    ImageEntityStateAttribute,
)
from .entity import (
    Image,
    ImageContentTypeError,
    ImageEntity,
    ImageEntityDescription,
    infer_image_type,
    valid_image_content_type,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)


TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=5)


FRAME_BOUNDARY = "frame-boundary"
FRAME_SEPARATOR = bytes(f"\r\n--{FRAME_BOUNDARY}\r\n", "utf-8")
LAST_FRAME_MARKER = bytes(f"\r\n--{FRAME_BOUNDARY}--\r\n", "utf-8")


__all__ = [
    "ATTR_FILENAME",
    "DEFAULT_CONTENT_TYPE",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "GET_IMAGE_TIMEOUT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SNAPSHOT",
    "Image",
    "ImageContentTypeError",
    "ImageEntity",
    "ImageEntityDescription",
    "ImageEntityStateAttribute",
    "async_get_image",
    "infer_image_type",
    "valid_image_content_type",
]


async def _async_get_image(image_entity: ImageEntity, timeout: int) -> Image:
    """Fetch image from an image entity."""
    with suppress(TimeoutError, ImageContentTypeError):
        async with asyncio.timeout(timeout):
            if image_bytes := await image_entity.async_image():
                content_type = valid_image_content_type(image_entity.content_type)
                return Image(content_type, image_bytes)

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="image_unavailable",
        translation_placeholders={"entity_id": image_entity.entity_id},
    )


async def async_get_image(
    hass: HomeAssistant,
    entity_id: str,
    timeout: int = 10,
) -> Image:
    """Fetch an image from an image entity."""
    component = hass.data[DATA_COMPONENT]

    if (image := component.get_entity(entity_id)) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    return await _async_get_image(image, timeout)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the image component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ImageEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    hass.http.register_view(ImageView(component))
    hass.http.register_view(ImageStreamView(component))

    await component.async_setup(config)

    @callback
    def update_tokens(time: datetime) -> None:
        """Update tokens of the entities."""
        for entity in component.entities:
            entity.async_update_token()
            entity.async_write_ha_state()

    unsub = async_track_time_interval(
        hass, update_tokens, TOKEN_CHANGE_INTERVAL, name="Image update tokens"
    )

    @callback
    def unsub_track_time_interval(_event: Event) -> None:
        """Unsubscribe track time interval timer."""
        unsub()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsub_track_time_interval)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class ImageView(HomeAssistantView):
    """View to serve an image."""

    name = "api:image:image"
    requires_auth = False
    url = "/api/image_proxy/{entity_id}"

    def __init__(self, component: EntityComponent[ImageEntity]) -> None:
        """Initialize an image view."""
        self.component = component

    async def _authenticate_request(
        self, request: web.Request, entity_id: str
    ) -> ImageEntity:
        """Authenticate request and return image entity."""
        if (image_entity := self.component.get_entity(entity_id)) is None:
            raise (
                web.HTTPNotFound if request[KEY_AUTHENTICATED] else web.HTTPUnauthorized
            )

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") in image_entity.access_tokens
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

        return image_entity

    async def head(self, request: web.Request, entity_id: str) -> web.Response:
        """Start a HEAD request.

        This is sent by some DLNA renderers, like Samsung ones, prior to sending
        the GET request.
        """
        image_entity = await self._authenticate_request(request, entity_id)

        # Don't use `handle` as we don't care about the stream case, we only want
        # to verify that the image exists.
        try:
            image = await _async_get_image(image_entity, IMAGE_TIMEOUT)
        except (HomeAssistantError, ValueError) as ex:
            raise web.HTTPInternalServerError from ex

        return web.Response(
            content_type=image.content_type,
            headers={"Content-Length": str(len(image.content))},
        )

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Start a GET request."""
        image_entity = await self._authenticate_request(request, entity_id)
        return await self.handle(request, image_entity)

    async def handle(
        self, request: web.Request, image_entity: ImageEntity
    ) -> web.StreamResponse:
        """Serve image."""
        try:
            image = await _async_get_image(image_entity, IMAGE_TIMEOUT)
        except (HomeAssistantError, ValueError) as ex:
            raise web.HTTPInternalServerError from ex

        return web.Response(
            body=image.content,
            content_type=image.content_type,
            headers={"Content-Length": str(len(image.content))},
        )


async def async_get_still_stream(
    request: web.Request,
    image_entity: ImageEntity,
) -> web.StreamResponse:
    """Generate an HTTP multipart stream from the Image."""
    response = web.StreamResponse()
    response.content_type = CONTENT_TYPE_MULTIPART.format(FRAME_BOUNDARY)
    await response.prepare(request)

    async def _write_frame() -> bool:
        img_bytes = await image_entity.async_image()
        if img_bytes is None:
            await response.write(LAST_FRAME_MARKER)
            return False
        frame = bytearray(FRAME_SEPARATOR)
        header = bytes(
            f"Content-Type: {image_entity.content_type}\r\n"
            f"Content-Length: {len(img_bytes)}\r\n\r\n",
            "utf-8",
        )
        frame.extend(header)
        frame.extend(img_bytes)
        # Chrome shows the n-1 frame so send the frame twice
        # https://issues.chromium.org/issues/41199053
        # https://issues.chromium.org/issues/40791855
        # While this results in additional bandwidth usage,
        # given the low frequency of image updates, it is acceptable.
        frame.extend(frame)
        await response.write(frame)
        return True

    event = asyncio.Event()
    timed_out = False

    @callback
    def _async_image_state_update(_event: Event[EventStateChangedData]) -> None:
        """Write image to stream."""
        event.set()

    @callback
    def _async_timeout_reached() -> None:
        """Handle timeout."""
        nonlocal timed_out
        timed_out = True
        event.set()

    hass = request.app[KEY_HASS]
    loop = hass.loop
    remove = async_track_state_change_event(
        hass,
        image_entity.entity_id,
        _async_image_state_update,
    )
    timeout_handle = None
    try:
        while True:
            if not await _write_frame():
                return response
            # Ensure that an image is sent at least every 55 seconds
            # Otherwise some devices go blank
            timeout_handle = loop.call_later(55, _async_timeout_reached)
            await event.wait()
            event.clear()
            if not timed_out:
                timeout_handle.cancel()
            timed_out = False
    finally:
        if timeout_handle:
            timeout_handle.cancel()
        remove()


class ImageStreamView(ImageView):
    """Image View to serve an multipart stream."""

    url = "/api/image_proxy_stream/{entity_id}"
    name = "api:image:stream"

    @override
    async def handle(
        self, request: web.Request, image_entity: ImageEntity
    ) -> web.StreamResponse:
        """Serve image stream."""
        return await async_get_still_stream(request, image_entity)
