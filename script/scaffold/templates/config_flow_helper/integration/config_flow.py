"""Config flow for NEW_NAME integration."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import helper_config_entry_flow, selector

from .const import DOMAIN

STEPS = {
    "init": vol.Schema(
        {
            vol.Required("name"): selector.selector({"text": {}}),
            vol.Required("entity_id"): selector.selector(
                {"entity": {"domain": "sensor"}}
            ),
        }
    )
}


class ConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for NEW_NAME."""

    steps = STEPS

    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, user_input["name"]) if "name" in user_input else ""

    @staticmethod
    def async_initial_options_step(config_entry: ConfigEntry) -> str | None:
        """Return initial options step."""
        # TODO Return initial option step_id, or remove the method if the integration
        # does not have an options flow
        return "init"
