"""Config Flow for Advantage Air integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hass_splunk import hass_splunk
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

DEFAULT_PORT = 8088
DEFAULT_NAME = "Home Assistant"

SPLUNK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SPLUNK_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
    }
)


class SplunkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Advantage Air API connection."""

    VERSION = 1
    DOMAIN = DOMAIN
    entry: config_entries.ConfigEntry | None

    async def async_check(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Check if Splunk HTTP Event Collector configuration is valid."""
        splunk = hass_splunk(
            session=async_get_clientsession(self.hass),
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            token=user_input[CONF_TOKEN],
            use_ssl=user_input[CONF_SSL],
            verify_ssl=user_input[CONF_VERIFY_SSL],
        )
        if not await splunk.check(connectivity=True, token=False, busy=False):
            return {"base": "cannot_connect"}
        if not await splunk.check(connectivity=False, token=True, busy=False):
            return {"base": "invalid_auth"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Get configuration from the user."""
        errors: dict[str, str] = {}
        if user_input:
            if not (errors := await self.async_check(user_input)):
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SPLUNK_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle a flow initiated by configuration file."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth on credential failure."""
        # self._reauth = entry_data
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle reauth token."""
        assert self.entry is not None
        errors: dict[str, str] = {}

        if user_input and self.entry:
            data = {
                **self.entry.data,
                CONF_TOKEN: user_input[CONF_TOKEN],
            }

            if not (errors := await self.async_check(data)):
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "host": self.entry.data[CONF_HOST],
                "port": self.entry.data[CONF_PORT],
            },
            data_schema=SPLUNK_REAUTH_SCHEMA,
            errors=errors,
        )
