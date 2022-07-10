"""Config flow for Discord integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
import nextcord
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, URL_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


class DiscordFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord."""

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}

        if user_input:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if info and (entry := await self.async_set_unique_id(str(info.id))):
                self.hass.config_entries.async_update_entry(
                    entry, data=entry.data | user_input
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            if error:
                errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CONFIG_SCHEMA,
            description_placeholders=URL_PLACEHOLDER,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(str(info.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name,
                    data=user_input | {CONF_NAME: info.name},
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            description_placeholders=URL_PLACEHOLDER,
            errors=errors,
        )


async def _async_try_connect(token: str) -> tuple[str | None, nextcord.AppInfo | None]:
    """Try connecting to Discord."""
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(token)
        info = await discord_bot.application_info()
    except nextcord.LoginFailure:
        return "invalid_auth", None
    except (ClientConnectorError, nextcord.HTTPException, nextcord.NotFound):
        return "cannot_connect", None
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception: %s", ex)
        return "unknown", None
    await discord_bot.close()
    return None, info
