"""Support for image which integrates with other components."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN, ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .const import CONF_PICTURE
from .template_entity import TemplateEntity, make_template_entity_common_schema
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Image"

GET_IMAGE_TIMEOUT = 10

IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
).extend(make_template_entity_common_schema(DEFAULT_NAME).schema)


IMAGE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.template,
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[StateImageEntity]:
    """Create the template image."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(StateImageEntity(hass, definition, unique_id))
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template image."""
    if discovery_info is None:
        _LOGGER.warning(
            "Template image entities can only be configured under template:"
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerImageEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = IMAGE_CONFIG_SCHEMA(_options)
    async_add_entities(
        [StateImageEntity(hass, validated_config, config_entry.entry_id)]
    )


class StateImageEntity(TemplateEntity, ImageEntity):
    """Representation of a template image."""

    _attr_should_poll = False
    _attr_image_url: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the image."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        ImageEntity.__init__(self, hass, config[CONF_VERIFY_SSL])
        self._url_template = config[CONF_URL]
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

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

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute("_url", self._url_template, None, self._update_url)
        super()._async_setup_templates()


class TriggerImageEntity(TriggerEntity, ImageEntity):
    """Image entity based on trigger data."""

    _attr_image_url: str | None = None

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
