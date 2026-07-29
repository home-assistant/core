"""Config flow for the Universal media player integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import SERVICE_SELECT_SOURCE
from homeassistant.config_entries import ConfigFlowResult, SOURCE_IMPORT
from homeassistant.const import (
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .media_player import CONF_ATTRS, CONF_BROWSE_MEDIA_ENTITY, CONF_CHILDREN, CONF_COMMANDS

_LOGGER = logging.getLogger(__name__)

DOMAIN = "universal"

EXPOSED_COMMANDS = (
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    SERVICE_VOLUME_UP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_SELECT_SOURCE,
)

_CHILDREN_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="media_player", multiple=True)
)
_ACTION_SELECTOR = selector.ActionSelector()

_CONFIG_BASIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Optional(CONF_CHILDREN, default=[]): _CHILDREN_SELECTOR,
    }
)

_COMMANDS_SCHEMA = vol.Schema(
    {
        vol.Optional(SERVICE_TURN_ON): _ACTION_SELECTOR,
        vol.Optional(SERVICE_TURN_OFF): _ACTION_SELECTOR,
        vol.Optional(SERVICE_VOLUME_UP): _ACTION_SELECTOR,
        vol.Optional(SERVICE_VOLUME_DOWN): _ACTION_SELECTOR,
        vol.Optional(SERVICE_VOLUME_MUTE): _ACTION_SELECTOR,
        vol.Optional(SERVICE_SELECT_SOURCE): _ACTION_SELECTOR,
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


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(_CONFIG_BASIC_SCHEMA, next_step="commands"),
    "commands": SchemaFlowFormStep(
        _COMMANDS_SCHEMA, validate_user_input=_validate_commands
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_OPTIONS_BASIC_SCHEMA, next_step="commands"),
    "commands": SchemaFlowFormStep(
        _COMMANDS_SCHEMA, validate_user_input=_validate_commands
    ),
}


class UniversalFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a Universal media player config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_NAME]

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import a Universal media player from YAML configuration."""
        unique_id: str = import_data.get("unique_id") or f"yaml_{import_data[CONF_NAME]}"
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

        raw_attrs = import_data.get(CONF_ATTRS, {})
        if isinstance(raw_attrs, list):
            merged: dict[str, str] = {}
            for item in raw_attrs:
                merged.update(item)
            raw_attrs = merged
        options[CONF_ATTRS] = raw_attrs

        for cmd in EXPOSED_COMMANDS:
            options[cmd] = [yaml_commands[cmd]] if cmd in yaml_commands else []

        _LOGGER.warning(
            (
                "Universal media player '%s' is configured via YAML, which is "
                "deprecated. Remove it from your configuration.yaml and recreate "
                "it through the UI (Settings → Devices & services → Add integration "
                "→ Universal media player)."
            ),
            import_data[CONF_NAME],
        )

        return self.async_create_entry(data=options)
