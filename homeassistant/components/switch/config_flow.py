"""Config flow for Switch integration."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.helpers import config_entry_flow, selector

from .const import DOMAIN

STEPS = {
    "init": vol.Schema(
        {
            vol.Required("entity_id"): selector.selector(
                {"entity": {"domain": "switch"}}
            ),
            vol.Required("name"): selector.selector({"text": {}}),
        }
    )
}


class SwitchLightConfigFlowHandler(
    config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Switch Light."""

    steps = STEPS

    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, user_input["name"])
