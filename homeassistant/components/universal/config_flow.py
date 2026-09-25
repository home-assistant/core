"""Config flow for the Universal media player integration."""

from collections.abc import Mapping
from typing import Any, override

import voluptuous as vol

from homeassistant.components.media_player import DEVICE_CLASSES
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_STATE_TEMPLATE
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .media_player import (
    CONF_ACTIVE_CHILD_TEMPLATE,
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    EXPOSED_ATTRIBUTES,
    EXPOSED_COMMANDS,
)

DOMAIN = "universal"

_CHILDREN_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="media_player", multiple=True)
)
_ACTION_SELECTOR = selector.ActionSelector()
_ATTRIBUTE_SELECTOR = selector.TextSelector()

_CONFIG_BASIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Optional(CONF_CHILDREN, default=[]): _CHILDREN_SELECTOR,
    }
)

_COMMANDS_SCHEMA = vol.Schema(
    {vol.Optional(cmd): _ACTION_SELECTOR for cmd in EXPOSED_COMMANDS}
)

_ATTRIBUTES_SCHEMA = vol.Schema(
    {vol.Optional(attr): _ATTRIBUTE_SELECTOR for attr in EXPOSED_ATTRIBUTES}
)

_ADVANCED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=DEVICE_CLASSES,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="device_class",
                sort=True,
            )
        ),
        vol.Optional(CONF_BROWSE_MEDIA_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        ),
        vol.Optional(CONF_ACTIVE_CHILD_TEMPLATE): selector.TemplateSelector(),
        vol.Optional(CONF_STATE_TEMPLATE): selector.TemplateSelector(),
    }
)

_OPTIONS_BASIC_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CHILDREN, default=[]): _CHILDREN_SELECTOR,
    }
)


async def _validate_commands(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Normalise command inputs; always write all keys so clearing works."""
    return {cmd: user_input.get(cmd, []) for cmd in EXPOSED_COMMANDS}


async def _attributes_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Flatten the stored attribute overrides for form pre-population."""
    return dict(handler.options.get(CONF_ATTRS, {}))


async def _validate_attributes(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Normalise attribute inputs, omitting blank fields so clearing works.

    Unlike commands (where an empty list cleanly means "not configured"),
    an empty string can't be stored as a value here: media_player.py's
    attrs parser does `value.split("|", 1)` unconditionally, so "" would be
    treated as an override pointing at entity_id "" instead of being absent.
    """
    return {
        CONF_ATTRS: {
            attr: user_input[attr]
            for attr in EXPOSED_ATTRIBUTES
            if user_input.get(attr)
        }
    }


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(_CONFIG_BASIC_SCHEMA, next_step="commands"),
    "commands": SchemaFlowFormStep(
        _COMMANDS_SCHEMA,
        next_step="attributes",
        validate_user_input=_validate_commands,
    ),
    "attributes": SchemaFlowFormStep(
        _ATTRIBUTES_SCHEMA,
        next_step="advanced",
        validate_user_input=_validate_attributes,
        suggested_values=_attributes_suggested_values,
    ),
    "advanced": SchemaFlowFormStep(_ADVANCED_SCHEMA),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_OPTIONS_BASIC_SCHEMA, next_step="commands"),
    "commands": SchemaFlowFormStep(
        _COMMANDS_SCHEMA,
        next_step="attributes",
        validate_user_input=_validate_commands,
    ),
    "attributes": SchemaFlowFormStep(
        _ATTRIBUTES_SCHEMA,
        next_step="advanced",
        validate_user_input=_validate_attributes,
        suggested_values=_attributes_suggested_values,
    ),
    "advanced": SchemaFlowFormStep(_ADVANCED_SCHEMA),
}


class UniversalFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a Universal media player config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]
