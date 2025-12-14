"""Support for image which integrates with other components."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.image import (
    DOMAIN as IMAGE_DOMAIN,
    ENTITY_ID_FORMAT,
    ImageEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
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


class AbstractTemplateImage(AbstractTemplateEntity, ImageEntity):
    """Representation of a template image features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attr_image_url: str | None = None

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        ImageEntity.__init__(self, hass, config[CONF_VERIFY_SSL])
        self._url_template = config[CONF_URL]
        self._has_picture_template = CONF_PICTURE in config

    def _handle_state(self, result: Any) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_image = None
        self._attr_image_url = result


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
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if self._has_picture_template:
            return TemplateEntity.entity_picture.__get__(self)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _update_url(self, result):
        if isinstance(result, TemplateError):
            self._attr_image_url = None
            return
        self._handle_state(result)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute("_url", self._url_template, None, self._update_url)
        super()._async_setup_templates()


class TriggerImageEntity(TriggerEntity, AbstractTemplateImage):
    """Image entity based on trigger data."""

    domain = IMAGE_DOMAIN
    extra_template_keys = (CONF_URL,)

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
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if self._has_picture_template:
            return TriggerEntity.entity_picture.__get__(self)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _process_data(self) -> None:
        """Process new data."""
        super()._process_data()
        self._handle_state(self._rendered.get(CONF_URL))
