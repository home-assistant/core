"""Support for buttons which integrates with other components."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.button import DEVICE_CLASSES_SCHEMA, ButtonEntity
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA,
    TEMPLATE_ENTITY_ICON_SCHEMA,
    TemplateEntity,
)

_LOGGER = logging.getLogger(__name__)

CONF_PRESS = "press"

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
        self._command_press = Script(hass, config[CONF_PRESS], self._attr_name, DOMAIN)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state = None

    async def async_press(self) -> None:
        """Press the button."""
        await self.async_run_script(self._command_press, context=self._context)
