"""Config flow for Discord integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp.client_exceptions import ClientConnectorError
import nextcord
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import callback

from .const import CONF_CHANNEL_ID, DOMAIN, SUBENTRY_TYPE_CHANNEL, URL_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = probatio.Schema({probatio.Required(CONF_API_TOKEN): str})

CHANNEL_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_CHANNEL_ID): probatio.Coerce(int)}
)


class DiscordFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord."""

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_CHANNEL: ChannelSubentryFlowHandler}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors = {}

        if user_input:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if info and (entry := await self.async_set_unique_id(str(info.id))):
                return self.async_update_reload_and_abort(
                    entry, data=entry.data | user_input
                )
            if error:
                errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CONFIG_SCHEMA,
            description_placeholders=URL_PLACEHOLDER,
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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


class ChannelSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding a Discord channel."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a channel to send notifications to."""
        entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            channel_id = user_input[CONF_CHANNEL_ID]
            for subentry in entry.subentries.values():
                if subentry.unique_id == str(channel_id):
                    return self.async_abort(reason="already_configured")

            error, name = await _async_try_channel(
                entry.data[CONF_API_TOKEN], channel_id
            )
            if error is not None:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_CHANNEL_ID: channel_id},
                    unique_id=str(channel_id),
                )

        return self.async_show_form(
            step_id="user", data_schema=CHANNEL_SCHEMA, errors=errors
        )


async def _async_try_connect(token: str) -> tuple[str | None, nextcord.AppInfo | None]:
    """Try connecting to Discord."""
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(token)
        info = await discord_bot.application_info()
    except nextcord.LoginFailure:
        return "invalid_auth", None
    except ClientConnectorError, nextcord.HTTPException, nextcord.NotFound:
        return "cannot_connect", None
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown", None
    await discord_bot.close()
    return None, info


async def _async_try_channel(token: str, channel_id: int) -> tuple[str | None, str]:
    """Try resolving a Discord channel or user, returning an error or its name."""
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(token)
        try:
            channel = await discord_bot.fetch_channel(channel_id)
            name = getattr(channel, "name", None)
        except nextcord.NotFound:
            name = (await discord_bot.fetch_user(channel_id)).name
    except nextcord.LoginFailure:
        return "invalid_auth", ""
    except nextcord.NotFound:
        return "channel_not_found", ""
    except ClientConnectorError, nextcord.HTTPException:
        return "cannot_connect", ""
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown", ""
    finally:
        await discord_bot.close()
    return None, name or str(channel_id)
