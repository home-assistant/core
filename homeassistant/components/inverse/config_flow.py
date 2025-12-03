"""Config flow for Inverse integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    wrapped_entity_config_entry_title,
)

from .const import DOMAIN

SUPPORTED_PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
]

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SUPPORTED_PLATFORMS),
        ),
    }
)


class InverseConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Inverse."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step with entity selection."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        entity_id = user_input[CONF_ENTITY_ID]

        # Hide the wrapped entity if registered
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(entity_id)
        if entity_entry is not None and not entity_entry.hidden:
            registry.async_update_entity(
                entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
            )

        title = wrapped_entity_config_entry_title(self.hass, entity_id)
        return self.async_create_entry(title=title, data={CONF_ENTITY_ID: entity_id})
