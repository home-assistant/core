"""Support for buttons which integrates with other components."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.button import DEVICE_CLASSES_SCHEMA, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PRESS, DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Button"
DEFAULT_OPTIMISTIC = False

BUTTON_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Required(CONF_PRESS): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_ICON_SCHEMA.schema)
)

CONFIG_BUTTON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.template,
        vol.Optional(CONF_PRESS): selector.ActionSelector(),
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[TemplateButtonEntity]:
    """Create the Template button."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(TemplateButtonEntity(hass, definition, unique_id))
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template button."""
    if not discovery_info or "coordinator" in discovery_info:
        raise PlatformNotReady(
            "The template button platform doesn't support trigger entities"
        )

    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = CONFIG_BUTTON_SCHEMA(_options)
    async_add_entities(
        [TemplateButtonEntity(hass, validated_config, config_entry.entry_id)]
    )


class TemplateButtonEntity(TemplateEntity, ButtonEntity):
    """Representation of a template button."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config,
        unique_id: str | None,
    ) -> None:
        """Initialize the button."""
        super().__init__(hass, config=config, unique_id=unique_id)
        assert self._attr_name is not None
        self._command_press = (
            Script(hass, config.get(CONF_PRESS), self._attr_name, DOMAIN)
            if config.get(CONF_PRESS, None) is not None
            else None
        )
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state = None
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

    async def async_press(self) -> None:
        """Press the button."""
        if self._command_press:
            await self.async_run_script(self._command_press, context=self._context)
