"""Config flow to configure the Nextcloud integration."""
from __future__ import annotations

import asyncio

from nextcloudmonitor import NextcloudMonitorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from . import NextcloudMonitorWrapper
from .const import DEFAULT_NAME, DOMAIN


class NextCloudFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Nextcloud config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _async_endpoint_existed(self, endpoint: str) -> bool:
        existing_endpoints = [
            f"{entry.data.get(CONF_NAME)}" for entry in self._async_current_entries()
        ]
        return endpoint in existing_endpoints

    async def _async_try_connect(
        self, url: str, user: str, password: str, verify_ssl: bool
    ) -> bool:

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, NextcloudMonitorWrapper, url, user, password, verify_ssl
            )
        except NextcloudMonitorError:
            return False
        return True

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            url = user_input[CONF_URL]
            user = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            verify_ssl = user_input[CONF_VERIFY_SSL]

            if await self._async_endpoint_existed(name):
                errors[CONF_URL] = "already_configured"
            elif not await self._async_try_connect(url, user, password, verify_ssl):
                errors[CONF_URL] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
                    ): bool,
                }
            ),
            errors=errors,
        )
