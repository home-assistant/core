"""The image integration."""
from __future__ import annotations

import asyncio
import collections
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from random import SystemRandom
from typing import Final, final

from aiohttp import hdrs, web
import async_timeout

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, IMAGE_TIMEOUT  # noqa: F401

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=30)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

DEFAULT_CONTENT_TYPE: Final = "image/jpeg"
ENTITY_IMAGE_URL: Final = "/api/image_proxy/{0}?token={1}"

TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=5)
_RND: Final = SystemRandom()


@dataclass
class ImageEntityDescription(EntityDescription):
    """A class that describes image entities."""


@dataclass
class Image:
    """Represent an image."""

    content_type: str
    content: bytes


async def _async_get_image(image_entity: ImageEntity, timeout: int) -> Image:
    """Fetch image from an image entity."""
    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
        async with async_timeout.timeout(timeout):
            if image_bytes := await image_entity.async_image():
                content_type = image_entity.content_type
                image = Image(content_type, image_bytes)
                return image

    raise HomeAssistantError("Unable to get image")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the image component."""
    component = hass.data[DOMAIN] = EntityComponent[ImageEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    hass.http.register_view(ImageView(component))

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

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[ImageEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[ImageEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class ImageEntity(Entity):
    """The base class for image entities."""

    # Entity Properties
    _attr_content_type: str = DEFAULT_CONTENT_TYPE
    _attr_image_last_updated: datetime | None = None
    _attr_should_poll: bool = False  # No need to poll image entities
    _attr_state: None = None  # State is determined by last_updated

    def __init__(self) -> None:
        """Initialize an image entity."""
        self.access_tokens: collections.deque = collections.deque([], 2)
        self.async_update_token()

    @property
    def content_type(self) -> str:
        """Image content type."""
        return self._attr_content_type

    @property
    def entity_picture(self) -> str:
        """Return a link to the image as entity picture."""
        if self._attr_entity_picture is not None:
            return self._attr_entity_picture
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_tokens[-1])

    @property
    def image_last_updated(self) -> datetime | None:
        """The time when the image was last updated."""
        return self._attr_image_last_updated

    def image(self) -> bytes | None:
        """Return bytes of image."""
        raise NotImplementedError()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
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
            raise web.HTTPNotFound()

        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") in image_entity.access_tokens
        )

        if not authenticated:
            # Attempt with invalid bearer token, raise unauthorized
            # so ban middleware can handle it.
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized()
            # Invalid sigAuth or image entity access token
            raise web.HTTPForbidden()

        return await self.handle(request, image_entity)

    async def handle(
        self, request: web.Request, image_entity: ImageEntity
    ) -> web.StreamResponse:
        """Serve image."""
        try:
            image = await _async_get_image(image_entity, IMAGE_TIMEOUT)
        except (HomeAssistantError, ValueError) as ex:
            raise web.HTTPInternalServerError() from ex

        return web.Response(body=image.content, content_type=image.content_type)
