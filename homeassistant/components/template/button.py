"""Support for buttons which integrates with other components."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.button import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BUTTON_DOMAIN,
    ENTITY_ID_FORMAT,
    ButtonEntity,
),
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PRESS, DOMAIN
from .helpers import async_setup_template_platform
from .template_entity import TemplateEntity, make_template_entity_common_modern_schema

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Button"
DEFAULT_OPTIMISTIC = False

BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRESS): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
).extend(make_template_entity_common_modern_schema(DEFAULT_NAME).schema)

CONFIG_BUTTON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.template,
        vol.Optional(CONF_PRESS): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template button."""
    await async_setup_template_platform(
        hass,
        BUTTON_DOMAIN,
        config,
        StateButtonEntity,
        None,
        async_add_entities,
        discovery_info,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = CONFIG_BUTTON_SCHEMA(_options)
    async_add_entities(
        [StateButtonEntity(hass, validated_config, config_entry.entry_id)]
    )


class StateButtonEntity(TemplateEntity, ButtonEntity):
    """Representation of a template button."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config,
        unique_id: str | None,
    ) -> None:
        """Initialize the button."""
        TemplateEntity.__init__(self, hass, config, unique_id, ENTITY_ID_FORMAT)

        if TYPE_CHECKING:
            assert self._attr_name is not None

        # Scripts can be an empty list, therefore we need to check for None
        if (action := config.get(CONF_PRESS)) is not None:
            self.add_script(CONF_PRESS, action, self._attr_name, DOMAIN)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state = None
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )

    async def async_press(self) -> None:
        """Press the button."""
        if script := self._action_scripts.get(CONF_PRESS):
            await self.async_run_script(script, context=self._context)
