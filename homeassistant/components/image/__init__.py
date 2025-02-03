"""The image integration."""

from __future__ import annotations

import asyncio
import collections
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import os
from random import SystemRandom
from typing import Final, final

from aiohttp import hdrs, web
import httpx
from propcache.api import cached_property
import voluptuous as vol

from homeassistant.components.http import KEY_AUTHENTICATED, KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONTENT_TYPE_MULTIPART, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import (
    UNDEFINED,
    ConfigType,
    UndefinedType,
    VolDictType,
)

from .const import DATA_COMPONENT, DOMAIN, IMAGE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

SERVICE_SNAPSHOT: Final = "snapshot"

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

ATTR_FILENAME: Final = "filename"

DEFAULT_CONTENT_TYPE: Final = "image/jpeg"
ENTITY_IMAGE_URL: Final = "/api/image_proxy/{0}?token={1}"

TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=5)
_RND: Final = SystemRandom()

GET_IMAGE_TIMEOUT: Final = 10

FRAME_BOUNDARY = "frame-boundary"
FRAME_SEPARATOR = bytes(f"\r\n--{FRAME_BOUNDARY}\r\n", "utf-8")
LAST_FRAME_MARKER = bytes(f"\r\n--{FRAME_BOUNDARY}--\r\n", "utf-8")

IMAGE_SERVICE_SNAPSHOT: VolDictType = {vol.Required(ATTR_FILENAME): cv.string}


class ImageEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes image entities."""


@dataclass
class Image:
    """Represent an image."""

    content_type: str
    content: bytes


class ImageContentTypeError(HomeAssistantError):
    """Error with the content type while loading an image."""


def valid_image_content_type(content_type: str | None) -> str:
    """Validate the assigned content type is one of an image."""
    if content_type is None or content_type.split("/", 1)[0].lower() != "image":
        raise ImageContentTypeError
    return content_type


async def _async_get_image(image_entity: ImageEntity, timeout: int) -> Image:
    """Fetch image from an image entity."""
    with suppress(asyncio.CancelledError, TimeoutError, ImageContentTypeError):
        async with asyncio.timeout(timeout):
            if image_bytes := await image_entity.async_image():
                content_type = valid_image_content_type(image_entity.content_type)
                return Image(content_type, image_bytes)

    raise HomeAssistantError("Unable to get image")


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

    component.async_register_entity_service(
        SERVICE_SNAPSHOT, IMAGE_SERVICE_SNAPSHOT, async_handle_snapshot_service
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


CACHED_PROPERTIES_WITH_ATTR_ = {
    "content_type",
    "image_last_updated",
    "image_url",
}


class ImageEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """The base class for image entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {"access_token", "entity_picture"}
    )

    # Entity Properties
    _attr_content_type: str = DEFAULT_CONTENT_TYPE
    _attr_image_last_updated: datetime | None = None
    _attr_image_url: str | None | UndefinedType = UNDEFINED
    _attr_should_poll: bool = False  # No need to poll image entities
    _attr_state: None = None  # State is determined by last_updated
    _cached_image: Image | None = None

    def __init__(self, hass: HomeAssistant, verify_ssl: bool = False) -> None:
        """Initialize an image entity."""
        self._client = get_async_client(hass, verify_ssl=verify_ssl)
        self.access_tokens: collections.deque = collections.deque([], 2)
        self.async_update_token()

    @cached_property
    def content_type(self) -> str:
        """Image content type."""
        return self._attr_content_type

    @property
    def entity_picture(self) -> str | None:
        """Return a link to the image as entity picture."""
        if self._attr_entity_picture is not None:
            return self._attr_entity_picture
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_tokens[-1])

    @cached_property
    def image_last_updated(self) -> datetime | None:
        """Time the image was last updated."""
        return self._attr_image_last_updated

    @cached_property
    def image_url(self) -> str | None | UndefinedType:
        """Return URL of image."""
        return self._attr_image_url

    def image(self) -> bytes | None:
        """Return bytes of image."""
        raise NotImplementedError

    async def _fetch_url(self, url: str) -> httpx.Response | None:
        """Fetch a URL."""
        try:
            response = await self._client.get(
                url, timeout=GET_IMAGE_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            _LOGGER.error("%s: Timeout getting image from %s", self.entity_id, url)
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error(
                "%s: Error getting new image from %s: %s",
                self.entity_id,
                url,
                err,
            )
            return None
        return response

    async def _async_load_image_from_url(self, url: str) -> Image | None:
        """Load an image by url."""
        if response := await self._fetch_url(url):
            content_type = response.headers.get("content-type")
            try:
                return Image(
                    content=response.content,
                    content_type=valid_image_content_type(content_type),
                )
            except ImageContentTypeError:
                _LOGGER.error(
                    "%s: Image from %s has invalid content type: %s",
                    self.entity_id,
                    url,
                    content_type,
                )
                return None
        return None

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""

        if self._cached_image:
            return self._cached_image.content
        if (url := self.image_url) is not UNDEFINED:
            if not url or (image := await self._async_load_image_from_url(url)) is None:
                return None
            self._cached_image = image
            self._attr_content_type = image.content_type
            return image.content
        return await self.hass.async_add_executor_job(self.image)

    @property
    @final
    def state(self) -> str | None:
        """Return the state."""
        if self.image_last_updated is None:
            return None
        return self.image_last_updated.isoformat()

    @final
    @property
    def state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return {"access_token": self.access_tokens[-1]}

    @callback
    def async_update_token(self) -> None:
        """Update the used token."""
        self.access_tokens.append(hex(_RND.getrandbits(256))[2:])


class ImageView(HomeAssistantView):
    """View to serve an image."""

    name = "api:image:image"
    requires_auth = False
    url = "/api/image_proxy/{entity_id}"

    def __init__(self, component: EntityComponent[ImageEntity]) -> None:
        """Initialize an image view."""
        self.component = component

    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Start a GET request."""
        if (image_entity := self.component.get_entity(entity_id)) is None:
            raise web.HTTPNotFound

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") in image_entity.access_tokens
        )

        if not authenticated:
            # Attempt with invalid bearer token, raise unauthorized
            # so ban middleware can handle it.
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized
            # Invalid sigAuth or image entity access token
            raise web.HTTPForbidden

        return await self.handle(request, image_entity)

    async def handle(
        self, request: web.Request, image_entity: ImageEntity
    ) -> web.StreamResponse:
        """Serve image."""
        try:
            image = await _async_get_image(image_entity, IMAGE_TIMEOUT)
        except (HomeAssistantError, ValueError) as ex:
            raise web.HTTPInternalServerError from ex

        return web.Response(body=image.content, content_type=image.content_type)


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

    async def handle(
        self, request: web.Request, image_entity: ImageEntity
    ) -> web.StreamResponse:
        """Serve image stream."""
        return await async_get_still_stream(request, image_entity)


async def async_handle_snapshot_service(
    image: ImageEntity, service_call: ServiceCall
) -> None:
    """Handle snapshot services calls."""
    hass = image.hass
    snapshot_file: str = service_call.data[ATTR_FILENAME]

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        raise HomeAssistantError(
            f"Cannot write `{snapshot_file}`, no access to path; `allowlist_external_dirs` may need to be adjusted in `configuration.yaml`"
        )

    async with asyncio.timeout(IMAGE_TIMEOUT):
        image_data = await image.async_image()

    if image_data is None:
        return

    def _write_image(to_file: str, image_data: bytes) -> None:
        """Executor helper to write image."""
        os.makedirs(os.path.dirname(to_file), exist_ok=True)
        with open(to_file, "wb") as img_file:
            img_file.write(image_data)

    try:
        await hass.async_add_executor_job(_write_image, snapshot_file, image_data)
    except OSError as err:
        raise HomeAssistantError("Can't write image to file") from err
