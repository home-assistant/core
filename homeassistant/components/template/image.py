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


class StateImageEntity(TemplateEntity, ImageEntity):
    """Representation of a template image."""

    _attr_should_poll = False
    _attr_image_url: str | None = None
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the image."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        ImageEntity.__init__(self, hass, config[CONF_VERIFY_SSL])
        self._url_template = config[CONF_URL]

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        if self._entity_picture_template:
            return TemplateEntity.entity_picture.__get__(self)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _update_url(self, result):
        if isinstance(result, TemplateError):
            self._attr_image_url = None
            return
        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_image = None
        self._attr_image_url = result
        # immediately cache the image because url might be invalid by the time the image is requested
        self.hass.async_create_task(self._async_cache_image(self._attr_image_url))

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute("_url", self._url_template, None, self._update_url)
        super()._async_setup_templates()


class TriggerImageEntity(TriggerEntity, ImageEntity):
    """Image entity based on trigger data."""

    _attr_image_url: str | None = None
    _entity_id_format = ENTITY_ID_FORMAT

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
        ImageEntity.__init__(self, hass, config[CONF_VERIFY_SSL])

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        if CONF_PICTURE in self._config:
            return TriggerEntity.entity_picture.fget(self)  # type: ignore[attr-defined]
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _process_data(self) -> None:
        """Process new data."""
        super()._process_data()
        self._attr_image_last_updated = dt_util.utcnow()
        self._cached_image = None
        self._attr_image_url = self._rendered.get(CONF_URL)
        # immediately cache the image because url might be invalid by the time the image is requested
        self.hass.async_create_task(self._async_cache_image(self._attr_image_url))
