"""Config flow for sky_remote."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import selector

from .const import DOMAIN, SKY_REMOTE_CONFIG_SCHEMA


class SkyRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sky Remote."""

    VERSION = 1
    MINOR_VERSION = 1
    DATA_SCHEMA: dict[Any, Any] = {
        **SKY_REMOTE_CONFIG_SCHEMA,
        "legacy_port": selector({"boolean": None}),
    }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        if user_input is not None:
            logging.warning(user_input)
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self.DATA_SCHEMA)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the reconfiguration."""

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data=user_input,
                title=user_input["name"],
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(self.DATA_SCHEMA), entry.data
            ),
        )
