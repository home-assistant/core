"""Config flow to configure the Nextcloud integration."""
from __future__ import annotations

from typing import Any

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NextcloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Nextcloud config flow."""

    VERSION = 1

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by configuration file."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input.get(CONF_URL)})
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        def _connect_nc():
            return NextcloudMonitor(
                user_input[CONF_URL],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input.get(CONF_URL)})
            try:
                await self.hass.async_add_executor_job(_connect_nc)
            except NextcloudMonitorError:
                errors["base"] = "connection_error"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data={
                        CONF_URL: user_input[CONF_URL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
