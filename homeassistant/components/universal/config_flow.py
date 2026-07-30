"""Config flow for the Universal media player integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components.media_player import DEVICE_CLASSES
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_STATE_TEMPLATE
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.template import Template

from .media_player import (
    CONF_ACTIVE_CHILD_TEMPLATE,
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    CONF_COMMANDS,
    EXPOSED_ATTRIBUTES,
    EXPOSED_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)

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
    """Merge attribute overrides, preserving any YAML-only keys not exposed here."""
    attrs: dict[str, Any] = dict(handler.options.get(CONF_ATTRS, {}))
    for attr in EXPOSED_ATTRIBUTES:
        if user_input.get(attr):
            attrs[attr] = user_input[attr]
        else:
            attrs.pop(attr, None)
    return {CONF_ATTRS: attrs}


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


def _flatten_templates(value: Any) -> Any:
    """Recursively convert Template objects back to their raw template text.

    CMD_SCHEMA (via cv.SERVICE_SCHEMA) compiles any templated `data`/`target`
    values within a YAML command into Template objects, which config entry
    storage (JSON) can't hold; media_player.async_setup_entry recompiles them
    when constructing the entity.
    """
    if isinstance(value, Template):
        return value.template
    if isinstance(value, list):
        return [_flatten_templates(item) for item in value]
    if isinstance(value, dict):
        return {key: _flatten_templates(item) for key, item in value.items()}
    return value


class UniversalFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a Universal media player config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a Universal media player from YAML configuration."""
        unique_id: str = (
            import_data.get("unique_id") or f"yaml_{import_data[CONF_NAME]}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Commands in YAML are single service-call dicts; wrap in a list to
        # match the ActionSelector storage format used by the UI flow.
        yaml_commands: dict[str, Any] = import_data.get(CONF_COMMANDS, {})
        options: dict[str, Any] = {
            CONF_NAME: import_data[CONF_NAME],
            CONF_CHILDREN: import_data.get(CONF_CHILDREN, []),
            # Preserve JSON-serialisable advanced options so they survive the
            # round-trip through config entry storage unchanged.
            CONF_BROWSE_MEDIA_ENTITY: import_data.get(CONF_BROWSE_MEDIA_ENTITY),
        }
        # DEVICE_CLASSES_SCHEMA coerces this to a MediaPlayerDeviceClass
        # (StrEnum); unwrap to a plain string since config entry storage is
        # JSON and StrEnum members are not accepted by the JSON encoder.
        if device_class := import_data.get(CONF_DEVICE_CLASS):
            options[CONF_DEVICE_CLASS] = device_class.value

        # Templates are cv.template-validated Template objects at this point;
        # store the raw template text, matching what TemplateSelector returns.
        for template_key in (CONF_ACTIVE_CHILD_TEMPLATE, CONF_STATE_TEMPLATE):
            if template := import_data.get(template_key):
                options[template_key] = template.template

        raw_attrs = import_data.get(CONF_ATTRS, {})
        if isinstance(raw_attrs, list):
            merged: dict[str, str] = {}
            for item in raw_attrs:
                merged.update(item)
            raw_attrs = merged
        options[CONF_ATTRS] = raw_attrs

        for cmd in EXPOSED_COMMANDS:
            options[cmd] = (
                [_flatten_templates(yaml_commands[cmd])] if cmd in yaml_commands else []
            )

        # YAML commands accept arbitrary slug keys (play_media, toggle,
        # repeat_set, shuffle_set, clear_playlist, etc.), not just
        # EXPOSED_COMMANDS; preserve anything outside that bounded list so
        # migration doesn't silently turn them into delegation to the active
        # child.
        options[CONF_COMMANDS] = {
            cmd: _flatten_templates(action)
            for cmd, action in yaml_commands.items()
            if cmd not in EXPOSED_COMMANDS
        }

        _LOGGER.warning(
            (
                "Universal media player '%s' is configured via YAML, which is "
                "deprecated. Remove it from your configuration.yaml and recreate "
                "it through the UI (Settings → Devices & services → Add integration "
                "→ Universal media player)"
            ),
            import_data[CONF_NAME],
        )

        return self.async_create_entry(data=options)
