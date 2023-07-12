"""Config flow for Twitch."""
from __future__ import annotations

import logging
from typing import Any

from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_CHANNELS, CONF_REFRESH_TOKEN, DOMAIN, LOGGER, OAUTH_SCOPES


async def _get_twitch_client(
    client_id: str, client_secret: str, access_token: str, refresh_token: str
) -> Twitch:
    client = await Twitch(
        app_id=client_id,
        app_secret=client_secret,
        target_app_auth_scope=OAUTH_SCOPES,
    )
    client.auto_refresh_auth = False
    await client.set_user_authentication(
        token=access_token,
        refresh_token=refresh_token,
        scope=OAUTH_SCOPES,
        validate=True,
    )
    return client


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Twitch OAuth2 authentication."""

    DOMAIN = DOMAIN
    _data: dict[str, Any] = {}

    _user_display_name: str = ""
    _user_id: str = ""

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join([scope.value for scope in OAUTH_SCOPES])}

    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> FlowResult:
        """Handle the initial step."""
        client_id = self.flow_impl.__dict__[CONF_CLIENT_ID]
        client_secret = self.flow_impl.__dict__[CONF_CLIENT_SECRET]
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = data[CONF_TOKEN][CONF_REFRESH_TOKEN]

        client = await _get_twitch_client(
            client_id, client_secret, access_token, refresh_token
        )
        if not (user := await first(client.get_users())):
            return self.async_abort(reason="user_not_found")

        self._user_display_name = user.display_name
        self._user_id = user.id
        self._data = data

        await self.async_set_unique_id(user.id)
        self._abort_if_unique_id_configured()

        return await self.async_step_channels()

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which channels to follow. The channels the user follow are prefilled."""
        client_id = self.flow_impl.__dict__[CONF_CLIENT_ID]
        client_secret = self.flow_impl.__dict__[CONF_CLIENT_SECRET]
        access_token = self._data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = self._data[CONF_TOKEN][CONF_REFRESH_TOKEN]

        client = await _get_twitch_client(
            client_id, client_secret, access_token, refresh_token
        )

        if user_input is not None:
            client.get_users(logins=user_input[CONF_CHANNELS])
            #     Need to check if it checks all channels if they are valid
            return self.async_create_entry(
                title=self._user_display_name, data=self._data, options=user_input
            )
        followed_channels = await client.get_followed_channels(user_id=self._user_id)

        followed_channel_list = [
            SelectOptionDict(
                value=channel.broadcaster_login, label=channel.broadcaster_name
            )
            for channel in followed_channels.data
        ]

        return self.async_show_form(
            step_id="channels",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNELS): SelectSelector(
                        SelectSelectorConfig(
                            options=followed_channel_list,
                            custom_value=True,
                            multiple=True,
                        )
                    )
                }
            ),
        )
