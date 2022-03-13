"""Config flow for Switch as X integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.helpers import helper_config_entry_flow, selector

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
                                {"value": Platform.LIGHT, "label": "Light"},
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
        """Return config entry title."""
        return helper_config_entry_flow.wrapped_entity_config_entry_title(
            self.hass, options[CONF_ENTITY_ID]
        )
