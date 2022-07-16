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
from .data import TwitchFollower, TwitchResponse, TwitchResponsePagination, TwitchUser


async def get_user(
    hass: HomeAssistant,
    client: Twitch,
) -> TwitchUser | None:
    """Return the username of the user."""
    users_response = TwitchResponse(
        **await hass.async_add_executor_job(client.get_users)
    )

    if users_response.data is not None:
        return TwitchUser(**users_response.data[0])
    return None


async def get_followed_channels(
    hass: HomeAssistant,
    client: Twitch,
    user_id: str,
) -> list[TwitchFollower]:
    """Return a list of channels the user is following."""
    cursor = None
    channels: list[TwitchFollower] = []
    while True:
        followers_response = TwitchResponse(
            **await hass.async_add_executor_job(
                client.get_users_follows,
                cursor,
                100,
                user_id,
            )
        )

        if followers_response.data is not None:
            channels.extend(
                [TwitchFollower(**follower) for follower in followers_response.data]
            )
        if (
            followers_response.pagination is not None
            and followers_response.pagination != {}
        ):
            cursor = TwitchResponsePagination(**followers_response.pagination).cursor
        else:
            break

    return sorted(
        channels,
        key=lambda channel: channel.to_name.lower(),
        reverse=False,
    )


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

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": ",".join([scope.value for scope in OAUTH_SCOPES])}

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

        try:
            user = await get_user(self.hass, self._client)
        except TwitchAuthorizationException as err:
            self.logger.error("Authorization error: %s", err)
            return self.async_abort(reason="invalid_auth")
        except (TwitchAPIException, TwitchBackendException) as err:
            self.logger.error("Twitch API error: %s", err)
            return self.async_abort(reason="cannot_connect")

        if not user:
            self.logger.error("No user found")
            return self.async_abort(reason="user_not_found")

        self.logger.debug("User: %s", user)

        if not user_input:
            try:
                channels = await get_followed_channels(
                    self.hass,
                    self._client,
                    user.id,
                )
            except (TwitchAPIException, TwitchBackendException) as err:
                self.logger.error("Twitch API error: %s", err)
                return self.async_abort(reason="cannot_connect")

            self.logger.debug("Channels: %s", channels)

            return self.async_show_form(
                step_id="channels",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CHANNELS): cv.multi_select(
                            {channel.to_id: channel.to_name for channel in channels}
                        ),
                    }
                ),
            )

        return self.async_create_entry(
            title=user.display_name,
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
        """Handle init options flow."""
        return await self.async_step_channels(user_input)

    async def async_step_channels(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle channels options flow."""
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

            try:
                channels = await get_followed_channels(
                    self.hass,
                    client,
                    self.config_entry.data["user"]["id"],
                )
            except TwitchAuthorizationException as err:
                self.logger.error("Authorization error: %s", err)
                return self.async_abort(reason="invalid_auth")
            except (TwitchAPIException, TwitchBackendException) as err:
                self.logger.error("Twitch API error: %s", err)
                return self.async_abort(reason="cannot_connect")

            channel_ids = [channel.to_id for channel in channels]
            channels_dict = {channel.to_id: channel.to_name for channel in channels}

            self.logger.debug("Channels: %s", channels_dict)

            # In case the user has removed a channel that is already tracked
            for channel in configured_channels:
                if channel not in channel_ids:
                    channels_dict[channel] = channel

            return self.async_show_form(
                step_id="channels",
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
