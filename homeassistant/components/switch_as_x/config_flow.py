"""Config flow for Switch as X integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import (
    entity_registry as er,
    helper_config_entry_flow,
    selector,
)

from .const import CONF_TARGET_DOMAIN, DOMAIN

CONFIG_FLOW = {
    "user": helper_config_entry_flow.HelperFlowStep(
        vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.selector(
                    {"entity": {"domain": Platform.SWITCH}}
                ),
                vol.Required(CONF_TARGET_DOMAIN): selector.selector(
                    {
                        "select": {
                            "options": [
                                {"value": Platform.COVER, "label": "Cover"},
                                {"value": Platform.FAN, "label": "Fan"},
                                {"value": Platform.LIGHT, "label": "Light"},
                                {"value": Platform.LOCK, "label": "Lock"},
                                {"value": Platform.SIREN, "label": "Siren"},
                            ]
                        }
                    }
                ),
            }
        )
    )
}


class SwitchAsXConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config flow for Switch as X."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title and hide the wrapped entity if registered."""
        # Hide the wrapped entry if registered
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(options[CONF_ENTITY_ID])
        if entity_entry is not None and not entity_entry.hidden:
            registry.async_update_entity(
                options[CONF_ENTITY_ID], hidden_by=er.RegistryEntryHider.INTEGRATION
            )

        return helper_config_entry_flow.wrapped_entity_config_entry_title(
            self.hass, options[CONF_ENTITY_ID]
        )
