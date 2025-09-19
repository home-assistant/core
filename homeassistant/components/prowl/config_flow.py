"""The config flow for the Prowl component."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import prowlpy
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ProwlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Prowl component."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api_key = ""
        self.name = "Prowl"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user configuration."""
        errors = {}

        if user_input and user_input[CONF_API_KEY]:
            self.api_key = user_input[CONF_API_KEY]
            if user_input[CONF_NAME] and len(user_input[CONF_NAME]) > 0:
                self.name = user_input[CONF_NAME]
            await self.async_set_unique_id(self.name)
            self._abort_if_unique_id_configured()
            errors = await self._validate_api_key(self.api_key)
            if not errors:
                return self.async_create_entry(
                    title=self.name,
                    data={
                        CONF_API_KEY: self.api_key,
                        CONF_NAME: self.name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the API key is invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        entry = self._get_reauth_entry()

        if user_input:
            api_key = user_input[CONF_API_KEY]
            errors = await self._validate_api_key(api_key)

            if not errors:
                # Update existing entry with new API key
                data = {CONF_NAME: entry.data[CONF_NAME], CONF_API_KEY: api_key}
                self.hass.config_entries.async_update_entry(entry, data=data)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate the provided API key."""
        prowl = prowlpy.Prowl(api_key)
        try:
            async with asyncio.timeout(10):
                await self.hass.async_add_executor_job(prowl.verify_key)
                return {}
        except TimeoutError:
            return {"base": "api_timeout"}
        except prowlpy.APIError as ex:
            if str(ex).startswith("Invalid API key"):
                return {"base": "invalid_api_key"}
            return {"base": "bad_api_response"}
