"""Base entity for the Image platform."""

import collections
from dataclasses import dataclass
from datetime import datetime
import logging
from random import SystemRandom
from typing import Any, Final, final, override

import httpx2
from propcache.api import cached_property

from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import Undefined

from .const import (
    DEFAULT_CONTENT_TYPE,
    ENTITY_IMAGE_URL,
    GET_IMAGE_TIMEOUT,
    MAP_MAGIC_NUMBERS_TO_CONTENT_TYPE,
    ImageEntityStateAttribute,
)

_LOGGER = logging.getLogger(__package__)


_RND: Final = SystemRandom()


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


def infer_image_type(content: bytes) -> str | None:
    """Infer image type from first 4 bytes (magic number)."""
    return MAP_MAGIC_NUMBERS_TO_CONTENT_TYPE.get(content[:4])


CACHED_PROPERTIES_WITH_ATTR_ = {
    "content_type",
    "image_last_updated",
    "image_url",
}


class ImageEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """The base class for image entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {ImageEntityStateAttribute.ACCESS_TOKEN, EntityStateAttribute.ENTITY_PICTURE}
    )

    # Entity Properties
    _attr_content_type: str = DEFAULT_CONTENT_TYPE
    _attr_image_last_updated: datetime | None = None
    _attr_image_url: str | Undefined | None = Undefined
    _attr_should_poll: bool = False  # No need to poll image entities
    _attr_state: None = None  # State is determined by last_updated
    _cached_image: Image | None = None

    def __init__(self, hass: HomeAssistant, verify_ssl: bool = False) -> None:
        """Initialize an image entity."""
        self._client = get_async_client(hass, verify_ssl=verify_ssl)
        self.access_tokens: collections.deque = collections.deque(maxlen=2)
        self.async_update_token()

    @cached_property
    def content_type(self) -> str:
        """Image content type."""
        return self._attr_content_type

    @property
    @override
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
    def image_url(self) -> str | Undefined | None:
        """Return URL of image."""
        return self._attr_image_url

    def image(self) -> bytes | None:
        """Return bytes of image."""
        raise NotImplementedError

    async def _fetch_url(self, url: str) -> httpx2.Response | None:
        """Fetch a URL."""
        try:
            response = await self._client.get(
                url, timeout=GET_IMAGE_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
        except httpx2.TimeoutException:
            _LOGGER.error("%s: Timeout getting image from %s", self.entity_id, url)
            return None
        except (httpx2.RequestError, httpx2.HTTPStatusError) as err:
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
            content_type = response.headers.get("content-type") or infer_image_type(
                response.content
            )
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
        if (url := self.image_url) is not Undefined:
            if not url or (image := await self._async_load_image_from_url(url)) is None:
                return None
            self._cached_image = image
            self._attr_content_type = image.content_type
            return image.content
        return await self.hass.async_add_executor_job(self.image)

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the state."""
        if self.image_last_updated is None:
            return None
        return self.image_last_updated.isoformat()

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {ImageEntityStateAttribute.ACCESS_TOKEN: self.access_tokens[-1]}

    @callback
    def async_update_token(self) -> None:
        """Update the used token."""
        self.access_tokens.append(hex(_RND.getrandbits(256))[2:])
