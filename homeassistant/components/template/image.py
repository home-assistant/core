"""Support for image which integrates with other components."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
import pathlib
from typing import Any, Self, override

import aiofiles
import aiofiles.os
import probatio

from homeassistant.components.image import (
    DOMAIN as IMAGE_DOMAIN,
    ENTITY_ID_FORMAT,
    Image,
    ImageContentTypeError,
    ImageEntity,
    ImageEntityStateAttribute,
    valid_image_content_type,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object

from . import validators as tcv
from .const import CONF_PICTURE
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import async_setup_template_entry, async_setup_template_platform
from .image_cache import image_cache_dir
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Image"

GET_IMAGE_TIMEOUT = 10

_BLOCKED_ATTRIBUTES = tcv.BlockedTemplateAttributes(
    attributes=ImageEntityStateAttribute
)

IMAGE_YAML_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): cv.template,
        probatio.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
).extend(
    make_template_entity_common_schema(
        IMAGE_DOMAIN, DEFAULT_NAME, _BLOCKED_ATTRIBUTES
    ).schema
)


IMAGE_CONFIG_ENTRY_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): cv.template,
        probatio.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
).extend(TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template image."""
    await async_setup_template_platform(
        hass,
        IMAGE_DOMAIN,
        config,
        StateImageEntity,
        TriggerImageEntity,
        async_add_entities,
        discovery_info,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateImageEntity,
        IMAGE_CONFIG_ENTRY_SCHEMA,
    )


@dataclass(kw_only=True)
class ImageExtraStoredData(ExtraStoredData):
    """Holds extra stored data for template image entities."""

    image_last_updated: datetime | None
    image_url: str | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the image data."""
        image_last_updated: datetime | dict[str, str] | None = self.image_last_updated
        if isinstance(image_last_updated, datetime):
            image_last_updated = {
                "__type": str(type(image_last_updated)),
                "isoformat": image_last_updated.isoformat(),
            }

        return {
            "image_last_updated": image_last_updated,
            "image_url": self.image_url,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored image state from a dict."""
        try:
            stored_last_updated = restored["image_last_updated"]
            image_url = restored["image_url"]
        except KeyError:
            return None

        if image_url is not None and not isinstance(image_url, str):
            return None

        image_last_updated: datetime | None = None
        if stored_last_updated is not None:
            if (
                not isinstance(stored_last_updated, dict)
                or stored_last_updated.get("__type") != str(datetime)
                or not isinstance(
                    isoformat := stored_last_updated.get("isoformat"), str
                )
            ):
                return None
            try:
                image_last_updated = dt_util.parse_datetime(isoformat)
            except ValueError:
                return None
            if image_last_updated is None:
                return None

        return cls(image_last_updated=image_last_updated, image_url=image_url)


class AbstractTemplateImage(AbstractTemplateEntity, ImageEntity, RestoreEntity):
    """Representation of a template image features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attr_image_url: str | None = None
    _blocked_attributes = _BLOCKED_ATTRIBUTES
    _restore_state_extra_data = ImageExtraStoredData
    _restore_state_properties = ("_attr_image_last_updated",)
    _restore_state_cache_data = bytes

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        ImageEntity.__init__(self, hass, config[CONF_VERIFY_SSL])
        self._has_picture_template = CONF_PICTURE in config
        # Removal and shutdown can both dump the cache, and they share a temp file.
        self._cache_lock = asyncio.Lock()
        self._cache_deleted = False
        # Counts URL updates, timestamps can repeat.
        self._url_generation = 0

        self.setup_template(CONF_URL, "_url", None, self._update_url)

    def _update_url(self, result: Any) -> None:
        if result is None:
            self._attr_image_url = None
            return

        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_image = None
        self._url_generation += 1
        self._attr_image_url = result

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        # The image proxy reads the content type right after this returns.
        if self._cached_image:
            self._attr_content_type = self._cached_image.content_type
            return self._cached_image.content
        if not (url := self._attr_image_url):
            return None
        generation = self._url_generation
        if (image := await self._async_load_image_from_url(url)) is None:
            return None
        # A download for a previous URL must not replace the current image.
        if self._url_generation == generation:
            self._cached_image = image
        self._attr_content_type = image.content_type
        return image.content

    @property
    @override
    def extra_restore_state_data(self) -> ImageExtraStoredData:
        """Return image specific state data to be restored."""
        return ImageExtraStoredData(
            image_last_updated=self._attr_image_last_updated,
            image_url=self._attr_image_url,
        )

    @override
    def restore_extra_data(self, extra_data: ImageExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_image_last_updated = extra_data.image_last_updated
        self._attr_image_url = extra_data.image_url

    def _cache_path(self) -> pathlib.Path:
        # Restore state follows the registry ID across entity_id changes.
        key = self.registry_entry.id if self.registry_entry else self.entity_id
        return image_cache_dir(self.hass) / f"{key}.bin"

    @override
    async def async_dump_cache(self) -> None:
        """Save image data."""
        async with self._cache_lock:
            await self._async_dump_cache()

    @override
    async def async_removed_from_registry(self) -> None:
        """Delete the cached image of a deleted entity."""
        await super().async_removed_from_registry()
        async with self._cache_lock:
            # The removal that follows would otherwise save it under the entity_id.
            self._cache_deleted = True
            await self._async_remove_cache_file(self._cache_path())

    async def _async_remove_cache_file(self, image_path: pathlib.Path) -> None:
        try:
            await aiofiles.os.remove(image_path)
        except FileNotFoundError:
            pass
        except OSError as err:
            _LOGGER.warning(
                "%s: Unable to remove image cache %s: %s",
                self.entity_id,
                image_path,
                err,
            )

    async def _async_dump_cache(self) -> None:
        if self._cache_deleted:
            return

        image_path = self._cache_path()
        if (image := self._cached_image) is None or (
            last_updated := self._attr_image_last_updated
        ) is None:
            # Don't let a previous image be restored alongside a newer URL.
            await self._async_remove_cache_file(image_path)
            return

        # A single-line JSON header ties the bytes to the state they belong to.
        # Built before awaiting so a concurrent update can't mix metadata and content.
        payload = (
            json_bytes(
                {
                    "image_url": self._attr_image_url,
                    "image_last_updated": last_updated.isoformat(),
                    "content_type": image.content_type,
                }
            )
            + b"\n"
            + image.content
        )
        tmp_path = image_path.with_suffix(".tmp")
        try:
            await aiofiles.os.makedirs(image_path.parent, exist_ok=True)
            async with aiofiles.open(tmp_path, "wb") as fh:
                await fh.write(payload)
            # An interrupted write must never leave a truncated cache file.
            await aiofiles.os.replace(tmp_path, image_path)
        except OSError as err:
            _LOGGER.warning(
                "%s: Unable to save image cache %s: %s", self.entity_id, image_path, err
            )

    async def _async_read_cache_file(self) -> bytes | None:
        paths = [self._cache_path()]
        if self.registry_entry is not None:
            # Restore state moves to the registry ID when a unique_id is added.
            paths.append(image_cache_dir(self.hass) / f"{self.entity_id}.bin")
        for image_path in paths:
            try:
                async with aiofiles.open(image_path, "rb") as fh:
                    return await fh.read()
            except FileNotFoundError:
                continue
            except OSError as err:
                _LOGGER.warning(
                    "%s: Unable to read image cache %s: %s",
                    self.entity_id,
                    image_path,
                    err,
                )
                return None
        return None

    @override
    async def async_get_cached_data(self) -> Image | None:
        if (data := await self._async_read_cache_file()) is None:
            return None

        header, _, content = data.partition(b"\n")
        if not content:
            return None
        try:
            metadata = json_loads_object(header)
            content_type = metadata["content_type"]
            stored_last_updated = metadata["image_last_updated"]
            image_url = metadata["image_url"]
        except ValueError, KeyError:
            return None

        if not isinstance(content_type, str) or not isinstance(
            stored_last_updated, str
        ):
            return None

        try:
            content_type = valid_image_content_type(content_type)
            last_updated = dt_util.parse_datetime(stored_last_updated)
        except ValueError, ImageContentTypeError:
            return None

        # Checked after the read, so an update during the await is not overwritten.
        if (
            last_updated is None
            or last_updated != self._attr_image_last_updated
            or image_url != self._attr_image_url
        ):
            return None
        return Image(content_type=content_type, content=content)

    @override
    def restore_cached_data(self, cached_data: Image) -> None:
        """Restore cached data from the last state."""
        self._cached_image = cached_data
        self._attr_content_type = cached_data.content_type


class StateImageEntity(TemplateEntity, AbstractTemplateImage):
    """Representation of a template image."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the image."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateImage.__init__(self, hass, config)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if self._has_picture_template:
            return TemplateEntity.entity_picture.__get__(self)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]


class TriggerImageEntity(TriggerEntity, AbstractTemplateImage):
    """Image entity based on trigger data."""

    domain = IMAGE_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateImage.__init__(self, hass, config)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if self._has_picture_template:
            return TriggerEntity.entity_picture.__get__(self)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]
