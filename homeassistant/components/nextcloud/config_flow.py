"""Config flow to configure the Nextcloud integration."""
from __future__ import annotations

import logging
from typing import Any

from nextcloudmonitor import NextcloudMonitor, NextcloudMonitorError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
_LOGGER = logging.getLogger(__name__)


class NextcloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Nextcloud config flow."""

    VERSION = 1

    def _try_connect_nc(self, user_input: dict) -> NextcloudMonitor:
        """Try to connect to nextcloud server."""
        return NextcloudMonitor(
            user_input[CONF_URL],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by configuration file."""
        self._async_abort_entries_match({CONF_URL: user_input.get(CONF_URL)})
        try:
            await self.hass.async_add_executor_job(self._try_connect_nc, user_input)
        except NextcloudMonitorError:
            _LOGGER.error(
                "Connection error during import of yaml configuration, import aborted"
            )
            return self.async_abort(reason="connection_error_during_import")
        return await self.async_step_user(
            {
                CONF_URL: user_input[CONF_URL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_USERNAME: user_input[CONF_USERNAME],
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_URL: user_input.get(CONF_URL)})
            try:
                await self.hass.async_add_executor_job(self._try_connect_nc, user_input)
            except NextcloudMonitorError:
                errors["base"] = "connection_error"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data=user_input,
                )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA_USER, user_input)
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
