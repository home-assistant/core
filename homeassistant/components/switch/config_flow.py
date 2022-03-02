"""Config flow for Switch integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.helpers import config_entry_flow, selector

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
