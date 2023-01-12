"""Config flow for imap integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aioimaplib import AioImapException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CHARSET,
    CONF_FOLDER,
    CONF_SEARCH,
    CONF_SERVER,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import connect_to_server
from .errors import InvalidAuth, InvalidFolder

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERVER): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CHARSET, default="utf-8"): str,
        vol.Optional(CONF_FOLDER, default="INBOX"): str,
        vol.Optional(CONF_SEARCH, default="UnSeen UnDeleted"): str,
    }
)


async def validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    errors = {}

    try:
        imap_client = await connect_to_server(user_input)
        result, lines = await imap_client.search(
            user_input[CONF_SEARCH],
            charset=user_input[CONF_CHARSET],
        )

    except InvalidAuth:
        errors[CONF_USERNAME] = errors[CONF_PASSWORD] = "invalid_auth"
    except InvalidFolder:
        errors[CONF_FOLDER] = "invalid_folder"
    except (asyncio.TimeoutError, AioImapException, ConnectionRefusedError):
        errors["base"] = "cannot_connect"
    else:
        if result != "OK":
            if "The specified charset is not supported" in lines[0].decode("utf-8"):
                errors[CONF_CHARSET] = "invalid_charset"
            else:
                errors[CONF_SEARCH] = "invalid_search"
    return errors


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for imap."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._async_abort_entries_match(
            {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_FOLDER: user_input[CONF_FOLDER],
                CONF_SEARCH: user_input[CONF_SEARCH],
            }
        )

        if not (errors := await validate_input(user_input)):
            # To be removed when YAML import is removed
            title = user_input.get(CONF_NAME, user_input[CONF_USERNAME])

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        assert self._reauth_entry
        if user_input is not None:
            user_input = {**self._reauth_entry.data, **user_input}
            if not (errors := await validate_input(user_input)):
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
