"""Support for image which integrates with other components."""

from contextlib import suppress
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
from .const import CONF_PICTURE, DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import async_setup_template_entry, async_setup_template_platform
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Image"

GET_IMAGE_TIMEOUT = 10
IMAGES_DIR = "images"

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

        self.setup_template(CONF_URL, "_url", None, self._update_url)

    def _update_url(self, result: Any) -> None:
        if result is None:
            self._attr_image_url = None
            return

        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_image = None
        self._attr_image_url = result

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
        return (
            pathlib.Path(self.hass.config.cache_path(DOMAIN, IMAGES_DIR))
            / f"{self.entity_id}.bin"
        )

    @override
    async def async_dump_cache(self) -> None:
        """Save image data."""
        image_path = self._cache_path()
        if not self._cached_image or self._attr_image_last_updated is None:
            # Don't let a previous image be restored alongside a newer URL.
            with suppress(FileNotFoundError):
                await aiofiles.os.remove(image_path)
            return

        # A single-line JSON header ties the bytes to the state they belong to.
        header = json_bytes(
            {
                "image_url": self._attr_image_url,
                "image_last_updated": self._attr_image_last_updated.isoformat(),
                "content_type": self._cached_image.content_type,
            }
        )
        await aiofiles.os.makedirs(image_path.parent, exist_ok=True)
        async with aiofiles.open(image_path, "wb") as fh:
            await fh.write(header + b"\n" + self._cached_image.content)

    @override
    async def async_get_cached_data(self) -> Image | None:
        try:
            async with aiofiles.open(self._cache_path(), "rb") as fh:
                data = await fh.read()
        except FileNotFoundError:
            return None

        header, _, content = data.partition(b"\n")
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
