"""Config flow for Switch integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): selector.selector({"entity": {"domain": "switch"}}),
        vol.Required("name"): selector.selector({"text": {}}),
    }
)


class SwitchLightConfigFlowHandler(
    config_entries.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Switch Light."""

    _schema = DATA_SCHEMA

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return config_entries.HelperOptionsFlowHandler(config_entry, DATA_SCHEMA)
