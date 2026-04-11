"""Config flow for the Discord integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
import nextcord
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import DiscordConfigEntry
from .const import CONF_CHANNEL_ID, DOMAIN, SUBENTRY_TYPE_CHANNEL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)

CHANNEL_ID_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHANNEL_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        )
    }
)


class DiscordFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: DiscordConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {SUBENTRY_TYPE_CHANNEL: DiscordChannelSubEntryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(str(info.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name,
                    data={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            description_placeholders={
                "portal_url": "https://discord.com/developers/applications"
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorisation flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(str(info.id))
                self._abort_if_unique_id_mismatch()
                return self.async_update_and_abort(
                    self._get_reauth_entry(),
                    title=info.name,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            description_placeholders={"bot_name": self._get_reauth_entry().title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, info = await _async_try_connect(user_input[CONF_API_TOKEN])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(str(info.id))
                self._abort_if_unique_id_mismatch()
                return self.async_update_and_abort(
                    self._get_reconfigure_entry(),
                    title=info.name,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or self._get_reconfigure_entry().data,
            ),
            description_placeholders={"bot_name": self._get_reconfigure_entry().title},
            errors=errors,
        )


class DiscordChannelSubEntryFlowHandler(ConfigSubentryFlow):
    """Handle adding a Discord channel as a subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a Discord channel."""
        config_entry: DiscordConfigEntry = self._get_entry()

        if config_entry.state != ConfigEntryState.LOADED:
            return self.async_abort(
                reason="entry_not_loaded",
                description_placeholders={"bot_name": config_entry.title},
            )

        errors: dict[str, str] = {}
        channel_name: str | None = None

        if user_input is not None:
            raw_id = user_input[CONF_CHANNEL_ID].strip()
            try:
                channel_id = int(raw_id)
            except ValueError:
                errors["base"] = "channel_not_found"
            else:
                # Validate the channel exists and fetch its name.
                nextcord.VoiceClient.warn_nacl = False
                discord_bot = nextcord.Client()
                try:
                    await discord_bot.login(config_entry.runtime_data)
                    try:
                        channel = await discord_bot.fetch_channel(channel_id)
                        channel_name = getattr(channel, "name", str(channel_id))
                    except nextcord.NotFound:
                        try:
                            user = await discord_bot.fetch_user(channel_id)
                            channel_name = user.name
                        except nextcord.NotFound:
                            errors["base"] = "channel_not_found"
                    except nextcord.Forbidden:
                        errors["base"] = "cannot_access_channel"
                    except nextcord.HTTPException, ClientConnectorError:
                        errors["base"] = "cannot_connect"
                except nextcord.LoginFailure:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error looking up Discord channel %s", channel_id
                    )
                    errors["base"] = "cannot_connect"
                finally:
                    await discord_bot.close()

            if not errors and channel_name is not None:
                return self.async_create_entry(
                    title=channel_name,
                    data={CONF_CHANNEL_ID: channel_id},
                    unique_id=str(channel_id),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CHANNEL_ID_SCHEMA,
            errors=errors,
        )


async def _async_try_connect(
    token: str,
) -> tuple[str | None, nextcord.AppInfo | None]:
    """Try connecting to Discord and return (error_key, app_info)."""
    nextcord.VoiceClient.warn_nacl = False
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(token)
        info = await discord_bot.application_info()
    except nextcord.LoginFailure:
        return "invalid_auth", None
    except ClientConnectorError, nextcord.HTTPException, nextcord.NotFound:
        return "cannot_connect", None
    except Exception:
        _LOGGER.exception("Unexpected exception connecting to Discord")
        return "unknown", None
    finally:
        await discord_bot.close()
    return None, info
