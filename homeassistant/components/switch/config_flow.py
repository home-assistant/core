"""Config flow for Switch integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.helpers import config_entry_flow, entity_registry as er, selector

from .const import DOMAIN

STEPS = {
    "init": vol.Schema(
        {
            vol.Required("entity_id"): selector.selector(
                {"entity": {"domain": "switch"}}
            ),
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
        registry = er.async_get(self.hass)
        object_id = split_entity_id(user_input["entity_id"])[1]
        entry = registry.async_get(user_input["entity_id"])
        if entry:
            return entry.name or object_id
        state = self.hass.states.get(user_input["entity_id"])
        if state:
            return state.name or object_id
        return object_id
