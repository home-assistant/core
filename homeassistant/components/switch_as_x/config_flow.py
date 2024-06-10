"""Config flow for Switch as X integration."""

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

from .const import CONF_INVERT, CONF_TARGET_DOMAIN, DOMAIN

TARGET_DOMAIN_OPTIONS = [
    selector.SelectOptionDict(value=Platform.COVER, label="Cover"),
    selector.SelectOptionDict(value=Platform.FAN, label="Fan"),
    selector.SelectOptionDict(value=Platform.LIGHT, label="Light"),
    selector.SelectOptionDict(value=Platform.LOCK, label="Lock"),
    selector.SelectOptionDict(value=Platform.SIREN, label="Siren"),
    selector.SelectOptionDict(value=Platform.VALVE, label="Valve"),
]

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=Platform.SWITCH),
                ),
                vol.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
                vol.Required(CONF_TARGET_DOMAIN): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=TARGET_DOMAIN_OPTIONS),
                ),
            }
        )
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        vol.Schema({vol.Required(CONF_INVERT): selector.BooleanSelector()})
    ),
}


class SwitchAsXConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Switch as X."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    VERSION = 1
    MINOR_VERSION = 2

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
