"""Config flow for the Universal media player integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.components.media_player import DEVICE_CLASSES
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE_TEMPLATE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .media_player import (
    CONF_ACTIVE_CHILD_TEMPLATE,
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    CONF_COMMANDS,
    EXPOSED_ATTRIBUTES,
    EXPOSED_COMMANDS,
)

DOMAIN = "universal"

_TEMPLATE_SELECTOR = selector.TemplateSelector()
_ACTION_SELECTOR = selector.ActionSelector()
_TEXT_SELECTOR = selector.TextSelector()

_ENTITY_FIELDS: dict[probatio.Marker, Any] = {
    probatio.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=DEVICE_CLASSES,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key="device_class",
            sort=True,
        )
    ),
    probatio.Optional(CONF_STATE_TEMPLATE): _TEMPLATE_SELECTOR,
    # Commands
    **{probatio.Optional(cmd): _ACTION_SELECTOR for cmd in EXPOSED_COMMANDS},
    # Attribute overrides (entity_id or entity_id|attribute, not templates)
    **{probatio.Optional(attr): _TEXT_SELECTOR for attr in EXPOSED_ATTRIBUTES},
    # Children and advanced
    probatio.Optional(CONF_CHILDREN, default=[]): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="media_player", multiple=True)
    ),
    probatio.Optional(CONF_BROWSE_MEDIA_ENTITY): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="media_player")
    ),
    probatio.Optional(CONF_ACTIVE_CHILD_TEMPLATE): _TEMPLATE_SELECTOR,
}

_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): selector.TextSelector(),
        **_ENTITY_FIELDS,
    }
)

_OPTIONS_SCHEMA = probatio.Schema(_ENTITY_FIELDS)


async def _validate_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Normalise user input for storage."""
    # Commands: ensure all keys present so clearing works
    for cmd in EXPOSED_COMMANDS:
        user_input.setdefault(cmd, [])

    # Attributes: nest under CONF_ATTRS, drop blanks.
    # Preserve any extra attributes from YAML import that aren't in the form.
    existing_attrs = dict(handler.options.get(CONF_ATTRS, {}))
    attrs = {k: v for k, v in existing_attrs.items() if k not in EXPOSED_ATTRIBUTES}
    for attr in EXPOSED_ATTRIBUTES:
        if val := user_input.pop(attr, None):
            attrs[attr] = val
    user_input[CONF_ATTRS] = attrs

    return user_input


async def _suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Flatten stored options for form pre-population."""
    return {
        **handler.options,
        **handler.options.get(CONF_ATTRS, {}),
    }


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        _CONFIG_SCHEMA,
        validate_user_input=_validate_input,
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        _OPTIONS_SCHEMA,
        validate_user_input=_validate_input,
        suggested_values=_suggested_values,
    ),
}


def _strip_templates(obj: Any) -> Any:
    """Recursively convert Template objects to raw strings for JSON storage."""
    if isinstance(obj, Template):
        return obj.template
    if isinstance(obj, dict):
        return {_strip_templates(k): _strip_templates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_templates(v) for v in obj]
    return obj


class UniversalFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a Universal media player config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Import a YAML-configured universal media player."""
        name: str = import_data[CONF_NAME]

        # Deduplicate by unique_id when available, otherwise by name
        if unique_id := import_data.get(CONF_UNIQUE_ID):
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
        else:
            self._async_abort_entries_match({CONF_NAME: name})

        yaml_commands: dict[str, Any] = import_data.get(CONF_COMMANDS, {})
        options: dict[str, Any] = {}
        extra_commands: dict[str, Any] = {}
        for cmd, cmd_config in yaml_commands.items():
            raw = _strip_templates(dict(cmd_config))
            if "service" in raw:
                raw["action"] = raw.pop("service")
            if "service_template" in raw:
                raw["action"] = raw.pop("service_template")
            if "data_template" in raw:
                if "data" in raw:
                    raw["data"] = {**raw.pop("data_template"), **raw["data"]}
                else:
                    raw["data"] = raw.pop("data_template")
            # Move entity_id from data to target (old -> new YAML style)
            if "data" in raw and isinstance(raw["data"], dict) and "entity_id" in raw["data"]:
                eid = raw["data"].pop("entity_id")
                raw.setdefault("target", {})["entity_id"] = eid
                if not raw["data"]:
                    del raw["data"]
            if "entity_id" in raw and "target" not in raw:
                raw["target"] = {"entity_id": raw.pop("entity_id")}
            if cmd in EXPOSED_COMMANDS:
                options[cmd] = [raw]
            else:
                extra_commands[cmd] = raw
        for cmd in EXPOSED_COMMANDS:
            options.setdefault(cmd, [])

        if extra_commands:
            options[CONF_COMMANDS] = extra_commands
        options[CONF_ATTRS] = dict(import_data.get(CONF_ATTRS, {}))
        options[CONF_NAME] = name
        options[CONF_CHILDREN] = list(import_data.get(CONF_CHILDREN, []))

        if browse := import_data.get(CONF_BROWSE_MEDIA_ENTITY):
            options[CONF_BROWSE_MEDIA_ENTITY] = browse
        if device_class := import_data.get(CONF_DEVICE_CLASS):
            options[CONF_DEVICE_CLASS] = device_class
        if tmpl := import_data.get(CONF_ACTIVE_CHILD_TEMPLATE):
            options[CONF_ACTIVE_CHILD_TEMPLATE] = tmpl.template
        if tmpl := import_data.get(CONF_STATE_TEMPLATE):
            options[CONF_STATE_TEMPLATE] = tmpl.template
        if unique_id := import_data.get(CONF_UNIQUE_ID):
            options[CONF_UNIQUE_ID] = unique_id

        return self.async_create_entry(data=options)
