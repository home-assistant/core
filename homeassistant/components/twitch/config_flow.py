"""Config flow for Twitch."""
from __future__ import annotations

import logging
from typing import Any

from twitchAPI.twitch import (
    Twitch,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchBackendException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv

from .const import CONF_CHANNELS, CONF_REFRESH_TOKEN, DOMAIN, OAUTH_SCOPES


async def get_user(
    hass: HomeAssistant,
    logger: logging.Logger,
    client: Twitch,
) -> dict | None:
    """Return the username of the user."""
    try:
        users = await hass.async_add_executor_job(client.get_users)
    except (TwitchAPIException, TwitchBackendException) as err:
        logger.error("Twitch API error: %s", err)
        return None

    return users["data"][0]


async def get_channels(
    hass: HomeAssistant,
    logger: logging.Logger,
    client: Twitch,
    user_id: str,
) -> list[dict]:
    """Return a list of channels the user is following."""
    cursor = None
    channels: list[dict] = []
    try:
        while True:
            response = await hass.async_add_executor_job(
                client.get_users_follows,
                cursor,
                100,
                user_id,
            )
            channels.extend(response["data"])
            pagination = response.get("pagination")
            if pagination is not None and pagination.get("cursor") is not None:
                cursor = pagination["cursor"]
            else:
                break
    except TwitchAuthorizationException:
        logger.error("Invalid client ID or client secret")
        return []
    except (TwitchAPIException, TwitchBackendException) as err:
        logger.error("Twitch API error: %s", err)
        return []

    logger.debug("Found %s channels", len(channels))

    return sorted(channels, key=lambda channel: channel["to_login"])


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Twitch OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._client: Twitch = None
        self._oauth_data: dict[str, Any] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        client_id = data["auth_implementation"].split("_")[1]
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = data[CONF_TOKEN][CONF_REFRESH_TOKEN]

        self._client = Twitch(
            app_id=client_id,
            authenticate_app=False,
            target_app_auth_scope=OAUTH_SCOPES,
        )
        self._client.auto_refresh_auth = False

        await self.hass.async_add_executor_job(
            self._client.set_user_authentication,
            access_token,
            OAUTH_SCOPES,
            refresh_token,
            True,
        )

        self._oauth_data = data

        return await self.async_step_channels()

    async def async_step_channels(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle channels step."""
        self.logger.debug("Step channels: %s", user_input)

        user = await get_user(
            self.hass,
            self.logger,
            self._client,
        )

        if not user:
            return self.async_abort(reason="user_not_found")

        self.logger.debug("User: %s", user)

        if not user_input:
            channels = await get_channels(
                self.hass,
                self.logger,
                self._client,
                user["id"],
            )
            self.logger.debug("Channels: %s", channels)

            return self.async_show_form(
                step_id="channels",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CHANNELS): cv.multi_select(
                            {
                                channel["to_id"]: channel["to_name"]
                                for channel in channels
                            }
                        ),
                    }
                ),
            )

        return self.async_create_entry(
            title=user.get("display_name", user["id"]),
            data={**self._oauth_data, "user": user},
            options={CONF_CHANNELS: user_input[CONF_CHANNELS]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for GitHub."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle options flow."""
        if not user_input:
            configured_channels: list[str] = self.config_entry.options[CONF_CHANNELS]

            client_id = self.config_entry.data["auth_implementation"].split("_")[1]
            access_token = self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            refresh_token = self.config_entry.data[CONF_TOKEN][CONF_REFRESH_TOKEN]

            client = Twitch(
                app_id=client_id,
                authenticate_app=False,
                target_app_auth_scope=OAUTH_SCOPES,
            )
            client.auto_refresh_auth = False

            await self.hass.async_add_executor_job(
                client.set_user_authentication,
                access_token,
                OAUTH_SCOPES,
                refresh_token,
                True,
            )

            channels = await get_channels(
                self.hass,
                self.logger,
                client,
                self.config_entry.data["user"]["id"],
            )

            self.logger.debug("Channels: %s", channels)

            channel_ids = [channel["to_id"] for channel in channels]
            channels_dict = {
                channel["to_id"]: channel["to_name"] for channel in channels
            }

            # In case the user has removed a channel that is already tracked
            for channel in configured_channels:
                if channel not in channel_ids:
                    channels_dict[channel] = channel

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_CHANNELS,
                            default=configured_channels,
                        ): cv.multi_select(channels_dict),
                    }
                ),
            )

        return self.async_create_entry(title="", data=user_input)
