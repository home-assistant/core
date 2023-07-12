"""Config flow for Twitch."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import time
from typing import Any

from twitchAPI.helper import first
from twitchAPI.twitch import Twitch
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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
from homeassistant.helpers.typing import ConfigType

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
    _oauth_data: dict[str, Any] = {}

    reauth_entry: ConfigEntry | None = None

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
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        client_id = self.flow_impl.__dict__[CONF_CLIENT_ID]
        client_secret = self.flow_impl.__dict__[CONF_CLIENT_SECRET]
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = data[CONF_TOKEN][CONF_REFRESH_TOKEN]

        await _get_twitch_client(client_id, client_secret, access_token, refresh_token)
        self._oauth_data = data

        return await self.async_step_channels()

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which channels to follow. The channels the user follow are prefilled."""
        client_id = self.flow_impl.__dict__[CONF_CLIENT_ID]
        client_secret = self.flow_impl.__dict__[CONF_CLIENT_SECRET]
        access_token = self._oauth_data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        refresh_token = self._oauth_data[CONF_TOKEN][CONF_REFRESH_TOKEN]

        client = await _get_twitch_client(
            client_id, client_secret, access_token, refresh_token
        )

        if not (user := await first(client.get_users())):
            return self.async_abort(reason="user_not_found")

        if user_input is not None:
            client.get_users(logins=user_input[CONF_CHANNELS])
            #     Need to check if it checks all channels if they are valid
            return self.async_create_entry(
                title=user.display_name, data=self._oauth_data, options=user_input
            )
        followed_channels = await client.get_followed_channels(user_id=user.id)

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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Handle import of yaml configuration."""
        if len(self._async_current_entries()) > 0:
            return self.async_abort(reason="already_configured")
        scopes = [scope.value for scope in OAUTH_SCOPES]
        return self.async_create_entry(
            title="",
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    CONF_CLIENT_ID: import_config[CONF_CLIENT_ID],
                    CONF_CLIENT_SECRET: import_config[CONF_CLIENT_SECRET],
                    "access_token": "",
                    "refresh_token": "",
                    "expires_at": time.time(),
                    "scope": " ".join(scopes),
                },
            },
            options={CONF_CHANNELS: import_config[CONF_CHANNELS]},
        )
