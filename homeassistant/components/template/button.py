"""Support for buttons which integrates with other components."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.button import (
    DEVICE_CLASSES_SCHEMA,
    ButtonDeviceClass,
    ButtonEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ICON, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.template import Template, TemplateError

from .const import CONF_AVAILABILITY, DOMAIN
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)

CONF_PRESS = "press"

DEFAULT_NAME = "Template Button"
DEFAULT_OPTIMISTIC = False

BUTTON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
        vol.Required(CONF_PRESS): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ICON): cv.template,
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
        entities.append(
            TemplateButtonEntity(
                hass,
                definition[CONF_NAME],
                definition.get(CONF_AVAILABILITY),
                definition[CONF_PRESS],
                definition.get(CONF_DEVICE_CLASS),
                unique_id,
                definition.get(CONF_ICON),
            )
        )
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: Config,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the template button."""
    if "coordinator" in discovery_info:
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

    def __init__(
        self,
        hass: HomeAssistant,
        name_template: Template,
        availability_template: Template | None,
        command_press: dict[str, Any],
        device_class: ButtonDeviceClass | None,
        unique_id: str | None,
        icon_template: Template | None,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            availability_template=availability_template, icon_template=icon_template
        )
        self._attr_name = DEFAULT_NAME
        self._name_template = name_template
        name_template.hass = hass
        with contextlib.suppress(TemplateError):
            self._attr_name = name_template.async_render(parse_result=False)
        self._command_press = Script(hass, command_press, self._attr_name, DOMAIN)
        self._attr_device_class = device_class
        self._attr_unique_id = unique_id
        self._attr_state = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._name_template and not self._name_template.is_static:
            self.add_template_attribute("_attr_name", self._name_template, cv.string)
        await super().async_added_to_hass()

    async def async_press(self) -> None:
        """Press the button."""
        await self._command_press.async_run(context=self._context)
