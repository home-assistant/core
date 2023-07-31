"""Config flow to configure the Nextcloud integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nextcloudmonitor import (
    NextcloudMonitor,
    NextcloudMonitorAuthorizationError,
    NextcloudMonitorConnectionError,
    NextcloudMonitorRequestError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_VERIFY_SSL, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)
DATA_SCHEMA_REAUTH = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NextcloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Nextcloud config flow."""

    VERSION = 1

    _entry: ConfigEntry | None = None

    def _try_connect_nc(self, user_input: dict) -> NextcloudMonitor:
        """Try to connect to nextcloud server."""
        return NextcloudMonitor(
            user_input[CONF_URL],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
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
            except NextcloudMonitorAuthorizationError:
                errors["base"] = "invalid_auth"
            except (NextcloudMonitorConnectionError, NextcloudMonitorRequestError):
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle flow upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        errors = {}
        assert self._entry is not None

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    self._try_connect_nc, {**self._entry.data, **user_input}
                )
            except NextcloudMonitorAuthorizationError:
                errors["base"] = "invalid_auth"
            except (NextcloudMonitorConnectionError, NextcloudMonitorRequestError):
                errors["base"] = "connection_error"
            else:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, **user_input},
                )
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        data_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA_REAUTH,
            {CONF_USERNAME: self._entry.data[CONF_USERNAME], **(user_input or {})},
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            description_placeholders={"url": self._entry.data[CONF_URL]},
            errors=errors,
        )
