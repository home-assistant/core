"""Config flow for Switch integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.helpers import (
    entity_registry as er,
    helper_config_entry_flow,
    selector,
)

from .const import DOMAIN

CONFIG_FLOW = {
    "user": helper_config_entry_flow.HelperFlowStep(
        vol.Schema(
            {
                vol.Required("entity_id"): selector.selector(
                    {"entity": {"domain": "switch"}}
                ),
            }
        )
    )
}


class SwitchLightConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Switch Light."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        registry = er.async_get(self.hass)
        object_id = split_entity_id(options["entity_id"])[1]
        entry = registry.async_get(options["entity_id"])
        if entry:
            return entry.name or entry.original_name or object_id
        state = self.hass.states.get(options["entity_id"])
        if state:
            return state.name or object_id
        return object_id
