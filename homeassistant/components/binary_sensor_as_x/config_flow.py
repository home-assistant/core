"""Config flow for Binary sensor as X integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)

from .const import CONF_TARGET_DOMAIN, DOMAIN

TARGET_DOMAIN_OPTIONS = [
    selector.SelectOptionDict(value=Platform.COVER, label="Cover"),
]

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=Platform.BINARY_SENSOR),
                ),
                vol.Required(CONF_TARGET_DOMAIN): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=TARGET_DOMAIN_OPTIONS),
                ),
            }
        )
    )
}


class BinarySensorAsXConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Binary sensor as X."""

    config_flow = CONFIG_FLOW

    VERSION = 1
    MINOR_VERSION = 0

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title and hide the wrapped entity if registered."""
        # Hide the wrapped entry if registered
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(options[CONF_ENTITY_ID])
        if entity_entry is not None and not entity_entry.hidden:
            registry.async_update_entity(
                options[CONF_ENTITY_ID], hidden_by=er.RegistryEntryHider.INTEGRATION
            )

        return wrapped_entity_config_entry_title(self.hass, options[CONF_ENTITY_ID])
