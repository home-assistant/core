"""Config flow for Discord integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
import discord
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DiscordFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord."""

    async def async_step_reauth(self, config: dict[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                errors={},
            )

        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            name = user_input.get(CONF_NAME, DEFAULT_NAME)

            error, unique_id = await _async_try_connect(token)
            entry = await self.async_set_unique_id(unique_id)
            if entry and self.source == config_entries.SOURCE_REAUTH:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            self._abort_if_unique_id_configured()
            if error is None:
                return self.async_create_entry(
                    title=name,
                    data={CONF_TOKEN: token, CONF_NAME: name},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN, default=user_input.get(CONF_TOKEN)): str,
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_TOKEN] == import_config[CONF_TOKEN]:
                _part = import_config[CONF_TOKEN][0:4]
                _msg = f"Discord yaml config with partial key {_part} has been imported. Please remove it"
                _LOGGER.warning(_msg)
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)


async def _async_try_connect(token: str) -> tuple[str | None, Any]:
    """Try connecting to Discord."""
    discord_bot = discord.Client()
    try:
        await discord_bot.login(token)
        info = await discord_bot.application_info()
    except discord.LoginFailure:
        return "invalid_auth", None
    except (ClientConnectorError, discord.HTTPException, discord.NotFound):
        return "cannot_connect", None
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        return "unknown", None
    await discord_bot.close()
    return None, info.id
