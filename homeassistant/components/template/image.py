"""Support for image which integrates with other components."""

import base64
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Self, override

import voluptuous as vol

from homeassistant.components.image import (
    DOMAIN as IMAGE_DOMAIN,
    ENTITY_ID_FORMAT,
    Image,
    ImageEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .const import CONF_PICTURE
from .entity import AbstractTemplateEntity
from .helpers import async_setup_template_entry, async_setup_template_platform
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Image"

GET_IMAGE_TIMEOUT = 10

IMAGE_YAML_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
).extend(
    make_template_entity_common_modern_attributes_schema(
        IMAGE_DOMAIN, DEFAULT_NAME
    ).schema
)


IMAGE_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
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
    cached_image: Image | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the image data."""
        cached_image: Image | dict[str, str] | None = self.cached_image
        if isinstance(cached_image, Image):
            cached_image = {
                "__type": str(type(cached_image)),
                "content_type": cached_image.content_type,
                "content": base64.b64encode(cached_image.content).decode("utf-8"),
            }

        image_last_updated: datetime | dict[str, str] | None = self.image_last_updated
        if isinstance(image_last_updated, datetime):
            image_last_updated = {
                "__type": str(type(image_last_updated)),
                "isoformat": image_last_updated.isoformat(),
            }

        return {
            "image_last_updated": image_last_updated,
            "image_url": self.image_url,
            "cached_image": cached_image,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored image state from a dict."""

        try:
            image_last_updated = restored["image_last_updated"]
        except KeyError:
            return None
        try:
            type_ = image_last_updated["__type"]
            if type_ == "<class 'datetime.datetime'>":
                image_last_updated = dt_util.parse_datetime(
                    image_last_updated["isoformat"]
                )
        except TypeError:
            pass
        except KeyError:
            return None

        try:
            cached_image = restored["cached_image"]
        except KeyError:
            return None
        try:
            type_ = cached_image["__type"]
            if type_ == "<class 'homeassistant.components.image.Image'>":
                cached_image = Image(
                    content_type=cached_image["content_type"],
                    content=base64.b64decode(cached_image["content"]),
                )
        except TypeError:
            pass
        except KeyError:
            return None

        return cls(
            image_last_updated=image_last_updated,
            image_url=restored["image_url"],
            cached_image=cached_image,
        )


class AbstractTemplateImage(AbstractTemplateEntity, ImageEntity, RestoreEntity):
    """Representation of a template image features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attr_image_url: str | None = None
    _restore_state_extra_data = ImageExtraStoredData
    _restore_state_properties = ("_cached_image",)

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
            cached_image=self._cached_image,
        )

    @override
    def restore_extra_data(self, extra_data: ImageExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_image_last_updated = extra_data.image_last_updated
        self._attr_image_url = extra_data.image_url
        self._cached_image = extra_data.cached_image


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
